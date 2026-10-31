"""Electrical circuit graph and netlist representation for Firmware-Alchemist.

Manages circuit parts, breadboard tie-strip connectivity, electrical nets,
wire routing, and automated circuit suggestions from firmware simulation plans.
"""

from typing import Dict, List, Optional, Set, Tuple
import json
import re
from pydantic import ValidationError

from core.schemas import (
    CircuitDocument,
    CircuitPart,
    CircuitWire,
    PinReference,
    SimulationPlan,
)


class UnionFind:
    """Disjoint-set data structure with path compression and union by rank."""

    def __init__(self):
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, x: str, y: str) -> None:
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x == root_y:
            return
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1

    def get_groups(self) -> Dict[str, Set[str]]:
        groups: Dict[str, Set[str]] = {}
        for item in list(self.parent.keys()):
            root = self.find(item)
            groups.setdefault(root, set()).add(item)
        return groups


def get_breadboard_internal_net(bb_id: str, pin_id: str) -> Optional[str]:
    """Maps a breadboard hole ID to its internal connected tie-strip or power rail.

    Format examples:
      - 'row_10_a' or '10a' -> '{bb_id}:row_10_left' (cols a, b, c, d, e)
      - 'row_10_f' or '10f' -> '{bb_id}:row_10_right' (cols f, g, h, i, j)
      - 'top_pos_5' or 'top_+_5' or 'top_+' -> '{bb_id}:rail_top_pos'
      - 'top_neg_5' or 'top_-_5' or 'top_-' -> '{bb_id}:rail_top_neg'
      - 'bot_pos_5' or 'bot_+_5' or 'bot_+' -> '{bb_id}:rail_bot_pos'
      - 'bot_neg_5' or 'bot_-_5' or 'bot_-' -> '{bb_id}:rail_bot_neg'
    """
    pid = pin_id.strip().lower()

    # Power rail patterns
    if "top" in pid:
        if "+" in pid or "pos" in pid or "vcc" in pid:
            return f"{bb_id}:rail_top_pos"
        if "-" in pid or "neg" in pid or "gnd" in pid:
            return f"{bb_id}:rail_top_neg"
    if "bot" in pid or "bottom" in pid:
        if "+" in pid or "pos" in pid or "vcc" in pid:
            return f"{bb_id}:rail_bot_pos"
        if "-" in pid or "neg" in pid or "gnd" in pid:
            return f"{bb_id}:rail_bot_neg"

    # Terminal rows: e.g. 15c, row_15_c, r15c
    m = re.search(r"(\d+)\s*([a-jA-J])", pid)
    if m:
        row_num = int(m.group(1))
        col_letter = m.group(2).lower()
        if col_letter in ("a", "b", "c", "d", "e"):
            return f"{bb_id}:row_{row_num}_left"
        elif col_letter in ("f", "g", "h", "i", "j"):
            return f"{bb_id}:row_{row_num}_right"

    # Row only specified (default left)
    m_row = re.search(r"row_?(\d+)", pid)
    if m_row:
        return f"{bb_id}:row_{int(m_row.group(1))}_left"

    return f"{bb_id}:{pin_id}"


