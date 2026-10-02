"""Сайты и контакты застройщиков, у которых на Циане нет ни сайта, ни телефона: поиск Яндекса (Bright Data) по названию
застройщика → первый результат, где название застройщика есть в домене или заголовке → телефоны и почты с сайта (бесплатно).

python parsers/developers_sites.py
Итог: data/raw/developers_sites.json {застройщик: {сайт, заголовок, телефоны, почты}}; подхватывает parsers/cian_villages.py --rebuild.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import pandas as pd

from uk_search import NOISE
from villages_merge import key
from yandex_maps_bd import ROOT, env
from yandex_search_bd import REGISTRY, serp, site_contacts

AGG = r"novostroy|mskguru|realty\.ru|avaho|stroiki|buro-estate|stroycata|vk\.(?:ru|com)|zhukovka\.moscow|olimpstroyservis|novostroyki|domofond|zagorod"
LEGAL =r"\b(ООО|АО|ЗАО|ПАО|ГК|СЗ|Специализированный\s+Застройщик|группа компаний|компания)\b|[«»\"']|\(.*?\)"


def clean_name(n: str) -> str:
    return re.sub(r"\s+", " ", re.sub(LEGAL, " ", n, flags=re.I)).strip()


def pick(dev: str, village: str, items: list) -> dict:
    k = key(clean_name(dev))[:7]
    if len(k) < 3:
        return {}
    for i in items:
        if re.search(NOISE + "|" + REGISTRY + "|" + AGG, i["url"]):
            continue
        host = urlparse(i["url"]).netloc.lower().removeprefix("www.")
        if k in re.sub(r"[^a-z0-9]", "", host) or k in key(i["title"]):
            return {"сайт": f"https://{host}/", "заголовок": i["title"][:150]}
    return {}


def one(row: dict, token: str) -> dict:
    dev, village = row["застройщик"], row["посёлок"]
    p = pick(dev, village, serp(f'{clean_name(dev)} застройщик коттеджный поселок {village} официальный сайт', token) or [])
    if p:
        p["телефоны"], p["почты"] = site_contacts(p["сайт"])
    return p


def main():
    d = pd.read_csv(ROOT / "data" / "lists" / "cian_poselki.tsv", sep="\t", dtype=str).fillna("")
    has = (d["сайт"] != "") | (d["телефоны с сайта"] != "") | (d["почты с сайта"] != "") | (d["телефон застройщика"] != "")
    todo = d[(d["застройщик"].str.strip() != "") & ~has].drop_duplicates("застройщик").to_dict("records")
    f = ROOT / "data" / "raw" / "developers_sites.json"
    res = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    res = {k: ({} if v and re.search(AGG, v["сайт"]) else v) for k, v in res.items()}  # агрегаторы и брокеры — не застройщик
    f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    todo = [r for r in todo if r["застройщик"] not in res]
    print(f"застройщиков к поиску {len(todo)}", flush=True)
    token = env("BRIGHTDATA_API_TOKEN")
    with ThreadPoolExecutor(8) as pool:
        for n, (r, p) in enumerate(zip(todo, pool.map(lambda r: one(r, token), todo)), 1):
            res[r["застройщик"]] = p
            if n % 10 == 0 or n == len(todo):
                f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(todo)}", flush=True)
    v = list(res.values())
    print(f"сайт найден {sum(bool(x.get('сайт')) for x in v)} из {len(v)}, с телефоном {sum(bool(x.get('телефоны')) for x in v)}, с почтой {sum(bool(x.get('почты')) for x in v)}")


if __name__ == "__main__":
    main()
