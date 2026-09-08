"""Genera samples/meta-ads-sample.csv: un export sintetico con el schema real
de Meta Ads Manager, pero con numeros armados para que el informe tenga algo
interesante que contar (no solo una tabla plana).

Historia de los 60 dias (dos periodos de 30):
- Retargeting - Carrito:      ROAS solido y en alza -> recomendar escalar
- Black Friday - Ofertas:     arranca floja, explota en el segundo periodo (estacional)
- Prospecting - Video LAL:    ROAS y CPA se deterioran -> revisar creatividad
- Prospecting - Intereses:    quema presupuesto, CTR bajo, casi sin conversion -> pausar
- Retargeting - Visitantes:   estable, sin sorpresas
- Branding - Alcance:         CPM bajo, sin objetivo de conversion (deja conversions null)

Determinista (seed fija) para que el demo sea reproducible.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "samples" / "meta-ads-sample.csv"
random.seed(7)

START = date(2026, 7, 6)
DAYS = 60


def daterange():
    for i in range(DAYS):
        yield START + timedelta(days=i)


def jitter(value: float, pct: float = 0.12) -> float:
    return max(0.0, value * (1 + random.uniform(-pct, pct)))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


ROWS: list[dict] = []

for day in daterange():
    t = (day - START).days / (DAYS - 1)  # 0..1 a lo largo del periodo

    # --- Retargeting - Carrito: ROAS sube de ~2.8 a ~4.2 ---
    spend = jitter(lerp(140, 190, t))
    impressions = jitter(lerp(9000, 11000, t))
    ctr = lerp(0.021, 0.026, t)
    clicks = impressions * ctr
    roas = lerp(2.8, 4.2, t)
    conv_value = spend * roas
    conv_rate = lerp(0.07, 0.09, t)
    conversions = clicks * conv_rate
    ROWS.append(dict(
        date=day, campaign="Retargeting - Carrito abandonado", spend=spend,
        impressions=impressions, clicks=clicks, conversions=conversions,
        conversion_value=conv_value,
    ))

    # --- Black Friday - Ofertas: floja primeros 30 dias, explota despues ---
    is_second = t >= 0.5
    spend_bf = jitter(lerp(60, 90, t) if not is_second else lerp(90, 340, (t - 0.5) * 2))
    impressions_bf = jitter(spend_bf / 0.012)
    ctr_bf = 0.018 if not is_second else lerp(0.022, 0.041, (t - 0.5) * 2)
    clicks_bf = impressions_bf * ctr_bf
    roas_bf = 1.6 if not is_second else lerp(2.0, 5.1, (t - 0.5) * 2)
    conv_value_bf = spend_bf * roas_bf
    conversions_bf = clicks_bf * lerp(0.03, 0.06, t)
    ROWS.append(dict(
        date=day, campaign="Black Friday - Ofertas", spend=spend_bf,
        impressions=impressions_bf, clicks=clicks_bf, conversions=conversions_bf,
        conversion_value=conv_value_bf,
    ))

    # --- Prospecting - Video Lookalike: se deteriora ---
    spend_v = jitter(lerp(110, 160, t))
    impressions_v = jitter(lerp(14000, 15500, t))
    ctr_v = lerp(0.016, 0.010, t)  # cae
    clicks_v = impressions_v * ctr_v
    cpa_v = lerp(18, 34, t)  # sube
    conversions_v = spend_v / cpa_v
    roas_v = lerp(2.1, 1.1, t)
    conv_value_v = spend_v * roas_v
    ROWS.append(dict(
        date=day, campaign="Prospecting - Video Lookalike", spend=spend_v,
        impressions=impressions_v, clicks=clicks_v, conversions=conversions_v,
        conversion_value=conv_value_v,
    ))

    # --- Prospecting - Intereses amplios: mal desde el arranque ---
    spend_i = jitter(lerp(95, 105, t))
    impressions_i = jitter(lerp(21000, 23000, t))
    ctr_i = jitter(0.006, 0.2)
    clicks_i = impressions_i * ctr_i
    conversions_i = clicks_i * 0.008
    roas_i = jitter(0.55, 0.25)
    conv_value_i = spend_i * roas_i
    ROWS.append(dict(
        date=day, campaign="Prospecting - Intereses amplios", spend=spend_i,
        impressions=impressions_i, clicks=clicks_i, conversions=conversions_i,
        conversion_value=conv_value_i,
    ))

    # --- Retargeting - Visitantes web: estable ---
    spend_r = jitter(95)
    impressions_r = jitter(7000)
    clicks_r = impressions_r * jitter(0.024, 0.1)
    conversions_r = clicks_r * jitter(0.075, 0.15)
    conv_value_r = spend_r * jitter(3.1, 0.15)
    ROWS.append(dict(
        date=day, campaign="Retargeting - Visitantes web", spend=spend_r,
        impressions=impressions_r, clicks=clicks_r, conversions=conversions_r,
        conversion_value=conv_value_r,
    ))

    # --- Branding - Alcance: sin conversion trackeada (deja vacio) ---
    spend_b = jitter(70)
    impressions_b = jitter(48000)
    clicks_b = impressions_b * jitter(0.008, 0.2)
    ROWS.append(dict(
        date=day, campaign="Branding - Alcance", spend=spend_b,
        impressions=impressions_b, clicks=clicks_b, conversions="", conversion_value="",
    ))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Reporting starts", "Campaign name", "Amount spent (USD)",
        "Impressions", "Link clicks", "Purchases", "Purchases conversion value",
    ]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in ROWS:
            w.writerow({
                "Reporting starts": r["date"].isoformat(),
                "Campaign name": r["campaign"],
                "Amount spent (USD)": round(r["spend"], 2),
                "Impressions": int(r["impressions"]),
                "Link clicks": int(r["clicks"]),
                "Purchases": "" if r["conversions"] == "" else round(r["conversions"], 1),
                "Purchases conversion value": (
                    "" if r["conversion_value"] == "" else round(r["conversion_value"], 2)
                ),
            })
    print(f"OK: {len(ROWS)} filas -> {OUT}")


if __name__ == "__main__":
    main()
