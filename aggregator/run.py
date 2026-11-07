"""Agrégateur PumpWize : lit chaque source nationale et publie un fichier
compact par pays plus un index.

Usage :
    python -s -m aggregator.run --out site/data [--only ES,PT] [--previous URL]

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
import traceback
from datetime import datetime, timedelta, timezone

from .common import SourceError, dump, fetch, now_iso

SOURCES = ("fr", "es", "pt", "it", "uk", "mx", "si", "au")
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
    for name in SOURCES:
        if wanted and name not in wanted:
            continue
        mod = importlib.import_module(f".sources.{name}", __package__)
        country = mod.COUNTRY
        print(f"== {country.code} ({country.source_name})", flush=True)
        try:
            doc = mod.load()
            stale = False
        except (SourceError, ValueError, KeyError, TypeError) as e:
            print(f"  ÉCHEC : {e}", flush=True)
            doc = _previous(args.previous, country.code)
            stale = True
            if doc is None:
                failures += 1
                print("  aucune version précédente utilisable : pays omis", flush=True)
                continue
            print(f"  version précédente conservée ({doc['generated']})", flush=True)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
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
        }
        print(f"  {len(doc['stations'])} stations, {len(text) // 1024} Ko{' (périmé)' if stale else ''}", flush=True)

    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(index))
    print(f"index : {len(index['countries'])} pays, {failures} échec(s)")
    return 0 if index["countries"] else 1


if __name__ == "__main__":
    sys.exit(main())
