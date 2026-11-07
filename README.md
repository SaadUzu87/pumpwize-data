# pumpwize-data

Agrégateur open source des prix des carburants pour l'application
**PumpWize**. Toutes les 30 minutes, GitHub Actions lit les sources
officielles de chaque pays et publie sur GitHub Pages un fichier compact par
pays :

- `https://saaduzu87.github.io/pumpwize-data/data/index.json`
- `https://saaduzu87.github.io/pumpwize-data/data/<cc>.json`

Les données restent celles des États et organismes qui les publient (voir
les licences de chaque source dans `aggregator/README.md`). Ce dépôt ne
contient aucune donnée personnelle ni aucun secret.

Documentation technique : [aggregator/README.md](aggregator/README.md).
