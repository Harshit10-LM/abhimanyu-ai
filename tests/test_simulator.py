"""Unit tests for the state-machine simulator in core/simulator.py."""

import pytest
from core.code_parser import CodeParser
from core.schemas import PinState, SimulationPlan, TimedEvent
from core.simulator import HardwareSimulator


def test_simulator_independent_of_ollama():
    # Directly build a plan
    plan = SimulationPlan(
        pins=[PinState(pin="13", mode="OUTPUT", component_hint="LED")],
        events=[
            TimedEvent(t_ms=0, action="digitalWrite", pin="13", value="HIGH"),
            TimedEvent(t_ms=1000, action="digitalWrite", pin="13", value="LOW"),
            TimedEvent(t_ms=2000, action="digitalWrite", pin="13", value="HIGH"),
        ],
        loop_detected=True,
        loop_period_ms=2000,
    )

    sim = HardwareSimulator(step_ms=100)
    frames = sim.simulate(plan, duration_ms=2500)

    assert len(frames) > 0
    # At t=0 ms: HIGH
    frame_0 = [f for f in frames if f.t_ms == 0][0]
    assert frame_0.pin_states["13"].digital_state == "HIGH"

    # At t=500 ms: still HIGH
    frame_500 = [f for f in frames if f.t_ms == 500][0]
    assert frame_500.pin_states["13"].digital_state == "HIGH"

    # At t=1000 ms: transitioned to LOW
    frame_1000 = [f for f in frames if f.t_ms == 1000][0]
    assert frame_1000.pin_states["13"].digital_state == "LOW"

    # At t=2000 ms: transitioned back to HIGH
    frame_2000 = [f for f in frames if f.t_ms == 2000][0]
    assert frame_2000.pin_states["13"].digital_state == "HIGH"


def test_simulator_led_remaining_high_bug():
    """Validates the demo requirement: when no LOW event is written, LED stays HIGH permanently."""
    sketch = """
    #define LED_PIN 13
    #define BUTTON_PIN 2

    void setup() {
        pinMode(LED_PIN, OUTPUT);
    }

    void loop() {
        int buttonState = digitalRead(BUTTON_PIN);
        if (buttonState == LOW) {
            digitalWrite(LED_PIN, HIGH);
            delay(1500);
            // No digitalWrite(LED_PIN, LOW)!
        }
    }
    """
    parser = CodeParser(max_duration_ms=4000)
    # Virtual button pressed (LOW)
    plan = parser.parse(sketch, virtual_inputs={"2": "LOW"})

    sim = HardwareSimulator(step_ms=100)
    frames = sim.simulate(plan, duration_ms=4000)

    # After t=0ms, LED turns HIGH and MUST remain HIGH for the rest of simulation
    frames_after_boot = [f for f in frames if f.t_ms >= 100]
    for f in frames_after_boot:
        assert f.pin_states["13"].digital_state == "HIGH", (
            f"Frame at t={f.t_ms}ms should remain HIGH but was {f.pin_states['13'].digital_state}"
        )


def test_simulator_pwm_duty_cycle_updates():
    plan = SimulationPlan(
        pins=[PinState(pin="9", mode="OUTPUT", component_hint="PWM")],
        events=[
            TimedEvent(t_ms=0, action="analogWrite", pin="9", value=64),
            TimedEvent(t_ms=500, action="analogWrite", pin="9", value=200),
        ],
        loop_detected=False,
    )
    sim = HardwareSimulator(step_ms=100)
    frames = sim.simulate(plan, duration_ms=1000)

    f_0 = [f for f in frames if f.t_ms == 0][0]
    assert f_0.pin_states["9"].pwm_duty == 64

    f_600 = [f for f in frames if f.t_ms == 600][0]
    assert f_600.pin_states["9"].pwm_duty == 200


def test_simulator_analog_read_updates():
    plan = SimulationPlan(
        pins=[PinState(pin="A0", mode="INPUT", component_hint="SENSOR")],
        events=[
            TimedEvent(t_ms=100, action="analogRead", pin="A0", value=750),
        ],
    )
    sim = HardwareSimulator(step_ms=100)
    frames = sim.simulate(plan, duration_ms=500)
    f_100 = [f for f in frames if f.t_ms == 100][0]
    assert f_100.pin_states["A0"].analog_value == 750
    assert f_100.pin_states["A0"].digital_state == "HIGH"


