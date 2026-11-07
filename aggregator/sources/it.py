"""Italie : MIMIT, « Carburanti – prezzi praticati e anagrafica degli impianti »
(deux CSV quotidiens, licence IODL 2.0)."""
import csv
import io
from datetime import timedelta, timezone

from ..common import Country, Station, clean, coord, fetch, minutes, parse_dt, price, finalize, title_case

COUNTRY = Country("IT", "EUR", "mimit.gov.it (Osservaprezzi carburanti)",
                  "https://carburanti.mise.gov.it", 0.2, 5.0)
ANAG = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
PREZZI = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"
TZ = timezone(timedelta(hours=1))


def _rows(data: bytes, expected: int):
    """Lit un CSV MIMIT : une ligne d'en-tête libre, puis le séparateur est
    détecté sur la ligne des noms de colonnes (il a changé en 2026)."""
    text = data.decode("utf-8-sig", "replace")
    lines = text.splitlines()
    if len(lines) < 3:
        raise ValueError("CSV vide")
    start = 0 if lines[0].lower().startswith("idimpianto") else 1
    header = lines[start]
    sep = max((";", "|", "\t", ","), key=lambda c: header.count(c))
    if header.count(sep) < expected - 1:
        raise ValueError(f"séparateur introuvable dans : {header[:80]!r}")
    reader = csv.reader(lines[start:], delimiter=sep)
    names = [n.strip() for n in next(reader)]
    for row in reader:
        if len(row) >= len(names):
            yield dict(zip(names, row))


def load():
    stations: dict[str, Station] = {}
    # Le serveur du ministère ne répond pas depuis certains réseaux : délai court.
    for r in _rows(fetch(ANAG, timeout=60), 10):
        rid = clean(r.get("idImpianto"), 12)
        c = coord(r.get("Latitudine"), r.get("Longitudine"))
        if not rid or c is None:
            continue
        stations[rid] = Station(rid, c[0], c[1], "",
                                title_case(clean(r.get("Comune"), 60)),
                                title_case(clean(r.get("Indirizzo"), 100)))
    for r in _rows(fetch(PREZZI, timeout=60), 5):
        s = stations.get(clean(r.get("idImpianto"), 12))
        if s is None:
            continue
        desc = clean(r.get("descCarburante"), 40).lower()
        is_self = r.get("isSelf", "").strip() == "1"
        if desc == "benzina":
            col = "petrol95"
        elif desc == "gasolio":
            col = "diesel"
        elif desc == "gpl":
            col = "lpg"
        elif desc.startswith("benzina") and ("98" in desc or "100" in desc):
            col = "premium98"
        else:
            continue  # metano, gasoli premium de marque, etc.
        p = price(r.get("prezzo"), COUNTRY)
        if p is None:
            continue
        idx = ["diesel", "petrol95", "e10", "premium98", "e85", "lpg"].index(col)
        current = s.prices[idx]
        # Prix « self » prioritaire ; sinon le moins cher communiqué.
        if current is None or is_self or p < current:
            s.prices[idx] = p
        m = minutes(parse_dt(r.get("dtComu", ""), ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"), TZ))
        if m is not None and (s.maj is None or m > s.maj):
            s.maj = m
    return finalize(COUNTRY, list(stations.values()), 5000)
