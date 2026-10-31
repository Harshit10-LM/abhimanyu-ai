"""Tests for circuit graph, breadboard tie strips, and netlist resolution."""

from core.circuit_graph import (
    CircuitGraph,
    build_suggested_circuit,
    export_circuit_json,
    get_breadboard_internal_net,
    import_circuit_json,
    reset_circuit,
)
from core.schemas import CircuitDocument, CircuitPart, CircuitWire, PinReference, SimulationPlan, PinState


def test_breadboard_tie_strip_internal_nets():
    # Holes in the same 5-hole strip must share internal net
    net_10a = get_breadboard_internal_net("bb1", "10a")
    net_10e = get_breadboard_internal_net("bb1", "10e")
    net_10f = get_breadboard_internal_net("bb1", "10f")
    net_11a = get_breadboard_internal_net("bb1", "11a")

    assert net_10a == "bb1:row_10_left"
    assert net_10e == "bb1:row_10_left"
    assert net_10a == net_10e, "Holes 10a and 10e must share the same tie strip"

    assert net_10f == "bb1:row_10_right", "Center channel must separate left and right strips"
    assert net_10a != net_10f, "Left and right terminal strips must be electrically isolated"

    assert net_10a != net_11a, "Different rows must be electrically isolated"


def test_breadboard_power_rails():
    net_top_pos = get_breadboard_internal_net("bb1", "top_+")
    net_top_pos_5 = get_breadboard_internal_net("bb1", "top_pos_5")
    net_top_neg = get_breadboard_internal_net("bb1", "top_-")

    assert net_top_pos == "bb1:rail_top_pos"
    assert net_top_pos_5 == "bb1:rail_top_pos"
    assert net_top_pos == net_top_pos_5
    assert net_top_pos != net_top_neg, "Positive and negative rails must be isolated"


def test_circuit_graph_connectivity():
    doc = CircuitDocument(
        board="arduino_uno",
        parts=[
            CircuitPart(id="mcu1", type="arduino_uno", x=0, y=0),
            CircuitPart(id="bb1", type="breadboard_half", x=300, y=0),
            CircuitPart(id="led1", type="led", x=400, y=100),
        ],
        wires=[
            # Wire MCU pin 13 to breadboard hole 10a
            CircuitWire(
                id="w1",
                source=PinReference(part_id="mcu1", pin_id="13"),
                target=PinReference(part_id="bb1", pin_id="10a"),
            ),
            # Wire LED anode to breadboard hole 10e (same row!)
            CircuitWire(
                id="w2",
                source=PinReference(part_id="led1", pin_id="anode"),
                target=PinReference(part_id="bb1", pin_id="10e"),
            ),
        ],
    )

    graph = CircuitGraph(doc)

    # Pin 13 and LED anode should be connected through breadboard row 10
    assert graph.are_connected(
        PinReference(part_id="mcu1", pin_id="13"),
        PinReference(part_id="led1", pin_id="anode"),
    )

    # LED cathode is unconnected and should not be connected to Pin 13
    assert not graph.are_connected(
        PinReference(part_id="mcu1", pin_id="13"),
        PinReference(part_id="led1", pin_id="cathode"),
    )


def test_build_suggested_circuit():
    plan = SimulationPlan(
        pins=[
            PinState(pin="13", mode="OUTPUT", component_hint="LED"),
            PinState(pin="2", mode="INPUT_PULLUP", component_hint="BUTTON"),
        ]
    )

    doc = build_suggested_circuit("arduino_uno", plan)

    assert doc.board == "arduino_uno"
    assert doc.suggested is True
    part_types = [p.type for p in doc.parts]
    assert "arduino_uno" in part_types
    assert "breadboard_half" in part_types
    assert "led" in part_types
    assert "resistor" in part_types
    assert "button" in part_types
    assert len(doc.wires) >= 5


def test_circuit_serialization():
    doc = reset_circuit("arduino_uno")
    json_str = export_circuit_json(doc)
    restored = import_circuit_json(json_str)

    assert restored.board == doc.board
    assert len(restored.parts) == len(doc.parts)

