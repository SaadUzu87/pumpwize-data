"""Hong Kong : prix affichés par enseigne (Consumer Council, « Pump Prices
of Auto-Fuels », data.gov.hk). Chaque enseigne pratique le même prix dans
toutes ses stations ; l'essence courante y est du 98 (colonne SP98)."""
from datetime import datetime, timezone

from ..common import Country, clean, fetch_json
from .. import national

COUNTRY = Country("HK", "HKD", "Consumer Council (data.gov.hk)",
                  "https://www.consumer.org.hk/pricewatch/oilwatch", 5.0, 100.0)
URL = "https://www.consumer.org.hk/pricewatch/oilwatch/opendata/oilprice.json"
TYPES = {"standard petrol": "premium98", "diesel": "diesel"}
# Enseigne (clé anglaise) -> variantes rencontrées dans les étiquettes OSM
ALIASES = {
    "shell": ("shell", "蜆殼"),
    "esso": ("esso", "埃索"),
    "caltex": ("caltex", "加德士"),
    "sinopec": ("sinopec", "中石化", "中國石化", "中国石化"),
    "petrochina": ("petrochina", "中國石油", "中国石油", "中石油"),
}


def load():
    doc = fetch_json(URL, timeout=60, max_bytes=512 * 1024)
    if not isinstance(doc, list):
        raise ValueError("réponse inattendue")
    by_brand: dict[str, dict] = {}
    for block in doc:
        if not isinstance(block, dict):
            continue
        kind = clean((block.get("type") or {}).get("en"), 30).lower()
        col = TYPES.get(kind)
        if col is None:
            continue
        for p in block.get("prices") or []:
            if not isinstance(p, dict):
                continue
            vendor = clean((p.get("vendor") or {}).get("en"), 20).lower()
            for key, names in ALIASES.items():
                if vendor in names:
                    for alias in names:
                        by_brand.setdefault(alias, {})[col] = p.get("price")
    if not by_brand:
        raise ValueError("aucun prix d'enseigne")
    return national.build(COUNTRY, mode="brand", brand_prices=by_brand,
                          price_date=datetime.now(timezone.utc),
                          note="Prix affichés par enseigne avant remises ; l'essence courante est du 98.")
