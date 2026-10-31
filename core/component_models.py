"""Electronic component physical and electrical behavior models.

Simulates current flow, forward/reverse bias, resistance, voltage division,
brightness, and sensor states based on active electrical nets.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple
from core.circuit_graph import CircuitGraph
from core.schemas import CircuitPart, PinReference, PinSnapshot


@dataclass
class ComponentEvaluationResult:
    """Evaluated physical state of a single circuit component."""

    part_id: str
    part_type: str
    state: Literal["OFF", "ON", "ERROR", "ACTIVE", "IDLE"]
    is_powered: bool = False
    brightness: int = 0  # 0 to 255 for LEDs
    voltage_drop_v: float = 0.0
    current_ma: float = 0.0
    angle_deg: float = 0.0  # For servos
    analog_reading: int = 0  # For ADC/pots
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, str | int | float | bool] = field(default_factory=dict)


class ComponentSimulator:
    """Evaluates electrical states of all components attached to the circuit graph."""

    def __init__(self, board_id: str = "arduino_uno"):
        self.board_id = board_id
        # Supply voltage: 5.0V for Uno, 3.3V for ESP32 and STM32
        self.vcc_voltage = 3.3 if ("esp32" in board_id or "stm32" in board_id) else 5.0

    def evaluate_circuit(
        self,
        graph: CircuitGraph,
        mcu_pin_states: Dict[str, PinSnapshot],
    ) -> Dict[str, ComponentEvaluationResult]:
        """Calculates physical states for all non-MCU components in the circuit."""
        results: Dict[str, ComponentEvaluationResult] = {}

        # 1. Map electrical net potentials based on MCU pins
        net_potentials = self._calculate_net_potentials(graph, mcu_pin_states)

        # 2. Evaluate each component
        for part in graph.doc.parts:
            if part.type.startswith("breadboard") or part.type in ("arduino_uno", "esp32_devkit", "stm32_bluepill"):
                continue

            if part.type == "led":
                results[part.id] = self._evaluate_led(part, graph, net_potentials, mcu_pin_states)
            elif part.type == "resistor":
                results[part.id] = self._evaluate_resistor(part, graph, net_potentials)
            elif part.type == "button":
                results[part.id] = self._evaluate_button(part, graph, net_potentials)
            elif part.type == "potentiometer":
                results[part.id] = self._evaluate_potentiometer(part, graph, net_potentials)
            elif part.type == "buzzer":
                results[part.id] = self._evaluate_buzzer(part, graph, net_potentials)
            elif part.type == "servo":
                results[part.id] = self._evaluate_servo(part, graph, net_potentials, mcu_pin_states)
            elif part.type in ("dht11", "hcsr04", "ldr"):
                results[part.id] = self._evaluate_sensor(part, graph, net_potentials)

        return results

    def _calculate_net_potentials(
        self, graph: CircuitGraph, mcu_pin_states: Dict[str, PinSnapshot]
    ) -> Dict[str, float]:
        """Maps each canonical electrical net root to its drive voltage (0.0 to VCC)."""
        potentials: Dict[str, float] = {}

        mcu_part = graph.get_mcu_part()
        mcu_id = mcu_part.id if mcu_part else "mcu1"

        # Ground nets are 0.0V across all MCU GND variants
        self.gnd_nets: Set[str] = set()
        for gpin in ("GND", "GND.1", "GND.2", "GND1", "GND2", "gnd"):
            gnet = graph.get_net_of_pin(mcu_id, gpin)
            potentials[gnet] = 0.0
            self.gnd_nets.add(gnet)

        # Power nets are VCC
        vcc_pin = "3V3" if "esp32" in self.board_id else ("3.3V" if "stm32" in self.board_id else "5V")
        vcc_net = graph.get_net_of_pin(mcu_id, vcc_pin)
        potentials[vcc_net] = self.vcc_voltage

        for vpin in ("5V", "3.3V", "3V3", "VIN", "VCC"):
            v_val = 3.3 if vpin in ("3.3V", "3V3") else self.vcc_voltage
            p_net = graph.get_net_of_pin(mcu_id, vpin)
            potentials[p_net] = v_val

        # Map GPIO outputs
        for pin_name, snap in mcu_pin_states.items():
            net = graph.get_net_of_pin(mcu_id, pin_name)
            if snap.mode == "OUTPUT":
                if snap.digital_state == "HIGH":
                    duty = snap.pwm_duty if snap.pwm_duty is not None else 255
                    potentials[net] = (duty / 255.0) * self.vcc_voltage
                else:
                    potentials[net] = 0.0
            elif snap.mode == "INPUT_PULLUP":
                # Pulled up weakly to VCC
                potentials.setdefault(net, self.vcc_voltage)

        return potentials

    def _evaluate_led(
        self,
        led_part: CircuitPart,
        graph: CircuitGraph,
        potentials: Dict[str, float],
        mcu_pin_states: Dict[str, PinSnapshot],
    ) -> ComponentEvaluationResult:
        """Evaluates LED state: requires closed circuit path with forward bias."""
        anode_net = graph.get_net_of_pin(led_part.id, "anode")
        cathode_net = graph.get_net_of_pin(led_part.id, "cathode")

        warnings: List[str] = []
        mcu_part = graph.get_mcu_part()
        mcu_id = mcu_part.id if mcu_part else "mcu1"
        gnd_net = graph.get_net_of_pin(mcu_id, "GND")

        # Trace high potential source (GPIO or VCC) and ground connection
        # Path from Anode to Source and Cathode to Ground (Normal Forward Bias)
        fwd_source_v, r_anode, src_desc = self._trace_to_voltage_source(anode_net, graph, potentials)
        fwd_gnd_reached, r_cathode = self._trace_to_gnd(cathode_net, graph, getattr(self, "gnd_nets", {gnd_net}))

        # Path from Cathode to Source and Anode to Ground (Reverse Bias)
        rev_source_v, r_rev_src, rev_src_desc = self._trace_to_voltage_source(cathode_net, graph, potentials)
        rev_gnd_reached, r_rev_gnd = self._trace_to_gnd(anode_net, graph, getattr(self, "gnd_nets", {gnd_net}))

        v_forward = float(led_part.properties.get("forward_voltage", 2.0))

        # Check reverse bias first
        if rev_source_v is not None and rev_source_v > 1.5 and rev_gnd_reached:
            warnings.append("LED is reverse-biased (Cathode connected to voltage source, Anode to Ground).")
            return ComponentEvaluationResult(
                part_id=led_part.id,
                part_type="led",
                state="OFF",
                is_powered=False,
                brightness=0,
                voltage_drop_v=-rev_source_v,
                current_ma=0.0,
                warnings=warnings,
                details={"status": "Reverse Biased"},
            )

        # Check forward bias closed loop
        if fwd_source_v is not None and fwd_gnd_reached:
            total_r = r_anode + r_cathode
            has_resistor = total_r > 0

            if fwd_source_v >= v_forward:
                if not has_resistor or total_r < 50:
                    warnings.append(
                        "Warning: High current! No adequate current-limiting resistor found in series."
                    )
                    eff_r = 10.0  # internal diode resistance
                else:
                    eff_r = total_r

                current_ma = max(0.0, ((fwd_source_v - v_forward) / eff_r) * 1000.0)
                brightness = min(255, int((fwd_source_v / self.vcc_voltage) * 255))

                return ComponentEvaluationResult(
                    part_id=led_part.id,
                    part_type="led",
                    state="ON",
                    is_powered=True,
                    brightness=brightness,
                    voltage_drop_v=v_forward,
                    current_ma=round(current_ma, 2),
                    warnings=warnings,
                    details={
                        "color": led_part.properties.get("color", "red"),
                        "series_resistance_ohms": total_r,
                        "source": src_desc,
                    },
                )
            else:
                # Voltage below forward threshold (e.g. Pin is LOW: 0V)
                return ComponentEvaluationResult(
                    part_id=led_part.id,
                    part_type="led",
                    state="OFF",
                    is_powered=False,
                    brightness=0,
                    voltage_drop_v=fwd_source_v,
                    current_ma=0.0,
                    warnings=warnings,
                    details={"status": "Pin LOW or below threshold"},
                )

        # Circuit path is open or floating
        unconnected = []
        if fwd_source_v is None:
            unconnected.append("Anode has no path to voltage/GPIO")
        if not fwd_gnd_reached:
            unconnected.append("Cathode has no return path to Ground")

        return ComponentEvaluationResult(
            part_id=led_part.id,
            part_type="led",
            state="OFF",
            is_powered=False,
            brightness=0,
            voltage_drop_v=0.0,
            current_ma=0.0,
            warnings=["LED terminal is floating or disconnected from power/ground: " + ", ".join(unconnected)],
        )

    def _trace_to_voltage_source(
        self, start_net: str, graph: CircuitGraph, potentials: Dict[str, float]
    ) -> Tuple[Optional[float], float, str]:
        """Traces if start_net reaches a voltage source directly or through a series resistor."""
        # 1. Direct connection
        if start_net in potentials:
            return potentials[start_net], 0.0, f"Net {start_net}"

        # 2. Check resistors connected to start_net
        for part in graph.doc.parts:
            if part.type == "resistor":
                r_net1 = graph.get_net_of_pin(part.id, "pin1")
                r_net2 = graph.get_net_of_pin(part.id, "pin2")

                r_val = float(part.properties.get("resistance", 220))
                if part.properties.get("unit") == "kΩ":
                    r_val *= 1000.0

                if start_net == r_net1 and r_net2 in potentials:
                    return potentials[r_net2], r_val, f"Resistor {part.id} to Net {r_net2}"
                elif start_net == r_net2 and r_net1 in potentials:
                    return potentials[r_net1], r_val, f"Resistor {part.id} to Net {r_net1}"

        return None, 0.0, "None"

    def _trace_to_gnd(
        self, start_net: str, graph: CircuitGraph, gnd_nets: Set[str] | str
    ) -> Tuple[bool, float]:
        """Traces if start_net reaches GND directly or through a series resistor."""
        target_nets = {gnd_nets} if isinstance(gnd_nets, str) else gnd_nets

        # 1. Direct connection to GND
        if start_net in target_nets:
            return True, 0.0

        # 2. Check resistors connected to start_net
        for part in graph.doc.parts:
            if part.type == "resistor":
                r_net1 = graph.get_net_of_pin(part.id, "pin1")
                r_net2 = graph.get_net_of_pin(part.id, "pin2")

                r_val = float(part.properties.get("resistance", 220))
                if part.properties.get("unit") == "kΩ":
                    r_val *= 1000.0

                if (start_net == r_net1 and r_net2 in target_nets) or (start_net == r_net2 and r_net1 in target_nets):
                    return True, r_val

        return False, 0.0

    def _evaluate_resistor(
        self, part: CircuitPart, graph: CircuitGraph, potentials: Dict[str, float]
    ) -> ComponentEvaluationResult:
        net1 = graph.get_net_of_pin(part.id, "pin1")
        net2 = graph.get_net_of_pin(part.id, "pin2")

        v1 = potentials.get(net1, None)
        v2 = potentials.get(net2, None)

        if v1 is None or v2 is None:
            return ComponentEvaluationResult(
                part_id=part.id,
                part_type="resistor",
                state="IDLE",
                is_powered=False,
                warnings=["Resistor terminal is open/unconnected."],
            )

        v_drop = abs(v1 - v2)
        r_val = float(part.properties.get("resistance", 220))
        unit = part.properties.get("unit", "Ω")
        if unit == "kΩ":
            r_val *= 1000.0
        current_ma = (v_drop / r_val) * 1000.0 if r_val > 0 else 0.0

        return ComponentEvaluationResult(
            part_id=part.id,
            part_type="resistor",
            state="ACTIVE" if v_drop > 0.05 else "IDLE",
            is_powered=v_drop > 0.05,
            voltage_drop_v=round(v_drop, 3),
            current_ma=round(current_ma, 2),
            details={"resistance_ohms": r_val},
        )

    def _evaluate_button(
        self, part: CircuitPart, graph: CircuitGraph, potentials: Dict[str, float]
    ) -> ComponentEvaluationResult:
        is_pressed = part.properties.get("is_pressed", False)
        return ComponentEvaluationResult(
            part_id=part.id,
            part_type="button",
            state="ON" if is_pressed else "OFF",
            is_powered=is_pressed,
            details={"is_pressed": is_pressed, "type": "momentary_push_button"},
        )

    def _evaluate_potentiometer(
        self, part: CircuitPart, graph: CircuitGraph, potentials: Dict[str, float]
    ) -> ComponentEvaluationResult:
        ratio = float(part.properties.get("ratio", 0.5))  # 0.0 to 1.0
        ratio = max(0.0, min(1.0, ratio))

        net1 = graph.get_net_of_pin(part.id, "pin1")
        net2 = graph.get_net_of_pin(part.id, "pin2")

        v1 = potentials.get(net1, 0.0)
        v2 = potentials.get(net2, self.vcc_voltage)

        wiper_v = v1 + ratio * (v2 - v1)
        adc_val = int((wiper_v / self.vcc_voltage) * 1023)

        return ComponentEvaluationResult(
            part_id=part.id,
            part_type="potentiometer",
            state="ACTIVE",
            is_powered=True,
            voltage_drop_v=round(wiper_v, 2),
            analog_reading=adc_val,
            details={"ratio": ratio, "wiper_voltage": round(wiper_v, 2)},
        )

    def _evaluate_buzzer(
        self, part: CircuitPart, graph: CircuitGraph, potentials: Dict[str, float]
    ) -> ComponentEvaluationResult:
        pos_net = graph.get_net_of_pin(part.id, "positive")
        neg_net = graph.get_net_of_pin(part.id, "negative")

        v_pos = potentials.get(pos_net, 0.0)
        v_neg = potentials.get(neg_net, 0.0)

        diff = v_pos - v_neg
        is_sounding = diff > 2.0

        return ComponentEvaluationResult(
            part_id=part.id,
            part_type="buzzer",
            state="ACTIVE" if is_sounding else "OFF",
            is_powered=is_sounding,
            voltage_drop_v=round(max(0.0, diff), 2),
            details={"sounding": is_sounding},
        )

    def _evaluate_servo(
        self,
        part: CircuitPart,
        graph: CircuitGraph,
        potentials: Dict[str, float],
        mcu_pin_states: Dict[str, PinSnapshot],
    ) -> ComponentEvaluationResult:
        vcc_net = graph.get_net_of_pin(part.id, "vcc")
        gnd_net = graph.get_net_of_pin(part.id, "gnd")
        sig_net = graph.get_net_of_pin(part.id, "signal")

        is_powered = (potentials.get(vcc_net, 0.0) >= 3.0) and (potentials.get(gnd_net, 1.0) <= 0.1)

        # Check PWM on signal net
        angle = 90.0
        if is_powered:
            for snap in mcu_pin_states.values():
                if snap.pwm_duty is not None and snap.pwm_duty > 0:
                    # Map 0-255 duty cycle to 0-180 degrees
                    angle = (snap.pwm_duty / 255.0) * 180.0
                    break

        return ComponentEvaluationResult(
            part_id=part.id,
            part_type="servo",
            state="ACTIVE" if is_powered else "OFF",
            is_powered=is_powered,
            angle_deg=round(angle, 1),
            details={"angle_deg": round(angle, 1)},
        )

    def _evaluate_sensor(
        self, part: CircuitPart, graph: CircuitGraph, potentials: Dict[str, float]
    ) -> ComponentEvaluationResult:
        vcc_net = graph.get_net_of_pin(part.id, "vcc")
        gnd_net = graph.get_net_of_pin(part.id, "gnd")

        is_powered = (potentials.get(vcc_net, 0.0) >= 3.0) and (potentials.get(gnd_net, 1.0) <= 0.1)

        return ComponentEvaluationResult(
            part_id=part.id,
            part_type=part.type,
            state="ACTIVE" if is_powered else "IDLE",
            is_powered=is_powered,
            details=part.properties,
        )
