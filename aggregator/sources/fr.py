"""France : open data officiel prix-carburants.gouv.fr (data.economie.gouv.fr).

Les identifiants ne sont pas préfixés : l'application interroge aussi cette
API directement (prix frais autour de l'utilisateur) et fusionne par id.
"""
from ..common import Country, Station, clean, coord, fetch_json, minutes, price, finalize
from datetime import datetime

COUNTRY = Country("FR", "EUR", "prix-carburants.gouv.fr",
                  "https://www.prix-carburants.gouv.fr", 0.2, 5.0, name_prefix=False)

URL = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/exports/json?select="
       "id,geom,cp,ville,adresse,gazole_prix,sp95_prix,e10_prix,sp98_prix,"
       "e85_prix,gplc_prix,gazole_maj,sp95_maj,e10_maj,sp98_maj,e85_maj,gplc_maj")
FUELS = (("gazole", "diesel"), ("sp95", "petrol95"), ("e10", "e10"),
         ("sp98", "premium98"), ("e85", "e85"), ("gplc", "lpg"))


def _iso_minutes(v):
    if not isinstance(v, str) or not v:
        return None
    try:
        return minutes(datetime.fromisoformat(v.replace("Z", "+00:00")))
    except ValueError:
        return None


def load():
    records = fetch_json(URL)
    if not isinstance(records, list):
        raise ValueError("réponse inattendue")
    out = []
    for r in records:
        if not isinstance(r, dict) or not isinstance(r.get("geom"), dict):
            continue
        c = coord(r["geom"].get("lat"), r["geom"].get("lon"))
        rid = r.get("id")
        if c is None or not isinstance(rid, int) or rid <= 0:
            continue
        s = Station(str(rid), c[0], c[1], clean(r.get("cp"), 5),
                    clean(r.get("ville"), 60), clean(r.get("adresse"), 100))
        maj = None
        for api, col in FUELS:
            s.set(col, price(r.get(f"{api}_prix"), COUNTRY))
            m = _iso_minutes(r.get(f"{api}_maj"))
            if m is not None and (maj is None or m > maj):
                maj = m
        s.maj = maj
        out.append(s)
    return finalize(COUNTRY, out, 5000)
