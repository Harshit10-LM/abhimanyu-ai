"""Deterministic state-machine interpreter and timeline generator.

Consumes a SimulationPlan and generates discrete time-slice frames
representing virtual microcontroller hardware pin states over time.
"""

from typing import Dict, List, Optional
from core.circuit_graph import CircuitGraph
from core.component_models import ComponentSimulator
from core.schemas import CircuitDocument, PinSnapshot, SimulationFrame, SimulationPlan, TimedEvent

FRAME_STEP_MS = 100
DEFAULT_DURATION_MS = 6000


class HardwareSimulator:
    """Simulates digital pin transitions and electrical component states over a discrete time window."""

    def __init__(self, step_ms: int = FRAME_STEP_MS, board_id: str = "arduino_uno"):
        self.step_ms = step_ms
        self.board_id = board_id

    def simulate(
        self,
        plan: SimulationPlan,
        duration_ms: int = DEFAULT_DURATION_MS,
        circuit_doc: Optional[CircuitDocument] = None,
    ) -> List[SimulationFrame]:
        """Generates chronologically ordered frames from t=0 to duration_ms."""
        # Initialize circuit graph and component evaluator if document provided
        graph: Optional[CircuitGraph] = CircuitGraph(circuit_doc) if circuit_doc else None
        comp_sim = ComponentSimulator(board_id=self.board_id) if graph else None
        # Initialize initial pin state snapshots
        current_pins: Dict[str, PinSnapshot] = {}
        for p in plan.pins:
            default_digital = "UNKNOWN"
            if p.mode == "INPUT_PULLUP":
                default_digital = "HIGH"
            elif p.mode == "OUTPUT":
                default_digital = "LOW"

            current_pins[p.pin] = PinSnapshot(
                pin=p.pin,
                mode=p.mode,
                digital_state=default_digital,
                analog_value=None,
                pwm_duty=0 if p.mode == "OUTPUT" else None,
                component_hint=p.component_hint,
            )

        # Group events by timestamp
        events_by_time: Dict[int, List[TimedEvent]] = {}
        for evt in sorted(plan.events, key=lambda e: e.t_ms):
            events_by_time.setdefault(evt.t_ms, []).append(evt)

        # Determine effective duration
        max_event_time = max(events_by_time.keys()) if events_by_time else 0
        total_duration = max(duration_ms, max_event_time)

        frames: List[SimulationFrame] = []
        last_event_desc = "Initial boot / Power ON"

        for t in range(0, total_duration + 1, self.step_ms):
            # Check for any events that occurred in the interval (t - step_ms, t]
            current_interval_events: List[TimedEvent] = []
            for evt_time, evts in events_by_time.items():
                if (t == 0 and evt_time == 0) or (t - self.step_ms < evt_time <= t):
                    current_interval_events.extend(evts)

            # Apply events to pin state
            for evt in current_interval_events:
                pin_id = evt.pin
                if pin_id not in current_pins:
                    # Dynamically register unlisted pin
                    current_pins[pin_id] = PinSnapshot(
                        pin=pin_id,
                        mode="OUTPUT" if evt.action in ("digitalWrite", "analogWrite") else "INPUT",
                        digital_state="LOW",
                        pwm_duty=0,
                        component_hint="LED" if pin_id in ("13", "2", "PC13") else None,
                    )

                if evt.action == "digitalWrite":
                    val_str = str(evt.value).upper()
                    new_state = "HIGH" if val_str == "HIGH" else "LOW"
                    current_pins[pin_id].digital_state = new_state
                    current_pins[pin_id].pwm_duty = 255 if new_state == "HIGH" else 0
                    last_event_desc = f"t={evt.t_ms}ms: digitalWrite({pin_id}, {new_state})"

                elif evt.action == "analogWrite":
                    duty = int(evt.value) if evt.value is not None else 128
                    duty = max(0, min(255, duty))
                    current_pins[pin_id].pwm_duty = duty
                    current_pins[pin_id].digital_state = (
                        "HIGH" if duty > 200 else ("LOW" if duty < 50 else "HIGH")
                    )
                    pct = round((duty / 255.0) * 100, 1)
                    last_event_desc = (
                        f"t={evt.t_ms}ms: analogWrite({pin_id}, {duty}) [{pct}% duty cycle]"
                    )

                elif evt.action == "digitalRead":
                    val_str = str(evt.value).upper()
                    current_pins[pin_id].digital_state = (
                        "HIGH" if val_str == "HIGH" else "LOW"
                    )
                    last_event_desc = f"t={evt.t_ms}ms: digitalRead({pin_id}) -> {val_str}"

                elif evt.action == "analogRead":
                    try:
                        a_val = int(evt.value) if evt.value is not None else 512
                    except (ValueError, TypeError):
                        a_val = 512
                    current_pins[pin_id].analog_value = a_val
                    current_pins[pin_id].digital_state = "HIGH" if a_val > 512 else "LOW"
                    last_event_desc = f"t={evt.t_ms}ms: analogRead({pin_id}) -> {a_val} (ADC)"

            # Create a detached deep snapshot for this frame
            frame_pins = {
                pid: PinSnapshot(
                    pin=snap.pin,
                    mode=snap.mode,
                    digital_state=snap.digital_state,
                    analog_value=snap.analog_value,
                    pwm_duty=snap.pwm_duty,
                    component_hint=snap.component_hint,
                )
                for pid, snap in current_pins.items()
            }

            # Evaluate electrical components if circuit graph is present
            comp_states: Dict[str, dict] = {}
            if graph and comp_sim:
                eval_res = comp_sim.evaluate_circuit(graph, frame_pins)
                for part_id, res in eval_res.items():
                    comp_states[part_id] = {
                        "state": res.state,
                        "is_powered": res.is_powered,
                        "brightness": res.brightness,
                        "voltage_drop_v": res.voltage_drop_v,
                        "current_ma": res.current_ma,
                        "angle_deg": res.angle_deg,
                        "analog_reading": res.analog_reading,
                        "warnings": res.warnings,
                        "details": res.details,
                    }

            frames.append(
                SimulationFrame(
                    t_ms=t,
                    pin_states=frame_pins,
                    active_event_description=last_event_desc,
                    component_states=comp_states,
                )
            )

        return frames

