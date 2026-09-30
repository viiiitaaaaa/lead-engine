"""Отзывы Яндекс Карт через Bright Data: страница /maps/org/<seoname>/<id>/reviews/ отдаёт до 50 отзывов.

Берёт организации с отзывами из последней таблицы yandex_maps_bd.py. Имена авторов НЕ сохраняются —
только текст, оценка, дата и ответ компании (для карты болей).

python parsers/yandex_reviews_bd.py            # все организации с отзывами
python parsers/yandex_reviews_bd.py --limit 5  # проба
"""
import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

from yandex_maps_bd import DRIVE, ROOT, env
import urllib.request


def fetch(card: str, token: str) -> list[dict]:
    url = card.rstrip("/") + "/reviews/"
    body = json.dumps({"zone": "serp_api1", "url": url, "format": "raw"}).encode()
    for _ in range(3):
        req = urllib.request.Request("https://api.brightdata.com/request", data=body, method="POST",
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            html = urllib.request.urlopen(req, timeout=150).read().decode("utf-8", "ignore")
        except Exception:
            continue
        m = re.search(r'<script[^>]*class="state-view"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            continue
        for s in json.loads(m.group(1)).get("stack", []):
            for it in (s.get("results") or {}).get("items") or []:
                rr = it.get("reviewResults") or {}
                if rr.get("reviews") is not None:
                    return rr["reviews"]
        return []
    return []


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--limit", type=int, default=0)
    o = a.parse_args()
    src = max(DRIVE.glob("яндекс_карты_BD_*.xlsx"), key=lambda p: p.stat().st_mtime)
    orgs = pd.read_excel(src, sheet_name="организации")
    orgs = orgs[orgs["отзывов"].fillna(0) > 0].sort_values("отзывов", ascending=False)
    if o.limit:
        orgs = orgs.head(o.limit)
    print(f"источник: {src.name}; организаций с отзывами: {len(orgs)}")
    token = env("BRIGHTDATA_API_TOKEN")
    recs = orgs.to_dict("records")
    with ThreadPoolExecutor(5) as pool:
        got = list(pool.map(lambda r: fetch(r["карточка"], token), recs))
    rows, raw, empty = [], {}, []
    for r, reviews in zip(recs, got):
        raw[str(r["id"])] = [{k: v.get(k) for k in ("rating", "text", "updatedTime", "businessComment")} for v in reviews]
        if not reviews:
            empty.append(r["название"])
        for v in reviews:
            rows.append({
                "организация": r["название"],
                "вид деятельности": r["вид деятельности"],
                "тип запроса": r["тип запроса"],
                "оценка": v.get("rating"),
                "дата": (v.get("updatedTime") or "")[:10],
                "отзыв": v.get("text"),
                "ответ компании": (v.get("businessComment") or {}).get("text"),
                "карточка": r["карточка"],
            })
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    (ROOT / "data" / "raw" / f"yreviews_{stamp}.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    df = pd.DataFrame(rows)
    out = DRIVE / f"яндекс_отзывы_{stamp}.xlsx"
    with pd.ExcelWriter(out) as w:
        df.to_excel(w, sheet_name="отзывы", index=False)
        pd.DataFrame({"без отзывов в ответе": empty}).to_excel(w, sheet_name="пусто", index=False)
    print(f"отзывов: {len(df)}; организаций без ответа: {len(empty)}\nтаблица: {out}")


if __name__ == "__main__":
    main()
