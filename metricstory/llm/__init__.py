"""Puerto de modelos de chat + proveedores intercambiables.

Mismo patron que use en un proyecto anterior (Foundry, un editor WPF): el resto
del programa depende solo de `ChatModel` (mensajes -> texto). Cambiar de
proveedor es una linea en config.toml, sin tocar codigo.
"""

from .base import ChatMessage, ChatModel, ChatModelError
from .factory import available_providers, build_model

__all__ = ["ChatMessage", "ChatModel", "ChatModelError", "build_model", "available_providers"]
