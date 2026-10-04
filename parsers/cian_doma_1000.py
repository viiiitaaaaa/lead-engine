"""Премиальные дома от 1000 м² на продаже (её список 04.10: «премиум ИЖС от 1000 кв2» как клиенты-коммерция).
Циан, бесплатно: продажа домов по Новорижскому, Рублёво-Успенскому и Ильинскому шоссе, фильтр minarea=1000
(mintarea Циан для домов игнорирует — проверено 04.10). Дом такого размера = центральная вентиляция, бассейн, СПА, котельная.

python parsers/cian_doma_1000.py
Итог: data/lists/doma_1000.tsv
"""
import re
import time

import pandas as pd

from cian_villages import ROADS, get, json_after
from yandex_maps_bd import ROOT


def main():
    rows = {}
    for road, name in ROADS.items():
        p, total = 1, None
        while True:
            t = get(f"https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&object_type%5B0%5D=1&offer_type=suburban"
                    f"&region=4593&highway%5B0%5D={road}&minarea=1000&p={p}")
            total = total or int((re.search(r'"totalOffers":(\d+)', t) or [0, 0])[1])
            offers = json_after(t, '"offers":', t.find('"offers":[')) or []
            new = 0
            for o in offers:
                area = float(o.get("totalArea") or 0)
                if area < 1000 or o.get("cianId") in rows:
                    continue
                new += 1
                geo = o.get("geo") or {}
                land = o.get("land") or {}
                user = o.get("user") or {}
                rows[o["cianId"]] = {
                    "шоссе": name, "площадь дома, м²": area, "участок, сот.": land.get("area"),
                    "цена, млн ₽": round(((o.get("bargainTerms") or {}).get("priceRur") or 0) / 1e6, 1),
                    "посёлок": (o.get("kp") or {}).get("name") or next((a.get("name") for a in geo.get("address") or []
                                                                        if a.get("type") in ("location", "village") and not str(a.get("name")).startswith("Московск")), ""),
                    "адрес": geo.get("userInput", ""), "год постройки": (o.get("building") or {}).get("buildYear"),
                    "материал": (o.get("building") or {}).get("materialType"), "продавец": "собственник" if user.get("isOwner") else (user.get("agencyName") or user.get("companyName") or "агент"),
                    "ссылка": (o.get("fullUrl") or "").split("?")[0]}
            print(f"{name}: страница {p}, домов {len(rows)} (в выдаче {total})", flush=True)
            if not offers or not new or p * 28 >= total:
                break
            p += 1
            time.sleep(2)
    t = pd.DataFrame(rows.values())
    t.to_csv(ROOT / "data/lists/doma_1000.tsv", sep="\t", index=False)
    print(t.groupby("шоссе").agg(домов=("площадь дома, м²", "size"), медиана_м2=("площадь дома, м²", "median"), медиана_цены=("цена, млн ₽", "median")).to_string())


if __name__ == "__main__":
    main()
