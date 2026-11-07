"""Royaume-Uni : flux JSON publiés par les enseignes dans le cadre du
« temporary pricing scheme » de la CMA (gov.uk, Access fuel price data).

Chaque flux est indépendant : un flux en panne ou périmé (> 7 jours) est
ignoré, les autres sont conservés. Les prix sont en pence par litre (ou
parfois en livres) : tout est ramené en livres.
"""
from datetime import datetime, timedelta, timezone

from ..common import Country, Station, SourceError, clean, coord, fetch_json, minutes, parse_dt, price, finalize

COUNTRY = Country("GB", "GBP", "gov.uk (CMA fuel price data)",
                  "https://www.gov.uk/guidance/access-fuel-price-data", 0.5, 4.0)
FEEDS = (
    "https://storelocator.asda.com/fuel_prices_data.json",
    "https://fuelprices.esso.co.uk/latestdata.json",
    "https://jetlocal.co.uk/fuel_prices_data.json",
    "https://moto-way.com/fuel-price/fuel_prices.json",
    "https://www.rontec-servicestations.co.uk/fuel-prices/data/fuel_prices_data.json",
    "https://www.sgnretail.uk/files/data/SGN_daily_fuel_prices.json",
    "https://www.morrisons.com/fuel-prices/fuel.json",
    "https://applegreenstores.com/fuel-prices/data.json",
    "https://www.tesco.com/fuel_prices/fuel_prices_data.json",
    "https://www.bp.com/en_gb/united-kingdom/home/fuelprices/fuel_prices_data.json",
    "https://api.sainsburys.co.uk/v1/exports/latest/fuel_prices_data.json",
    "https://fuelprices.asconagroup.co.uk/newfuel.json",
    "https://api2.krlmedia.com/integration/live_price/krl",
)
FIELDS = (("B7", "diesel"), ("E10", "e10"), ("E5", "premium98"))
MAX_AGE = timedelta(days=7)


def _pounds(v):
    """Pence (167.9) ou livres (1.679) selon l'ordre de grandeur."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f / 100 if f > 20 else f


def load(log=print):
    stations: dict[str, Station] = {}
    ok = 0
    for url in FEEDS:
        try:
            doc = fetch_json(url, timeout=60)
            rows = doc.get("stations") if isinstance(doc, dict) else None
            if not isinstance(rows, list):
                raise SourceError("pas de liste de stations")
            updated = parse_dt(doc.get("last_updated", ""),
                               ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"))
            if updated is None:
                updated = datetime.now(timezone.utc)
            if datetime.now(timezone.utc) - updated > MAX_AGE:
                log(f"  GB : flux périmé ignoré ({updated.date()}) {url}")
                continue
            maj = minutes(updated)
            n = 0
            for r in rows:
                if not isinstance(r, dict) or not isinstance(r.get("location"), dict):
                    continue
                rid = clean(str(r.get("site_id") or ""), 24)
                c = coord(r["location"].get("latitude"), r["location"].get("longitude"))
                if not rid or c is None or not isinstance(r.get("prices"), dict):
                    continue
                s = Station(rid, c[0], c[1], clean(r.get("postcode"), 10), "",
                            clean(r.get("address"), 100), maj=maj)
                brand = clean(r.get("brand"), 30)
                if brand and brand.lower() not in s.address.lower():
                    s.address = f"{brand} · {s.address}" if s.address else brand
                for key, col in FIELDS:
                    s.set(col, price(_pounds(r["prices"].get(key)), COUNTRY))
                stations[rid] = s
                n += 1
            ok += 1
            log(f"  GB : {n} stations depuis {url}")
        except SourceError as e:
            log(f"  GB : flux ignoré ({e}) {url}")
    if ok == 0:
        raise SourceError("aucun flux britannique disponible")
    return finalize(COUNTRY, list(stations.values()), 300)
