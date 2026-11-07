"""Portugal : DGEG, « Preços dos combustíveis online » (API publique)."""
from datetime import timedelta, timezone

from ..common import Country, Station, clean, coord, fetch_json, minutes, parse_dt, price, finalize

COUNTRY = Country("PT", "EUR", "precoscombustiveis.dgeg.gov.pt",
                  "https://precoscombustiveis.dgeg.gov.pt", 0.2, 5.0)
BASE = ("https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/PesquisarPostos"
        "?idsTiposComb={fuel}&idMarca=&idTipoPosto=&idDistrito=&idsMunicipios="
        "&qtdPorPagina=20000&pagina=1")
# Identifiants de carburant de l'API (GetTiposCombustiveis).
FUELS = ((2101, "diesel"), (3201, "petrol95"), (3400, "premium98"), (1120, "lpg"))
TZ = timezone(timedelta(hours=0))  # Lisbonne ≈ UTC (±1 h selon la saison)


def load():
    stations: dict[str, Station] = {}
    for fuel_id, col in FUELS:
        doc = fetch_json(BASE.format(fuel=fuel_id))
        rows = doc.get("resultado") if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            raise ValueError(f"réponse inattendue pour {fuel_id}")
        for r in rows:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("Id") or "")
            c = coord(r.get("Latitude"), r.get("Longitude"))
            if not rid.isdigit() or c is None:
                continue
            s = stations.get(rid)
            if s is None:
                s = Station(rid, c[0], c[1], clean(r.get("CodPostal"), 8),
                            clean(r.get("Localidade"), 60),
                            clean(r.get("Morada"), 100))
                stations[rid] = s
            s.set(col, price(r.get("Preco"), COUNTRY))
            m = minutes(parse_dt(r.get("DataAtualizacao", ""), ("%Y-%m-%d %H:%M",), TZ))
            if m is not None and (s.maj is None or m > s.maj):
                s.maj = m
    return finalize(COUNTRY, list(stations.values()), 1500)
