"""Ollama local LLM client for structured text and vision inference.

Follows strict offline-first principles, structured Pydantic v2 JSON schema
enforcement, loopback network boundary, and resilient retry mechanisms.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from ollama import Client, ResponseError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from core.board_database import BoardSpec
from core.prompts import (
    FIRMWARE_AUDIT_SYSTEM_PROMPT,
    VISION_DIAGNOSIS_SYSTEM_PROMPT,
    VISION_INVENTORY_SYSTEM_PROMPT,
)
from core.schemas import AuditResponse, DiagnosisResult, InventoryResult

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_VISION_FALLBACK = "qwen2.5vl:7b"
DEFAULT_CONTEXT_WINDOW = 8192
DEFAULT_TIMEOUT = 180.0


class OllamaClientManager:
    """Manages local Ollama connection and structured schema-driven inference."""

    def __init__(self, host: str = DEFAULT_OLLAMA_HOST, timeout: float = DEFAULT_TIMEOUT):
        self._validate_local_host(host)
        self.host = host
        self.timeout = timeout
        self.client = Client(host=self.host, timeout=self.timeout)

    @staticmethod
    def _validate_local_host(host: str) -> None:
        """Enforces that only localhost/loopback addresses are permitted."""
        parsed = urlparse(host)
        hostname = parsed.hostname or ""
        allowed = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
        if hostname not in allowed:
            raise ValueError(
                f"Security violation: Only local loopback endpoints are allowed (got '{host}'). External cloud APIs are strictly disabled."
            )

    def check_connection(self) -> bool:
        """Checks if the local Ollama server is alive and responding."""
        try:
            self.client.list()
            return True
        except Exception as exc:
            logger.debug("Ollama connection check failed: %s", exc)
            return False

    def list_local_models(self) -> List[str]:
        """Lists all locally installed models on the Ollama instance."""
        try:
            resp = self.client.list()
            # Ollama Python SDK returns models list with .model or ['name']
            models = []
            model_items = getattr(resp, "models", []) or resp.get("models", [])
            for m in model_items:
                name = getattr(m, "model", None) or getattr(m, "name", None)
                if not name and isinstance(m, dict):
                    name = m.get("model") or m.get("name")
                if name:
                    # Strip tag if desired or keep clean
                    models.append(str(name))
            return models
        except Exception as exc:
            logger.warning("Failed to list Ollama models: %s", exc)
            return []

    def is_model_available(self, model_name: str) -> bool:
        """Checks whether the requested model is present locally."""
        installed = self.list_local_models()
        # Check exact or prefix match (e.g. gemma4:e4b vs gemma4:e4b-latest)
        base = model_name.split(":")[0].lower()
        return any(model_name.lower() in m.lower() or base in m.lower() for m in installed)

    def unload_model(self, model_name: str) -> bool:
        """Evicts the active model from unified GPU/RAM by setting keep_alive to 0."""
        try:
            self.client.generate(model=model_name, prompt="", keep_alive=0)
            return True
        except Exception as exc:
            logger.warning("Failed to unload model %s: %s", model_name, exc)
            return False

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        reraise=True,
    )
    def _execute_chat_with_schema(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        schema_dict: Dict[str, Any],
        num_ctx: int = DEFAULT_CONTEXT_WINDOW,
    ) -> str:
        """Executes non-streaming Ollama chat with structured JSON schema format."""
        response = self.client.chat(
            model=model,
            messages=messages,
            format=schema_dict,
            options={
                "temperature": 0.0,
                "num_ctx": num_ctx,
            },
            stream=False,
        )

        msg = getattr(response, "message", None)
        if msg is not None:
            content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
        elif isinstance(response, dict):
            content = response.get("message", {}).get("content", "")
        else:
            content = str(response)

        if not content:
            raise ValueError("Ollama returned an empty response.")

        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content)

        return content.strip()

    def audit_firmware(
        self,
        source_code: str,
        board: BoardSpec,
        expected_behavior: str = "",
        model: str = DEFAULT_MODEL,
    ) -> AuditResponse:
        """Audits firmware source code against target board constraints."""
        board_info = f"Board: {board.display_name}\nMCU: {board.mcu}\nOperating Voltage: {board.logic_voltage}V\nKnown constraints:\n"
        board_info += "\n".join(f"- {w}" for w in board.hardware_warnings)

        system_prompt = FIRMWARE_AUDIT_SYSTEM_PROMPT.format(
            BOARD_INFO=board_info,
            EXPECTED_BEHAVIOR=expected_behavior or "No specific expected behavior provided.",
        )

        user_content = f"Please audit the following embedded firmware:\n\n```cpp\n{source_code}\n```"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        raw_json = self._execute_chat_with_schema(
            model=model,
            messages=messages,
            schema_dict=AuditResponse.model_json_schema(),
        )

        return AuditResponse.model_validate_json(raw_json)

    def inventory_circuit(
        self,
        image_bytes: bytes,
        model: str = DEFAULT_MODEL,
    ) -> InventoryResult:
        """Phase 2 Call 1: Pure visual component inventory from breadboard photograph."""
        messages = [
            {"role": "system", "content": VISION_INVENTORY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Perform a rigorous visual component inventory on this breadboard circuit image.",
                "images": [image_bytes],
            },
        ]

        raw_json = self._execute_chat_with_schema(
            model=model,
            messages=messages,
            schema_dict=InventoryResult.model_json_schema(),
        )

        return InventoryResult.model_validate_json(raw_json)

    def diagnose_circuit(
        self,
        image_bytes: bytes,
        inventory: InventoryResult,
        user_symptom: str,
        user_components: str,
        board: BoardSpec,
        model: str = DEFAULT_MODEL,
    ) -> DiagnosisResult:
        """Phase 2 Call 2: Contextual circuit diagnosis and multimeter verification checklist."""
        inventory_json = inventory.model_dump_json(indent=2)
        board_info = f"{board.display_name} ({board.logic_voltage}V logic, MCU: {board.mcu})"

        system_prompt = VISION_DIAGNOSIS_SYSTEM_PROMPT.format(
            INVENTORY_JSON=inventory_json,
            USER_SYMPTOM=user_symptom or "Circuit is malfunctioning or not turning on.",
            USER_COMPONENTS=user_components or "Unspecified components.",
            BOARD_INFO=board_info,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Analyze the circuit photograph alongside the verified component inventory to identify wiring issues, root causes, and multimeter verification procedures.",
                "images": [image_bytes],
            },
        ]

        raw_json = self._execute_chat_with_schema(
            model=model,
            messages=messages,
            schema_dict=DiagnosisResult.model_json_schema(),
        )

        return DiagnosisResult.model_validate_json(raw_json)

