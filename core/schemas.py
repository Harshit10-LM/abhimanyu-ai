"""Pydantic v2 schemas for Firmware-Alchemist structured data validation."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CodeIssue(BaseModel):
    """Represents a single static or AI-identified code issue."""

    model_config = ConfigDict(extra="forbid")

    line: int = Field(description="1-based line number in source code")
    severity: Literal["high", "medium", "low"] = Field(
        description="Severity level: high, medium, or low"
    )
    category: Literal[
        "syntax",
        "logic",
        "hardware",
        "memory",
        "timing",
        "security",
    ] = Field(description="Issue category")
    issue: str = Field(description="Clear title/summary of the issue")
    evidence: str = Field(description="Exact snippet of offending code")
    impact: str = Field(description="Consequence of this issue on hardware/execution")
    fix: str = Field(description="Recommended fix or replacement code")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level of detection"
    )
    source: Literal["deterministic", "ai"] = Field(
        default="ai", description="Origin of finding (deterministic rule or AI audit)"
    )


class AuditResponse(BaseModel):
    """Top-level firmware audit result."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Executive summary of the firmware audit")
    issues: list[CodeIssue] = Field(
        default_factory=list, description="List of detected code issues"
    )


class PinState(BaseModel):
    """Configured pin declaration extracted from firmware."""

    pin: str = Field(description="Pin identifier (e.g. '13', 'A0', 'GPIO2')")
    mode: str = Field(description="Configured mode: OUTPUT, INPUT, INPUT_PULLUP, etc.")
    component_hint: str | None = Field(
        default=None, description="Inferred hardware component (e.g. 'LED', 'BUTTON', 'SENSOR')"
    )


class TimedEvent(BaseModel):
    """Deterministic timeline event occurring at a given simulated millisecond."""

    t_ms: int = Field(description="Timestamp in milliseconds from simulation start")
    action: str = Field(description="Action name (digitalWrite, delay, analogWrite, etc.)")
    pin: str = Field(description="Target pin identifier")
    value: str | int | None = Field(
        default=None, description="State value: HIGH, LOW, PWM duty cycle, or analog reading"
    )


class SimulationPlan(BaseModel):
    """Deterministic simulation blueprint produced by the code parser."""

    pins: list[PinState] = Field(default_factory=list)
    events: list[TimedEvent] = Field(default_factory=list)
    loop_detected: bool = Field(default=False)
    loop_period_ms: int | None = Field(default=None)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PinSnapshot(BaseModel):
    """Hardware state of a single pin at a specific frame timestamp."""

    pin: str
    mode: str
    digital_state: Literal["HIGH", "LOW", "UNKNOWN"] = "UNKNOWN"
    analog_value: int | None = None
    pwm_duty: int | None = None
    component_hint: str | None = None


class SimulationFrame(BaseModel):
    """Full hardware snapshot at a discrete simulation time slice."""

    model_config = ConfigDict(extra="ignore")

    t_ms: int
    pin_states: dict[str, PinSnapshot]
    active_event_description: str | None = None
    component_states: dict[str, dict] = Field(default_factory=dict)



# Vision Debugger Schemas (Phase 2)


class ComponentLeg(BaseModel):
    """Terminal/pin connection observation for a visible electronic component."""

    leg_label: str = Field(description="Leg identifier, e.g. Anode, Cathode, Pin 1, VCC")
    connects_to: str = Field(
        description="Observed tie point or breadboard coordinate/rail"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence of tracing"
    )
    observation: str = Field(description="Visual observation details")


class VisibleComponent(BaseModel):
    """Individual hardware component identified in the photograph."""

    name: str = Field(description="Component name (e.g. Arduino Uno, ESP32, Red 5mm LED, 220Ω Resistor)")
    type: str = Field(default="generic", description="Component category/type: mcu, breadboard, led, resistor, button, sensor, wire")
    color: str | None = Field(default=None, description="Visible component or wire color")
    location: str = Field(description="Breadboard area or spatial location")
    visibility: Literal["clear", "partial", "obscured"] = Field(
        description="Visual clarity"
    )
    bbox: list[float] | None = Field(
        default=None,
        description="Normalized bounding box [ymin, xmin, ymax, xmax] with values in 0.0 to 1.0"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="high", description="Identification confidence"
    )
    legs: list[ComponentLeg] = Field(default_factory=list)


