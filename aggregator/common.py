"""Outils communs de l'agrégateur PumpWize.

Chaque source nationale produit une liste de `Station` normalisées ; le
format de sortie (une ligne compacte par station) est celui que lit
l'application :

    [id, lat, lon, code_postal, ville, adresse, diesel, essence95, e10,
     essence98, e85, gpl, maj_minutes]

Les prix sont exprimés par litre dans la devise du pays, `None` quand la
station ne vend pas ce carburant. `maj_minutes` est l'horodatage (minutes
Unix UTC) de la dernière mise à jour connue.

Règles de sécurité : TLS vérifié, taille des réponses plafonnée, délais
maximaux, chaque champ nettoyé et borné avant écriture.
"""
from __future__ import annotations

import gzip
import io
import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

USER_AGENT = "PumpWize-aggregator/1.0 (+https://github.com/SaadUzu87/pumpwize)"
COLUMNS = ("diesel", "petrol95", "e10", "premium98", "e85", "lpg")
MAX_BYTES = 80 * 1024 * 1024
TIMEOUT = 120

_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


class SourceError(Exception):
    """Source indisponible ou réponse inexploitable."""


@dataclass
class Station:
    id: str
    lat: float
    lon: float
    cp: str = ""
    city: str = ""
    address: str = ""
    prices: list = field(default_factory=lambda: [None] * len(COLUMNS))
    maj: int | None = None  # minutes Unix UTC

    def set(self, column: str, price):
        self.prices[COLUMNS.index(column)] = price

    def row(self):
        return [self.id, round(self.lat, 6), round(self.lon, 6), self.cp,
                self.city, self.address, *self.prices, self.maj]


@dataclass
class Country:
    code: str            # ISO 3166-1 alpha-2
    currency: str        # ISO 4217
    source_name: str     # affiché dans l'application
    source_url: str      # page de référence de la source
    min_price: float     # bornes de vraisemblance, par litre, devise locale
    max_price: float
    name_prefix: bool = True  # préfixer les identifiants par « cc: »


# ------------------------------------------------------------------ réseau

def fetch(url: str, *, timeout: int = TIMEOUT, max_bytes: int = MAX_BYTES,
          headers: dict | None = None, accept: str = "*/*") -> bytes:
    """GET avec vérification TLS, plafond de taille et délai maximal."""
    h = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                raise SourceError(f"HTTP {r.status} pour {url}")
            data = r.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise SourceError(f"réponse trop volumineuse : {url}")
            if r.headers.get("Content-Encoding") == "gzip":
                data = gzip.GzipFile(fileobj=io.BytesIO(data)).read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise SourceError(f"réponse décompressée trop volumineuse : {url}")
            return data
    except SourceError:
        raise
    except Exception as e:  # réseau, TLS, délai
        raise SourceError(f"{type(e).__name__}: {e}") from e


def fetch_json(url: str, **kw):
    try:
        return json.loads(fetch(url, accept="application/json", **kw).decode("utf-8-sig"))
    except json.JSONDecodeError as e:
        raise SourceError(f"JSON illisible : {url} ({e})") from e


# -------------------------------------------------------------- validation

def clean(value, max_len: int) -> str:
    if not isinstance(value, str):
        return ""
    s = _SPACES.sub(" ", _CTRL.sub(" ", value)).strip()
    return s[:max_len]


def title_case(s: str) -> str:
    """Les sources publient souvent en capitales : on adoucit."""
    if s and s == s.upper():
        return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))
    return s


def number(value) -> float | None:
    """Nombre depuis une chaîne à virgule ou à point, ou un nombre."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None  # NaN exclu
    if not isinstance(value, str):
        return None
    s = value.strip().replace(" ", "").replace(" ", "")
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def price(value, country: Country, scale: float = 1.0) -> float | None:
    p = number(value)
    if p is None:
        return None
    p *= scale
    if not (country.min_price <= p <= country.max_price):
        return None
    return round(p, 3)


def coord(lat, lon) -> tuple[float, float] | None:
    la, lo = number(lat), number(lon)
    if la is None or lo is None:
        return None
    if not (-90 <= la <= 90 and -180 <= lo <= 180) or (la == 0 and lo == 0):
        return None
    return la, lo


def minutes(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() // 60)


def parse_dt(value: str, formats: tuple[str, ...], tz=timezone.utc) -> datetime | None:
    if not isinstance(value, str):
        return None
    for f in formats:
        try:
            return datetime.strptime(value.strip(), f).replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def now_minutes() -> int:
    return int(time.time() // 60)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ----------------------------------------------------------------- sortie

def finalize(country: Country, stations: list[Station], min_count: int) -> dict:
    """Déduplique, valide et construit le document d'un pays."""
    seen: dict[str, Station] = {}
    for s in stations:
        if not s.id or len(s.id) > 40 or coord(s.lat, s.lon) is None:
            continue
        if not any(p is not None for p in s.prices):
            continue
        sid = f"{country.code.lower()}:{s.id}" if country.name_prefix else s.id
        s.id = sid
        s.cp = clean(s.cp, 12)
        s.city = clean(s.city, 60)
        s.address = clean(s.address, 100)
        seen[sid] = s
    if len(seen) < min_count:
        raise SourceError(f"{country.code} : seulement {len(seen)} stations valides (< {min_count})")
    rows = [s.row() for s in seen.values()]
    rows.sort(key=lambda r: r[0])
    return {
        "v": 2,
        "country": country.code,
        "currency": country.currency,
        "generated": now_iso(),
        "source": {"name": country.source_name, "url": country.source_url},
        "columns": list(COLUMNS),
        "stations": rows,
    }


def dump(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
