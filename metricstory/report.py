"""Orquestacion: ReportFacts + tono -> narrativa redactada.

Regla de oro: el modelo recibe solo el JSON de hechos ya calculados. No ve el
CSV, no calcula nada. Si un numero no esta en los hechos, el informe no puede
inventarlo.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from .facts import ReportFacts
from .llm import ChatMessage, ChatModel

TONES: dict[str, str] = {
    "cliente": (
        "El lector es el cliente y no es tecnico. Evita jerga; cuando uses una "
        "sigla (ROAS, CPA, CTR) explicala en pocas palabras la primera vez. "
        "Tono profesional, claro y tranquilizador, sin exagerar resultados."
    ),
    "interno": (
        "El lector es el equipo interno de la agencia. Podes usar jerga de "
        "performance sin explicar. Tono directo, foco en decisiones y proximos "
        "pasos, sin relleno."
    ),
    "ejecutivo": (
        "El lector es un director o gerente del cliente con poco tiempo. Maximo "
        "impacto en minimo texto: titulares, cifras clave y la recomendacion. "
        "Nada de detalle campaña por campaña salvo que sea decisivo."
    ),
}

SYSTEM_PROMPT = """\
Sos analista de medios pagos en una agencia de marketing y redactas el informe \
mensual de campañas para {audience_label}.

{tone_instructions}

Reglas estrictas:
- Usa UNICAMENTE los numeros del JSON de hechos que te paso. No estimes, no \
inventes ni completes datos que no esten.
- Si un dato no esta disponible (valor null), decilo con naturalidad o no lo \
menciones. Nunca lo reemplaces por un numero inventado.
- Las variaciones ("deltas") ya vienen calculadas como proporcion (0.12 = +12%).
- Moneda: {currency}. Formatea los importes con esa moneda.
- Estructura el informe en Markdown con estas secciones: \
"## Resumen del periodo", "## Desempeño por campaña", \
"## Ritmo de inversion" (solo si hay datos de presupuesto), \
"## Recomendaciones para el proximo periodo".
- Las recomendaciones tienen que desprenderse de los numeros: menciona la \
campaña y la metrica que las justifica.
- No agregues un preambulo ni un cierre fuera de esas secciones.
"""

USER_PROMPT = """\
Periodo actual: {cur_start} a {cur_end}
Periodo de comparacion: {prev}

JSON de hechos:
```json
{facts_json}
```

Redacta el informe siguiendo las reglas del sistema.
"""


@dataclass
class GeneratedReport:
    markdown: str
    provider: str
    tone: str
    facts: ReportFacts


def _audience_label(tone: str) -> str:
    return {
        "cliente": "el cliente (no tecnico)",
        "interno": "el equipo interno",
        "ejecutivo": "la direccion del cliente",
    }.get(tone, "el cliente")


def _facts_json(facts: ReportFacts) -> str:
    return json.dumps(facts.to_dict(), ensure_ascii=False, indent=2)


def build_prompts(facts: ReportFacts, tone: str) -> tuple[str, str]:
    tone_key = tone if tone in TONES else "cliente"
    system = SYSTEM_PROMPT.format(
        audience_label=_audience_label(tone_key),
        tone_instructions=TONES[tone_key],
        currency=facts.account_currency,
    )
    prev = (
        f"{facts.previous_period[0].isoformat()} a {facts.previous_period[1].isoformat()}"
        if facts.previous_period
        else "sin periodo anterior disponible"
    )
    user = USER_PROMPT.format(
        cur_start=facts.current_period[0].isoformat(),
        cur_end=facts.current_period[1].isoformat(),
        prev=prev,
        facts_json=_facts_json(facts),
    )
    return system, user


def generate_report(
    facts: ReportFacts,
    model: ChatModel,
    *,
    tone: str = "cliente",
    temperature: float = 0.4,
) -> GeneratedReport:
    system, user = build_prompts(facts, tone)
    markdown = model.run(system, user, temperature=temperature).strip()
    markdown = _strip_code_fence(markdown)
    return GeneratedReport(markdown=markdown, provider=model.name, tone=tone, facts=facts)


EDIT_SYSTEM = """\
Sos analista de medios pagos en una agencia de marketing. Ya redactaste el \
informe mensual de campañas para {audience_label} y ahora te piden un cambio \
puntual.

{tone_instructions}

Reglas estrictas:
- Usa UNICAMENTE los numeros del JSON de hechos. No estimes ni inventes datos \
que no esten. Si te piden un dato que no esta, decilo; no lo reemplaces por un \
numero inventado.
- Devolve el INFORME COMPLETO actualizado en Markdown, con la misma estructura \
de secciones que el original, aplicando el cambio pedido.
- No agregues comentarios fuera del informe ni expliques que cambiaste.
- Moneda: {currency}.

JSON de hechos:
```json
{facts_json}
```

Informe actual:
```markdown
{current_report}
```
"""

QUESTION_SYSTEM = """\
Sos analista de medios pagos en una agencia de marketing. Redactaste el informe \
mensual de campañas para {audience_label} y ahora respondes preguntas sobre los \
numeros del periodo.

{tone_instructions}

Reglas estrictas:
- Responde en 2 a 4 oraciones, en prosa llana. No reescribas el informe.
- Usa UNICAMENTE los numeros del JSON de hechos. Si la respuesta no esta en los \
hechos, decilo; no inventes.
- Moneda: {currency}.

JSON de hechos:
```json
{facts_json}
```

Informe actual (para contexto):
```markdown
{current_report}
```
"""


@dataclass
class QA:
    """Un turno de pregunta y respuesta ya cerrado, para el historial."""

    question: str
    answer: str


def _conversation_system(template: str, facts: ReportFacts, tone: str, current_report: str) -> str:
    tone_key = tone if tone in TONES else "cliente"
    return template.format(
        audience_label=_audience_label(tone_key),
        tone_instructions=TONES[tone_key],
        currency=facts.account_currency,
        facts_json=_facts_json(facts),
        current_report=current_report,
    )


def edit_report(
    facts: ReportFacts,
    model: ChatModel,
    *,
    current_report: str,
    request: str,
    tone: str = "cliente",
    temperature: float = 0.4,
) -> str:
    """Aplica un pedido de cambio y devuelve el informe completo actualizado."""
    system = _conversation_system(EDIT_SYSTEM, facts, tone, current_report)
    reply = model.run(system, request, temperature=temperature).strip()
    return _strip_code_fence(reply)


def answer_question(
    facts: ReportFacts,
    model: ChatModel,
    *,
    current_report: str,
    question: str,
    history: Sequence[QA] = (),
    tone: str = "cliente",
    temperature: float = 0.4,
) -> str:
    """Responde una pregunta sobre los hechos, sin tocar el informe."""
    system = _conversation_system(QUESTION_SYSTEM, facts, tone, current_report)
    messages = [ChatMessage("system", system)]
    for qa in history:
        messages.append(ChatMessage("user", qa.question))
        messages.append(ChatMessage("assistant", qa.answer))
    messages.append(ChatMessage("user", question))
    return model.complete(messages, temperature=temperature).strip()


def _strip_code_fence(text: str) -> str:
    """Algunos modelos envuelven todo en ```markdown ... ```."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()
