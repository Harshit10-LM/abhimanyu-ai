"""Visual Hardware Debugger (Phase 2).

Orchestrates the two-step local vision pipeline (Call 1: Inventory,
Call 2: Diagnosis), electrical safety validation, and reproducible demo mode.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Tuple
from PIL import Image

from core.board_database import BoardSpec
from core.demo_data import (
    DEMO_DIAGNOSIS,
    DEMO_FIXTURE_LABEL,
    DEMO_INVENTORY,
)
from core.image_processor import ImageProcessor
from core.llm_client import OllamaClientManager
from core.schemas import DiagnosisResult, InventoryResult

MANDATORY_SAFETY_WARNINGS = [
    "SAFETY: ALWAYS DISCONNECT POWER before inserting, removing, or relocating jumper wires.",
    "MULTIMETER SAFETY: NEVER measure resistance or continuity on an energized circuit; always power down first.",
    "VOLTAGE COMPATIBILITY: Confirm sensor and MCU logic voltage compatibility before powering on.",
    "COMMON GROUND: Ensure all separate boards, power supplies, and external sensors share a unified common GND rail.",
]


class VisionDebugger:
    """Manages the breadboard visual analysis workflow."""

    def __init__(self, llm_manager: Optional[OllamaClientManager] = None):
        self.llm_manager = llm_manager or OllamaClientManager()

    def run_two_step_pipeline(
        self,
        image_bytes: bytes,
        user_symptom: str,
        user_components: str,
        board: BoardSpec,
        model: str,
    ) -> Tuple[InventoryResult, DiagnosisResult]:
        """Executes Call 1 (Visual Inventory) followed by Call 2 (Contextual Diagnosis)."""
        # Step 1: Image Preprocessing (Pillow)
        _, cleaned_bytes = ImageProcessor.process_upload(image_bytes)

        # Call 1: Pure Visual Inventory
        inventory = self.llm_manager.inventory_circuit(
            image_bytes=cleaned_bytes,
            model=model,
        )

        # Call 2: Contextual Diagnosis based on verified inventory
        diagnosis = self.llm_manager.diagnose_circuit(
            image_bytes=cleaned_bytes,
            inventory=inventory,
            user_symptom=user_symptom,
            user_components=user_components,
            board=board,
            model=model,
        )

        # Enforce mandatory electrical safety rules
        self._enforce_safety_rules(diagnosis, board)

        return inventory, diagnosis

    def get_reproducible_demo(self) -> Tuple[InventoryResult, DiagnosisResult, str]:
        """Returns the reproducible demo fixture for reliable hackathon presentation."""
        return DEMO_INVENTORY, DEMO_DIAGNOSIS, DEMO_FIXTURE_LABEL

    def export_report_json(
        self,
        inventory: InventoryResult,
        diagnosis: DiagnosisResult,
        board: BoardSpec,
        is_demo: bool = False,
    ) -> str:
        """Serializes the complete Phase 2 audit and diagnosis report to structured JSON."""
        data = {
            "application": "Firmware-Alchemist",
            "phase": "Phase 2: Visual Circuit Debugger",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_board": {
                "id": board.id,
                "name": board.display_name,
                "mcu": board.mcu,
                "logic_voltage": board.logic_voltage,
            },
            "is_demo_fixture": is_demo,
            "inventory": inventory.model_dump(),
            "diagnosis": diagnosis.model_dump(),
        }
        return json.dumps(data, indent=2)

    def _enforce_safety_rules(self, diagnosis: DiagnosisResult, board: BoardSpec) -> None:
        """Injects mandatory unpowered multimeter warnings and voltage precautions."""
        existing_warnings = set(w.lower() for w in diagnosis.safety_warnings)

        for std_w in MANDATORY_SAFETY_WARNINGS:
            if not any(key in existing_warnings for key in ("disconnect power", "never measure resistance")):
                diagnosis.safety_warnings.insert(0, std_w)

        # Voltage specific warnings
        if board.logic_voltage < 5.0:
            v_warn = f"CRITICAL VOLTAGE RULE: {board.display_name} uses {board.logic_voltage}V logic. Do NOT connect 5V sensors or power directly to non-tolerant GPIO pins."
            if not any("5v" in w.lower() for w in diagnosis.safety_warnings):
                diagnosis.safety_warnings.append(v_warn)

