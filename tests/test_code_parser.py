"""Unit tests for the deterministic Arduino C++ code parser in core/code_parser.py."""

import pytest
from core.code_parser import CodeParser


def test_parser_constants_and_macros():
    sketch = """
    #define LED_PIN 13
    const int BUTTON_PIN = 2;
    constexpr int SENSOR_PIN = A0;

    void setup() {
        pinMode(LED_PIN, OUTPUT);
        pinMode(BUTTON_PIN, INPUT_PULLUP);
    }
    void loop() {
        digitalWrite(LED_PIN, HIGH);
        delay(500);
        digitalWrite(LED_PIN, LOW);
        delay(500);
    }
    """
    parser = CodeParser(max_duration_ms=2000)
    plan = parser.parse(sketch)

    # Check extracted pins
    pin_ids = {p.pin for p in plan.pins}
    assert "13" in pin_ids
    assert "2" in pin_ids

    # Check pin modes
    pin_modes = {p.pin: p.mode for p in plan.pins}
    assert pin_modes["13"] == "OUTPUT"
    assert pin_modes["2"] == "INPUT_PULLUP"

    # Check timeline events
    assert len(plan.events) > 0
    actions = [e.action for e in plan.events]
    assert "digitalWrite" in actions
    assert "delay" in actions
    assert plan.loop_detected is True


def test_parser_conditional_evaluation():
    sketch = """
    #define LED_PIN 13
    #define BTN_PIN 2

    void setup() {
        pinMode(LED_PIN, OUTPUT);
        pinMode(BTN_PIN, INPUT);
    }

    void loop() {
        int state = digitalRead(BTN_PIN);
        if (state == LOW) {
            digitalWrite(LED_PIN, HIGH);
            delay(1000);
        } else {
            digitalWrite(LED_PIN, LOW);
            delay(1000);
        }
    }
    """
    # Virtual input: Button pressed (LOW)
    parser = CodeParser(max_duration_ms=2500)
    plan_low = parser.parse(sketch, virtual_inputs={"2": "LOW"})

    dw_events = [e for e in plan_low.events if e.action == "digitalWrite"]
    assert len(dw_events) > 0
    # Every write should be HIGH because button is LOW
    assert all(e.value == "HIGH" for e in dw_events)

    # Virtual input: Button released (HIGH)
    plan_high = parser.parse(sketch, virtual_inputs={"2": "HIGH"})
    dw_events_high = [e for e in plan_high.events if e.action == "digitalWrite"]
    assert len(dw_events_high) > 0
    # Every write should be LOW
    assert all(e.value == "LOW" for e in dw_events_high)


def test_parser_analog_write_and_read():
    sketch = """
    void setup() {
        pinMode(9, OUTPUT);
    }
    void loop() {
        int val = analogRead(A0);
        analogWrite(9, 128);
        delay(200);
    }
    """
    parser = CodeParser(max_duration_ms=500)
    plan = parser.parse(sketch)

    aw_events = [e for e in plan.events if e.action == "analogWrite"]
    assert len(aw_events) > 0
    assert aw_events[0].pin == "9"
    assert aw_events[0].value == 128


def test_parser_unconfigured_pins_warning():
    sketch = """
    void setup() {
        // Missing pinMode for pin 4
    }
    void loop() {
        digitalWrite(4, HIGH);
        delay(500);
    }
    """
    parser = CodeParser(max_duration_ms=1000)
    plan = parser.parse(sketch)

    # Should detect pin 4 and register a warning
    pin_ids = {p.pin for p in plan.pins}
    assert "4" in pin_ids
    assert any("without pinMode" in w for w in plan.warnings)


def test_parser_detect_input_pins():
    sketch = """
    #define SENSOR_PIN 4
    #define BTN_PIN 7

    void setup() {
        pinMode(SENSOR_PIN, INPUT);
        pinMode(BTN_PIN, INPUT_PULLUP);
        pinMode(13, OUTPUT);
    }
    void loop() {
        int unconf = digitalRead(8); // unconfigured read
    }
    """
    parser = CodeParser()
    inputs = parser.detect_input_pins(sketch)
    pin_names = [p for p, _ in inputs]
    assert "4" in pin_names
    assert "7" in pin_names
    assert "8" in pin_names
    assert "13" not in pin_names


def test_parser_flexible_virtual_pins():
    sketch = """
    void setup() {
        pinMode(5, INPUT);
        pinMode(8, OUTPUT);
    }
    void loop() {
        if (!digitalRead(5)) { // Active-low condition
            digitalWrite(8, HIGH);
        } else {
            digitalWrite(8, LOW);
        }
    }
    """
    parser = CodeParser(max_duration_ms=1000)
    # When pin 5 is LOW, !digitalRead(5) is True -> pin 8 should be HIGH
    plan_low = parser.parse(sketch, virtual_inputs={"5": "LOW"})
    dw_low = [e for e in plan_low.events if e.action == "digitalWrite" and e.pin == "8"]
    assert len(dw_low) > 0
    assert all(e.value == "HIGH" for e in dw_low)

    # When pin 5 is HIGH, !digitalRead(5) is False -> pin 8 should be LOW
    plan_high = parser.parse(sketch, virtual_inputs={"5": "HIGH"})
    dw_high = [e for e in plan_high.events if e.action == "digitalWrite" and e.pin == "8"]
    assert len(dw_high) > 0
    assert all(e.value == "LOW" for e in dw_high)


def test_parser_constant_delay_and_pwm():
    sketch = """
    #define BLINK_DELAY 800
    #define MOTOR_PWM 180
    void setup() {
        pinMode(9, OUTPUT);
    }
    void loop() {
        analogWrite(9, MOTOR_PWM);
        delay(BLINK_DELAY);
    }
    """
    parser = CodeParser(max_duration_ms=1000)
    plan = parser.parse(sketch)
    delays = [e for e in plan.events if e.action == "delay"]
    pwms = [e for e in plan.events if e.action == "analogWrite"]
    assert len(delays) > 0
    assert delays[0].value == 800
    assert len(pwms) > 0
    assert pwms[0].value == 180


def test_parser_variable_reassignment_and_toggle():
    sketch = """
    void setup() {
        pinMode(13, OUTPUT);
    }
    void loop() {
        int state = HIGH;
        digitalWrite(13, state);
        delay(500);
        state = LOW;
        digitalWrite(13, state);
        delay(500);
        state = !state;
        digitalWrite(13, state);
    }
    """
    parser = CodeParser(max_duration_ms=1100)
    plan = parser.parse(sketch)
    dw_events = [e for e in plan.events if e.action == "digitalWrite"]
    assert len(dw_events) >= 3
    assert dw_events[0].value == "HIGH"
    assert dw_events[1].value == "LOW"
    assert dw_events[2].value == "HIGH"