# Circuit Editor & Electrical Graph Schemas


class PinReference(BaseModel):
    """Reference to a specific pin on a circuit part or breadboard."""

    model_config = ConfigDict(extra="ignore")

    part_id: str = Field(description="ID of the circuit component or breadboard")
    pin_id: str = Field(description="Identifier of the specific pin/terminal on that component")


class CircuitPart(BaseModel):
    """An electronic part, board, or module placed in the circuit canvas."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique part identifier (e.g. 'mcu1', 'bb1', 'led1', 'r1')")
    type: str = Field(description="Part type: 'arduino_uno', 'esp32_devkit', 'stm32_bluepill', 'breadboard_half', 'breadboard_full', 'led', 'resistor', 'button', 'potentiometer', 'buzzer', 'servo', 'dht11', 'hcsr04', 'ldr'")
    x: float = Field(default=0.0, description="Canvas X coordinate")
    y: float = Field(default=0.0, description="Canvas Y coordinate")
    rotation: int = Field(default=0, description="Rotation in degrees (0, 90, 180, 270)")
    properties: dict = Field(default_factory=dict, description="Component parameters: color, resistance, state, etc.")


class CircuitWire(BaseModel):
    """Physical pin-to-pin or pin-to-breadboard jumper connection."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique wire identifier (e.g. 'w1', 'w2')")
    source: PinReference = Field(description="Starting pin reference")
    target: PinReference = Field(description="Ending pin reference")
    color: str = Field(default="#22c55e", description="Hex or named wire color (red, black, green, yellow, blue)")
    route: list[list[float]] = Field(default_factory=list, description="Waypoints for wire routing")
    style: Literal["solid", "dashed"] = Field(default="solid", description="Solid for confirmed, dashed for AI-proposed")
    confidence: Literal["confirmed", "uncertain", "unknown"] = Field(default="confirmed", description="Visual/electrical verification confidence")


class CircuitDocument(BaseModel):
    """Single source of truth document for the electronic circuit."""

    model_config = ConfigDict(extra="ignore")

    board: str = Field(default="arduino_uno", description="Microcontroller board identifier")
    parts: list[CircuitPart] = Field(default_factory=list, description="All components placed on the canvas")
    wires: list[CircuitWire] = Field(default_factory=list, description="All electrical connections between pins")
    suggested: bool = Field(default=False, description="True if automatically generated from firmware analysis")
    notes: list[str] = Field(default_factory=list, description="Circuit notes or guidelines")



class InventoryResult(BaseModel):
    """Phase 2 Call 1: Structured visual component inventory."""

    model_config = ConfigDict(extra="forbid")

    components: list[VisibleComponent] = Field(
        default_factory=list, description="List of recognized hardware components"
    )
    photo_quality_notes: str = Field(
        description="Assessment of lighting, focus, resolution, and angle"
    )
    uncertain_connections: list[str] = Field(
        default_factory=list,
        description="Connections that cannot be definitively verified visually",
    )


class DiagnosisFinding(BaseModel):
    """Specific circuit issue, evidence, and safe multimeter verification."""

    finding: str = Field(description="Clear title of the suspected issue")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Diagnosis confidence"
    )
    visual_evidence: str = Field(
        description="Specific visual cues or inventory items supporting this finding"
    )
    reasoning: str = Field(
        description="Electrical reasoning why this causes the reported symptom"
    )
    multimeter_verification: str = Field(
        description="Practical, safe step-by-step unpowered/low-voltage meter check"
    )
    fix: str = Field(description="Exact recommended wiring or component correction")


class DiagnosisResult(BaseModel):
    """Phase 2 Call 2: Complete circuit diagnostic report."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Executive diagnosis summary")
    findings: list[DiagnosisFinding] = Field(
        default_factory=list, description="Detailed hardware findings"
    )
    safety_warnings: list[str] = Field(
        default_factory=list, description="Mandatory electrical safety precautions"
    )
    next_steps_if_all_checks_pass: str = Field(
        description="Guidance on firmware checks, logic analyzer, or scope tests"
    )

