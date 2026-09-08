"""Capa de aplicacion: orquesta factory + report para los consumidores.

Hoy el unico consumidor es la UI de Streamlit (app.py). Cualquier otro
frontend (CLI, API HTTP, tarea batch) usa estas mismas funciones y no
necesita conocer `factory` ni `report` directamente.

No importa `streamlit` ni imprime nada: devuelve valores o levanta
`ChatModelError`. Que hacer con el error (mostrarlo, reintentar, loguear a
un servicio) es decision del consumidor.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from .config import AppConfig
from .facts import ReportFacts
from .llm import ChatModel, build_model
from .report import QA, answer_question, edit_report, generate_report

logger = logging.getLogger(__name__)

__all__ = ["Report", "QA", "generate", "apply_edit", "ask"]


@dataclass
class Report:
    markdown: str
    provider: str


def _model(provider: str, cfg: AppConfig) -> ChatModel:
    # La config del `config.toml` aplica solo al proveedor que quedo elegido
    # ahi; si la UI elige otro, ese usa los defaults de su adapter.
    provider_config = cfg.provider_config if provider == cfg.provider else {}
    return build_model(provider, provider_config)


def generate(facts: ReportFacts, cfg: AppConfig, *, tone: str, provider: str) -> Report:
    logger.info(
        "generar informe: proveedor=%s tono=%s campañas=%d", provider, tone, len(facts.campaigns)
    )
    result = generate_report(facts, _model(provider, cfg), tone=tone, temperature=cfg.temperature)
    return Report(markdown=result.markdown, provider=result.provider)


def apply_edit(
    facts: ReportFacts,
    cfg: AppConfig,
    *,
    current_report: str,
    request: str,
    tone: str,
    provider: str,
) -> str:
    logger.info("editar informe: proveedor=%s pedido=%r", provider, request[:80])
    return edit_report(
        facts, _model(provider, cfg),
        current_report=current_report, request=request,
        tone=tone, temperature=cfg.temperature,
    )


def ask(
    facts: ReportFacts,
    cfg: AppConfig,
    *,
    current_report: str,
    question: str,
    history: Sequence[QA] = (),
    tone: str,
    provider: str,
) -> str:
    logger.info("pregunta sobre informe: proveedor=%s pregunta=%r", provider, question[:80])
    return answer_question(
        facts, _model(provider, cfg),
        current_report=current_report, question=question, history=history,
        tone=tone, temperature=cfg.temperature,
    )
