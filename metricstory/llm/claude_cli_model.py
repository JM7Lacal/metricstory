from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from .base import ChatMessage, ChatModel, ChatModelError

logger = logging.getLogger(__name__)


def _resolve_cli() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / "claude.exe",
        Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "claude.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


class ClaudeCliChatModel(ChatModel):
    """Usa el CLI de Claude Code (`claude -p`) como backend. Sin API key aparte:
    aprovecha la sesion ya logueada. Cada llamada recarga el system prompt del
    CLI, asi que para uso intensivo conviene el proveedor `anthropic`.

    Config:
        provider = "claude-cli"
    """

    name = "claude-cli"

    def __init__(self, *, timeout: float = 120.0) -> None:
        self.cli = _resolve_cli()
        self.timeout = timeout
        if not self.cli:
            raise ChatModelError(
                "No se encontro el CLI `claude` en el PATH. Instalalo o usa otro proveedor."
            )

    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        user = "\n\n".join(m.content for m in messages if m.role != "system")
        args = [self.cli, "-p", "--output-format", "json"]
        if system:
            args += ["--append-system-prompt", system]

        try:
            proc = subprocess.run(
                args,
                input=user,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired as exc:
            logger.warning("el CLI `claude` no respondio en %ss", self.timeout)
            raise ChatModelError("El CLI `claude` no respondio a tiempo.") from exc

        if proc.returncode != 0:
            logger.warning("`claude` fallo (%s): %s", proc.returncode, proc.stderr.strip())
            raise ChatModelError(f"`claude` fallo ({proc.returncode}): {proc.stderr.strip()}")

        try:
            payload = json.loads(proc.stdout)
            return str(payload.get("result", "")).strip()
        except json.JSONDecodeError:
            return proc.stdout.strip()
