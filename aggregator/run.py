"""Agrégateur PumpWize : lit chaque source nationale et publie un fichier
compact par pays plus un index.

Usage :
    python -s -m aggregator.run --out site/data [--only ES,PT] [--previous URL]

Un module de source définit soit `COUNTRY` et `load()`, soit `COUNTRIES` et
`load(country)` (plusieurs pays tirés d'un même bulletin).

Si une source échoue, le fichier précédemment publié (téléchargé depuis
`--previous`, l'URL du site en ligne) est conservé tant qu'il a moins de
trois jours ; l'index indique alors `stale: true` pour ce pays.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

from .common import SourceError, dump, fetch, now_iso

SOURCES = ("fr", "es", "pt", "it", "uk", "mx", "si", "au", "dk", "ae", "my", "tw", "hk", "wob")
MAX_PREVIOUS_AGE = timedelta(days=3)


def _previous(base_url: str, code: str):
    if not base_url:
        return None
    try:
        doc = json.loads(fetch(f"{base_url.rstrip('/')}/{code.lower()}.json", timeout=60))
        gen = datetime.fromisoformat(doc["generated"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - gen > MAX_PREVIOUS_AGE:
            return None
        if doc.get("v") != 2 or not isinstance(doc.get("stations"), list):
            return None
        return doc
    except Exception:  # noqa: BLE001 - toute erreur = pas de version précédente
        return None


def _load_with_retry(loader, attempts: int = 2):
    """Une source lente ou capricieuse a droit à un second essai."""
    last = None
    for i in range(attempts):
        try:
            return loader()
        except SourceError as e:
            last = e
            print(f"  essai {i + 1}/{attempts} raté : {str(e)[:160]}", flush=True)
            time.sleep(10)
    raise last


def _jobs(wanted: set[str]):
    """(pays, chargeur) pour chaque pays demandé."""
    for name in SOURCES:
        mod = importlib.import_module(f".sources.{name}", __package__)
        if hasattr(mod, "COUNTRIES"):
            for country in mod.COUNTRIES:
                if not wanted or name in wanted or country.code.lower() in wanted:
                    yield country, (lambda m=mod, c=country: m.load(c))
        elif not wanted or name in wanted or mod.COUNTRY.code.lower() in wanted:
            yield mod.COUNTRY, mod.load


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--previous", default=os.environ.get("PUMPWIZE_PREVIOUS", ""))
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    wanted = {s.strip().lower() for s in args.only.split(",") if s.strip()}
    index = {"v": 2, "generated": now_iso(), "countries": {}}
    failures = 0
    summary = ["| Pays | Résultat |", "|---|---|"]
    for country, loader in _jobs(wanted):
        print(f"== {country.code} ({country.source_name})", flush=True)
        started = time.monotonic()
        try:
            doc = _load_with_retry(loader)
            stale = False
            summary.append(f"| {country.code} | {len(doc['stations'])} stations en {time.monotonic() - started:.0f} s |")
        except (SourceError, ValueError, KeyError, TypeError) as e:
            reason = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"  ÉCHEC : {reason}", flush=True)
            doc = _previous(args.previous, country.code)
            stale = True
            if doc is None:
                failures += 1
                summary.append(f"| {country.code} | ÉCHEC, pays omis : {reason} |")
                print("  aucune version précédente utilisable : pays omis", flush=True)
                continue
            summary.append(f"| {country.code} | ÉCHEC, version du {doc['generated']} conservée : {reason} |")
            print(f"  version précédente conservée ({doc['generated']})", flush=True)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            summary.append(f"| {country.code} | ERREUR INTERNE : {type(e).__name__}: {str(e)[:160]} |")
            failures += 1
            continue
        text = dump(doc)
        path = os.path.join(args.out, f"{country.code.lower()}.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        index["countries"][country.code] = {
            "file": f"{country.code.lower()}.json",
            "n": len(doc["stations"]),
            "bytes": len(text.encode("utf-8")),
            "currency": doc["currency"],
            "generated": doc["generated"],
            "source": doc["source"],
            "stale": stale,
            "priceMode": doc.get("priceMode", "station"),
        }
        print(f"  {len(doc['stations'])} stations, {len(text) // 1024} Ko{' (périmé)' if stale else ''}", flush=True)

    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(index))
    print(f"index : {len(index['countries'])} pays, {failures} échec(s)")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            lines = [f"## Agrégation du {index['generated']}", "", *summary, ""]
            f.write("\n".join(lines))
    return 0 if index["countries"] else 1


if __name__ == "__main__":
    sys.exit(main())
