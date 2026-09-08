"""Cubre los parsers 'sucios' de metrics.py: son la parte mas bug-prone del
repo (formatos de numero y fecha que varian por idioma/region del export)."""

import math

import pandas as pd
import pytest

from metricstory.metrics import _parse_dates, _to_number


def _num(values: list) -> list[float]:
    return list(_to_number(pd.Series(values)))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1234.56", 1234.56),          # US plano
        ("1,234.56", 1234.56),         # US con agrupador de miles
        ("$ 1,234.56", 1234.56),       # con simbolo de moneda
        ("1.234,56", 1234.56),         # LATAM/EU: coma decimal
        ("1.234", 1.234),             # punto solo -> decimal (ambiguo con miles EU; decimal es el default seguro para importes)
        ("1234", 1234.0),
        ("12,5", 12.5),                # coma decimal con 1-2 digitos
        ("1,234,567", 1234567.0),      # miles con coma, sin decimal
        ("1.234.567", 1234567.0),      # miles con punto, sin decimal
        ("-50.25", -50.25),
    ],
)
def test_to_number_parses_regional_formats(raw, expected):
    assert _num([raw])[0] == pytest.approx(expected)


def test_to_number_preserves_nan_for_empty_cells():
    out = _num(["", "  ", None])
    assert all(math.isnan(v) for v in out)


def test_to_number_passes_through_numeric_series():
    assert _num([10, 20.5, 30]) == [10.0, 20.5, 30.0]


def test_parse_dates_handles_iso_without_dayfirst_confusion():
    # '2026-01-12' NO debe leerse como 1 de diciembre
    parsed = _parse_dates(pd.Series(["2026-01-12", "2026-01-13"]))
    assert parsed.iloc[0].month == 1 and parsed.iloc[0].day == 12


def test_parse_dates_falls_back_to_dayfirst_for_dd_mm_yyyy():
    # dias > 12: sin dayfirst quedan NaT -> dispara el fallback
    parsed = _parse_dates(pd.Series(["13/02/2026", "14/02/2026", "15/02/2026"]))
    assert parsed.notna().all()
    assert parsed.iloc[0].month == 2 and parsed.iloc[0].day == 13
