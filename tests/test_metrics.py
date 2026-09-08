from datetime import date, timedelta

import pandas as pd
import pytest

from metricstory.columns import guess_mapping
from metricstory.metrics import build_facts, normalize


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


HEADERS = {
    "date": "Reporting starts",
    "campaign": "Campaign name",
    "spend": "Amount spent (USD)",
    "impressions": "Impressions",
    "clicks": "Link clicks",
    "conversions": "Purchases",
    "conversion_value": "Purchases conversion value",
}


def _row(day: date, campaign: str, spend, impressions, clicks, conversions, value):
    return {
        HEADERS["date"]: day.isoformat(),
        HEADERS["campaign"]: campaign,
        HEADERS["spend"]: spend,
        HEADERS["impressions"]: impressions,
        HEADERS["clicks"]: clicks,
        HEADERS["conversions"]: conversions,
        HEADERS["conversion_value"]: value,
    }


def _two_period_dataset() -> pd.DataFrame:
    start = date(2026, 1, 1)
    rows = []
    for i in range(20):
        day = start + timedelta(days=i)
        # periodo anterior (dias 0-9): peor; periodo actual (dias 10-19): mejor
        better = i >= 10
        rows.append(_row(
            day, "Campaña A",
            spend=100, impressions=10_000, clicks=200,
            conversions=20 if better else 10,
            value=400 if better else 150,
        ))
    return _make_df(rows)


def test_normalize_requires_mapped_columns():
    df = _two_period_dataset()
    mapping = guess_mapping(list(df.columns))
    normalized = normalize(df, mapping)
    assert len(normalized) == 20
    assert set(normalized.columns) >= {"date", "campaign", "spend", "impressions", "clicks"}


def test_build_facts_computes_expected_totals_and_deltas():
    df = _two_period_dataset()
    mapping = guess_mapping(list(df.columns))
    facts = build_facts(df, mapping, account_currency="USD", period_days=10)

    # 10 dias * 100 de spend = 1000 en cada periodo
    assert facts.total_current.spend == pytest.approx(1000.0)
    assert facts.total_previous.spend == pytest.approx(1000.0)

    # conversion_value actual = 10*400=4000, spend=1000 -> ROAS 4.0
    assert facts.total_current.roas == pytest.approx(4.0)
    # anterior: 10*150=1500/1000 -> ROAS 1.5
    assert facts.total_previous.roas == pytest.approx(1.5)

    # delta de ROAS: (4.0-1.5)/1.5
    assert facts.total_deltas["roas"] == pytest.approx((4.0 - 1.5) / 1.5)

    assert len(facts.campaigns) == 1
    assert facts.campaigns[0].spend_share == pytest.approx(1.0)


def test_build_facts_without_conversion_columns_sets_notes_and_none_metrics():
    start = date(2026, 1, 1)
    rows = [
        {
            HEADERS["date"]: (start + timedelta(days=i)).isoformat(),
            HEADERS["campaign"]: "Branding",
            HEADERS["spend"]: 50,
            HEADERS["impressions"]: 5000,
            HEADERS["clicks"]: 100,
        }
        for i in range(6)
    ]
    df = _make_df(rows)
    mapping = guess_mapping(list(df.columns))
    facts = build_facts(df, mapping)

    assert facts.total_current.roas is None
    assert facts.total_current.cpa is None
    assert any("conversiones" in n or "conversion" in n for n in facts.notes)


def test_build_facts_treats_blank_conversion_cells_as_missing_not_zero():
    """Una campaña de alcance que no trackea conversiones no tuvo *cero*
    conversiones: simplemente no se mide. roas/cpa deben quedar en None, no 0.0
    (regresion: fillna(0) sobre columnas opcionales rompia esta distincion)."""
    start = date(2026, 1, 1)
    rows = [
        _row(start + timedelta(days=i), "Branding", 50, 5000, 100, "", "")
        for i in range(6)
    ]
    df = _make_df(rows)
    mapping = guess_mapping(list(df.columns))
    facts = build_facts(df, mapping)

    assert facts.total_current.roas is None
    assert facts.total_current.cpa is None
    assert facts.campaigns[0].current.roas is None


def test_build_facts_raises_on_missing_required_columns():
    df = _make_df([{"foo": 1, "bar": 2}])
    mapping = guess_mapping(list(df.columns))
    with pytest.raises(ValueError):
        build_facts(df, mapping)


def test_build_facts_truncates_to_top_n_campaigns_and_notes_it():
    start = date(2026, 1, 1)
    rows = []
    for c in range(15):
        for i in range(4):
            rows.append(_row(
                start + timedelta(days=i), f"Campaña {c:02d}",
                spend=100 - c, impressions=1000, clicks=20, conversions=1, value=10,
            ))
    df = _make_df(rows)
    mapping = guess_mapping(list(df.columns))
    facts = build_facts(df, mapping, top_n_campaigns=5)

    assert len(facts.campaigns) == 5
    # ordenadas por inversion desc: la #0 gasta mas que la #14
    assert facts.campaigns[0].current.spend >= facts.campaigns[-1].current.spend
    assert any("15" in n and "5" in n for n in facts.notes)


def test_budget_pacing_projects_linearly():
    df = _two_period_dataset()
    mapping = guess_mapping(list(df.columns))
    facts = build_facts(df, mapping, monthly_budget=2000, period_days=10)

    assert facts.budget is not None
    assert facts.budget.spent == pytest.approx(1000.0)
    # 10 dias transcurridos de 10 del periodo -> pacing 100%, proyectado = spend actual
    assert facts.budget.days_elapsed == 10
    assert facts.budget.projected_spend == pytest.approx(1000.0)
