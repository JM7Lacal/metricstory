from metricstory.config import AppConfig

TOML = """\
provider = "anthropic"

[providers.anthropic]
model = "claude-sonnet-5"
api_key_env = "ANTHROPIC_API_KEY"

[providers.openai]
model = "gpt-4o-mini"

[report]
account_currency = "ARS"
monthly_budget = 500000
default_tone = "interno"
temperature = 0.2
"""


def test_load_reads_selected_provider_and_its_config(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(TOML, encoding="utf-8")

    cfg = AppConfig.load(p)

    assert cfg.provider == "anthropic"
    assert cfg.provider_config == {"model": "claude-sonnet-5", "api_key_env": "ANTHROPIC_API_KEY"}
    assert cfg.account_currency == "ARS"
    assert cfg.monthly_budget == 500000
    assert cfg.default_tone == "interno"
    assert cfg.temperature == 0.2


def test_load_returns_defaults_when_file_missing(tmp_path):
    cfg = AppConfig.load(tmp_path / "no-existe.toml")
    assert cfg.provider == "stub"
    assert cfg.provider_config == {}
    assert cfg.default_tone == "cliente"


def test_load_provider_config_is_empty_for_unlisted_provider(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('provider = "ollama"\n[providers.anthropic]\nmodel = "x"\n', encoding="utf-8")
    cfg = AppConfig.load(p)
    assert cfg.provider == "ollama"
    assert cfg.provider_config == {}
