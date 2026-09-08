from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class ChatModel(ABC):
    """Contrato minimo: una lista de mensajes entra, texto sale.

    Deliberadamente no expone streaming, tools ni tokens: el programa solo
    necesita "dame el informe redactado". Un proveedor que quiera mas lo maneja
    puertas adentro.
    """

    name: str = "chat-model"

    @abstractmethod
    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        ...

    # Azucar para el caso habitual (system + user).
    def run(self, system: str, user: str, *, temperature: float = 0.4) -> str:
        return self.complete(
            [ChatMessage("system", system), ChatMessage("user", user)],
            temperature=temperature,
        )


class ChatModelError(RuntimeError):
    """Falla al hablar con el proveedor (red, credenciales, formato)."""