class CircuitGraph:
    """Evaluates electrical nets and connections across components, breadboards, and wires."""

    def __init__(self, doc: CircuitDocument):
        self.doc = doc
        self.uf = UnionFind()
        self._build_graph()

    def _pin_key(self, part_id: str, pin_id: str) -> str:
        return f"{part_id}:{pin_id}"

    def _build_graph(self) -> None:
        """Populates Union-Find with all internal and wire connections."""
        # 1. Register all component pins in Union-Find
        for part in self.doc.parts:
            # Check internal component connections
            if part.type.startswith("breadboard"):
                # Breadboard internal nets will be unified as connections are made
                pass

            elif part.type == "button":
                # Button has pairs pin1a-pin1b and pin2a-pin2b internally joined
                self.uf.union(self._pin_key(part.id, "pin1a"), self._pin_key(part.id, "pin1b"))
                self.uf.union(self._pin_key(part.id, "pin2a"), self._pin_key(part.id, "pin2b"))
                # If pressed, connect pin1 and pin2
                if part.properties.get("is_pressed", False):
                    self.uf.union(self._pin_key(part.id, "pin1a"), self._pin_key(part.id, "pin2a"))

            elif part.type == "potentiometer":
                # Wiper ratio 0.0 connects to pin1, 1.0 connects to pin2
                pass

        # 2. Add wire connections
        for wire in self.doc.wires:
            src_key = self._resolve_pin_endpoint(wire.source)
            tgt_key = self._resolve_pin_endpoint(wire.target)
            self.uf.union(src_key, tgt_key)

    def _resolve_pin_endpoint(self, ref: PinReference) -> str:
        """Resolves breadboard holes to their internal strip net or component pin key."""
        # Check if part is a breadboard
        part = next((p for p in self.doc.parts if p.id == ref.part_id), None)
        if part and part.type.startswith("breadboard"):
            return get_breadboard_internal_net(ref.part_id, ref.pin_id) or self._pin_key(ref.part_id, ref.pin_id)
        return self._pin_key(ref.part_id, ref.pin_id)

    def get_net_of_pin(self, part_id: str, pin_id: str) -> str:
        """Returns the canonical root net identifier for a given pin."""
        key = self._resolve_pin_endpoint(PinReference(part_id=part_id, pin_id=pin_id))
        return self.uf.find(key)

    def are_connected(self, ref1: PinReference, ref2: PinReference) -> bool:
        """Returns True if two pins share the exact same electrical net."""
        key1 = self._resolve_pin_endpoint(ref1)
        key2 = self._resolve_pin_endpoint(ref2)
        return self.uf.find(key1) == self.uf.find(key2)

    def find_all_nets(self) -> Dict[str, Set[str]]:
        """Returns all electrical net clusters."""
        return self.uf.get_groups()

    def get_mcu_part(self) -> Optional[CircuitPart]:
        """Finds the primary microcontroller part in the document."""
        for part in self.doc.parts:
            if part.type in ("arduino_uno", "esp32_devkit", "stm32_bluepill"):
                return part
        return None

    def find_connected_pins(self, ref: PinReference) -> List[PinReference]:
        """Finds all other component pins connected to the same net."""
        target_root = self.uf.find(self._resolve_pin_endpoint(ref))
        connected: List[PinReference] = []

        for part in self.doc.parts:
            # Enumerate common pins for part
            pins = self._get_pins_for_part(part)
            for p in pins:
                if part.id == ref.part_id and p == ref.pin_id:
                    continue
                pref = PinReference(part_id=part.id, pin_id=p)
                if self.uf.find(self._resolve_pin_endpoint(pref)) == target_root:
                    connected.append(pref)

        return connected

    def _get_pins_for_part(self, part: CircuitPart) -> List[str]:
        if part.type == "led":
            return ["anode", "cathode"]
        if part.type == "resistor":
            return ["pin1", "pin2"]
        if part.type == "button":
            return ["pin1a", "pin1b", "pin2a", "pin2b"]
        if part.type == "potentiometer":
            return ["pin1", "wiper", "pin2"]
        if part.type == "buzzer":
            return ["positive", "negative"]
        if part.type == "servo":
            return ["gnd", "vcc", "signal"]
        if part.type == "dht11":
            return ["vcc", "data", "gnd"]
        if part.type == "hcsr04":
            return ["vcc", "trig", "echo", "gnd"]
        if part.type == "arduino_uno":
            return [
                "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13",
                "A0", "A1", "A2", "A3", "A4", "A5", "5V", "3.3V", "GND", "VIN", "RESET"
            ]
        if part.type == "esp32_devkit":
            return [
                "G23", "G22", "TX0", "RX0", "G21", "G19", "G18", "G5", "G17", "G16",
                "G4", "G0", "G2", "G15", "G13", "G12", "G14", "G27", "G26", "G25",
                "G33", "G32", "G35", "G34", "VN", "VP", "3V3", "GND", "VIN"
            ]
        if part.type == "stm32_bluepill":
            return [
                "PA0", "PA1", "PA2", "PA3", "PA4", "PA5", "PA6", "PA7", "PA8", "PA9",
                "PA10", "PA11", "PA12", "PA15", "PB0", "PB1", "PB3", "PB4", "PB5",
                "PB6", "PB7", "PB8", "PB9", "PB10", "PB11", "PB12", "PB13", "PB14",
                "PB15", "PC13", "PC14", "PC15", "3.3V", "GND", "VBAT", "NRST"
            ]
        return []


