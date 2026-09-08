from __future__ import annotations

import logging
import os

import httpx

from .base import ChatMessage, ChatModel, ChatModelError

logger = logging.getLogger(__name__)


class OpenAIChatModel(ChatModel):
    """Cliente de la Chat Completions API de OpenAI (o cualquier endpoint
    compatible: Azure OpenAI, Groq, OpenRouter, LM Studio...).

    Config:
        provider = "openai"
        [providers.openai]
        model = "gpt-4o-mini"
        api_key_env = "OPENAI_API_KEY"
        base_url = "https://api.openai.com/v1"
    """

    name = "openai"

    def __init__(
        self,
        *,
        model: str = "gpt-4o-mini",
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        self.timeout = timeout
        if not self.api_key:
            raise ChatModelError(
                f"Falta la variable de entorno {api_key_env} para el proveedor openai."
            )

    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=body,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("fallo la llamada a OpenAI (%s): %s", self.model, exc)
            raise ChatModelError(f"Error al llamar a OpenAI: {exc}") from exc

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            logger.warning("respuesta inesperada de OpenAI: %s", data)
            raise ChatModelError(f"Respuesta inesperada de OpenAI: {data}") from exc
