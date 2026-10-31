"""Unit tests for the deterministic static analyzer in core/static_analyzer.py."""

import pytest
from core.board_database import get_board
from core.schemas import CodeIssue
from core.static_analyzer import StaticAnalyzer


def test_missing_pinmode_detection():
    sketch = """void setup() {
    // Missing pinMode for pin 13
}
void loop() {
    digitalWrite(13, HIGH);
}"""
    analyzer = StaticAnalyzer(board=get_board("arduino_uno"))
    issues = analyzer.analyze(sketch)

    assert any("Missing pinMode" in i.issue for i in issues)
    missing_issues = [i for i in issues if "Missing pinMode" in i.issue]
    assert missing_issues[0].line == 5
    assert missing_issues[0].severity == "high"


def test_delay_in_isr_detection():
    sketch = """void onButtonPress() {
    digitalWrite(13, HIGH);
    delay(100);
}

void setup() {
    pinMode(13, OUTPUT);
    attachInterrupt(digitalPinToInterrupt(2), onButtonPress, RISING);
}

void loop() {
}"""
    analyzer = StaticAnalyzer(board=get_board("arduino_uno"))
    issues = analyzer.analyze(sketch)

    isr_issues = [i for i in issues if "ISR" in i.issue or "Interrupt" in i.issue]
    assert len(isr_issues) > 0
    assert isr_issues[0].severity == "high"
    assert isr_issues[0].category == "timing"
    assert "delay(100)" in isr_issues[0].evidence


def test_non_pwm_pin_analog_write():
    sketch = """void setup() {
    pinMode(4, OUTPUT);
}
void loop() {
    analogWrite(4, 128); // Arduino Uno Pin 4 has no PWM hardware!
}"""
    analyzer = StaticAnalyzer(board=get_board("arduino_uno"))
    issues = analyzer.analyze(sketch)

    pwm_issues = [i for i in issues if "PWM" in i.issue]
    assert len(pwm_issues) > 0
    assert pwm_issues[0].severity == "high"
    assert "Pin 4 does not support PWM" in pwm_issues[0].issue


def test_arduino_uno_analog_read_numeric_channel():
    sketch = """void setup() {}
void loop() {
    int val = analogRead(0); // standard Uno shorthand for A0
}"""
    analyzer = StaticAnalyzer(board=get_board("arduino_uno"))
    issues = analyzer.analyze(sketch)
    assert not any("no adc channel" in i.issue.lower() for i in issues)



def test_esp32_input_only_pin_as_output():
    sketch = """void setup() {
    pinMode(34, OUTPUT); // ESP32 GPIO 34 is input-only!
}
void loop() {
}"""
    analyzer = StaticAnalyzer(board=get_board("esp32_devkit"))
    issues = analyzer.analyze(sketch)

    input_only_issues = [i for i in issues if "input-only" in i.impact.lower()]
    assert len(input_only_issues) > 0
    assert input_only_issues[0].severity == "high"


def test_esp32_flash_reserved_pin():
    sketch = """void setup() {
    pinMode(6, OUTPUT); // ESP32 GPIO 6 is connected to internal SPI Flash!
}
void loop() {
}"""
    analyzer = StaticAnalyzer(board=get_board("esp32_devkit"))
    issues = analyzer.analyze(sketch)

    res_issues = [i for i in issues if "reserved" in i.impact.lower() or "flash" in i.impact.lower()]
    assert len(res_issues) > 0
    assert res_issues[0].severity == "high"


def test_verdict_calculation():
    # Pass with clean code
    clean_sketch = """void setup() {
    pinMode(13, OUTPUT);
}
void loop() {
    digitalWrite(13, HIGH);
    delay(500);
    digitalWrite(13, LOW);
    delay(500);
}"""
    analyzer = StaticAnalyzer(board=get_board("arduino_uno"))
    clean_issues = analyzer.analyze(clean_sketch)
    assert StaticAnalyzer.calculate_verdict(clean_issues) == "PASS"

    # Fail with high severity bug
    buggy_sketch = """void setup() {}
void loop() {
    digitalWrite(13, HIGH);
}"""
    bug_issues = analyzer.analyze(buggy_sketch)
    assert StaticAnalyzer.calculate_verdict(bug_issues) == "FAIL"


def test_commented_out_code_not_flagged():
    sketch = """void setup() {
    pinMode(13, OUTPUT);
    // pinMode(4, OUTPUT);
    /* digitalWrite(4, HIGH); */
}
void loop() {
    digitalWrite(13, HIGH);
    // digitalRead(2);
}"""
    analyzer = StaticAnalyzer(board=get_board("arduino_uno"))
    issues = analyzer.analyze(sketch)
    assert not any("pin '2'" in i.issue.lower() for i in issues)
    assert not any("pin '4'" in i.issue.lower() for i in issues)
    assert StaticAnalyzer.calculate_verdict(issues) == "PASS"


def test_validate_and_filter_ai_issues():
    source = "void setup() {\n    pinMode(13, OUTPUT);\n}\nvoid loop() {\n    digitalWrite(13, HIGH);\n}"
    ai_issue_valid = CodeIssue(
        line=5,
        severity="high",
        category="hardware",
        issue="Valid line",
        evidence="digitalWrite(13, HIGH);",
        impact="Test",
        fix="Test",
        confidence="high",
    )
    ai_issue_hallucinated_line = CodeIssue(
        line=999,  # Doesn't exist
        severity="high",
        category="hardware",
        issue="Fake line",
        evidence="nonExistentFunction();",
        impact="Test",
        fix="Test",
        confidence="high",
    )
    validated = StaticAnalyzer.validate_and_filter_ai_issues(
        [ai_issue_valid, ai_issue_hallucinated_line], source
    )
    assert len(validated) == 1
    assert validated[0].line == 5

