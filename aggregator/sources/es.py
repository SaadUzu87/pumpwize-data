"""Espagne : Ministerio para la Transición Ecológica, « Precios de carburantes »
(API REST publique, sans clé)."""
from datetime import timedelta, timezone

from ..common import Country, Station, clean, coord, fetch_json, minutes, parse_dt, price, finalize, title_case

COUNTRY = Country("ES", "EUR", "geoportalgasolineras.es",
                  "https://geoportalgasolineras.es", 0.2, 5.0)
URL = ("https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
       "PreciosCarburantes/EstacionesTerrestres/")
FIELDS = (("Precio Gasoleo A", "diesel"), ("Precio Gasolina 95 E5", "petrol95"),
          ("Precio Gasolina 95 E10", "e10"), ("Precio Gasolina 98 E5", "premium98"),
          ("Precio Gasolina 95 E85", "e85"), ("Precio Gases licuados del petróleo", "lpg"))


def load():
    doc = fetch_json(URL)
    rows = doc.get("ListaEESSPrecio") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise ValueError("réponse inattendue")
    # Heure espagnole (CET/CEST) approchée par UTC+1 ; une heure d'écart est
    # sans conséquence pour l'affichage « il y a … ».
    dt = parse_dt(doc.get("Fecha", ""), ("%d/%m/%Y %H:%M:%S",), timezone(timedelta(hours=1)))
    maj = minutes(dt)
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        c = coord(r.get("Latitud"), r.get("Longitud (WGS84)"))
        rid = clean(r.get("IDEESS"), 12)
        if c is None or not rid:
            continue
        s = Station(rid, c[0], c[1], clean(r.get("C.P."), 5),
                    title_case(clean(r.get("Localidad"), 60)),
                    title_case(clean(r.get("Dirección"), 100)), maj=maj)
        for key, col in FIELDS:
            s.set(col, price(r.get(key), COUNTRY))
        out.append(s)
    return finalize(COUNTRY, out, 5000)
