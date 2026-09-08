from __future__ import annotations

import logging
import os

import httpx

from .base import ChatMessage, ChatModel, ChatModelError

logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicChatModel(ChatModel):
    """Cliente directo de la Messages API de Anthropic (sin SDK, un archivo).

    Config:
        provider = "anthropic"
        [providers.anthropic]
        model = "claude-sonnet-5"
        api_key_env = "ANTHROPIC_API_KEY"
    """

    name = "anthropic"

    def __init__(
        self,
        *,
        model: str = "claude-sonnet-5",
        api_key_env: str = "ANTHROPIC_API_KEY",
        max_tokens: int = 2000,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.api_key = os.environ.get(api_key_env, "")
        self.max_tokens = max_tokens
        self.timeout = timeout
        if not self.api_key:
            raise ChatModelError(
                f"Falta la variable de entorno {api_key_env} para el proveedor anthropic."
            )

    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        turns = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in {"user", "assistant"}
        ]
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "messages": turns,
        }
        if system:
            body["system"] = system

        try:
            resp = httpx.post(
                API_URL,
                json=body,
                timeout=self.timeout,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("fallo la llamada a Anthropic (%s): %s", self.model, exc)
            raise ChatModelError(f"Error al llamar a Anthropic: {exc}") from exc

        data = resp.json()
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        text = "".join(parts).strip()
        if not text:
            raise ChatModelError("Anthropic devolvio una respuesta vacia.")
        return text
