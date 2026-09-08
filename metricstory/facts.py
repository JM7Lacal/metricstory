"""Hechos estructurados que produce la capa deterministica.

Esto es lo unico que ve el modelo de IA: numeros ya calculados y validados.
El modelo redacta sobre estos hechos, no los calcula ni ve el CSV crudo.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any


@dataclass
class MetricBlock:
    """Indicadores de un periodo, para el total o para una campaña."""

    spend: float
    impressions: int
    clicks: int
    conversions: float | None
    conversion_value: float | None

    ctr: float | None          # clicks / impressions
    cpc: float | None          # spend / clicks
    cpm: float | None          # spend / impressions * 1000
    cpa: float | None          # spend / conversions
    roas: float | None         # conversion_value / spend
    conversion_rate: float | None  # conversions / clicks


@dataclass
class CampaignFacts:
    name: str
    current: MetricBlock
    previous: MetricBlock | None
    spend_share: float                 # participacion en la inversion del periodo actual
    deltas: dict[str, float | None]    # variacion relativa vs periodo anterior por metrica


@dataclass
class BudgetPacing:
    monthly_budget: float
    spent: float
    days_elapsed: int
    days_in_period: int

    @property
    def spent_pct(self) -> float:
        return self.spent / self.monthly_budget if self.monthly_budget else 0.0

    @property
    def expected_pct(self) -> float:
        return self.days_elapsed / self.days_in_period if self.days_in_period else 0.0

    @property
    def projected_spend(self) -> float:
        if not self.days_elapsed:
            return 0.0
        return self.spent / self.days_elapsed * self.days_in_period


@dataclass
class ReportFacts:
    """Todo lo que necesita el redactor, ya masticado."""

    account_currency: str
    current_period: tuple[date, date]
    previous_period: tuple[date, date] | None
    total_current: MetricBlock
    total_previous: MetricBlock | None
    total_deltas: dict[str, float | None]
    campaigns: list[CampaignFacts]
    budget: BudgetPacing | None
    notes: list[str]                   # avisos de la capa de datos (columnas faltantes, etc.)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["current_period"] = [x.isoformat() for x in self.current_period]
        if self.previous_period:
            d["previous_period"] = [x.isoformat() for x in self.previous_period]
        if self.budget:
            b = self.budget
            d["budget"].update(
                spent_pct=round(b.spent_pct, 4),
                expected_pct=round(b.expected_pct, 4),
                projected_spend=round(b.projected_spend, 2),
            )
        return d
