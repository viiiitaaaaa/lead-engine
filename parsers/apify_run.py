"""Запуск любого сборщика из apify_actors.json с потолком трат (асинхронно: старт → ожидание → выгрузка).

python parsers/apify_run.py 2gis input.json --cap 0.5 [--name 2гис_компании]
Итог: data/raw/<ключ>_<время>.json (таблица на Диск — только с --xlsx: всё смотрим в панели, таблиц не плодим).
"""
import argparse
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DRIVE = Path(r"G:\Мой диск\Мои задачи\Лидогенерация — коттеджи и подрядчики\Выгрузки")
ACTORS = json.loads((Path(__file__).parent / "apify_actors.json").read_text(encoding="utf-8"))
API = "https://api.apify.com/v2"


def token() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("APIFY_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("нет APIFY_TOKEN в .env")


def call(url: str, body: bytes | None = None):
    req = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + token()})
    return json.load(urllib.request.urlopen(req, timeout=120))


def run(actor: str, inp: dict, cap: float, wait: int = 3600) -> tuple[list, dict]:
    r = call(f"{API}/acts/{actor.replace('/', '~')}/runs?maxTotalChargeUsd={cap}", json.dumps(inp).encode())["data"]
    t0 = time.time()
    while r["status"] in ("READY", "RUNNING") and time.time() - t0 < wait:
        time.sleep(15)
        r = call(f"{API}/actor-runs/{r['id']}")["data"]
    items = call(f"{API}/datasets/{r['defaultDatasetId']}/items?clean=true&format=json")
    return items, r


def main():
    a = argparse.ArgumentParser()
    a.add_argument("key", choices=[k for k in ACTORS if not k.startswith("_")])
    a.add_argument("input", help="json с параметрами сборщика")
    a.add_argument("--cap", type=float, default=0.3, help="потолок трат за запуск, $")
    a.add_argument("--name", help="имя таблицы на Диске")
    a.add_argument("--xlsx", action="store_true", help="ещё и таблицу на Диск (по умолчанию нет)")
    o = a.parse_args()
    items, r = run(ACTORS[o.key]["actor"], json.loads(Path(o.input).read_text(encoding="utf-8")), o.cap)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    raw = ROOT / "data" / "raw" / f"{o.key}_{stamp}.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    if items and o.xlsx:
        df = pd.json_normalize(items, max_level=1)
        df = df.apply(lambda c: c.map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v))
        out = DRIVE / f"{o.name or o.key}_{stamp}.xlsx"
        df.to_excel(out, index=False)
        print(f"таблица: {out}")
    print(f"статус: {r['status']}; записей: {len(items)}; стоимость: ${r.get('usageTotalUsd') or 0:.3f}")


if __name__ == "__main__":
    main()
