"""Mapeo tolerante de columnas.

El export de Meta Ads Manager (y de otras plataformas) trae nombres de columna
que cambian segun el idioma de la cuenta, la moneda y las columnas elegidas al
exportar. En vez de acoplar el resto del programa a un formato exacto, todo el
codigo aguas abajo trabaja con un esquema canonico y este modulo se encarga de
llevar cualquier CSV a ese esquema.

Campos canonicos (una fila = una campaña en un dia):

    date            fecha del dato
    campaign        nombre de la campaña
    spend           inversion en la moneda de la cuenta
    impressions     impresiones
    clicks          clicks en el enlace
    conversions     resultados / compras
    conversion_value  valor de conversion (ingresos atribuidos)

`spend`, `impressions` y `clicks` son obligatorios. `conversions` y
`conversion_value` son opcionales: sin ellos se omiten CPA y ROAS.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CANONICAL_FIELDS = [
    "date",
    "campaign",
    "spend",
    "impressions",
    "clicks",
    "conversions",
    "conversion_value",
]

REQUIRED_FIELDS = ["date", "campaign", "spend", "impressions", "clicks"]

# Sinonimos conocidos, en minuscula y sin espacios de sobra. Cubren los headers
# que exporta Meta Ads Manager en ingles y español, mas variantes habituales de
# Google Ads y GA4.
KNOWN_ALIASES: dict[str, list[str]] = {
    "date": [
        "date",
        "day",
        "reporting starts",
        "fecha",
        "dia",
        "inicio del informe",
        "date range",
    ],
    "campaign": [
        "campaign name",
        "campaign",
        "nombre de la campaña",
        "campaña",
        "ad set name",
        "nombre del conjunto de anuncios",
    ],
    "spend": [
        "amount spent",
        "amount spent (usd)",
        "amount spent (ars)",
        "spend",
        "cost",
        "importe gastado",
        "importe gastado (usd)",
        "importe gastado (ars)",
        "gasto",
        "inversion",
    ],
    "impressions": [
        "impressions",
        "impr.",
        "impresiones",
    ],
    "clicks": [
        "link clicks",
        "clicks",
        "clicks (all)",
        "clics en el enlace",
        "clics",
        "clics (todos)",
    ],
    "conversions": [
        "purchases",
        "results",
        "conversions",
        "conv.",
        "compras",
        "resultados",
        "conversiones",
    ],
    "conversion_value": [
        "purchases conversion value",
        "conversion value",
        "conv. value",
        "total conversion value",
        "valor de conversion de compras",
        "valor de conversion",
        "valor de conv.",
    ],
}


def _norm(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


@dataclass
class ColumnMapping:
    """Relacion columna-del-CSV -> campo canonico."""

    mapping: dict[str, str] = field(default_factory=dict)  # canonical -> source column

    @property
    def missing_required(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if f not in self.mapping]

    @property
    def is_complete(self) -> bool:
        return not self.missing_required

    def source_for(self, canonical: str) -> str | None:
        return self.mapping.get(canonical)


def guess_mapping(source_columns: list[str]) -> ColumnMapping:
    """Adivina el mapeo a partir de los nombres de columna del CSV.

    Devuelve lo que pudo resolver; la UI permite completar o corregir el resto.
    """
    normalized = {_norm(c): c for c in source_columns}
    resolved: dict[str, str] = {}

    for canonical, aliases in KNOWN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                resolved[canonical] = normalized[alias]
                break

    # Segundo intento: coincidencia por prefijo, util para headers como
    # "Amount spent (USD)" que ya cubrimos, pero tambien "Impressions (total)".
    for canonical, aliases in KNOWN_ALIASES.items():
        if canonical in resolved:
            continue
        for norm_name, original in normalized.items():
            if any(norm_name.startswith(alias) for alias in aliases):
                resolved[canonical] = original
                break

    return ColumnMapping(mapping=resolved)
