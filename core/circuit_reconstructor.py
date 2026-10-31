"""Converts computer-vision inventory and diagnostics into an editable CircuitDocument.

Enables the interactive circuit editor to load, visualize, and allow user modification
of the AI-reconstructed physical breadboard and microcontroller circuit.
"""

from typing import List, Optional
import re

from core.schemas import (
    CircuitDocument,
    CircuitPart,
    CircuitWire,
    DiagnosisResult,
    InventoryResult,
    PinReference,
    VisibleComponent,
)


def reconstruct_circuit_from_vision(
    inventory: InventoryResult,
    diagnosis: Optional[DiagnosisResult],
    board_id: str = "arduino_uno",
) -> CircuitDocument:
    """Translates visual component inventory and diagnostic findings into an editable circuit."""
    mcu_type = "arduino_uno"
    if "esp32" in board_id:
        mcu_type = "esp32_devkit"
    elif "stm32" in board_id:
        mcu_type = "stm32_bluepill"

    parts: List[CircuitPart] = [
        CircuitPart(
            id="mcu1",
            type=mcu_type,
            x=80.0,
            y=120.0,
            rotation=0,
            properties={"label": "Microcontroller", "board_id": board_id},
        ),
        CircuitPart(
            id="bb1",
            type="breadboard_half",
            x=450.0,
            y=100.0,
            rotation=0,
            properties={"label": "Breadboard"},
        ),
    ]

    wires: List[CircuitWire] = []
    wire_counter = 1

    # Check which connections are flagged as defective or uncertain in diagnosis
    flagged_keywords = set()
    if diagnosis:
        for finding in diagnosis.findings:
            flagged_keywords.update(re.findall(r"\b[A-Za-z0-9_]+\b", finding.finding.lower()))
            flagged_keywords.update(re.findall(r"\b[A-Za-z0-9_]+\b", finding.visual_evidence.lower()))

    uncertain_set = set(inventory.uncertain_connections)

    # Reconstruct discrete components
    comp_counts = {"led": 0, "resistor": 0, "sensor": 0, "button": 0}

    for idx, comp in enumerate(inventory.components):
        cname = comp.name.lower()
        ctype = comp.type.lower() if comp.type else "generic"

        # Categorize
        if "led" in cname or ctype == "led":
            comp_counts["led"] += 1
            part_id = f"led{comp_counts['led']}"
            color = comp.color or ("red" if "red" in cname else "green")
            parts.append(
                CircuitPart(
                    id=part_id,
                    type="led",
                    x=560.0 + (comp_counts["led"] * 40),
                    y=180.0,
                    rotation=0,
                    properties={"color": color, "label": comp.name},
                )
            )

            # Reconstruct legs
            for leg in comp.legs:
                is_anode = "anode" in leg.leg_label.lower() or "long" in leg.leg_label.lower()
                pin_id = "anode" if is_anode else "cathode"
                target_str = leg.connects_to

                # Check if flagged as uncertain
                is_uncertain = (
                    leg.confidence != "high"
                    or any(u in target_str for u in uncertain_set)
                    or any(k in target_str.lower() for k in ("missing", "wrong", "floating", "unconnected"))
                )

                # Map target
                target_ref = _resolve_target_ref(target_str, default_row=15 if is_anode else 16)
                wire_color = "#22c55e" if is_anode else "#3b82f6"
                if is_uncertain:
                    wire_color = "#f59e0b"  # Amber for uncertain

                wires.append(
                    CircuitWire(
                        id=f"w{wire_counter}",
                        source=PinReference(part_id=part_id, pin_id=pin_id),
                        target=target_ref,
                        color=wire_color,
                        style="dashed" if is_uncertain else "solid",
                        confidence="uncertain" if is_uncertain else "confirmed",
                    )
                )
                wire_counter += 1

        elif "resistor" in cname or ctype == "resistor":
            comp_counts["resistor"] += 1
            part_id = f"r{comp_counts['resistor']}"
            res_val = 220
            m_res = re.search(r"(\d+)\s*(k?)(?:Ω|ohm)", cname)
            if m_res:
                res_val = int(m_res.group(1)) * (1000 if m_res.group(2) == "k" else 1)

            parts.append(
                CircuitPart(
                    id=part_id,
                    type="resistor",
                    x=560.0 + (comp_counts["resistor"] * 40),
                    y=260.0,
                    rotation=90,
                    properties={"resistance": res_val, "unit": "Ω", "label": comp.name},
                )
            )

            for l_idx, leg in enumerate(comp.legs[:2]):
                pin_id = f"pin{l_idx+1}"
                target_str = leg.connects_to
                is_uncertain = leg.confidence != "high"
                target_ref = _resolve_target_ref(target_str, default_row=16 if l_idx == 0 else 20)

                wires.append(
                    CircuitWire(
                        id=f"w{wire_counter}",
                        source=PinReference(part_id=part_id, pin_id=pin_id),
                        target=target_ref,
                        color="#f59e0b" if is_uncertain else "#111827",
                        style="dashed" if is_uncertain else "solid",
                        confidence="uncertain" if is_uncertain else "confirmed",
                    )
                )
                wire_counter += 1

        elif any(s in cname for s in ("sensor", "dht", "ultrasonic", "hcsr04", "ldr")):
            comp_counts["sensor"] += 1
            part_id = f"sensor{comp_counts['sensor']}"
            parts.append(
                CircuitPart(
                    id=part_id,
                    type="dht11",
                    x=680.0,
                    y=180.0,
                    rotation=0,
                    properties={"label": comp.name},
                )
            )

    # Reconstruct MCU connections from legs on the MCU component
    for comp in inventory.components:
        if any(b in comp.name.lower() for b in ("arduino", "esp32", "stm32")):
            for leg in comp.legs:
                m_pin = re.search(r"\b(GPIO\s*\d+|\d+|A\d+|3V3|5V|GND)\b", leg.leg_label, re.IGNORECASE)
                if m_pin:
                    pin_clean = m_pin.group(1).replace(" ", "").upper()
                    target_ref = _resolve_target_ref(leg.connects_to, default_row=15)
                    is_uncertain = leg.confidence != "high"
                    wires.append(
                        CircuitWire(
                            id=f"w{wire_counter}",
                            source=PinReference(part_id="mcu1", pin_id=pin_clean),
                            target=target_ref,
                            color="#f59e0b" if is_uncertain else ("#ef4444" if "3V3" in pin_clean or "5V" in pin_clean else ("#111827" if "GND" in pin_clean else "#22c55e")),
                            style="dashed" if is_uncertain else "solid",
                            confidence="uncertain" if is_uncertain else "confirmed",
                        )
                    )
                    wire_counter += 1

    notes = [
        "AI-GENERATED CIRCUIT RECONSTRUCTION — VERIFY CONNECTIONS",
        "Solid wires indicate visually confirmed electrical paths.",
        "Dashed amber wires represent proposed, uncertain, or flagged connections that require multimeter verification.",
        "Use the interactive canvas to edit, add, or delete connections before running the digital twin.",
    ]

    return CircuitDocument(
        board=board_id,
        parts=parts,
        wires=wires,
        suggested=True,
        notes=notes,
    )


def _resolve_target_ref(connects_to: str, default_row: int = 15) -> PinReference:
    """Helper to parse breadboard row or power rail from leg connects_to string."""
    c_lower = connects_to.lower()

    # Power rail
    if "top" in c_lower and ("+" in c_lower or "red" in c_lower or "pos" in c_lower):
        return PinReference(part_id="bb1", pin_id="top_+")
    if "top" in c_lower and ("-" in c_lower or "blue" in c_lower or "neg" in c_lower or "gnd" in c_lower):
        return PinReference(part_id="bb1", pin_id="top_-")
    if "bot" in c_lower or "rail" in c_lower:
        if "-" in c_lower or "blue" in c_lower or "neg" in c_lower or "gnd" in c_lower:
            return PinReference(part_id="bb1", pin_id="bot_-")
        if "+" in c_lower or "red" in c_lower or "pos" in c_lower:
            return PinReference(part_id="bb1", pin_id="bot_+")

    # Row number
    m_row = re.search(r"row\s*(\d+)", c_lower)
    if m_row:
        row_n = m_row.group(1)
        # default column e or a
        return PinReference(part_id="bb1", pin_id=f"{row_n}e")

    return PinReference(part_id="bb1", pin_id=f"{default_row}e")

