# Agrégateur PumpWize

Programme Python (bibliothèque standard uniquement) exécuté toutes les
30 minutes par GitHub Actions (`.github/workflows/aggregate.yml`). Il lit les
sources officielles de chaque pays et publie sur GitHub Pages :

- `data/index.json` : liste des pays, date de génération, nombre de
  stations, devise, source ;
- `data/<cc>.json` : une ligne compacte par station, même format que le
  cache de l'application :
  `[id, lat, lon, code_postal, ville, adresse, diesel, essence95, e10,
  essence98, e85, gpl, maj_minutes]`.

Si une source est en panne, le fichier précédemment publié est conservé
jusqu'à trois jours (`stale: true` dans l'index), puis le pays disparaît.

## Sources (novembre 2026)

| Pays | Source | Accès | Notes |
|---|---|---|---|
| FR | data.economie.gouv.fr | libre | Aussi interrogée directement par l'app |
| ES | Ministerio (sedeaplicaciones.minetur.gob.es) | libre | ~11 000 stations |
| PT | DGEG precoscombustiveis.dgeg.gov.pt | libre | 4 requêtes (un carburant chacune) |
| IT | MIMIT (deux CSV quotidiens) | libre | Injoignable depuis certains réseaux ; séparateur détecté automatiquement |
| GB | Flux JSON des enseignes (dispositif CMA) | libre | Partiel : Tesco, BP, Shell, Sainsbury's refusent ou ont fermé leur flux. Le dispositif officiel « Fuel Finder » (DESNZ) exige un compte GOV.UK One Login : à brancher plus tard |
| MX | CRE (publicacionexterna.azurewebsites.net) | libre | Pas d'horodatage par station |
| SI | goriva.si | libre | Paginé, ~550 stations |
| AU | FuelWatch (Australie-Occidentale) | libre | Les autres États demandent une clé d'API |

À brancher avec une clé (gratuite, à demander par le propriétaire du
projet) : Allemagne (Tankerkönig, recherche par rayon uniquement : plutôt
une requête directe depuis l'app), Nouvelle-Galles du Sud (FuelCheck),
Corée (Opinet), Chili (CNE), Royaume-Uni (Fuel Finder).

## Lancer en local

```bash
python -s -m aggregator.run --out site/data --only es,pt
```

Puis servir `site/` en HTTP local et compiler l'application en débogage
avec `--dart-define=PUMPWIZE_DATA_BASE=http://10.0.2.2:8000/data`
(émulateur Android).

## Ajouter un pays

1. Créer `aggregator/sources/<cc>.py` avec `COUNTRY = Country(...)` et une
   fonction `load()` qui retourne `finalize(COUNTRY, stations, minimum)`.
2. L'ajouter à `SOURCES` dans `run.py`.
3. Borner les prix (`min_price`, `max_price`) dans la devise locale et ne
   jamais faire confiance aux textes reçus (`clean()`).
