"""Stations-service issues d'OpenStreetMap, pour les pays où le prix ne
dépend pas de la station (prix fixé par l'État, prix d'enseigne, moyenne
nationale) : la position vient d'OSM, le prix d'une source officielle.

Overpass est un service bénévole et lent : il n'est jamais appelé depuis
GitHub Actions. Les positions sont photographiées à la main et versionnées
dans `aggregator/osm/<cc>.json` :

    python -s -m aggregator.osm AE MY TW        # (re)photographie ces pays

Format d'une photo : {"v": 1, "country": "AE", "fetched": "…Z",
"stations": [[id, lat, lon, cp, ville, adresse, enseigne], …]}.
Données © les contributeurs d'OpenStreetMap, licence ODbL.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from .common import MAX_BYTES, USER_AGENT, Country, SourceError, Station, clean, coord, now_iso, title_case

OVERPASS = ("https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter")
# Pas de filtre admin_level : Hong Kong (admin_level 3) porte aussi ISO3166-1.
QUERY = ('[out:json][timeout:240];area["ISO3166-1"="{cc}"]->.a;'
         '(node["amenity"="fuel"](area.a);way["amenity"="fuel"](area.a););out center tags;')
# Territoires sans zone « ISO3166-1 » exploitable dans Overpass : emprise.
BBOX = {"HK": "(22.15,113.82,22.57,114.45)"}
QUERY_BBOX = ('[out:json][timeout:240];(node["amenity"="fuel"]{bbox};way["amenity"="fuel"]{bbox};);'
              'out center tags;')
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "osm")
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
_CC = re.compile(r"^[A-Z]{2}$")


def path(cc: str) -> str:
    return os.path.join(DIR, f"{cc.lower()}.json")


def stations(country: Country, min_count: int) -> tuple[list[Station], str]:
    """Stations du pays depuis la photo versionnée, avec la date (ISO) de
    la photo. Chaque station porte son enseigne dans `brand`."""
    if not _CC.match(country.code):
        raise ValueError(country.code)
    try:
        with open(path(country.code), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise SourceError(f"photo OSM absente ou illisible pour {country.code} : {e}") from e
    if doc.get("v") != 1 or doc.get("country") != country.code or not isinstance(doc.get("stations"), list):
        raise SourceError(f"photo OSM invalide pour {country.code}")
    out = []
    for r in doc["stations"]:
        if not isinstance(r, list) or len(r) < 7:
            continue
        c = coord(r[1], r[2])
        if c is None:
            continue
        s = Station(clean(str(r[0]), 20), c[0], c[1], clean(r[3], 12), clean(r[4], 60), clean(r[5], 100))
        s.brand = clean(r[6], 40)  # attribut libre, lu par national.build
        out.append(s)
    if len(out) < min_count:
        raise SourceError(f"OSM {country.code} : seulement {len(out)} stations")
    return out, str(doc.get("fetched") or "")


# ------------------------------------------------------------- Overpass

def fetch(cc: str) -> dict:
    """Interroge Overpass et retourne la photo (non écrite)."""
    if not _CC.match(cc):
        raise ValueError(cc)
    query = QUERY_BBOX.format(bbox=BBOX[cc]) if cc in BBOX else QUERY.format(cc=cc)
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for url in OVERPASS:
        try:
            doc = json.loads(_post(url, data))
            break
        except SourceError as e:
            last = e
            print(f"  {url.split('/')[2]} : {str(e)[:120]}", flush=True)
            time.sleep(30)
    else:
        raise last
    rows = []
    for el in doc.get("elements") or []:
        if not isinstance(el, dict):
            continue
        tags = el.get("tags") or {}
        if el.get("type") == "node":
            c = coord(el.get("lat"), el.get("lon"))
        else:
            center = el.get("center") or {}
            c = coord(center.get("lat"), center.get("lon"))
        if c is None:
            continue
        if tags.get("disused") == "yes" or tags.get("abandoned") == "yes":
            continue
        rid = f"{'n' if el.get('type') == 'node' else 'w'}{el.get('id')}"
        # Libellés latins de préférence (name:en) : les noms locaux en arabe
        # ou en chinois restent disponibles pour l'appariement d'enseigne.
        brand_en = clean(tags.get("brand:en") or tags.get("operator:en") or "", 40)
        brand_local = clean(tags.get("brand") or tags.get("operator") or "", 40)
        brand = " / ".join(dict.fromkeys(x for x in (brand_en, brand_local) if x))
        name = title_case(clean(tags.get("name:en") or brand_en or tags.get("name") or brand_local, 40))
        addr = " ".join(x for x in (clean(tags.get("addr:street"), 60), clean(tags.get("addr:housenumber"), 10)) if x)
        rows.append([rid, round(c[0], 6), round(c[1], 6), clean(tags.get("addr:postcode"), 12),
                     title_case(clean(tags.get("addr:city"), 60)),
                     f"{name} · {addr}" if name and addr else name or addr, brand])
    if len(rows) < 20:
        raise SourceError(f"{cc} : réponse Overpass quasi vide ({len(rows)} stations)")
    rows.sort(key=lambda r: r[0])
    return {"v": 1, "country": cc, "fetched": now_iso(), "attribution": ATTRIBUTION, "stations": rows}


def _post(url: str, data: bytes) -> bytes:
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=280) as r:
            if r.status != 200:
                raise SourceError(f"HTTP {r.status}")
            body = r.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise SourceError("réponse Overpass trop volumineuse")
            return body
    except SourceError:
        raise
    except Exception as e:  # réseau, TLS, délai
        raise SourceError(f"{type(e).__name__}: {e}") from e


def main(argv=None) -> int:
    codes = [c.upper() for c in (argv if argv is not None else sys.argv[1:])]
    if not codes:
        print(__doc__)
        return 2
    os.makedirs(DIR, exist_ok=True)
    failed = 0
    for i, cc in enumerate(codes):
        print(f"== {cc}", flush=True)
        try:
            doc = fetch(cc)
        except (SourceError, ValueError) as e:
            failed += 1
            print(f"  ÉCHEC : {e}", flush=True)
            continue
        with open(path(cc), "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print(f"  {len(doc['stations'])} stations", flush=True)
        if i + 1 < len(codes):
            time.sleep(8)  # courtoisie envers Overpass
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
