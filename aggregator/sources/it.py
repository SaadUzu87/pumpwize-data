"""Italie : Osservaprezzi carburanti (MIMIT), API de l'application officielle.

Les CSV quotidiens de www.mimit.gov.it ne répondent plus depuis octobre 2026
aux serveurs de GitHub ; l'API `carburanti.mise.gov.it/ospzApi` livre les
mêmes stations (mêmes identifiants), région par région, avec les adresses.
Licence des données : IODL 2.0.
"""
import re
import time
from datetime import datetime

from ..common import Country, SourceError, Station, clean, coord, fetch_json, minutes, post_json, price, finalize, title_case

COUNTRY = Country("IT", "EUR", "Osservaprezzi carburanti (MIMIT)",
                  "https://carburanti.mise.gov.it", 0.2, 5.0)
BASE = "https://carburanti.mise.gov.it/ospzApi"
_CP = re.compile(r"(?<![0-9])([0-9]{5})(?![0-9])")
_PROV = re.compile(r"\s+\(?[A-Z]{2}\)?\s*$")
PAUSE = 1.0


def _regions():
    doc = fetch_json(f"{BASE}/registry/region", timeout=60)
    ids = []
    for r in doc.get("results") or []:
        try:
            ids.append(int(r["id"]))
        except (KeyError, TypeError, ValueError):
            continue
    if len(ids) < 15:
        raise SourceError(f"liste des régions incomplète ({len(ids)})")
    return ids


def _station(r) -> Station | None:
    if not isinstance(r, dict):
        return None
    rid = str(r.get("id") or "")
    loc = r.get("location") or {}
    c = coord(loc.get("lat"), loc.get("lng"))
    if not rid.isdigit() or c is None:
        return None
    s = Station(rid, c[0], c[1])
    full = clean(r.get("address"), 160)
    cps = list(_CP.finditer(full))
    if cps:
        # Formats vus : « VIA X 122 11100 - AOSTA AO », « ..., dir. Y - 11020 - NUS AO »
        m = cps[-1]
        s.cp = m.group(1)
        s.address = title_case(full[:m.start()].strip(" -,"))
        s.city = title_case(_PROV.sub("", full[m.end():].strip(" -,")))
    else:
        s.address = title_case(full)
    brand = clean(r.get("brand"), 40)
    if brand and brand.lower() not in ("pompebianche",):
        s.address = f"{brand} · {s.address}" if s.address else brand
    for f in r.get("fuels") or []:
        if not isinstance(f, dict):
            continue
        fid = f.get("fuelId")
        name = clean(f.get("name"), 40).lower()
        if fid == 1:
            col = "premium98" if ("98" in name or "100" in name) else "petrol95"
        elif fid == 2:
            col = "diesel"
        elif fid == 4:
            col = "lpg"
        else:
            continue  # metano, GNL, gasoli premium de marque…
        p = price(f.get("price"), COUNTRY)
        if p is None:
            continue
        idx = ["diesel", "petrol95", "e10", "premium98", "e85", "lpg"].index(col)
        current = s.prices[idx]
        # Prix « self » prioritaire ; sinon le moins cher communiqué.
        if current is None or f.get("isSelf") is True or p < current:
            s.prices[idx] = p
    when = r.get("insertDate")
    if isinstance(when, str):
        try:
            m2 = minutes(datetime.fromisoformat(when.replace("Z", "+00:00")))
            if m2 is not None:
                s.maj = m2
        except ValueError:
            pass
    return s


def load():
    stations: dict[str, Station] = {}
    for rid in _regions():
        last = None
        for attempt in range(3):
            try:
                doc = post_json(f"{BASE}/search/area", {"region": rid}, timeout=120)
                break
            except SourceError as e:
                last = e
                time.sleep(10)
        else:
            raise last
        results = doc.get("results") if isinstance(doc, dict) else None
        if not isinstance(results, list):
            raise ValueError(f"région {rid} : réponse inattendue")
        for r in results:
            s = _station(r)
            if s is not None:
                stations[s.id] = s
        time.sleep(PAUSE)
    return finalize(COUNTRY, list(stations.values()), 15000)
