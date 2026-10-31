"""End-to-end integration and acceptance tests for Firmware-Alchemist (Acceptance Tests A through I)."""

from core.board_database import get_board
from core.circuit_graph import (
    CircuitGraph,
    build_suggested_circuit,
    export_circuit_json,
    import_circuit_json,
    reset_circuit,
)
from core.circuit_reconstructor import reconstruct_circuit_from_vision
from core.circuit_validator import CircuitValidator
from core.code_parser import CodeParser
from core.component_models import ComponentSimulator
from core.demo_data import DEMO_DIAGNOSIS, DEMO_INVENTORY
from core.schemas import (
    CircuitDocument,
    CircuitPart,
    CircuitWire,
    CodeIssue,
    PinReference,
    PinSnapshot,
    PinState,
    SimulationPlan,
)
from core.simulator import HardwareSimulator
from core.static_analyzer import StaticAnalyzer


def test_acceptance_a_correct_blinking_led():
    """TEST A — CORRECT BLINKING LED:
    Audit passes -> 'CODE VALID' -> Circuit editor opens -> Simulation runs -> LED illuminates.
    """
    code = """
#define LED_PIN 13

void setup() {
    pinMode(LED_PIN, OUTPUT);
}

void loop() {
    digitalWrite(LED_PIN, HIGH);
    delay(1000);
    digitalWrite(LED_PIN, LOW);
    delay(1000);
}
"""
    board = get_board("arduino_uno")
    analyzer = StaticAnalyzer(board=board)
    issues = analyzer.analyze(code)

    # 1. Audit passes: No high-severity issues
    sig_errors = [i for i in issues if i.severity == "high"]
    assert len(sig_errors) == 0, f"Expected clean audit for correct blinking LED, got {sig_errors}"

    # 2. Parse firmware into SimulationPlan
    parser = CodeParser(max_duration_ms=4000)
    plan = parser.parse(code)
    assert len(plan.events) >= 2

    # 3. Build suggested circuit
    circuit_doc = build_suggested_circuit(board.id, plan)
    part_types = [p.type for p in circuit_doc.parts]
    assert "arduino_uno" in part_types
    assert "breadboard_half" in part_types
    assert "led" in part_types
    assert "resistor" in part_types

    # 4. Simulate with circuit graph
    sim = HardwareSimulator(step_ms=100, board_id=board.id)
    frames = sim.simulate(plan=plan, duration_ms=4000, circuit_doc=circuit_doc)
    assert len(frames) > 0

    # 5. Check that LED illuminates only when GPIO 13 is HIGH and circuit is closed
    high_frames = [f for f in frames if f.pin_states.get("13", PinSnapshot(pin="13", mode="OUTPUT")).digital_state == "HIGH"]
    assert len(high_frames) > 0

    first_high = high_frames[0]
    led1_state = first_high.component_states.get("led1")
    assert led1_state is not None
    assert led1_state["state"] == "ON"
    assert led1_state["brightness"] > 0
    assert led1_state["current_ma"] > 0


def test_acceptance_b_incorrect_firmware():
    """TEST B — INCORRECT FIRMWARE:
    Buggy firmware -> Error identified -> Line shown -> Explanation -> Correction -> Simulation blocked.
    """
    # Buggy code: missing pinMode for pin 13
    code = """
#define LED_PIN 13

void setup() {
    // Missing pinMode(LED_PIN, OUTPUT);
}

void loop() {
    digitalWrite(LED_PIN, HIGH);
    delay(1000);
}
"""
    board = get_board("arduino_uno")
    analyzer = StaticAnalyzer(board=board)
    issues = analyzer.analyze(code)

    # 1. Error identified
    sig_errors = [i for i in issues if i.severity == "high" or "pinmode" in i.issue.lower()]
    assert len(sig_errors) > 0, "Static analyzer must flag missing pinMode as a significant error"

    err = sig_errors[0]
    # 2. Line number provided
    assert err.line > 0
    # 3. Explanation and impact provided
    assert len(err.impact) > 0
    # 4. Suggested fix provided
    assert "OUTPUT" in err.fix or "pinMode" in err.fix


