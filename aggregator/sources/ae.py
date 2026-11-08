"""Émirats arabes unis : prix fixé chaque mois par le comité de suivi des
prix des carburants (ministère de l'Énergie et des Infrastructures),
identique dans toutes les stations. Aucun flux officiel lisible par machine :
on lit le relais communautaire github.com/pedrofintech/uae-fuel-data, qui
recopie chaque mois le communiqué (vérifié : mois courant exigé)."""
from datetime import datetime, timedelta, timezone

from ..common import Country, SourceError, fetch_json
from .. import national

COUNTRY = Country("AE", "AED", "Comité des prix des carburants (EAU), via uae-fuel-data",
                  "https://github.com/pedrofintech/uae-fuel-data", 0.5, 20.0)
URL = "https://raw.githubusercontent.com/pedrofintech/uae-fuel-data/main/petrol.json"
GULF = timezone(timedelta(hours=4))


def load():
    doc = fetch_json(URL, timeout=60, max_bytes=512 * 1024)
    cur = doc.get("cur") if isinstance(doc, dict) else None
    month = doc.get("m") if isinstance(doc, dict) else None
    if not isinstance(cur, dict) or not isinstance(month, str):
        raise ValueError("document inattendu")
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=GULF)
    except ValueError as e:
        raise ValueError(f"mois illisible : {month!r}") from e
    now = datetime.now(GULF)
    if now - start > timedelta(days=62):
        raise SourceError(f"relais non mis à jour depuis {month}")
    return national.build(
        COUNTRY,
        {"petrol95": cur.get("s95"), "premium98": cur.get("s98"), "diesel": cur.get("d")},
        price_date=start,
        note="Prix mensuels officiels (Special 95, Super 98, Diesel) ; E-Plus 91 non repris.",
    )
