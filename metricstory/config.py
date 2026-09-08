"""Carga de config.toml. Seleccion de proveedor en una linea, sin recompilar."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass
class AppConfig:
    provider: str = "stub"
    provider_config: dict = field(default_factory=dict)
    account_currency: str = "USD"
    monthly_budget: float | None = None
    default_tone: str = "cliente"
    temperature: float = 0.4

    @classmethod
    def load(cls, path: Path | str | None = None) -> "AppConfig":
        p = Path(path) if path else DEFAULT_PATH
        if not p.exists():
            return cls()
        data = tomllib.loads(p.read_text(encoding="utf-8"))

        provider = str(data.get("provider", "stub")).strip().lower()
        providers = data.get("providers", {}) or {}
        report = data.get("report", {}) or {}

        return cls(
            provider=provider,
            provider_config=dict(providers.get(provider, {}) or {}),
            account_currency=str(report.get("account_currency", "USD")),
            monthly_budget=report.get("monthly_budget"),
            default_tone=str(report.get("default_tone", "cliente")),
            temperature=float(report.get("temperature", 0.4)),
        )
