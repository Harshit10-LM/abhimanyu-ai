"""Generates architectural Mermaid diagrams for embedded projects.

Inspired by Cyréna and Tiesta. Translates firmware modules, board configuration,
pin assignments, and connected electronic peripherals into standard Mermaid graphs.
"""

from typing import List, Optional
from core.board_database import BoardSpec
from core.pin_conflict_analyzer import WiringEntry
from core.schemas import CircuitDocument, SimulationPlan


class ArchitectureMapper:
    """Generates clean, readable Mermaid flowchart diagrams of embedded systems."""

    @staticmethod
    def generate_mermaid_diagram(
        board: BoardSpec,
        plan: Optional[SimulationPlan],
        circuit_doc: Optional[CircuitDocument] = None,
        wiring_table: Optional[List[WiringEntry]] = None,
    ) -> str:
        """Constructs a standard Mermaid graph TD diagram."""
        lines = ["flowchart TD"]

        # Board Node
        lines.append(f'    subgraph MCU["🖥️ {board.display_name} ({board.mcu})"]')
        lines.append('        CORE["Microcontroller Core"]')
        lines.append(f'        PWR["Logic Level: {board.logic_voltage}V"]')

        # Pins
        pins_list = []
        if plan and plan.pins:
            for p in plan.pins:
                clean_id = f"PIN_{p.pin.replace(' ', '_').replace('.', '_')}"
                lines.append(f'        {clean_id}["Pin {p.pin} ({p.mode})"]')
                pins_list.append((clean_id, p))
        elif wiring_table:
            for idx, w in enumerate(wiring_table[:4]):
                clean_id = f"PIN_W_{idx}"
                lines.append(f'        {clean_id}["{w.mcu_pin}"]')
                pins_list.append((clean_id, type("P", (), {"pin": w.mcu_pin, "mode": w.purpose})()))
        else:
            lines.append('        PIN_13["Pin 13 (OUTPUT)"]')
            lines.append('        PIN_GND["GND (0V)"]')
        lines.append("    end")

        # Peripherals Subgraph
        lines.append('    subgraph PERIPHERALS["🔌 Electronic Components & Breadboard"]')
        if circuit_doc and circuit_doc.parts:
            for part in circuit_doc.parts:
                if part.type.startswith("breadboard") or part.type in ("arduino_uno", "esp32_devkit", "stm32_bluepill"):
                    continue
                part_label = part.properties.get("label", part.type.upper())
                clean_part_id = f"COMP_{part.id}"
                lines.append(f'        {clean_part_id}["{part_label}"]')
        else:
            lines.append('        COMP_LED["5mm Red LED"]')
            lines.append('        COMP_RES["220Ω Resistor"]')
        lines.append("    end")

        # Connections
        if circuit_doc and circuit_doc.wires:
            for w in circuit_doc.wires[:8]:
                s_id = f"PIN_{w.source.pin_id.replace(' ', '_')}" if w.source.part_id.startswith("mcu") else f"COMP_{w.source.part_id}"
                t_id = f"COMP_{w.target.part_id}" if not w.target.part_id.startswith("mcu") else f"PIN_{w.target.pin_id.replace(' ', '_')}"
                lines.append(f"    {s_id} -->|{w.style}| {t_id}")
        else:
            lines.append("    PIN_13 -->|Signal| COMP_LED")
            lines.append("    COMP_LED --> COMP_RES")
            lines.append("    COMP_RES --> PIN_GND")

        return "\n".join(lines)

