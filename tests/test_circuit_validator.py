"""Tests for deterministic circuit validator and electrical safety checks."""

from core.circuit_validator import CircuitValidator
from core.schemas import CircuitDocument, CircuitPart, CircuitWire, PinReference


def test_short_circuit_detection():
    # Direct wire between 5V and GND on Arduino Uno
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[CircuitPart(id="mcu1", type="arduino_uno")],
        wires=[
            CircuitWire(
                id="w1",
                source=PinReference(part_id="mcu1", pin_id="5V"),
                target=PinReference(part_id="mcu1", pin_id="GND"),
            )
        ],
    )

    validator = CircuitValidator(board_id="arduino_uno")
    report = validator.validate(doc)

    assert report.is_valid is False
    assert len(report.short_circuits) >= 1
    assert any("Short Circuit" in i.title for i in report.issues)


def test_disconnected_parts_detection():
    # LED placed with no wires connected
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno"),
            CircuitPart(id="led1", type="led"),
        ],
        wires=[],
    )

    validator = CircuitValidator(board_id="arduino_uno")
    report = validator.validate(doc)

    assert "led1" in report.disconnected_parts
    assert any("Disconnected" in i.title for i in report.issues)


def test_led_missing_current_limiting_resistor():
    # LED connected directly across 5V and GND without resistor
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno"),
            CircuitPart(id="led1", type="led"),
        ],
        wires=[
            CircuitWire(id="w1", source=PinReference(part_id="mcu1", pin_id="13"), target=PinReference(part_id="led1", pin_id="anode")),
            CircuitWire(id="w2", source=PinReference(part_id="led1", pin_id="cathode"), target=PinReference(part_id="mcu1", pin_id="GND")),
        ],
    )

    validator = CircuitValidator(board_id="arduino_uno")
    report = validator.validate(doc)

    # Should flag high current hazard / missing resistor
    assert any("resistor" in i.description.lower() or "current" in i.description.lower() for i in report.issues)

