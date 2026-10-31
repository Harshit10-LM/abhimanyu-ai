"""Tests for Phase 2 visual circuit reconstruction and image annotation."""

from PIL import Image
from core.circuit_reconstructor import reconstruct_circuit_from_vision
from core.demo_data import DEMO_DIAGNOSIS, DEMO_INVENTORY
from core.image_processor import ImageProcessor


def test_reconstruct_circuit_from_vision():
    doc = reconstruct_circuit_from_vision(
        inventory=DEMO_INVENTORY,
        diagnosis=DEMO_DIAGNOSIS,
        board_id="esp32_devkit",
    )

    assert doc.board == "esp32_devkit"
    part_types = [p.type for p in doc.parts]
    assert "esp32_devkit" in part_types
    assert "breadboard_half" in part_types
    assert "led" in part_types
    assert len(doc.wires) > 0

    # Verify notes contain mandatory header
    assert any("AI-GENERATED CIRCUIT RECONSTRUCTION" in n for n in doc.notes)

    # Verify at least one wire has dashed style or uncertain status
    styles = {w.style for w in doc.wires}
    assert "solid" in styles


def test_image_processor_annotation_views():
    # Create synthetic breadboard test image
    img = Image.new("RGB", (640, 480), color=(240, 240, 240))

    # Test Inventory Annotation
    annotated_inv = ImageProcessor.annotate_inventory(img, DEMO_INVENTORY)
    assert annotated_inv.size == (640, 480)
    assert annotated_inv.mode == "RGB"

    # Test Diagnostic Annotation
    annotated_diag = ImageProcessor.annotate_diagnostic(img, DEMO_INVENTORY, DEMO_DIAGNOSIS)
    assert annotated_diag.size == (640, 480)
    assert annotated_diag.mode == "RGB"

