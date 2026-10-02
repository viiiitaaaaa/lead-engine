"""Сводка «строка = посёлок» (формат ТЗ): всё, что собрано о посёлке, в одной строке.
Каталоги (poselki_katalog.tsv, с УК и Telegram) + Циан (cian_poselki.tsv: застройщик, класс, стройка) + сайты застройщиков
(data/raw/developers_sites.json) + ВК и FORUMHOUSE (soobshchestva_poselkov.tsv) + подрядчики в посёлке (podryadchiki_poselkov.tsv).

python parsers/poselki_svod.py
Итог: data/lists/poselki_svod.tsv; показывает панель.
"""
import json
import re
from collections import defaultdict

import pandas as pd

from villages_merge import key
from yandex_maps_bd import ROOT

L = ROOT / "data" / "lists"


def read(name: str) -> pd.DataFrame:
    p = L / name
    return pd.read_csv(p, sep="\t", dtype=str).fillna("") if p.exists() else pd.DataFrame()


def k8(name: str) -> str:
    return key(name)[:10]


def main():
    kat, cv, sb, pdr = read("poselki_katalog.tsv"), read("cian_poselki.tsv"), read("soobshchestva_poselkov.tsv"), read("podryadchiki_poselkov.tsv")
    kat = kat[kat["наша территория"] == "True"]
    dsf = ROOT / "data" / "raw" / "developers_sites.json"
    dev_sites = json.loads(dsf.read_text(encoding="utf-8")) if dsf.exists() else {}

    rows = {}
    for r in kat.to_dict("records"):
        # заголовки страниц вместо названий: «Купить дома и участки в посёлке Миллениум Парк | …», «Ренессанс Парк: дома и участки…»
        r["посёлок"] = re.sub(r"^.*?(?:в пос[её]лке|в кп)\s+|\s*[|:].*$", "", r["посёлок"], flags=re.I).strip()
        rows.setdefault(k8(r["посёлок"]), {"посёлок": r["посёлок"], "шоссе": r["шоссе"], "км до МКАД": r["км до МКАД"],
                                           "наш список": r["наш список"], "домов на Циане (от 50 млн)": r["домов на Циане"],
                                           "УК / сайт посёлка": r["контакт: что"], "сайт посёлка": r["контакт: сайт"],
                                           "телефоны посёлка": r["контакт: телефоны"], "почты посёлка": r["контакт: почты"],
                                           "Telegram": r["Telegram"], "Villagio": r["Villagio"], "ONEHOUSE": r["ONEHOUSE"]})
    for r in cv.to_dict("records"):
        name = re.sub(r"\s*\(.*?\)", "", r["посёлок"]).strip()
        alt = (re.search(r"\((.*?)\)", r["посёлок"]) or [None, ""])[1]  # «Chateau Souverain (Шато Соверен)» — ищем по обоим
        kk = next((k for k in (k8(name), k8(alt)) if k and k in rows), k8(name))
        e = rows.setdefault(kk, {"посёлок": name, "шоссе": r["шоссе"], "км до МКАД": r["км до МКАД"]})
        ds = dev_sites.get(r["застройщик"]) or {}
        e.update({"класс": r["класс"], "застройщик": r["застройщик"].strip(), "статус продаж": r["статус продаж"], "сдача": r["сдача"],
                  "участков в продаже": r["участков в продаже"],
                  "домов в продаже у застройщика": str(int(float(r["коттеджей в продаже"] or 0) + float(r["таунхаусов в продаже"] or 0))),
                  "строится объектов": r["строится объектов"], "площадь, га": r["площадь, га"], "материал": r["материал"],
                  "сайт застройщика": r["сайт"] or ds.get("сайт", ""),
                  "телефоны застройщика": r["телефон застройщика"] or r["телефоны с сайта"] or ds.get("телефоны", ""),
                  "почты застройщика": r["почты с сайта"] or ds.get("почты", ""), "Циан": r["Циан"]})

    vk, fh = defaultdict(list), defaultdict(list)
    for r in sb.to_dict("records"):
        (fh if r["вид"] == "FORUMHOUSE" else vk if r["вид"] == "ВК: сообщество" else defaultdict(list))[k8(r["посёлок"])].append(r["ссылка"])
    pod = defaultdict(list)
    for r in pdr.to_dict("records"):
        if r.get("сомнительно") == "True":
            continue
        for v in r["посёлки"].split(", "):
            pod[k8(v)].append(r["сайт"])
    for k, e in rows.items():
        e["групп ВК"], e["ВК"] = len(vk[k]), ", ".join(vk[k][:3])
        e["веток FORUMHOUSE"], e["FORUMHOUSE"] = len(fh[k]), ", ".join(fh[k][:3])
        e["подрядчиков работает"], e["подрядчики"] = len(pod[k]), ", ".join(pod[k][:5])
        e["есть контакт"] = any(e.get(c) for c in ("телефоны застройщика", "почты застройщика", "телефоны посёлка", "почты посёлка"))

    # её список по-русски, а посёлок назван латиницей: «Виджион» = КП VISION (Villagio Estate), выяснено 02.10
    for name, ours in {"VISION": "Виджион"}.items():
        k = k8(name)
        if k in rows:
            rows[k]["наш список"] = ours
    df = pd.DataFrame(rows.values()).fillna("")
    df["_km"] = pd.to_numeric(df["км до МКАД"], errors="coerce")
    df = df[df["_km"].fillna(0) <= 60].sort_values(["шоссе", "_km"]).drop(columns="_km")
    df.to_csv(L / "poselki_svod.tsv", sep="\t", index=False)
    print(f"посёлков {len(df)}: застройщик {(df['застройщик'] != '').sum()}, контакт {df['есть контакт'].sum()}, "
          f"Telegram {(df['Telegram'] != '').sum()}, ВК {(df['групп ВК'] > 0).sum()}, подрядчики {(df['подрядчиков работает'] > 0).sum()}, "
          f"класс элит/бизнес {df['класс'].isin(['элит', 'бизнес']).sum()}")


if __name__ == "__main__":
    main()
