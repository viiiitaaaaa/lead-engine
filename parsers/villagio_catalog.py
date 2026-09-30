"""Каталог посёлков Villagio Realty (villagio-vip.ru/villages) — обычными запросами, бесплатно.

python parsers/villagio_catalog.py
python parsers/villagio_catalog.py --fix   # перечитать карточки без шоссе
Итог: data/raw/villagio_<время>.json: посёлок, шоссе, км, объектов, эксперты, ссылка (дальше — villages_merge.py и панель).
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from apify_run import ROOT

SITE = "https://villagio-vip.ru"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def get(path: str) -> str:
    for n in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(SITE + path, headers=UA), timeout=40).read().decode("utf-8", "ignore")
        except Exception:
            time.sleep(2 + 3 * n)
    return ""


def card(vid: str) -> dict:
    t = get(f"/villages/{vid}/")
    title = html.unescape((re.search(r"<title>(.*?)</title>", t, re.S) or [None, ""])[1]).split("—")[0].strip()
    name = re.sub(r"^Коттеджный пос[её]лок\s*", "", title)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)))
    hw = re.search(r"(\d+)\s*км,\s*([А-ЯЁа-яё-]+(?:\s[А-ЯЁа-яё-]+)?\s+шоссе)", txt)
    km = re.search(r"Коттеджный пос[её]лок .{0,80}?(\d+)\s*км\s+Заказать", txt)
    if not hw:  # шоссе только в описании: «… по Новой Риге», «Рублёво-Успенскому»
        m = re.search(r"Новорижск|Новой Риг|Рубл[её]во-Успенск|Рублевск|Ильинск|Киевск|Минск|Калужск|Можайск|Волоколамск|Дмитровск", txt)
        alias = {"Новой Риг": "Новорижское шоссе", "Новорижск": "Новорижское шоссе", "Рублево-Успенск": "Рублёво-Успенское шоссе",
                 "Рублёво-Успенск": "Рублёво-Успенское шоссе", "Рублевск": "Рублевское шоссе"}
        hw_name = alias.get(m.group(0), m.group(0) + "ое шоссе") if m else ""
    experts = sorted(set(re.findall(r"([А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+)\s+Эксперт Villagio", txt)))
    return {"посёлок": name, "шоссе": hw.group(2) if hw else hw_name,
            "км до МКАД": int(hw.group(1)) if hw else int(km.group(1)) if km else None,
            "объектов в продаже": txt.count("Опубликовано"),
            "эксперты Villagio": ", ".join(experts[:5]), "ссылка": f"{SITE}/villages/{vid}/"}


def main():
    if "--fix" in sys.argv:  # дочинить посёлки без шоссе в последней выгрузке
        f = sorted((ROOT / "data" / "raw").glob("villagio_*.json"))[-1]
        rows = json.loads(f.read_text(encoding="utf-8"))
        bad = [i for i, r in enumerate(rows) if not r["шоссе"]]
        with ThreadPoolExecutor(4) as pool:
            for i, r in zip(bad, pool.map(lambda i: card(rows[i]["ссылка"].rstrip("/").split("/")[-1]), bad)):
                rows[i] = r
        return save(rows)
    first = get("/villages/")
    pages = max(int(p) for p in re.findall(r"/villages/\?page=(\d+)", first))
    with ThreadPoolExecutor(4) as pool:
        listing = [first] + list(pool.map(lambda p: get(f"/villages/?page={p}"), range(2, pages + 1)))
    ids = sorted({i for t in listing for i in re.findall(r'href="/villages/(\d+)/"', t)}, key=int)
    print(f"страниц {pages}, посёлков {len(ids)}")
    with ThreadPoolExecutor(4) as pool:
        rows = list(pool.map(card, ids))
    save(rows)


def save(rows):
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    (ROOT / "data" / "raw" / f"villagio_{stamp}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    df = pd.DataFrame(rows)
    print(len(df), df["шоссе"].value_counts().head(12).to_dict())


if __name__ == "__main__":
    main()
