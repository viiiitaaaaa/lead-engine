"""Яндекс Карты через Apify (m_mamaev/yandex-maps-places-scraper): запросы → карточки организаций с отзывами.

Запуск:  python parsers/yandex_maps.py "Миллениум Парк коттеджный посёлок" "Берг Хаус инжиниринг" --items 5 --reviews 10 --cap 0.3
Итог: data/raw/yandex_<время>.json и таблица в Google Диск → Выгрузки.
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DRIVE = Path(r"G:\Мой диск\Мои задачи\Лидогенерация — коттеджи и подрядчики\Выгрузки")
ACTOR = "m_mamaev~yandex-maps-places-scraper"


def token() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("APIFY_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit("нет APIFY_TOKEN в .env")


def run(queries, items, reviews, cap, loc):
    url = (f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
           f"?maxTotalChargeUsd={cap}&timeout=600")
    body = {"query": queries, "locations": loc, "maxItems": items,
            "language": "RU", "maxReviews": reviews}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + token()})
    return json.load(urllib.request.urlopen(req, timeout=700))


def flat(p: dict) -> dict:
    """Одна строка таблицы: что нужно для воронки."""
    phones = p.get("phones") or []
    socials = p.get("socialLinks") or p.get("social") or []
    reviews = p.get("reviews") or []
    return {
        "запрос": p.get("query") or p.get("searchQuery"),
        "название": p.get("title") or p.get("name"),
        "вид деятельности": ", ".join(c if isinstance(c, str) else c.get("name", "") for c in (p.get("categories") or [])),
        "адрес": p.get("address"),
        "телефоны": ", ".join(x if isinstance(x, str) else (x.get("number") or x.get("formatted") or "") for x in phones),
        "сайт": ", ".join(p["website"]) if isinstance(p.get("website"), list) else p.get("website"),
        "соцсети": ", ".join(x if isinstance(x, str) else (x.get("href") or x.get("url") or "") for x in socials),
        "рейтинг": round(p["totalScore"], 1) if p.get("totalScore") else p.get("rating"),
        "отзывов": p.get("reviewsCount") or p.get("reviewCount"),
        "карточка": p.get("url") or f"https://yandex.ru/maps/org/{p.get('placeId')}/",
        "отзывы (текст)": "\n---\n".join((r.get("text") or "") for r in reviews if isinstance(r, dict)),
    }


def main():
    a = argparse.ArgumentParser()
    a.add_argument("queries", nargs="+")
    a.add_argument("--items", type=int, default=5)
    a.add_argument("--reviews", type=int, default=10)
    a.add_argument("--loc", default="Московская область")
    a.add_argument("--cap", type=float, default=0.3, help="потолок трат за запуск, $")
    o = a.parse_args()
    data = run(o.queries, o.items, o.reviews, o.cap, o.loc)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    raw = ROOT / "data" / "raw" / f"yandex_{stamp}.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    df = pd.DataFrame([flat(p) for p in data])
    DRIVE.mkdir(parents=True, exist_ok=True)
    out = DRIVE / f"яндекс_карты_{stamp}.xlsx"
    df.to_excel(out, index=False)
    print(f"организаций: {len(df)}\nсырые: {raw}\nтаблица: {out}")


if __name__ == "__main__":
    main()
