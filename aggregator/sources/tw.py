"""Taïwan : prix de référence hebdomadaires de la CPC (compagnie pétrolière
publique), données ouvertes (Open Government Data License 1.0). Les autres
enseignes s'alignent à quelques centimes près."""
from datetime import datetime, timezone

from ..common import Country, clean, fetch_json, number
from .. import national

COUNTRY = Country("TW", "TWD", "CPC Corporation (données ouvertes)",
                  "https://vipmbr.cpc.com.tw/opendata/swagger/index.html", 10.0, 100.0)
URL = "https://vipmbr.cpc.com.tw/opendata/mainprodlistprice"
NAMES = {"95無鉛汽油": "petrol95", "98無鉛汽油": "premium98", "超級柴油": "diesel"}


def _roc_date(value: str):
    """« 1151109 » = année 115 de la République (2026), 9 novembre."""
    v = clean(value, 8)
    if len(v) != 7 or not v.isdigit():
        return None
    try:
        return datetime(int(v[:3]) + 1911, int(v[3:5]), int(v[5:7]), tzinfo=timezone.utc)
    except ValueError:
        return None


def load():
    rows = fetch_json(URL, timeout=60, max_bytes=1024 * 1024)
    if not isinstance(rows, list):
        raise ValueError("réponse inattendue")
    prices = {}
    when = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        col = NAMES.get(clean(r.get("產品名稱"), 20))
        if col is None or clean(r.get("交貨地點"), 20) != "中油自營站":
            continue
        p = number(r.get("參考牌價_金額"))
        if p is None:
            continue
        prices[col] = p
        d = _roc_date(r.get("牌價生效日期", ""))
        if d is not None and (when is None or d > when):
            when = d
    if when is not None and when > datetime.now(timezone.utc):
        when = datetime.now(timezone.utc)  # le tarif de lundi est publié dimanche
    return national.build(COUNTRY, prices, price_date=when, note="Prix de référence CPC, par litre.")
