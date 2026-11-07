"""Slovénie : goriva.si (Ministère de l'économie), API publique paginée."""
from ..common import Country, Station, clean, coord, fetch_json, now_minutes, price, finalize, title_case

COUNTRY = Country("SI", "EUR", "goriva.si", "https://goriva.si", 0.2, 5.0)
URL = ("https://goriva.si/api/v1/search/?position=Slovenija&radius=200000"
       "&franchise=&name=&o=&page={page}")
FIELDS = (("dizel", "diesel"), ("95", "petrol95"), ("98", "premium98"),
          ("100", "premium98"), ("avtoplin-lpg", "lpg"))
MAX_PAGES = 80


def load():
    out = []
    maj = now_minutes()
    for page in range(1, MAX_PAGES + 1):
        doc = fetch_json(URL.format(page=page), timeout=60)
        results = doc.get("results") if isinstance(doc, dict) else None
        if not isinstance(results, list):
            raise ValueError("réponse inattendue")
        for r in results:
            if not isinstance(r, dict) or not isinstance(r.get("prices"), dict):
                continue
            rid = str(r.get("pk") or "")
            c = coord(r.get("lat"), r.get("lng"))
            if not rid.isdigit() or c is None:
                continue
            s = Station(rid, c[0], c[1], clean(r.get("zip_code"), 8), "",
                        title_case(clean(r.get("name"), 60)), maj=maj)
            addr = title_case(clean(r.get("address"), 100))
            if addr:
                s.address = f"{s.address} · {addr}" if s.address else addr
            for key, col in FIELDS:
                p = price(r["prices"].get(key), COUNTRY)
                idx = ["diesel", "petrol95", "e10", "premium98", "e85", "lpg"].index(col)
                if p is not None and (s.prices[idx] is None or p < s.prices[idx]):
                    s.prices[idx] = p
            out.append(s)
        if not doc.get("next"):
            break
    return finalize(COUNTRY, out, 200)
