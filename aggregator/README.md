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

Trois natures de prix, indiquées dans chaque fichier (`priceMode`) :
`station` (relevé station par station), `national` (prix fixé par l'État,
identique partout), `brand` (prix d'enseigne) et `average` (moyenne
nationale indicative). Pour les trois derniers, les positions des stations
viennent d'OpenStreetMap (photos versionnées dans `aggregator/osm/`,
voir plus bas).

| Pays | Mode | Source | Notes |
|---|---|---|---|
| FR | station | data.economie.gouv.fr | Aussi interrogée directement par l'app |
| ES | station | Ministerio (sedeaplicaciones.minetur.gob.es) | ~11 000 stations |
| PT | station | DGEG precoscombustiveis.dgeg.gov.pt | 4 requêtes (un carburant chacune) |
| IT | station | Osservaprezzi carburanti, API `carburanti.mise.gov.it/ospzApi` | 20 requêtes (une par région), ~21 500 stations ; les CSV de mimit.gov.it ne répondent plus depuis GitHub |
| GB | station | Flux JSON des enseignes (dispositif CMA) | Partiel ; le « Fuel Finder » officiel exige un compte GOV.UK One Login |
| MX | station | CRE (publicacionexterna.azurewebsites.net) | Pas d'horodatage par station |
| SI | station | goriva.si | Paginé, ~550 stations |
| AU | station | FuelWatch (Australie-Occidentale) | Les autres États demandent une clé d'API |
| DK | station | API des enseignes OK et Shell (loi § 16a, 2026) | Partiel : Circle K, Q8, Uno-X, OIL! sans documentation trouvée |
| AE | national | Comité des prix des carburants, via le relais github.com/pedrofintech/uae-fuel-data | Pas de flux officiel ; mois courant exigé |
| MY | national | KPDN via data.gov.my | Prix non subventionnés |
| TW | national | CPC (données ouvertes) | Tarif de référence hebdomadaire |
| HK | brand | Consumer Council (data.gov.hk) | Prix par enseigne, essence courante = 98 |
| AT BE BG HR CY CZ EE FI GR HU IE LV LT LU MT NL PL RO SK SE | average | Weekly Oil Bulletin (Commission européenne) + taux BCE | Moyenne nationale hebdomadaire, convertie en monnaie locale |

Allemagne : les conditions de Tankerkönig interdisent la recopie en masse ;
l'application interroge l'API directement, à la demande (voir le dépôt de
l'app). À brancher avec une clé (gratuite, à demander par le propriétaire du
projet) : Nouvelle-Galles du Sud (FuelCheck), Victoria, Queensland (API
temps réel), Corée (Opinet), Chili (CNE), Royaume-Uni (Fuel Finder).

## Positions OpenStreetMap

Overpass est lent et bénévole : il n'est jamais appelé depuis GitHub
Actions. Les positions sont photographiées à la main et versionnées :

```bash
python -s -m aggregator.osm AE MY TW HK AT BE ...
```

À refaire de temps en temps (quelques fois par an suffisent). Données
© les contributeurs d'OpenStreetMap, licence ODbL.

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
