"""Deterministic pin conflict analyzer and structured wiring table generator.

Inspired by Arduino-Copilot. Detects bus collisions (Serial on Pins 0/1, I2C, SPI),
duplicate pin roles, and produces a structured MCU-to-Component wiring table.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Set, Tuple
from core.board_database import BoardSpec, get_board
from core.schemas import CircuitDocument, PinState, SimulationPlan


@dataclass
class PinUsage:
    """Represents a pin assignment, mode, and line number."""

    pin: str
    role: str
    line: int
    raw_token: str


@dataclass
class PinConflict:
    """Represents an identified pin conflict or hardware hazard."""

    pin: str
    severity: str  # "error", "warning"
    title: str
    description: str
    recommendation: str


@dataclass
class WiringEntry:
    """Row in the structured Pin-to-Component wiring table."""

    mcu_pin: str
    component_name: str
    component_pin: str
    purpose: str
    is_inferred: bool = False


class PinConflictAnalyzer:
    """Analyzes firmware pin assignments, detects bus collisions, and generates wiring tables."""

    def __init__(self, board: Optional[BoardSpec] = None):
        self.board = board or get_board("arduino_uno")

    def analyze(self, source_code: str) -> Tuple[List[PinConflict], List[WiringEntry], List[str]]:
        """Scans code for pin conflicts and builds a structured wiring table."""
        lines = source_code.splitlines()
        constants = self._extract_constants(lines)
        usages, buses = self._extract_pin_usages(lines, constants)
        conflicts = self._detect_conflicts(usages, buses)
        wiring_table = self._build_wiring_table(usages, buses)

        return conflicts, wiring_table, sorted(list(buses))

    def _extract_constants(self, lines: List[str]) -> Dict[str, str]:
        constants: Dict[str, str] = {
            "LED_BUILTIN": "13" if self.board.id == "arduino_uno" else ("2" if self.board.id == "esp32_devkit" else "PC13")
        }
        def_re = re.compile(r"^\s*#define\s+([A-Za-z_]\w*)\s+(\w+)")
        const_re = re.compile(r"^\s*(?:const|constexpr)\s+(?:int|uint8_t|byte)\s+([A-Za-z_]\w*)\s*=\s*(\w+)\s*;")

        for line in lines:
            # Strip comments
            clean = re.sub(r"//.*", "", line)
            m_def = def_re.search(clean)
            if m_def:
                constants[m_def.group(1)] = m_def.group(2)
                continue
            m_c = const_re.search(clean)
            if m_c:
                constants[m_c.group(1)] = m_c.group(2)

        return constants

    def _resolve_pin(self, token: str, constants: Dict[str, str]) -> str:
        tok = token.strip()
        return constants.get(tok, tok)

    def _extract_pin_usages(
        self, lines: List[str], constants: Dict[str, str]
    ) -> Tuple[List[PinUsage], Set[str]]:
        usages: List[PinUsage] = []
        buses: Set[str] = set()

        pm_re = re.compile(r"\bpinMode\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]+)\s*\)")
        dw_re = re.compile(r"\bdigitalWrite\s*\(\s*([A-Za-z_]\w*)")
        dr_re = re.compile(r"\bdigitalRead\s*\(\s*([A-Za-z_]\w*)")
        aw_re = re.compile(r"\banalogWrite\s*\(\s*([A-Za-z_]\w*)")
        ar_re = re.compile(r"\banalogRead\s*\(\s*([A-Za-z_]\w*)")

        for idx, line in enumerate(lines, start=1):
            clean = re.sub(r"//.*", "", line)

            # Check buses
            if "Serial.begin" in clean:
                buses.add("Hardware Serial (USB)")
            if "Wire.begin" in clean:
                buses.add("I2C Bus (Wire)")
            if "SPI.begin" in clean:
                buses.add("SPI Bus")

            m_pm = pm_re.search(clean)
            if m_pm:
                pin = self._resolve_pin(m_pm.group(1), constants)
                usages.append(PinUsage(pin=pin, role=f"pinMode {m_pm.group(2)}", line=idx, raw_token=m_pm.group(1)))

            m_dw = dw_re.search(clean)
            if m_dw:
                pin = self._resolve_pin(m_dw.group(1), constants)
                usages.append(PinUsage(pin=pin, role="digitalWrite", line=idx, raw_token=m_dw.group(1)))

            m_dr = dr_re.search(clean)
            if m_dr:
                pin = self._resolve_pin(m_dr.group(1), constants)
                usages.append(PinUsage(pin=pin, role="digitalRead", line=idx, raw_token=m_dr.group(1)))

            m_aw = aw_re.search(clean)
            if m_aw:
                pin = self._resolve_pin(m_aw.group(1), constants)
                usages.append(PinUsage(pin=pin, role="analogWrite (PWM)", line=idx, raw_token=m_aw.group(1)))

            m_ar = ar_re.search(clean)
            if m_ar:
                pin = self._resolve_pin(m_ar.group(1), constants)
                usages.append(PinUsage(pin=pin, role="analogRead (ADC)", line=idx, raw_token=m_ar.group(1)))

        return usages, buses

    def _detect_conflicts(self, usages: List[PinUsage], buses: Set[str]) -> List[PinConflict]:
        conflicts: List[PinConflict] = []
        pins_used = {u.pin for u in usages}

        # 1. Classic Arduino Serial upload blocker: Pin 0/1 with Serial.begin
        if "Hardware Serial (USB)" in buses and self.board.id == "arduino_uno":
            for p in ("0", "1"):
                if p in pins_used:
                    conflicts.append(
                        PinConflict(
                            pin=p,
                            severity="error",
                            title=f"Hardware Serial Conflict on Pin {p}",
                            description=(
                                f"Pin {p} is used for general GPIO while Serial.begin() is active. "
                                "Pins 0 (RX) and 1 (TX) share the hardware USB transceiver; connecting external components "
                                "corrupts serial monitor output and prevents firmware sketch uploads via bootloader."
                            ),
                            recommendation=f"Move the connection from Pin {p} to any free digital pin (e.g., Pin 4-8).",
                        )
                    )

        # 2. I2C Bus conflict on Arduino Uno (A4 = SDA, A5 = SCL)
        if "I2C Bus (Wire)" in buses and self.board.id == "arduino_uno":
            for p, bus_role in (("A4", "SDA"), ("A5", "SCL"), ("18", "SDA"), ("19", "SCL")):
                if p in pins_used:
                    matching = [u for u in usages if u.pin == p and "analogRead" in u.role]
                    if matching:
                        conflicts.append(
                            PinConflict(
                                pin=p,
                                severity="warning",
                                title=f"I2C Bus Collision on Pin {p} ({bus_role})",
                                description=f"Pin {p} is used with analogRead() while I2C (Wire) is enabled. A4/A5 are shared with I2C.",
                                recommendation="Reserve A4/A5 for I2C devices and use A0-A3 for analog sensors.",
                            )
                        )

        # 3. Conflicting roles on same pin (e.g. configured as OUTPUT and later analogRead)
        pins_by_role: Dict[str, Set[str]] = {}
        for u in usages:
            pins_by_role.setdefault(u.pin, set()).add(u.role)

        for pin, roles in pins_by_role.items():
            if any("OUTPUT" in r for r in roles) and any("INPUT" in r for r in roles):
                conflicts.append(
                    PinConflict(
                        pin=pin,
                        severity="error",
                        title=f"Contradictory Pin Modes on Pin {pin}",
                        description=f"Pin {pin} is configured as both OUTPUT and INPUT in the sketch.",
                        recommendation="Verify pin assignments to ensure distinct input and output lines.",
                    )
                )

        return conflicts

    def _build_wiring_table(self, usages: List[PinUsage], buses: Set[str]) -> List[WiringEntry]:
        table: List[WiringEntry] = []
        seen_pins: Set[str] = set()

        # Deduplicate pin usages and map to component hints
        for u in usages:
            if u.pin in seen_pins:
                continue
            seen_pins.add(u.pin)

            tok_lower = u.raw_token.lower()
            comp_name = "Generic Component"
            comp_pin = "Signal"
            purpose = u.role

            if any(k in tok_lower for k in ("led", "light", "lamp")):
                comp_name = "LED (5mm)"
                comp_pin = "Anode (+)"
                purpose = "Digital Output / Pulse Indicator"
            elif any(k in tok_lower for k in ("btn", "button", "switch")):
                comp_name = "Push Button"
                comp_pin = "Terminal 1a"
                purpose = "Digital Input"
            elif any(k in tok_lower for k in ("pot", "sensor", "adc", "ldr")):
                comp_name = "Analog Sensor / Potentiometer"
                comp_pin = "Analog Wiper / Out"
                purpose = "Analog Voltage Reading"
            elif any(k in tok_lower for k in ("servo", "motor")):
                comp_name = "Micro Servo (SG90)"
                comp_pin = "Signal (Orange/Yellow)"
                purpose = "PWM Control Signal"
            elif any(k in tok_lower for k in ("buzz", "sound", "piezo")):
                comp_name = "Piezo Buzzer"
                comp_pin = "Positive Lead (+)"
                purpose = "Tone / Alarm Output"
            elif any(k in tok_lower for k in ("relay",)):
                comp_name = "Relay Module"
                comp_pin = "IN (Control)"
                purpose = "High Voltage Switching"

            table.append(
                WiringEntry(
                    mcu_pin=f"Pin {u.pin}",
                    component_name=comp_name,
                    component_pin=comp_pin,
                    purpose=purpose,
                    is_inferred=True,
                )
            )

        # Append Ground and Power rail entries
        vcc_label = "3.3V" if "esp32" in self.board.id or "stm32" in self.board.id else "5V"
        table.append(
            WiringEntry(
                mcu_pin="GND",
                component_name="Common Ground Bus",
                component_pin="Cathode / Ground Return",
                purpose="Electrical Return Path",
                is_inferred=False,
            )
        )
        table.append(
            WiringEntry(
                mcu_pin=vcc_label,
                component_name="Power Rail (+)",
                component_pin="VCC / Power In",
                purpose="DC Supply Voltage",
                is_inferred=False,
            )
        )

        return table

