"""Parseo de respuesta y mapeo de errores de cada adapter, sin red real."""

import httpx
import pytest

from metricstory.llm import claude_cli_model
from metricstory.llm.anthropic_model import AnthropicChatModel
from metricstory.llm.base import ChatMessage, ChatModelError
from metricstory.llm.claude_cli_model import ClaudeCliChatModel
from metricstory.llm.ollama_model import OllamaChatModel
from metricstory.llm.openai_model import OpenAIChatModel

MSG = [ChatMessage("system", "s"), ChatMessage("user", "u")]


def _response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x"))


def _post_returning(response: httpx.Response):
    def _post(*_a, **_k):
        return response
    return _post


# --- Anthropic ---------------------------------------------------------------

def test_anthropic_extracts_text_blocks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(
        httpx, "post",
        _post_returning(_response(200, {"content": [{"type": "text", "text": "hola "},
                                                    {"type": "text", "text": "mundo"}]})),
    )
    assert AnthropicChatModel().complete(MSG) == "hola mundo"


def test_anthropic_maps_http_error_to_chatmodelerror(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", _post_returning(_response(500, {"error": "boom"})))
    with pytest.raises(ChatModelError):
        AnthropicChatModel().complete(MSG)


def test_anthropic_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ChatModelError):
        AnthropicChatModel()


# --- OpenAI -----------------------------------------------------------------

def test_openai_extracts_choice_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(
        httpx, "post",
        _post_returning(_response(200, {"choices": [{"message": {"content": " listo "}}]})),
    )
    assert OpenAIChatModel().complete(MSG) == "listo"


def test_openai_unexpected_shape_raises(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", _post_returning(_response(200, {"weird": True})))
    with pytest.raises(ChatModelError):
        OpenAIChatModel().complete(MSG)


# --- Ollama ---------------------------------------------------------------

def test_ollama_extracts_message_content(monkeypatch):
    monkeypatch.setattr(
        httpx, "post",
        _post_returning(_response(200, {"message": {"content": "respuesta local"}})),
    )
    assert OllamaChatModel().complete(MSG) == "respuesta local"


def test_ollama_empty_response_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", _post_returning(_response(200, {"message": {"content": ""}})))
    with pytest.raises(ChatModelError):
        OllamaChatModel().complete(MSG)


# --- Claude CLI ------------------------------------------------------------

class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_claude_cli_parses_json_result(monkeypatch):
    monkeypatch.setattr(claude_cli_model, "_resolve_cli", lambda: "claude")
    monkeypatch.setattr(claude_cli_model.subprocess, "run",
                        lambda *a, **k: _Proc(stdout='{"result": "informe"}'))
    assert ClaudeCliChatModel().complete(MSG) == "informe"


def test_claude_cli_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr(claude_cli_model, "_resolve_cli", lambda: "claude")
    monkeypatch.setattr(claude_cli_model.subprocess, "run",
                        lambda *a, **k: _Proc(returncode=1, stderr="no logueado"))
    with pytest.raises(ChatModelError):
        ClaudeCliChatModel().complete(MSG)


def test_claude_cli_missing_binary_raises(monkeypatch):
    monkeypatch.setattr(claude_cli_model, "_resolve_cli", lambda: None)
    with pytest.raises(ChatModelError):
        ClaudeCliChatModel()
