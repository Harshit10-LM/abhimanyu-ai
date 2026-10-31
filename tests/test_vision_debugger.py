"""Unit tests for Phase 2 vision pipeline, image preprocessing, and safety in core/vision_debugger.py."""

import io
import json
import pytest
from PIL import Image

from core.board_database import get_board
from core.demo_data import DEMO_FIXTURE_LABEL
from core.image_processor import ImageProcessor
from core.schemas import DiagnosisFinding, DiagnosisResult, InventoryResult, VisibleComponent
from core.vision_debugger import VisionDebugger


def test_image_processor_valid_png():
    # Create simple 200x200 PNG
    img = Image.new("RGB", (200, 200), color=(20, 30, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    proc_img, out_bytes = ImageProcessor.process_upload(raw_bytes)
    assert proc_img.size == (200, 200)
    assert len(out_bytes) > 0


def test_image_processor_rgba_transparency():
    # Create RGBA with transparency
    img = Image.new("RGBA", (150, 150), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    proc_img, out_bytes = ImageProcessor.process_upload(buf.getvalue())
    assert proc_img.mode == "RGB"
    assert len(out_bytes) > 0


def test_image_processor_rejects_tiny_images():
    tiny_img = Image.new("RGB", (10, 10), color=(0, 0, 0))
    buf = io.BytesIO()
    tiny_img.save(buf, format="PNG")

    with pytest.raises(ValueError, match="too low"):
        ImageProcessor.process_upload(buf.getvalue())


def test_image_processor_downscales_oversized():
    huge_img = Image.new("RGB", (2500, 1800), color=(100, 100, 100))
    buf = io.BytesIO()
    huge_img.save(buf, format="JPEG")

    proc_img, _ = ImageProcessor.process_upload(buf.getvalue(), max_edge=1000)
    assert max(proc_img.size) <= 1000


def test_demo_fixture_mode():
    debugger = VisionDebugger(llm_manager=None)
    inv, diag, label = debugger.get_reproducible_demo()

    assert label == DEMO_FIXTURE_LABEL
    assert len(inv.components) >= 3
    assert len(diag.findings) >= 2
    # Verify resistor and LED are in inventory
    comp_names = [c.name for c in inv.components]
    assert any("LED" in n for n in comp_names)
    assert any("Resistor" in n for n in comp_names)


def test_safety_warnings_enforcement():
    debugger = VisionDebugger(llm_manager=None)
    esp_board = get_board("esp32_devkit")

    # Diagnosis missing safety warnings
    diag = DiagnosisResult(
        summary="Test",
        findings=[],
        safety_warnings=[],
        next_steps_if_all_checks_pass="Test",
    )
    debugger._enforce_safety_rules(diag, esp_board)

    # Must inject mandatory warnings
    assert any("DISCONNECT POWER" in w for w in diag.safety_warnings)
    assert any("NEVER measure resistance" in w for w in diag.safety_warnings)
    # Must inject 3.3V voltage warning for ESP32
    assert any("3.3V" in w for w in diag.safety_warnings)


def test_export_report_json():
    debugger = VisionDebugger(llm_manager=None)
    inv, diag, _ = debugger.get_reproducible_demo()
    board = get_board("esp32_devkit")

    json_str = debugger.export_report_json(inv, diag, board, is_demo=True)
    parsed = json.loads(json_str)

    assert parsed["application"] == "Firmware-Alchemist"
    assert parsed["phase"] == "Phase 2: Visual Circuit Debugger"
    assert parsed["is_demo_fixture"] is True
    assert "findings" in parsed["diagnosis"]

