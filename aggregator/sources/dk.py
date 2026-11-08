"""Danemark : depuis le 1er janvier 2026 (brændstofprisbekendtgørelsen § 16a),
chaque enseigne publie ses prix à la pompe par station dans une API
publique. Enseignes branchées : OK et Shell (les autres n'ont pas encore de
documentation trouvable). Couverture partielle."""
from datetime import datetime

from ..common import Country, Station, clean, coord, fetch_json, minutes, now_minutes, price, finalize

COUNTRY = Country("DK", "DKK", "API des enseignes OK et Shell (partiel)",
                  "https://www.kfst.dk", 5.0, 40.0)
OK_URL = "https://mobility-prices.ok.dk/api/v1/fuel-prices"
SHELL_URL = "https://shellpumpepriser.geoapp.me/v1/prices"
COLS = ["diesel", "petrol95", "e10", "premium98", "e85", "lpg"]


def _set_min(s: Station, col: str, value):
    p = price(value, COUNTRY)
    if p is None:
        return
    i = COLS.index(col)
    if s.prices[i] is None or p < s.prices[i]:
        s.prices[i] = p


def _when(value) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        # Les deux API donnent une heure locale, parfois avec 7 décimales.
        v = value.split(".")[0] if "." in value and "+" not in value else value
        if "." in v and "+" in v:
            head, tail = v.split("+")
            v = head.split(".")[0] + "+" + tail
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            from datetime import timedelta, timezone
            dt = dt.replace(tzinfo=timezone(timedelta(hours=1)))
        return minutes(dt)
    except ValueError:
        return None


def _ok(out: list[Station]):
    doc = fetch_json(OK_URL, timeout=60)
    items = doc.get("items") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        raise ValueError("OK : réponse inattendue")
    for r in items:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("facility_number") or "")
        co = r.get("coordinates") or {}
        c = coord(co.get("latitude"), co.get("longitude"))
        if not rid.isdigit() or c is None:
            continue
        addr = " ".join(x for x in (clean(r.get("street"), 60), clean(str(r.get("house_number") or ""), 10)) if x)
        s = Station(f"ok{rid}", c[0], c[1], clean(str(r.get("postal_code") or ""), 8),
                    clean(r.get("city"), 60), f"OK · {addr}" if addr else "OK",
                    maj=_when(r.get("last_updated_time")) or now_minutes())
        for p in r.get("prices") or []:
            if not isinstance(p, dict):
                continue
            name = clean(p.get("product_name"), 40).lower()
            if "diesel" in name:
                _set_min(s, "diesel", p.get("price"))
            elif "95" in name:
                _set_min(s, "petrol95", p.get("price"))
            elif "100" in name or "98" in name:
                _set_min(s, "premium98", p.get("price"))
        out.append(s)


def _shell(out: list[Station]):
    doc = fetch_json(SHELL_URL, timeout=60)
    if not isinstance(doc, list):
        raise ValueError("Shell : réponse inattendue")
    for r in doc:
        if not isinstance(r, dict):
            continue
        rid = clean(r.get("stationId"), 12)
        co = r.get("coordinates") or {}
        c = coord(co.get("latitude"), co.get("longitude"))
        if not rid or c is None:
            continue
        brand = clean(r.get("brand"), 20) or "Shell"
        addr = " ".join(x for x in (clean(r.get("street"), 60), clean(r.get("houseNumber"), 10)) if x)
        s = Station(f"shell{rid}", c[0], c[1], clean(r.get("postalCode"), 8),
                    clean(r.get("city"), 60), f"{brand} · {addr}" if addr else brand)
        for p in r.get("prices") or []:
            if not isinstance(p, dict):
                continue
            kind = clean(p.get("fuelType"), 20).lower()
            octane = clean(str(p.get("octane") or ""), 4)
            if "diesel" in kind:
                _set_min(s, "diesel", p.get("price"))
            elif octane == "95":
                _set_min(s, "petrol95", p.get("price"))
            elif octane in ("98", "100"):
                _set_min(s, "premium98", p.get("price"))
            m = _when(p.get("lastUpdated"))
            if m is not None and (s.maj is None or m > s.maj):
                s.maj = m
        if s.maj is None:
            s.maj = now_minutes()
        out.append(s)


def load():
    out: list[Station] = []
    errors = []
    for name, fn in (("OK", _ok), ("Shell", _shell)):
        try:
            fn(out)
        except Exception as e:  # noqa: BLE001 - une enseigne en panne ne bloque pas l'autre
            errors.append(f"{name} : {type(e).__name__}: {str(e)[:80]}")
            print(f"  {name} indisponible : {e}", flush=True)
    if errors and len(out) < 300:
        from ..common import SourceError
        raise SourceError("; ".join(errors))
    return finalize(COUNTRY, out, 300)
