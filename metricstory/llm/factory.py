"""Seleccion de proveedor. Un unico punto de decision, como el
`RegisterAssistantProvider` de Foundry.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from .base import ChatModel, ChatModelError

logger = logging.getLogger(__name__)

_BUILDERS: dict[str, Callable[[dict], ChatModel]] = {}


def _register(name: str, builder) -> None:
    _BUILDERS[name] = builder


def _lazy():
    """Registro perezoso: no importamos httpx/subprocess hasta que hagan falta."""
    if _BUILDERS:
        return

    def stub(_cfg):
        from .stub import StubChatModel

        return StubChatModel()

    def anthropic(cfg):
        from .anthropic_model import AnthropicChatModel

        return AnthropicChatModel(**cfg)

    def openai(cfg):
        from .openai_model import OpenAIChatModel

        return OpenAIChatModel(**cfg)

    def ollama(cfg):
        from .ollama_model import OllamaChatModel

        return OllamaChatModel(**cfg)

    def claude_cli(cfg):
        from .claude_cli_model import ClaudeCliChatModel

        return ClaudeCliChatModel(**cfg)

    _register("stub", stub)
    _register("anthropic", anthropic)
    _register("openai", openai)
    _register("ollama", ollama)
    _register("claude-cli", claude_cli)


def available_providers() -> list[str]:
    _lazy()
    return sorted(_BUILDERS)


def build_model(provider: str, config: dict | None = None) -> ChatModel:
    _lazy()
    key = (provider or "stub").strip().lower()
    if key not in _BUILDERS:
        raise ChatModelError(
            f"Proveedor desconocido: {provider!r}. Opciones: {', '.join(available_providers())}"
        )
    logger.debug("construyendo proveedor %s", key)
    return _BUILDERS[key](config or {})
