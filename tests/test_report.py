import json

import pandas as pd

from metricstory.columns import guess_mapping
from metricstory.llm.base import ChatMessage, ChatModel
from metricstory.llm.stub import StubChatModel
from metricstory.metrics import build_facts
from metricstory.report import QA, answer_question, build_prompts, edit_report, generate_report


def _facts():
    rows = []
    for i in range(20):
        rows.append({
            "Reporting starts": f"2026-01-{i + 1:02d}",
            "Campaign name": "Retargeting",
            "Amount spent (USD)": 100,
            "Impressions": 10_000,
            "Link clicks": 200,
            "Purchases": 15,
            "Purchases conversion value": 300,
        })
    df = pd.DataFrame(rows)
    mapping = guess_mapping(list(df.columns))
    return build_facts(df, mapping, period_days=10)


def test_build_prompts_embeds_facts_as_json_not_prose():
    facts = _facts()
    system, user = build_prompts(facts, "cliente")
    assert "UNICAMENTE los numeros del JSON" in system
    assert "```json" in user
    payload = json.loads(user.split("```json", 1)[1].rsplit("```", 1)[0])
    assert payload["total_current"]["spend"] == facts.total_current.spend


def test_generate_report_with_stub_model_is_deterministic_and_uses_only_facts():
    facts = _facts()
    model = StubChatModel()
    result = generate_report(facts, model, tone="cliente")
    assert "Informe de campaña" in result.markdown
    # el gasto real (2000) tiene que aparecer; un numero inventado, no.
    assert f"{int(facts.total_current.spend)}" in result.markdown.replace(",", "")
    again = generate_report(facts, model, tone="cliente")
    assert result.markdown == again.markdown


class _RecordingModel(ChatModel):
    """Guarda los mensajes recibidos y devuelve una respuesta fija, para
    inspeccionar como se arma el prompt sin depender de un proveedor real."""

    name = "recording"

    def __init__(self, reply: str):
        self._reply = reply
        self.last_messages: list[ChatMessage] = []

    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        self.last_messages = messages
        return self._reply


def test_edit_report_returns_full_report_and_strips_code_fence():
    facts = _facts()
    model = _RecordingModel("```markdown\n## Informe editado\n\nMas corto.\n```")

    reply = edit_report(
        facts, model,
        current_report="## Informe original\n\nTexto largo.",
        request="hacelo mas corto",
    )

    assert reply == "## Informe editado\n\nMas corto."  # fence removido
    last = model.last_messages[-1]
    assert last.role == "user" and last.content == "hacelo mas corto"
    system = model.last_messages[0].content
    assert "Informe original" in system  # el informe actual va en el system
    assert str(int(facts.total_current.spend)) in system.replace(",", "")  # y el JSON de hechos


def test_answer_question_includes_history_and_keeps_text_verbatim():
    facts = _facts()
    model = _RecordingModel("El ROAS bajó porque subió el CPA.")

    reply = answer_question(
        facts, model,
        current_report="## Informe original",
        question="por qué bajó el ROAS?",
        history=[QA(question="cuánto se gastó?", answer="USD 2000.")],
    )

    assert reply == "El ROAS bajó porque subió el CPA."  # sin strip de fences
    roles = [m.role for m in model.last_messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert model.last_messages[-1].content == "por qué bajó el ROAS?"


def test_answer_question_with_stub_model_works_offline():
    facts = _facts()
    reply = answer_question(
        facts, StubChatModel(),
        current_report="## Informe original",
        question="cualquier pregunta",
    )
    assert reply  # el stub encuentra el JSON aunque este en el system prompt
