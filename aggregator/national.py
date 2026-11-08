"""Pays où le prix ne dépend pas de la station : positions OpenStreetMap,
prix issu d'une source officielle unique.

Trois modes, indiqués dans le document (`priceMode`) pour que l'application
affiche la bonne mention et ne « compare » pas des prix identiques :

* `national` : prix fixé par l'État, identique partout ;
* `brand`    : prix d'enseigne, identique dans toutes les stations de la
               marque (les stations d'enseigne inconnue sont omises) ;
* `average`  : moyenne nationale indicative (la station peut différer).
"""
from __future__ import annotations

from datetime import datetime

from . import osm
from .common import Country, SourceError, finalize, minutes, now_minutes, price

MODES = ("national", "brand", "average")


def build(country: Country, prices: dict[str, float | None] | None = None, *,
          price_date: datetime | None, mode: str = "national", min_count: int = 50,
          note: str = "", brand_prices: dict[str, dict[str, float | None]] | None = None) -> dict:
    """`prices` : colonne -> prix (None = carburant non vendu).
    `brand_prices` (mode brand) : enseigne (minuscules) -> {colonne: prix}."""
    if mode not in MODES:
        raise ValueError(mode)
    stations, fetched = osm.stations(country, min_count)
    maj = minutes(price_date) or now_minutes()
    if mode == "brand":
        if not brand_prices:
            raise SourceError(f"{country.code} : aucun prix d'enseigne")
        table = {k.lower(): {c: price(v, country) for c, v in p.items()} for k, p in brand_prices.items()}
        kept = []
        for s in stations:
            key = _match(getattr(s, "brand", ""), table) or _match(s.address, table)
            if key is None:
                continue
            for col, v in table[key].items():
                s.set(col, v)
            s.maj = maj
            kept.append(s)
        stations = kept
    else:
        if not prices:
            raise SourceError(f"{country.code} : aucun prix national")
        cleaned = {col: price(v, country) for col, v in prices.items()}
        if not any(v is not None for v in cleaned.values()):
            raise SourceError(f"{country.code} : aucun prix national plausible ({prices})")
        for s in stations:
            for col, v in cleaned.items():
                s.set(col, v)
            s.maj = maj
    doc = finalize(country, stations, min_count)
    doc["priceMode"] = mode
    doc["osmFetched"] = fetched
    doc["source"]["positions"] = osm.ATTRIBUTION
    if note:
        doc["source"]["note"] = note
    return doc


def _match(text: str, table: dict) -> str | None:
    t = (text or "").lower()
    if not t:
        return None
    for key in table:
        if key in t:
            return key
    return None
