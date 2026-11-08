"""Union européenne : moyennes nationales hebdomadaires du « Weekly Oil
Bulletin » de la Commission européenne (CC BY 4.0), pour les pays sans
relevé station par station. Les prix sont publiés en euros ; ils sont
convertis dans la monnaie locale avec les taux de référence de la BCE.

Mode « average » : l'application indique que la station peut pratiquer un
autre prix.
"""
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone

from ..common import Country, SourceError, fetch, number
from .. import national

WOB_URL = "https://energy.ec.europa.eu/document/download/264c2d0f-f161-4ea3-a777-78faae59bea0_en"
WOB_PAGE = "https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en"
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
SOURCE = "Weekly Oil Bulletin (Commission européenne), moyenne nationale"

# code, devise, nom dans le bulletin, bornes de vraisemblance (devise locale)
_TABLE = [
    ("AT", "EUR", "Austria", 0.2, 5.0), ("BE", "EUR", "Belgium", 0.2, 5.0),
    ("BG", "EUR", "Bulgaria", 0.2, 5.0), ("HR", "EUR", "Croatia", 0.2, 5.0),
    ("CY", "EUR", "Cyprus", 0.2, 5.0), ("CZ", "CZK", "Czechia", 10.0, 100.0),
    ("EE", "EUR", "Estonia", 0.2, 5.0), ("FI", "EUR", "Finland", 0.2, 5.0),
    ("GR", "EUR", "Greece", 0.2, 5.0), ("HU", "HUF", "Hungary", 200.0, 1500.0),
    ("IE", "EUR", "Ireland", 0.2, 5.0), ("LV", "EUR", "Latvia", 0.2, 5.0),
    ("LT", "EUR", "Lithuania", 0.2, 5.0), ("LU", "EUR", "Luxembourg", 0.2, 5.0),
    ("MT", "EUR", "Malta", 0.2, 5.0), ("NL", "EUR", "Netherlands", 0.2, 5.0),
    ("PL", "PLN", "Poland", 2.0, 20.0), ("RO", "RON", "Romania", 3.0, 20.0),
    ("SK", "EUR", "Slovakia", 0.2, 5.0), ("SE", "SEK", "Sweden", 5.0, 50.0),
]
COUNTRIES = [Country(c, cur, SOURCE, WOB_PAGE, lo, hi) for c, cur, _, lo, hi in _TABLE]
_NAMES = {c: name for c, _, name, _, _ in _TABLE}
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_cache: dict = {}


def _bulletin():
    """{pays: {colonne: €/L}}, date des prix."""
    if "wob" in _cache:
        return _cache["wob"]
    raw = fetch(WOB_URL, timeout=90, max_bytes=8 * 1024 * 1024)
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        shared = [''.join(t.text or '' for t in si.iter(f"{_NS}t"))
                  for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise SourceError(f"classeur illisible : {e}") from e
    rows = []
    for row in sheet.iter(f"{_NS}row"):
        cells = {}
        for c in row.iter(f"{_NS}c"):
            v = c.find(f"{_NS}v")
            val = v.text if v is not None else ""
            if c.get("t") == "s" and val.isdigit():
                val = shared[int(val)]
            col = re.sub(r"\d", "", c.get("r", ""))
            cells[col] = val
        rows.append(cells)
    if len(rows) < 10:
        raise SourceError("bulletin vide")
    header = rows[0]
    # Colonnes repérées par leur intitulé, pas par leur position.
    col_95 = col_diesel = col_lpg = None
    for col, label in header.items():
        low = label.lower()
        if "euro-super" in low:
            col_95 = col
        elif "automotive gas oil" in low or "gas oil automobile" in low:
            col_diesel = col
        elif "lpg" in low or "gpl" in low:
            col_lpg = col
    if not (col_95 and col_diesel):
        raise SourceError(f"colonnes introuvables : {header}")
    serial = number(rows[1].get("A"))
    if serial is None or not (40000 < serial < 80000):
        raise SourceError(f"date illisible : {rows[1].get('A')!r}")
    when = datetime(1899, 12, 30, tzinfo=timezone.utc) + timedelta(days=serial)
    if datetime.now(timezone.utc) - when > timedelta(days=45):
        raise SourceError(f"bulletin trop ancien ({when.date()})")
    table = {}
    for r in rows[2:]:
        name = (r.get("A") or "").strip()
        if not name:
            continue
        def per_litre(col):
            v = number(r.get(col)) if col else None
            return None if v is None or v <= 0 else v / 1000.0
        table[name] = {"petrol95": per_litre(col_95), "diesel": per_litre(col_diesel), "lpg": per_litre(col_lpg)}
    _cache["wob"] = (table, when)
    return _cache["wob"]


def _rates():
    if "ecb" in _cache:
        return _cache["ecb"]
    raw = fetch(ECB_URL, timeout=60, max_bytes=256 * 1024)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise SourceError(f"taux BCE illisibles : {e}") from e
    rates = {"EUR": 1.0}
    for cube in root.iter():
        cur, rate = cube.get("currency"), number(cube.get("rate"))
        if cur and rate:
            rates[cur] = rate
    if len(rates) < 10:
        raise SourceError("taux BCE incomplets")
    _cache["ecb"] = rates
    return rates


def load(country: Country):
    table, when = _bulletin()
    row = table.get(_NAMES[country.code])
    if row is None:
        raise SourceError(f"{country.code} absent du bulletin")
    rate = _rates().get(country.currency)
    if rate is None:
        raise SourceError(f"pas de taux BCE pour {country.currency}")
    prices = {col: (None if v is None else round(v * rate, 3)) for col, v in row.items()}
    return national.build(country, prices, price_date=when, mode="average",
                          note="Moyenne nationale hebdomadaire ; convertie en monnaie locale au taux BCE du jour."
                          if country.currency != "EUR" else "Moyenne nationale hebdomadaire.")
