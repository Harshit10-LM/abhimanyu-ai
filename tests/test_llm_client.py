"""Unit tests for the Ollama client manager in core/llm_client.py."""

from unittest.mock import MagicMock, patch
import pytest

from core.board_database import get_board
from core.llm_client import DEFAULT_MODEL, OllamaClientManager
from core.schemas import AuditResponse, CodeIssue


def test_loopback_restriction_security():
    # Valid loopback addresses
    OllamaClientManager(host="http://localhost:11434")
    OllamaClientManager(host="http://127.0.0.1:11434")

    # Cloud / external addresses MUST be blocked by security validator
    with pytest.raises(ValueError, match="Security violation"):
        OllamaClientManager(host="https://api.openai.com/v1")

    with pytest.raises(ValueError, match="Security violation"):
        OllamaClientManager(host="http://remote-server.com:11434")


def test_check_connection_success():
    manager = OllamaClientManager(host="http://127.0.0.1:11434")
    with patch.object(manager.client, "list", return_value={"models": []}):
        assert manager.check_connection() is True


def test_check_connection_failure():
    manager = OllamaClientManager(host="http://127.0.0.1:11434")
    with patch.object(manager.client, "list", side_effect=Exception("Connection refused")):
        assert manager.check_connection() is False


def test_list_local_models():
    manager = OllamaClientManager(host="http://127.0.0.1:11434")
    mock_resp = MagicMock()
    mock_resp.models = [
        MagicMock(model="gemma4:e4b"),
        MagicMock(model="qwen2.5vl:7b"),
    ]
    with patch.object(manager.client, "list", return_value=mock_resp):
        models = manager.list_local_models()
        assert "gemma4:e4b" in models
        assert "qwen2.5vl:7b" in models
        assert manager.is_model_available("gemma4:e4b") is True
        assert manager.is_model_available("llama3:70b") is False


def test_audit_firmware_mocked_success():
    manager = OllamaClientManager(host="http://127.0.0.1:11434")
    board = get_board("arduino_uno")

    mock_chat_response = MagicMock()
    mock_chat_response.message.content = """{
        "summary": "Detected 1 missing pinMode bug.",
        "issues": [
            {
                "line": 4,
                "severity": "high",
                "category": "hardware",
                "issue": "Missing pinMode for Pin 2",
                "evidence": "digitalRead(2);",
                "impact": "Pin 2 is floating.",
                "fix": "Add pinMode(2, INPUT_PULLUP);",
                "confidence": "high",
                "source": "ai"
            }
        ]
    }"""

    with patch.object(manager.client, "chat", return_value=mock_chat_response):
        result = manager.audit_firmware(
            source_code="void setup() {}\nvoid loop() {\n    digitalRead(2);\n}",
            board=board,
            model=DEFAULT_MODEL,
        )
        assert isinstance(result, AuditResponse)
        assert len(result.issues) == 1
        assert result.issues[0].line == 4
        assert result.issues[0].severity == "high"


def test_audit_firmware_markdown_fences():
    manager = OllamaClientManager(host="http://127.0.0.1:11434")
    board = get_board("arduino_uno")

    mock_chat_response = MagicMock()
    # Emulate LLM wrapping output in markdown code fences
    mock_chat_response.message.content = """```json
    {
        "summary": "Output wrapped in markdown fences.",
        "issues": []
    }
    ```"""

    with patch.object(manager.client, "chat", return_value=mock_chat_response):
        result = manager.audit_firmware(
            source_code="void setup() {}",
            board=board,
            model=DEFAULT_MODEL,
        )
        assert isinstance(result, AuditResponse)
        assert result.summary == "Output wrapped in markdown fences."


def test_audit_firmware_dict_response():
    manager = OllamaClientManager(host="http://127.0.0.1:11434")
    board = get_board("arduino_uno")

    # Dict response
    dict_response = {
        "message": {
            "content": '{"summary": "Dict response handled cleanly.", "issues": []}'
        }
    }

    with patch.object(manager.client, "chat", return_value=dict_response):
        result = manager.audit_firmware(
            source_code="void setup() {}",
            board=board,
            model=DEFAULT_MODEL,
        )
        assert isinstance(result, AuditResponse)
        assert result.summary == "Dict response handled cleanly."


def test_unload_model():
    manager = OllamaClientManager(host="http://127.0.0.1:11434")
    with patch.object(manager.client, "generate", return_value={}) as mock_gen:
        assert manager.unload_model("gemma4:e4b") is True
        mock_gen.assert_called_once_with(model="gemma4:e4b", prompt="", keep_alive=0)

