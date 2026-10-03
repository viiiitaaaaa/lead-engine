"""Отзывы о брендах климатического и инженерного оборудования (её задача 03.10, пункт 3): карточки брендов, их шоурумов и
официальных сервисов в 2ГИС по Москве и области (бесплатно). Наш Frivent — тоже здесь, чтобы видеть свои отзывы.

python parsers/klimat_brendy.py
Итог: data/raw/klimat_brendy.json = {бренд: {"карточки": [...], "отзывы": [...]}}
"""
import json
import re
import urllib.parse

from gis_reviews import SEARCH_KEY, j, reviews
from yandex_maps_bd import ROOT

OUT = ROOT / "data/raw/klimat_brendy.json"
BRANDS = {  # бренд: (поиск, регэксп названия карточки)
    "Frivent": ("Frivent", r"frivent|фривент"),
    "Turkov": ("Turkov", r"turkov|турков"),
    "Breezart": ("Breezart", r"breezart|бризарт"),
    "Zehnder": ("Zehnder", r"zehnder|цендер"),
    "Komfovent": ("Komfovent", r"komfovent|комфовент"),
    "Systemair": ("Systemair", r"systemair|системэйр"),
    "Salda": ("Salda", r"salda|салда"),
    "Dantherm": ("Dantherm", r"dantherm|данфер"),
    "Daikin": ("Daikin", r"daikin|дайкин"),
    "Mitsubishi Electric": ("Mitsubishi Electric", r"mitsubishi"),
    "Viessmann": ("Viessmann", r"viessmann|висман"),
    "Buderus": ("Buderus", r"buderus|будерус"),
    "Vaillant": ("Vaillant", r"vaillant|вайлант"),
    "Wolf": ("Wolf котлы", r"^wolf|вольф"),
    "Гейзер": ("Гейзер водоочистка", r"гейзер"),
    "Аквафор": ("Аквафор", r"аквафор"),
    "Ecosoft": ("Ecosoft", r"ecosoft|экософт"),
}


def main():
    res = {}
    for b, (q, rx) in BRANDS.items():
        cards = {}
        for page in range(1, 4):
            r = j(f"https://catalog.api.2gis.com/3.0/items?q={urllib.parse.quote(q)}&region_id=32&page_size=10&page={page}"
                  f"&fields=items.reviews,items.rubrics,items.address&key={SEARCH_KEY}")
            items = (r.get("result") or {}).get("items") or []
            for it in items:
                n = int((it.get("reviews") or {}).get("general_review_count") or 0)
                if it.get("type") == "branch" and n and re.search(rx, it.get("name", ""), re.I):
                    cards[it["id"].split("_")[0]] = {"название": it.get("name", ""), "адрес": it.get("address_name", ""), "отзывов": n,
                                                     "рубрики": ", ".join(x.get("name", "") for x in it.get("rubrics") or [])}
            if len(items) < 10:
                break
        rv = [dict(x, карточка=c["название"]) for k, c in cards.items() for x in reviews(k, cap=300)]
        res[b] = {"карточки": list(cards.values()), "отзывы": rv}
        OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        print(f"{b:20} карточек {len(cards):3}  отзывов {len(rv)}", flush=True)


if __name__ == "__main__":
    main()