def build_suggested_circuit(board_id: str, plan: SimulationPlan) -> CircuitDocument:
    """Generates an editable, suggested circuit layout matching parsed firmware requirements."""
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
            properties={"label": "Half Breadboard"},
        ),
    ]

    wires: List[CircuitWire] = []
    wire_counter = 1

    # Detect output pins (e.g. LED)
    output_pins = [p for p in plan.pins if p.mode == "OUTPUT"]
    input_pins = [p for p in plan.pins if "INPUT" in p.mode]

    # If no pins explicitly configured but events exist, check event pins
    if not output_pins and not input_pins:
        ev_pins = {e.pin for e in plan.events if e.action in ("digitalWrite", "analogWrite")}
        for ep in ev_pins:
            output_pins.append(type("Pin", (), {"pin": ep, "mode": "OUTPUT", "component_hint": "LED"})())

    # Default to Pin 13 if completely empty
    if not output_pins and not input_pins:
        output_pins.append(type("Pin", (), {"pin": "13", "mode": "OUTPUT", "component_hint": "LED"})())

    # Build LED + Resistor subcircuits for output pins
    bb_row = 10
    for idx, out_p in enumerate(output_pins[:3]):  # limit auto-placement to 3 outputs
        led_id = f"led{idx+1}"
        res_id = f"r{idx+1}"
        color = "red" if idx == 0 else ("green" if idx == 1 else "yellow")

        # Place LED on breadboard
        parts.append(
            CircuitPart(
                id=led_id,
                type="led",
                x=560.0 + (idx * 30),
                y=180.0,
                rotation=0,
                properties={"color": color, "label": f"{color.capitalize()} LED"},
            )
        )
        # Place 220 Ohm resistor
        parts.append(
            CircuitPart(
                id=res_id,
                type="resistor",
                x=560.0 + (idx * 30),
                y=260.0,
                rotation=90,
                properties={"resistance": 220, "unit": "Ω", "label": "220Ω Resistor"},
            )
        )

        # Connect MCU Output Pin -> Breadboard row (bb_row a)
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id="mcu1", pin_id=str(out_p.pin)),
                target=PinReference(part_id="bb1", pin_id=f"{bb_row}a"),
                color="#22c55e",  # Signal green
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

        # Connect LED Anode -> Breadboard row (bb_row e)
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id=led_id, pin_id="anode"),
                target=PinReference(part_id="bb1", pin_id=f"{bb_row}e"),
                color="#22c55e",
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

        # Connect LED Cathode -> Breadboard row (bb_row+1 e)
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id=led_id, pin_id="cathode"),
                target=PinReference(part_id="bb1", pin_id=f"{bb_row+1}e"),
                color="#3b82f6",  # Blue
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

        # Connect Resistor pin1 -> Breadboard row (bb_row+1 a)
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id=res_id, pin_id="pin1"),
                target=PinReference(part_id="bb1", pin_id=f"{bb_row+1}a"),
                color="#3b82f6",
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

        # Connect Resistor pin2 -> Breadboard bottom negative rail (GND)
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id=res_id, pin_id="pin2"),
                target=PinReference(part_id="bb1", pin_id="bot_neg"),
                color="#111827",  # Black GND
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

        bb_row += 5

    # Connect MCU GND to Breadboard bottom negative rail
    mcu_gnd_pin = "GND"
    wires.append(
        CircuitWire(
            id=f"w{wire_counter}",
            source=PinReference(part_id="mcu1", pin_id=mcu_gnd_pin),
            target=PinReference(part_id="bb1", pin_id="bot_neg"),
            color="#111827",  # Ground black
            style="solid",
            confidence="confirmed",
        )
    )
    wire_counter += 1

    # Connect input pins (e.g. Push Button)
    for idx, in_p in enumerate(input_pins[:2]):
        btn_id = f"btn{idx+1}"
        parts.append(
            CircuitPart(
                id=btn_id,
                type="button",
                x=680.0,
                y=180.0 + (idx * 80),
                rotation=0,
                properties={"label": "Push Button", "is_pressed": False},
            )
        )

        # Wire MCU input pin to button pin1a
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id="mcu1", pin_id=str(in_p.pin)),
                target=PinReference(part_id=btn_id, pin_id="pin1a"),
                color="#eab308",  # Control yellow
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

        # Wire button pin2a to GND rail
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id=btn_id, pin_id="pin2a"),
                target=PinReference(part_id="bb1", pin_id="bot_neg"),
                color="#111827",  # GND
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

    # Connect analog pins (e.g. Potentiometer for ADC / analogRead)
    analog_pins = [p for p in plan.pins if p.mode == "ANALOG" or str(p.pin).upper().startswith("A")]
    if not analog_pins:
        ev_an_pins = {e.pin for e in plan.events if e.action == "analogRead"}
        for ap in ev_an_pins:
            analog_pins.append(type("Pin", (), {"pin": ap, "mode": "ANALOG", "component_hint": "Potentiometer"})())

    for idx, an_p in enumerate(analog_pins[:1]):
        pot_id = f"pot{idx+1}"
        parts.append(
            CircuitPart(
                id=pot_id,
                type="potentiometer",
                x=720.0,
                y=260.0 + (idx * 80),
                rotation=0,
                properties={"ratio": 0.5, "label": "10kΩ Potentiometer"},
            )
        )
        vcc_name = "3V3" if "esp32" in board_id else ("3.3V" if "stm32" in board_id else "5V")
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id="mcu1", pin_id=vcc_name),
                target=PinReference(part_id=pot_id, pin_id="pin1"),
                color="#ef4444",  # VCC Red
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id="mcu1", pin_id=str(an_p.pin)),
                target=PinReference(part_id=pot_id, pin_id="wiper"),
                color="#3b82f6",  # Signal Blue
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1
        wires.append(
            CircuitWire(
                id=f"w{wire_counter}",
                source=PinReference(part_id=pot_id, pin_id="pin2"),
                target=PinReference(part_id="bb1", pin_id="bot_neg"),
                color="#111827",  # GND Black
                style="solid",
                confidence="confirmed",
            )
        )
        wire_counter += 1

    return CircuitDocument(
        board=board_id,
        parts=parts,
        wires=wires,
        suggested=True,
        notes=[
            "Suggested circuit generated from firmware I/O pins.",
            "LED is connected via a 220Ω current-limiting resistor to Ground.",
            "You can add, delete, or reroute wires directly in the canvas.",
        ],
    )


def export_circuit_json(doc: CircuitDocument) -> str:
    """Serializes a CircuitDocument into formatted JSON."""
    return doc.model_dump_json(indent=2)


def import_circuit_json(json_str: str) -> CircuitDocument:
    """Parses and validates a CircuitDocument from JSON string."""
    data = json.loads(json_str)
    return CircuitDocument.model_validate(data)


def reset_circuit(board_id: str) -> CircuitDocument:
    """Generates a blank workspace with just the MCU and a breadboard."""
    mcu_type = "arduino_uno"
    if "esp32" in board_id:
        mcu_type = "esp32_devkit"
    elif "stm32" in board_id:
        mcu_type = "stm32_bluepill"

    return CircuitDocument(
        board=board_id,
        parts=[
            CircuitPart(id="mcu1", type=mcu_type, x=80.0, y=120.0, rotation=0, properties={"board_id": board_id}),
            CircuitPart(id="bb1", type="breadboard_half", x=450.0, y=100.0, rotation=0, properties={}),
        ],
        wires=[],
        suggested=False,
        notes=["Workspace reset. Place components from the library and connect wires."],
    )