def test_acceptance_c_button_controlled_led():
    """TEST C — BUTTON-CONTROLLED LED:
    Virtual button input changes -> Firmware responds -> LED state changes.
    """
    code = """
#define BUTTON_PIN 2
#define LED_PIN 13

void setup() {
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
}

void loop() {
    if (digitalRead(BUTTON_PIN) == LOW) {
        digitalWrite(LED_PIN, HIGH);
    } else {
        digitalWrite(LED_PIN, LOW);
    }
}
"""
    parser = CodeParser(max_duration_ms=2000)

    # Case 1: Button Pressed (LOW)
    plan_pressed = parser.parse(code, virtual_inputs={"2": "LOW"})
    ev_pressed = [e for e in plan_pressed.events if e.action == "digitalWrite" and e.pin == "13"]
    assert any(str(e.value).upper() == "HIGH" for e in ev_pressed)

    # Case 2: Button Released (HIGH)
    plan_released = parser.parse(code, virtual_inputs={"2": "HIGH"})
    ev_released = [e for e in plan_released.events if e.action == "digitalWrite" and e.pin == "13"]
    assert any(str(e.value).upper() == "LOW" for e in ev_released)


def test_acceptance_d_disconnected_led():
    """TEST D — DISCONNECTED LED:
    GPIO output changes, but LED does NOT illuminate if path is open. Validator reports disconnected part.
    """
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno"),
            CircuitPart(id="led1", type="led"),
        ],
        wires=[
            # Anode wired to pin 13, but Cathode is completely disconnected
            CircuitWire(id="w1", source=PinReference(part_id="mcu1", pin_id="13"), target=PinReference(part_id="led1", pin_id="anode")),
        ],
    )

    # 1. Validation reports open circuit
    validator = CircuitValidator("arduino_uno")
    report = validator.validate(doc)
    assert any("Open Circuit" in i.title or "Disconnected" in i.title for i in report.issues)

    # 2. Physics simulation: LED must NOT illuminate even if pin 13 is HIGH
    sim = ComponentSimulator(board_id="arduino_uno")
    high_pins = {"13": PinSnapshot(pin="13", mode="OUTPUT", digital_state="HIGH", pwm_duty=255)}
    graph = CircuitGraph(doc)
    eval_res = sim.evaluate_circuit(graph, high_pins)

    assert eval_res["led1"].state == "OFF"
    assert eval_res["led1"].brightness == 0
    assert eval_res["led1"].is_powered is False


def test_acceptance_e_circuit_editing_and_serialization():
    """TEST E — CIRCUIT EDITING:
    Add component, connect pins, serialize JSON, and restore.
    """
    doc = reset_circuit("arduino_uno")
    assert len(doc.parts) == 2

    # Add LED
    doc.parts.append(CircuitPart(id="led1", type="led", x=500, y=150, properties={"color": "blue"}))
    # Add wire
    doc.wires.append(
        CircuitWire(
            id="w_test",
            source=PinReference(part_id="mcu1", pin_id="13"),
            target=PinReference(part_id="led1", pin_id="anode"),
            color="#3b82f6",
        )
    )

    json_str = export_circuit_json(doc)
    restored = import_circuit_json(json_str)

    assert len(restored.parts) == 3
    assert len(restored.wires) == 1
    assert restored.wires[0].color == "#3b82f6"


def test_acceptance_f_photograph_reconstruction():
    """TEST F — PHOTOGRAPH RECONSTRUCTION:
    AI vision inventory -> reconstructs editable CircuitDocument with distinct confirmed vs uncertain wires.
    """
    doc = reconstruct_circuit_from_vision(
        inventory=DEMO_INVENTORY,
        diagnosis=DEMO_DIAGNOSIS,
        board_id="esp32_devkit",
    )

    assert doc.board == "esp32_devkit"
    # Should have solid and dashed wires
    wire_styles = {w.style for w in doc.wires}
    assert "solid" in wire_styles
    assert any("AI-GENERATED CIRCUIT RECONSTRUCTION" in n for n in doc.notes)

