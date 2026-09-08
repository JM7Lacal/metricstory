"""Capa deterministica: CSV normalizado -> ReportFacts.

Sin IA. Todo lo que sale de aca es aritmetica reproducible y testeable.
"""

from __future__ import annotations

import warnings
from datetime import date, timedelta

import pandas as pd

from .columns import ColumnMapping
from .facts import (
    BudgetPacing,
    CampaignFacts,
    MetricBlock,
    ReportFacts,
)

# Metricas sobre las que reportamos variacion periodo a periodo.
DELTA_METRICS = ["spend", "impressions", "clicks", "conversions", "conversion_value",
                 "ctr", "cpc", "cpm", "cpa", "roas", "conversion_rate"]


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def _to_number(series: pd.Series) -> pd.Series:
    """Convierte texto tipo '1.234,56' o '$ 1,234.56' a numero.

    Preserva NaN para celdas vacias: "sin dato" y "cero" son cosas distintas
    (p. ej. una campaña de alcance que no trackea conversiones no tuvo *cero*
    conversiones, simplemente no se mide esa metrica). Rellenar con 0 haria
    que el informe reporte ROAS 0.00 en vez de "sin dato".
    """
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)

    cleaned = (
        series.astype(str)
        .str.replace(r"[^\d,.\-]", "", regex=True)
        .str.strip()
    )

    def parse(v: str) -> float:
        if not v or v in {"-", ".", ","}:
            return float("nan")
        if "," in v and "." in v:
            # el ultimo separador es el decimal
            if v.rfind(",") > v.rfind("."):
                v = v.replace(".", "").replace(",", ".")
            else:
                v = v.replace(",", "")
        elif v.count(",") > 1:
            v = v.replace(",", "")  # 1,234,567 -> agrupador de miles
        elif v.count(".") > 1:
            v = v.replace(".", "")  # 1.234.567 -> agrupador de miles
        elif "," in v:
            # coma como decimal si hay 1-2 digitos despues
            head, _, tail = v.rpartition(",")
            v = f"{head}.{tail}" if len(tail) in (1, 2) else v.replace(",", "")
        try:
            return float(v)
        except ValueError:
            return float("nan")

    return cleaned.map(parse)


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parsea fechas sin asumir un formato fijo.

    ``dayfirst=True`` a ciegas rompe fechas ISO (``2026-01-12`` termina
    leyendose como 2026-12-01): pandas/dateutil pueden aplicar la preferencia
    dayfirst incluso cuando el año ya viene primero. Por eso se intenta
    primero sin esa opcion (cubre ISO, que es lo que exporta Meta Ads) y solo
    se usa dayfirst como fallback si ese primer intento deja demasiadas fechas
    sin parsear (formato DD/MM/YYYY, comun en exports europeos).
    """
    # El primer intento (sin dayfirst) puede quejarse con formatos DD/MM: es
    # esperado, para eso esta el fallback de abajo. Silenciamos ese warning.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(series, errors="coerce")
        if len(series) and parsed.isna().mean() > 0.3:
            parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return parsed


def normalize(df: pd.DataFrame, mapping: ColumnMapping) -> pd.DataFrame:
    """Aplica el mapeo y devuelve un DataFrame con las columnas canonicas."""
    if not mapping.is_complete:
        raise ValueError(
            "Faltan columnas obligatorias: " + ", ".join(mapping.missing_required)
        )

    out = pd.DataFrame()
    out["date"] = _parse_dates(df[mapping.source_for("date")])
    out["campaign"] = df[mapping.source_for("campaign")].astype(str).str.strip()
    for numeric in ["spend", "impressions", "clicks"]:
        # obligatorios: una celda vacia se trata como 0, no como "sin dato".
        out[numeric] = _to_number(df[mapping.source_for(numeric)]).fillna(0)
    for numeric in ["conversions", "conversion_value"]:
        # opcionales: NaN se preserva, distingue "no trackeado" de "cero".
        src = mapping.source_for(numeric)
        out[numeric] = _to_number(df[src]) if src else float("nan")

    out = out.dropna(subset=["date"])
    out = out[out["campaign"].str.len() > 0]
    return out.reset_index(drop=True)


def _block(rows: pd.DataFrame) -> MetricBlock:
    spend = float(rows["spend"].sum())
    impressions = int(rows["impressions"].sum())
    clicks = int(rows["clicks"].sum())
    has_conv = rows["conversions"].notna().any()
    has_val = rows["conversion_value"].notna().any()
    conversions = float(rows["conversions"].sum()) if has_conv else None
    conversion_value = float(rows["conversion_value"].sum()) if has_val else None

    return MetricBlock(
        spend=round(spend, 2),
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        conversion_value=round(conversion_value, 2) if conversion_value is not None else None,
        ctr=_safe_div(clicks, impressions),
        cpc=_safe_div(spend, clicks),
        cpm=_safe_div(spend * 1000, impressions),
        cpa=_safe_div(spend, conversions),
        roas=_safe_div(conversion_value, spend),
        conversion_rate=_safe_div(conversions, clicks),
    )


def _deltas(cur: MetricBlock, prev: MetricBlock | None) -> dict[str, float | None]:
    if prev is None:
        return {m: None for m in DELTA_METRICS}
    result: dict[str, float | None] = {}
    for m in DELTA_METRICS:
        a = getattr(cur, m)
        b = getattr(prev, m)
        result[m] = _safe_div((a - b) if (a is not None and b is not None) else None, b)
    return result


def _split_periods(
    df: pd.DataFrame, period_days: int | None
) -> tuple[tuple[date, date], tuple[date, date] | None]:
    """Define periodo actual y anterior como ventanas contiguas del mismo largo.

    Si `period_days` no se especifica, usa la mitad del rango disponible.
    """
    min_d = df["date"].min().date()
    max_d = df["date"].max().date()
    span = (max_d - min_d).days + 1

    if period_days is None:
        period_days = max(1, span // 2)

    cur_start = max_d - timedelta(days=period_days - 1)
    current = (cur_start, max_d)

    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)
    previous = (prev_start, prev_end) if prev_start >= min_d else None
    return current, previous


def _mask(df: pd.DataFrame, period: tuple[date, date]) -> pd.Series:
    start, end = period
    d = df["date"].dt.date
    return (d >= start) & (d <= end)


def build_facts(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    *,
    account_currency: str = "USD",
    monthly_budget: float | None = None,
    period_days: int | None = None,
    top_n_campaigns: int = 12,
) -> ReportFacts:
    norm = normalize(df, mapping)
    if norm.empty:
        raise ValueError("El CSV no tiene filas validas despues de normalizar.")

    notes: list[str] = []
    if mapping.source_for("conversions") is None:
        notes.append("Sin columna de conversiones: se omiten CPA y tasa de conversion.")
    if mapping.source_for("conversion_value") is None:
        notes.append("Sin columna de valor de conversion: se omite ROAS.")

    current, previous = _split_periods(norm, period_days)

    cur_rows = norm[_mask(norm, current)]
    prev_rows = norm[_mask(norm, previous)] if previous else norm.iloc[0:0]

    total_current = _block(cur_rows)
    total_previous = _block(prev_rows) if previous and not prev_rows.empty else None
    total_deltas = _deltas(total_current, total_previous)

    campaigns: list[CampaignFacts] = []
    for name, group in cur_rows.groupby("campaign"):
        cur_block = _block(group)
        prev_group = prev_rows[prev_rows["campaign"] == name] if previous else None
        prev_block = (
            _block(prev_group) if prev_group is not None and not prev_group.empty else None
        )
        campaigns.append(
            CampaignFacts(
                name=str(name),
                current=cur_block,
                previous=prev_block,
                spend_share=_safe_div(cur_block.spend, total_current.spend) or 0.0,
                deltas=_deltas(cur_block, prev_block),
            )
        )

    campaigns.sort(key=lambda c: c.current.spend, reverse=True)
    if len(campaigns) > top_n_campaigns:
        notes.append(
            f"Se detallan las {top_n_campaigns} campañas de mayor inversion "
            f"de un total de {len(campaigns)}."
        )
        campaigns = campaigns[:top_n_campaigns]

    budget = None
    if monthly_budget:
        days_in_period = (current[1] - current[0]).days + 1
        days_elapsed = (cur_rows["date"].max().date() - current[0]).days + 1
        budget = BudgetPacing(
            monthly_budget=float(monthly_budget),
            spent=total_current.spend,
            days_elapsed=days_elapsed,
            days_in_period=days_in_period,
        )

    return ReportFacts(
        account_currency=account_currency,
        current_period=current,
        previous_period=previous,
        total_current=total_current,
        total_previous=total_previous,
        total_deltas=total_deltas,
        campaigns=campaigns,
        budget=budget,
        notes=notes,
    )
