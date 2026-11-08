"""Malaisie : prix hebdomadaires fixés par le ministère (KPDN), publiés en
données ouvertes (data.gov.my, CC BY 4.0). Identiques dans tout le pays
(le diesel de Malaisie orientale est repris tel quel pour l'ouest)."""
from datetime import datetime, timezone

from ..common import Country, fetch_json
from .. import national

COUNTRY = Country("MY", "MYR", "KPDN via data.gov.my", "https://data.gov.my/data-catalogue/fuelprice", 0.5, 20.0)
URL = "https://api.data.gov.my/data-catalogue?id=fuelprice"


def load():
    rows = fetch_json(URL, timeout=60, max_bytes=4 * 1024 * 1024)
    if not isinstance(rows, list):
        raise ValueError("réponse inattendue")
    levels = [r for r in rows if isinstance(r, dict) and r.get("series_type") == "level" and isinstance(r.get("date"), str)]
    if not levels:
        raise ValueError("aucune ligne de niveau")
    last = max(levels, key=lambda r: r["date"])
    when = datetime.strptime(last["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return national.build(
        COUNTRY,
        {"petrol95": last.get("ron95"), "premium98": last.get("ron97"), "diesel": last.get("diesel")},
        price_date=when,
        note="Prix non subventionnés (RON95, RON97, diesel) ; le prix BUDI95 subventionné réservé aux résidents n'est pas repris.",
    )
