"""Запуск любого сборщика из apify_actors.json с потолком трат.

python parsers/apify_run.py 2gis input.json --cap 0.5
Итог: data/raw/<ключ>_<время>.json
"""
import argparse
import json
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTORS = json.loads((Path(__file__).parent / "apify_actors.json").read_text(encoding="utf-8"))


def token() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("APIFY_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("нет APIFY_TOKEN в .env")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("key", choices=[k for k in ACTORS if not k.startswith("_")])
    a.add_argument("input", help="json с параметрами сборщика")
    a.add_argument("--cap", type=float, default=0.3, help="потолок трат за запуск, $")
    o = a.parse_args()
    actor = ACTORS[o.key]["actor"].replace("/", "~")
    body = Path(o.input).read_text(encoding="utf-8").encode()
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?maxTotalChargeUsd={o.cap}&timeout=600",
        data=body, method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + token()})
    data = json.load(urllib.request.urlopen(req, timeout=700))
    out = ROOT / "data" / "raw" / f"{o.key}_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"записей: {len(data)} → {out}")


if __name__ == "__main__":
    main()
