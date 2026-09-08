"""La capa de servicio: que elija bien el proveedor y su config, y que
propague el ChatModelError sin envolverlo en otra cosa."""

import pandas as pd
import pytest

from metricstory import service
from metricstory.columns import guess_mapping
from metricstory.config import AppConfig
from metricstory.llm.base import ChatMessage, ChatModel, ChatModelError
from metricstory.metrics import build_facts
from metricstory.report import QA


def _facts():
    rows = [{
        "Reporting starts": f"2026-01-{i + 1:02d}", "Campaign name": "A",
        "Amount spent (USD)": 100, "Impressions": 10_000, "Link clicks": 200,
        "Purchases": 15, "Purchases conversion value": 300,
    } for i in range(20)]
    df = pd.DataFrame(rows)
    return build_facts(df, guess_mapping(list(df.columns)), period_days=10)


class _FakeModel(ChatModel):
    name = "fake"

    def __init__(self, reply="ok", **cfg):
        self.reply = reply
        self.cfg = cfg

    def complete(self, messages: list[ChatMessage], *, temperature: float = 0.4) -> str:
        return self.reply


@pytest.fixture
def wired(monkeypatch):
    built = {}

    def fake_build(provider, config):
        built["provider"] = provider
        built["config"] = config
        return _FakeModel(reply="INFORME")

    monkeypatch.setattr(service, "build_model", fake_build)
    return built


def test_generate_uses_selected_provider_and_returns_report(wired):
    cfg = AppConfig(provider="anthropic", provider_config={"model": "x"})
    out = service.generate(_facts(), cfg, tone="cliente", provider="anthropic")
    assert out.markdown == "INFORME"
    assert wired["provider"] == "anthropic"
    assert wired["config"] == {"model": "x"}  # es el proveedor elegido -> lleva su config


def test_config_not_passed_to_a_different_provider(wired):
    cfg = AppConfig(provider="anthropic", provider_config={"model": "x"})
    service.generate(_facts(), cfg, tone="cliente", provider="ollama")
    assert wired["provider"] == "ollama"
    assert wired["config"] == {}  # otro proveedor -> defaults del adapter


def test_ask_passes_history(monkeypatch):
    seen = {}

    class _Recorder(_FakeModel):
        def complete(self, messages, *, temperature=0.4):
            seen["messages"] = messages
            return "respuesta"

    monkeypatch.setattr(service, "build_model", lambda p, c: _Recorder())
    service.ask(
        _facts(), AppConfig(),
        current_report="## Informe", question="y ahora?",
        history=[QA(question="antes?", answer="valor")],
        tone="cliente", provider="stub",
    )
    roles = [m.role for m in seen["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_service_propagates_chatmodelerror(monkeypatch):
    def boom(*_a, **_k):
        raise ChatModelError("sin API key")

    monkeypatch.setattr(service, "build_model", boom)
    with pytest.raises(ChatModelError):
        service.generate(_facts(), AppConfig(), tone="cliente", provider="anthropic")
