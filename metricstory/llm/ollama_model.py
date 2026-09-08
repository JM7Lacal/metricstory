from __future__ import annotations

import logging

import httpx

from .base import ChatMessage, ChatModel, ChatModelError

logger = logging.getLogger(__name__)


class OllamaChatModel(ChatModel):
    """Modelo local via Ollama (http://localhost:11434). Sin API key, sin costo,
    los datos no salen de la maquina: util cuando el CSV del cliente es sensible.

    Config:
        provider = "ollama"
        [providers.ollama]
        model = "llama3.1"
        host = "http://localhost:11434"
    """

    name = "ollama"

    def __init__(
        self,
        *,
        model: str = "llama3.1",
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        body = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        try:
            resp = httpx.post(f"{self.host}/api/chat", json=body, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("no se pudo hablar con Ollama en %s: %s", self.host, exc)
            raise ChatModelError(
                f"No se pudo hablar con Ollama en {self.host}: {exc}"
            ) from exc

        data = resp.json()
        text = (data.get("message") or {}).get("content", "").strip()
        if not text:
            raise ChatModelError(f"Ollama devolvio una respuesta vacia: {data}")
        return text
