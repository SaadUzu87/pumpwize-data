"""Mexique : Comisión Reguladora de Energía, prix publiés par station
(deux fichiers XML publics : emplacements et prix)."""
import xml.etree.ElementTree as ET

from ..common import Country, Station, clean, coord, fetch, now_minutes, price, finalize, title_case

COUNTRY = Country("MX", "MXN", "CRE (datos.gob.mx)",
                  "https://datos.gob.mx/busca/dataset/precios-de-gasolinas-y-diesel", 5.0, 60.0)
PLACES = "https://publicacionexterna.azurewebsites.net/publicaciones/places"
PRICES = "https://publicacionexterna.azurewebsites.net/publicaciones/prices"
TYPES = {"regular": "petrol95", "premium": "premium98", "diesel": "diesel"}


def _xml(url):
    try:
        return ET.fromstring(fetch(url).decode("utf-8-sig", "replace"))
    except ET.ParseError as e:
        raise ValueError(f"XML illisible : {url} ({e})") from e


def load():
    stations: dict[str, Station] = {}
    for place in _xml(PLACES).findall("place"):
        rid = clean(place.get("place_id"), 12)
        loc = place.find("location")
        if not rid or loc is None:
            continue
        c = coord(loc.findtext("y"), loc.findtext("x"))
        if c is None:
            continue
        stations[rid] = Station(rid, c[0], c[1], "", "",
                                title_case(clean(place.findtext("name"), 100)))
    maj = now_minutes()
    for place in _xml(PRICES).findall("place"):
        s = stations.get(clean(place.get("place_id"), 12))
        if s is None:
            continue
        for gp in place.findall("gas_price"):
            col = TYPES.get((gp.get("type") or "").lower())
            if col:
                s.set(col, price(gp.text, COUNTRY))
        s.maj = maj
    return finalize(COUNTRY, list(stations.values()), 5000)
