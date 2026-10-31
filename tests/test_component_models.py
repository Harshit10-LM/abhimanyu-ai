"""Tests for component physics: forward-bias LED, resistor current limit, open circuits."""

from core.circuit_graph import CircuitGraph, build_suggested_circuit
from core.component_models import ComponentSimulator
from core.schemas import CircuitDocument, CircuitPart, CircuitWire, PinReference, PinSnapshot, PinState, SimulationPlan


def test_led_illuminates_when_circuit_closed_and_forward_biased():
    # Construct complete circuit: Uno Pin 13 -> Resistor -> LED Anode -> LED Cathode -> GND
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno"),
            CircuitPart(id="r1", type="resistor", properties={"resistance": 220, "unit": "Ω"}),
            CircuitPart(id="led1", type="led", properties={"color": "red", "forward_voltage": 2.0}),
        ],
        wires=[
            CircuitWire(id="w1", source=PinReference(part_id="mcu1", pin_id="13"), target=PinReference(part_id="r1", pin_id="pin1")),
            CircuitWire(id="w2", source=PinReference(part_id="r1", pin_id="pin2"), target=PinReference(part_id="led1", pin_id="anode")),
            CircuitWire(id="w3", source=PinReference(part_id="led1", pin_id="cathode"), target=PinReference(part_id="mcu1", pin_id="GND")),
        ],
    )

    graph = CircuitGraph(doc)
    sim = ComponentSimulator(board_id="arduino_uno")

    # When Pin 13 is HIGH (5V)
    high_pins = {"13": PinSnapshot(pin="13", mode="OUTPUT", digital_state="HIGH", pwm_duty=255)}
    res_high = sim.evaluate_circuit(graph, high_pins)
    led_state = res_high["led1"]

    assert led_state.state == "ON"
    assert led_state.is_powered is True
    assert led_state.brightness > 200
    assert led_state.current_ma > 5.0, "Current should flow through closed circuit"

    # When Pin 13 is LOW (0V)
    low_pins = {"13": PinSnapshot(pin="13", mode="OUTPUT", digital_state="LOW", pwm_duty=0)}
    res_low = sim.evaluate_circuit(graph, low_pins)
    assert res_low["led1"].state == "OFF"
    assert res_low["led1"].is_powered is False
    assert res_low["led1"].brightness == 0


def test_disconnected_led_does_not_illuminate_even_if_pin_high():
    # LED anode connected to pin 13, but cathode is disconnected (floating/open circuit)
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno"),
            CircuitPart(id="led1", type="led"),
        ],
        wires=[
            CircuitWire(id="w1", source=PinReference(part_id="mcu1", pin_id="13"), target=PinReference(part_id="led1", pin_id="anode")),
        ],
    )

    graph = CircuitGraph(doc)
    sim = ComponentSimulator(board_id="arduino_uno")

    # Pin 13 is HIGH
    high_pins = {"13": PinSnapshot(pin="13", mode="OUTPUT", digital_state="HIGH", pwm_duty=255)}
    res = sim.evaluate_circuit(graph, high_pins)

    # Acceptance Test D requirement: Disconnected LED must NOT illuminate!
    assert res["led1"].state == "OFF"
    assert res["led1"].is_powered is False
    assert res["led1"].brightness == 0
    assert "floating or disconnected" in res["led1"].warnings[0]


def test_reverse_biased_led_does_not_illuminate():
    # LED reversed: Cathode connected to Pin 13 (HIGH), Anode connected to GND
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno"),
            CircuitPart(id="led1", type="led"),
        ],
        wires=[
            CircuitWire(id="w1", source=PinReference(part_id="mcu1", pin_id="13"), target=PinReference(part_id="led1", pin_id="cathode")),
            CircuitWire(id="w2", source=PinReference(part_id="led1", pin_id="anode"), target=PinReference(part_id="mcu1", pin_id="GND")),
        ],
    )

    graph = CircuitGraph(doc)
    sim = ComponentSimulator(board_id="arduino_uno")

    high_pins = {"13": PinSnapshot(pin="13", mode="OUTPUT", digital_state="HIGH", pwm_duty=255)}
    res = sim.evaluate_circuit(graph, high_pins)

    assert res["led1"].state == "OFF"
    assert res["led1"].is_powered is False
    assert any("reverse-biased" in w for w in res["led1"].warnings)


def test_potentiometer_voltage_divider():
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno"),
            CircuitPart(id="pot1", type="potentiometer", properties={"ratio": 0.75}),
        ],
        wires=[
            CircuitWire(id="w1", source=PinReference(part_id="mcu1", pin_id="5V"), target=PinReference(part_id="pot1", pin_id="pin2")),
            CircuitWire(id="w2", source=PinReference(part_id="mcu1", pin_id="GND"), target=PinReference(part_id="pot1", pin_id="pin1")),
            CircuitWire(id="w3", source=PinReference(part_id="pot1", pin_id="wiper"), target=PinReference(part_id="mcu1", pin_id="A0")),
        ],
    )

    graph = CircuitGraph(doc)
    sim = ComponentSimulator(board_id="arduino_uno")
    res = sim.evaluate_circuit(graph, {})

    pot_res = res["pot1"]
    assert pot_res.state == "ACTIVE"
    # 0.75 of 5V = 3.75V, ADC = 0.75 * 1023 = 767
    assert 760 <= pot_res.analog_reading <= 770

