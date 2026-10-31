"""Deterministic circuit validator for electronic correctness and electrical safety.

Validates complete circuit paths, detects short circuits, missing current-limiting
resistors, reverse bias on polarized components, and disconnected terminals.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from core.circuit_graph import CircuitGraph
from core.component_models import ComponentSimulator
from core.schemas import CircuitDocument, PinSnapshot


class CircuitValidationIssue(BaseModel):
    """Represents a wiring defect, electrical hazard, or disconnected component."""

    severity: str = Field(description="'error', 'warning', or 'info'")
    category: str = Field(description="'connectivity', 'safety', 'component', 'power'")
    part_id: Optional[str] = None
    title: str
    description: str
    recommendation: str


class CircuitValidationReport(BaseModel):
    """Comprehensive validation outcome of an electronic circuit document."""

    is_valid: bool
    issues: List[CircuitValidationIssue] = Field(default_factory=list)
    short_circuits: List[str] = Field(default_factory=list)
    disconnected_parts: List[str] = Field(default_factory=list)


class CircuitValidator:
    """Performs static and electrical topology verification on CircuitDocuments."""

    def __init__(self, board_id: str = "arduino_uno"):
        self.board_id = board_id

    def validate(
        self,
        doc: CircuitDocument,
        mcu_pin_states: Optional[Dict[str, PinSnapshot]] = None,
    ) -> CircuitValidationReport:
        issues: List[CircuitValidationIssue] = []
        short_circuits: List[str] = []
        disconnected_parts: List[str] = []

        graph = CircuitGraph(doc)
        mcu_part = graph.get_mcu_part()
        mcu_id = mcu_part.id if mcu_part else "mcu1"

        # 1. Check for Short Circuit between VCC and GND
        vcc_pin = "3V3" if "esp32" in self.board_id else ("3.3V" if "stm32" in self.board_id else "5V")
        gnd_net = graph.get_net_of_pin(mcu_id, "GND")
        vcc_net = graph.get_net_of_pin(mcu_id, vcc_pin)

        if gnd_net == vcc_net:
            msg = f"Direct short circuit detected between {vcc_pin} and GND!"
            short_circuits.append(msg)
            issues.append(
                CircuitValidationIssue(
                    severity="error",
                    category="safety",
                    title="Power-to-Ground Short Circuit",
                    description=msg,
                    recommendation="Immediately disconnect wires bridging VCC and GND rails to prevent board damage.",
                )
            )

        # 2. Check each placed component for connectivity
        simulator = ComponentSimulator(board_id=self.board_id)
        dummy_states = mcu_pin_states or {
            "13": PinSnapshot(pin="13", mode="OUTPUT", digital_state="HIGH", pwm_duty=255)
        }
        eval_results = simulator.evaluate_circuit(graph, dummy_states)

        for part in doc.parts:
            if part.type.startswith("breadboard") or part.type in ("arduino_uno", "esp32_devkit", "stm32_bluepill"):
                continue

            pins = graph._get_pins_for_part(part)
            connected_pins_count = 0
            for p in pins:
                net = graph.get_net_of_pin(part.id, p)
                # Check if this net has wires or connects to anything else
                net_members = graph.uf.get_groups().get(net, set())
                # If net contains more than just this pin
                if len(net_members) > 1:
                    connected_pins_count += 1

            if connected_pins_count == 0:
                disconnected_parts.append(part.id)
                issues.append(
                    CircuitValidationIssue(
                        severity="warning",
                        category="connectivity",
                        part_id=part.id,
                        title=f"Disconnected {part.type.upper()}",
                        description=f"Component '{part.id}' has no connected wires.",
                        recommendation=f"Connect '{part.id}' to breadboard terminal rows or microcontroller pins.",
                    )
                )
            elif connected_pins_count < len(pins) and part.type in ("led", "resistor", "buzzer"):
                issues.append(
                    CircuitValidationIssue(
                        severity="warning",
                        category="connectivity",
                        part_id=part.id,
                        title=f"Open Circuit on {part.type.upper()}",
                        description=f"Component '{part.id}' is only partially connected, forming an open circuit.",
                        recommendation="Complete the circuit loop by connecting both terminals (anode/cathode or pin1/pin2).",
                    )
                )

            # Check LED specific checks
            if part.type == "led":
                eval_res = eval_results.get(part.id)
                if eval_res:
                    for w in eval_res.warnings:
                        sev = "error" if "High current" in w else "warning"
                        issues.append(
                            CircuitValidationIssue(
                                severity=sev,
                                category="safety" if "High current" in w else "component",
                                part_id=part.id,
                                title="LED Configuration Issue",
                                description=w,
                                recommendation=(
                                    "Insert a 220Ω - 330Ω resistor in series with the LED to limit current."
                                    if "resistor" in w
                                    else "Ensure LED Anode connects toward positive voltage and Cathode toward GND."
                                ),
                            )
                        )

        # 3. Overall Validity
        has_errors = any(i.severity == "error" for i in issues)

        return CircuitValidationReport(
            is_valid=not has_errors,
            issues=issues,
            short_circuits=short_circuits,
            disconnected_parts=disconnected_parts,
        )

