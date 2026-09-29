# MetricStory

From campaign metrics to the report you send the client.

## The problem

Every month, at a digital marketing agency, someone has to turn the metrics
export from Meta Ads (or Google Ads) into a report a non-technical client
can understand: what happened, why it matters, what we recommend for the
next period. It's a repetitive task that still requires judgment — the
perfect fit for well-applied AI.

## How it works

```
Ad platform CSV
        │
        ▼
 tolerant column mapping        (columns.py — handles English/Spanish
        │                        headers, different platforms)
        ▼
 deterministic layer            (metrics.py — CTR, CPC, CPA, ROAS,
        │                        comparison vs. previous period,
        │                        budget pacing. 100% tested,
        │                        zero AI here)
        ▼
 structured facts (JSON)        (facts.py)
        │
        ▼
 AI-written narrative           (report.py + llm/ — the model receives
        │                        ONLY the facts JSON, never the raw
        │                        CSV. It can't invent a number that
        │                        isn't there)
        ▼
 Markdown report → export to .md / printable .html
```

`app.py` (UI) never calls `report.py` or `llm/` directly: it goes through
`service.py`, the application layer. That way the same flow can be reused
from a CLI or an API without touching the UI, and `service.py` is testable
without Streamlit.

**Core design rule:** the AI never calculates a number; it only narrates
numbers already computed and validated by deterministic code. This keeps
it from hallucinating figures — the most obvious risk of this kind of tool.

## Swappable AI providers

Same pattern I used in another project (Foundry, a WPF editor): the rest
of the program depends only on the `ChatModel` port (`llm/base.py`), not
on a concrete provider. Switching providers is one line in `config.toml`,
no code changes:

| Provider | Use |
|---|---|
| `stub` | No network, no API key. For offline demos and tests (deterministic output). |
| `anthropic` | Anthropic Messages API directly. |
| `openai` | OpenAI (or any compatible endpoint: Azure, Groq, OpenRouter...). |
| `ollama` | Local model — useful when the client's CSV is sensitive and can't leave the machine. |
| `claude-cli` | Uses the already-logged-in Claude Code CLI (`claude -p`), no separate API key. |

Adding a new provider: one file in `metricstory/llm/`, register it in
`factory.py`. Nothing else needs to know.

## Running locally

Requires Python 3.11+ (developed with 3.12).

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/python -m streamlit run app.py
```

By default it uses the synthetic CSV in `samples/meta-ads-sample.csv`
(real Meta Ads Manager schema, 6 campaigns × 60 days, with a deliberate
storyline: a seasonal campaign that takes off, another that deteriorates,
one that should be paused).

The UI and the generated reports are in Spanish (the target audience is
Spanish-speaking agencies).

## Configuration (`config.toml`)

```toml
provider = "claude-cli"          # one word, no rebuild

[report]
account_currency = "USD"
monthly_budget = 18000
default_tone = "cliente"         # cliente (client) | interno (internal) | ejecutivo (executive)
```

`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` go in environment variables, not
in the file.

## Tests

```bash
.venv/Scripts/python -m pytest
```

They cover: column mapping (English/Spanish headers), parsing numbers and
dates in regional formats, metric calculation and period-over-period
deltas, budget pacing, that the prompt passes the model only the facts
JSON (never prose with unvalidated data), the service layer (provider
selection and its config), response parsing for each AI adapter (with
the network mocked) and the Markdown/HTML export.

## What I'd do next

- Persistent column mapping per platform template (Meta / Google Ads /
  GA4), so it doesn't need reconfiguring every month.
- Comparing more than 2 periods (trend, not just delta).
- Per-client brand voice (glossary, tone, disclaimers) stored separately
  from the generic prompt.
- Cache of generated reports + per-client history.
