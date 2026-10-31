"""Tests for reference-inspired capabilities: pin conflict analyzer, non-blocking optimizer,
agentic patcher, memory advisor, serial diagnostics, and architecture mapper.
"""

from core.agentic_patcher import AgenticPatcher, CompilerDiagnostic
from core.architecture_mapper import ArchitectureMapper
from core.board_database import get_board
from core.memory_advisor import MemoryAdvisor
from core.optimizer import NonBlockingOptimizer
from core.pin_conflict_analyzer import PinConflictAnalyzer
from core.project_context import ProjectContextManager
from core.serial_diagnostics import SerialDiagnostics


def test_pin_conflict_serial_pins_0_and_1():
    code = """
#define SENSOR_PIN 0

void setup() {
    Serial.begin(9600);
    pinMode(SENSOR_PIN, INPUT);
}

void loop() {
    int val = digitalRead(SENSOR_PIN);
}
"""
    board = get_board("arduino_uno")
    analyzer = PinConflictAnalyzer(board=board)
    conflicts, wiring_table, buses = analyzer.analyze(code)

    assert "Hardware Serial (USB)" in buses
    assert len(conflicts) > 0
    # Pin 0 conflict with Serial must be caught
    assert any(c.pin == "0" and "Serial" in c.title for c in conflicts)

    # Wiring table must be populated
    assert len(wiring_table) >= 3
    assert any("GND" in w.mcu_pin for w in wiring_table)


def test_non_blocking_optimizer_delay_to_millis():
    code = """
void loop() {
    digitalWrite(13, HIGH);
    delay(1000);
    digitalWrite(13, LOW);
    delay(1000);
}
"""
    res = NonBlockingOptimizer.analyze_and_optimize(code)

    assert res.is_optimizable is True
    assert 1000 in res.delay_values_ms
    assert "millis()" in res.optimized_code
    assert "previousMillis" in res.optimized_code
    assert "without halting" in res.explanation.lower() or "elapsed" in res.explanation.lower()


def test_agentic_patcher_diff_and_proposal():
    orig = """void setup() {\n  // empty\n}\nvoid loop() {\n  digitalWrite(13, HIGH);\n}"""
    diag = [
        CompilerDiagnostic(
            file="sketch.ino",
            line=5,
            column=3,
            severity="error",
            message="Missing pinMode for pin 13",
        )
    ]

    patcher = AgenticPatcher(board=get_board("arduino_uno"))
    proposal = patcher.propose_fix_patch(orig, diag)

    assert proposal is not None
    assert "pinMode(13, OUTPUT)" in proposal.proposed_code
    assert "--- a/sketch.ino" in proposal.diff
    assert "+++ b/sketch.ino" in proposal.diff


def test_agentic_patcher_autonomous_loop():
    buggy_code = """void setup() {
  // empty
}
void loop() {
  digitalWrite(13, HIGH);
}"""
    patcher = AgenticPatcher(board=get_board("arduino_uno"))
    fixed_code, attempts, is_fixed = patcher.run_autonomous_loop(buggy_code, max_attempts=3)

    assert len(attempts) >= 1
    assert "pinMode(13, OUTPUT)" in fixed_code
    assert is_fixed is True



def test_memory_advisor_estimates():
    code = """
void setup() {
    Serial.begin(115200);
    Serial.println("Firmware Alchemist Memory Test");
}
void loop() {}
"""
    advisor = MemoryAdvisor(board=get_board("arduino_uno"))
    report = advisor.analyze(code)

    assert report.board_name == "Arduino Uno R3"
    assert report.flash_used_bytes > 0
    assert report.flash_total_bytes == 32256
    assert 0.0 < report.flash_pct < 100.0
    assert report.sram_total_bytes == 2048


def test_serial_diagnostics_baud_and_brownout():
    baud_log = "\x00\x00???\x08Hello World???"
    diag_baud = SerialDiagnostics.analyze_log(baud_log)
    assert diag_baud.is_garbled_baud is True
    assert any("Baud" in f for f in diag_baud.identified_faults)

    brownout_log = "[00:00:01] Booting...\n[00:00:02] Brownout detector was triggered\nrst:0x10 (RTCWDT_RTC_RESET)"
    diag_brownout = SerialDiagnostics.analyze_log(brownout_log)
    assert any("Brownout" in f for f in diag_brownout.identified_faults)
    assert any("capacitor" in c.lower() for c in diag_brownout.recommended_checks)


def test_architecture_mapper_mermaid_generation():
    board = get_board("arduino_uno")
    diagram = ArchitectureMapper.generate_mermaid_diagram(board=board, plan=None)

    assert "flowchart TD" in diagram
    assert "Arduino Uno" in diagram
    assert "PIN_13" in diagram

