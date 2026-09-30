"""Свод Циана: все data/raw/cian_*.json → дома (без дублей) + продавцы (брокеры, агентства, застройщики).

python parsers/cian_digest.py
Итог: Google Диск → Выгрузки\\циан_свод_<дата>.xlsx (лист «дома» первый — его читает build_base.py, лист «продавцы»).
"""
import json
import re
from collections import Counter
from datetime import datetime

import pandas as pd

from apify_run import DRIVE, ROOT

SKIP_GEO = {1, 2, 210}  # страна, область, городской округ


def place(i: dict) -> str:
    names = [g.get("fullName", "") for g in (i.get("geo") or {}).get("address", []) if g.get("locationTypeId") not in SKIP_GEO]
    kp = [n for n in names if n.endswith(" кп")]
    return kp[0][:-3] + " (КП)" if kp else next((n for n in names if not re.fullmatch(r"\d+|улица.*|.*муниципальный округ", n)), "")


def main():
    offers = {}
    for f in sorted((ROOT / "data" / "raw").glob("cian_*.json")):
        for i in json.loads(f.read_text(encoding="utf-8")):
            offers[i["id"]] = i
    houses = []
    for i in offers.values():
        ag = i.get("agent") or {}
        hw = next(iter((i.get("geo") or {}).get("highways") or []), {})
        who = "застройщик" if i.get("isFromDeveloper") else "собственник" if i.get("isByHomeowner") else {
            "agency": "агентство", "specialist": "риелтор", "managementCompany": "УК"}.get(ag.get("accountType"), "?")
        houses.append({"посёлок/место": place(i), "шоссе": hw.get("name", ""), "до МКАД, км": hw.get("distance", ""),
                       "цена, млн ₽": round((i.get("bargainTerms") or {}).get("price", 0) / 1e6, 1) or None,
                       "что": i.get("formattedFullInfo", ""), "адрес": i.get("formattedAddress", ""),
                       "продавец": ag.get("brandingName") or ag.get("name") or "", "кто продаёт": who,
                       "телефон": ", ".join(ag.get("phones") or []), "ссылка": f"https://www.cian.ru/sale/suburban/{i['id']}/"})
    h = pd.DataFrame(houses).sort_values("цена, млн ₽", ascending=False)
    sellers = []
    for (name, who), g in h[h["продавец"] != ""].groupby(["продавец", "кто продаёт"]):
        top = Counter(p for p in g["посёлок/место"] if p).most_common(4)
        sellers.append({"продавец": name, "кто": who, "домов": len(g), "телефоны": ", ".join(sorted({p for x in g["телефон"] for p in x.split(", ") if p})),
                        "цены, млн ₽": f'{g["цена, млн ₽"].min():g}–{g["цена, млн ₽"].max():g}',
                        "шоссе": ", ".join(sorted(set(g["шоссе"]) - {""})), "где продаёт": ", ".join(f"{p} ({n})" for p, n in top)})
    s = pd.DataFrame(sellers).sort_values("домов", ascending=False)
    out = DRIVE / f"циан_свод_{datetime.now():%Y-%m-%d}.xlsx"
    with pd.ExcelWriter(out) as w:
        h.to_excel(w, sheet_name="дома", index=False)
        s.to_excel(w, sheet_name="продавцы", index=False)
    print(f"домов {len(h)}, продавцов {len(s)} ({s['кто'].value_counts().to_dict()}) → {out}")
    print(h["посёлок/место"].value_counts().head(15).to_dict())


if __name__ == "__main__":
    main()
