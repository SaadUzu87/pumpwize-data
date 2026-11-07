"""Australie-Occidentale : FuelWatch (gouvernement de WA), flux RSS publics
par produit. Les prix sont en cents australiens par litre, fixés pour la
journée. Les autres États (NSW, QLD, SA, TAS, NT) demandent une clé d'API :
à ajouter plus tard."""
import xml.etree.ElementTree as ET

from ..common import Country, Station, clean, coord, fetch, now_minutes, price, finalize

COUNTRY = Country("AU", "AUD", "FuelWatch WA", "https://www.fuelwatch.wa.gov.au", 0.5, 5.0)
URL = "https://www.fuelwatch.wa.gov.au/fuelwatch/fuelWatchRSS?Product={product}&Day=today"
# Codes produits FuelWatch : 1 ULP (91), 4 Diesel, 5 LPG, 6 98 RON, 10 E85.
PRODUCTS = ((4, "diesel"), (1, "petrol95"), (6, "premium98"), (5, "lpg"), (10, "e85"))


def load():
    stations: dict[str, Station] = {}
    maj = now_minutes()
    for code, col in PRODUCTS:
        try:
            root = ET.fromstring(fetch(URL.format(product=code)).decode("utf-8-sig", "replace"))
        except ET.ParseError as e:
            raise ValueError(f"RSS illisible ({code}) : {e}") from e
        for item in root.iter("item"):
            c = coord(item.findtext("latitude"), item.findtext("longitude"))
            name = clean(item.findtext("trading-name"), 60)
            if c is None or not name:
                continue
            rid = f"{c[0]:.5f},{c[1]:.5f}"
            s = stations.get(rid)
            if s is None:
                s = Station(rid, c[0], c[1], "", clean(item.findtext("location"), 60),
                            f"{name} · {clean(item.findtext('address'), 60)}", maj=maj)
                stations[rid] = s
            s.set(col, price(item.findtext("price"), COUNTRY, scale=0.01))
    return finalize(COUNTRY, list(stations.values()), 200)
