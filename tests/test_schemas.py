"""Unit tests for Pydantic v2 schemas in core/schemas.py."""

import pytest
from pydantic import ValidationError
from core.schemas import (
    AuditResponse,
    CodeIssue,
    ComponentLeg,
    DiagnosisFinding,
    DiagnosisResult,
    InventoryResult,
    PinSnapshot,
    PinState,
    SimulationFrame,
    SimulationPlan,
    TimedEvent,
    VisibleComponent,
)


def test_code_issue_valid():
    issue = CodeIssue(
        line=10,
        severity="high",
        category="hardware",
        issue="Missing pinMode",
        evidence="digitalRead(2);",
        impact="Pin 2 is floating and reads ambient noise.",
        fix="Add pinMode(2, INPUT_PULLUP);",
        confidence="high",
        source="deterministic",
    )
    assert issue.line == 10
    assert issue.severity == "high"
    assert issue.category == "hardware"
    assert issue.source == "deterministic"


def test_code_issue_extra_forbidden():
    with pytest.raises(ValidationError):
        CodeIssue(
            line=5,
            severity="low",
            category="syntax",
            issue="Test",
            evidence="int x;",
            impact="None",
            fix="None",
            confidence="low",
            extra_field="disallowed",
        )


def test_audit_response_valid():
    audit = AuditResponse(
        summary="Audit completed with 1 issue.",
        issues=[
            CodeIssue(
                line=3,
                severity="medium",
                category="timing",
                issue="Blocking delay in loop",
                evidence="delay(1000);",
                impact="MCU frozen during delay.",
                fix="Use millis() timer.",
                confidence="medium",
            )
        ],
    )
    assert len(audit.issues) == 1
    assert audit.summary.startswith("Audit completed")


def test_simulation_plan_and_timed_event():
    event = TimedEvent(t_ms=100, action="digitalWrite", pin="13", value="HIGH")
    pin = PinState(pin="13", mode="OUTPUT", component_hint="LED")
    plan = SimulationPlan(
        pins=[pin],
        events=[event],
        loop_detected=True,
        loop_period_ms=1000,
        notes=["Test note"],
        warnings=[],
    )
    assert len(plan.pins) == 1
    assert plan.events[0].value == "HIGH"
    assert plan.loop_detected is True


def test_simulation_frame_and_pin_snapshot():
    snap = PinSnapshot(
        pin="13",
        mode="OUTPUT",
        digital_state="HIGH",
        pwm_duty=255,
        component_hint="LED",
    )
    frame = SimulationFrame(
        t_ms=500,
        pin_states={"13": snap},
        active_event_description="digitalWrite(13, HIGH)",
    )
    assert frame.t_ms == 500
    assert frame.pin_states["13"].digital_state == "HIGH"


def test_vision_schemas():
    leg = ComponentLeg(
        leg_label="Anode",
        connects_to="Row 15",
        confidence="high",
        observation="Red wire from D2 to row 15",
    )
    comp = VisibleComponent(
        name="Red LED",
        color="Red",
        location="Row 15-16",
        visibility="clear",
        legs=[leg],
    )
    inv = InventoryResult(
        components=[comp],
        photo_quality_notes="High quality overhead view",
        uncertain_connections=[],
    )
    assert len(inv.components) == 1
    assert inv.components[0].legs[0].confidence == "high"

    finding = DiagnosisFinding(
        finding="Missing series resistor on LED",
        confidence="high",
        visual_evidence="D2 connected directly to LED",
        reasoning="Exceeds GPIO current rating",
        multimeter_verification="Measure resistance in Ω mode",
        fix="Insert 220Ω resistor",
    )
    diag = DiagnosisResult(
        summary="Wiring errors found",
        findings=[finding],
        safety_warnings=["Disconnect power"],
        next_steps_if_all_checks_pass="Check logic analyzer",
    )
    assert len(diag.findings) == 1
    assert "Disconnect power" in diag.safety_warnings[0]

