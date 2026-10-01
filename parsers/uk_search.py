"""Управляющие компании посёлков: поиск Яндекса (Bright Data) + телефоны и почты с найденного сайта.

python parsers/uk_search.py            # все посёлки нашей территории из data/lists/poselki_katalog.tsv
python parsers/uk_search.py --limit 20 # проба
python parsers/uk_search.py --reclass  # пересортировать последнюю выгрузку строже, без запросов
Итог: data/raw/uk_<время>.json — {посёлок: {сайт, что это (УК / сайт посёлка), заголовок, сниппет, телефоны, почты}}; показывает панель.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

from yandex_maps_bd import ROOT, env
from villages_merge import key
from yandex_search_bd import REGISTRY, SKIP, serp, site_contacts

UK = r"управляющ|\bУК\b|эксплуатац|служба заказчика|ТСН|ДНП|СНТ|сервис.{0,15}пос[её]лк"
NOISE = SKIP + (r"|villagio|onehouse|zagorod|kp\.ru|poselkimo|move\.ru|domclick|realty\.yandex|mirkvartir|restate|intermark|prime\.su"
                r"|slrealty|homehunter|barn-estate|vesco|novaya-riga\.ru|whitewill|nf-group|knightfrank|tweed|foxproperty|arbor|kayra"
                r"|rublevka|zemdozor|kottedzhnye|poselki|countryhouse|metrium|incom|miel|etagi|sob\.ru|irr\.ru|youla")


def choose(items: list, k: str) -> tuple:
    """1) УК: «управляющая/эксплуатация» + название посёлка; 2) официальный сайт: название в домене; брокеров не берём"""
    items = [i for i in items if not re.search(NOISE + "|" + REGISTRY, i["url"])]
    uk = [i for i in items if k in key(i["title"] + " " + i["snippet"]) and re.search(UK, i["title"] + " " + i["snippet"], re.I)]
    own = [i for i in items if k in re.sub(r"[^a-z0-9]", "", urlparse(i["url"]).netloc.lower())]
    return (uk[0], "УК") if uk else (own[0], "сайт посёлка") if own else ({}, "")


def one(row: dict, token: str) -> dict:
    k = key(row["посёлок"])[:8]
    pick, kind = ({}, "")
    if k:
        pick, kind = choose(serp(f'управляющая компания коттеджный поселок {row["посёлок"]} {row["шоссе"]} шоссе', token), k)
    if k and not pick:  # второй заход: официальный сайт посёлка
        pick, kind = choose(serp(f'коттеджный поселок {row["посёлок"]} официальный сайт', token), k)
    ph, ml = site_contacts(pick["url"]) if pick else ("", "")
    return {"сайт": pick.get("url", ""), "что это": kind, "заголовок": pick.get("title", ""), "сниппет": pick.get("snippet", "")[:300],
            "телефоны": ph, "почты": ml}


JUNK_SITES = r"buro-estate|pointestate|forumhouse|domzamkad|xn--e1agfdnfp|cian|avito|dzen|journal|statya|article|news|novosti|lomonosov|spb|len/"
REG = r"sravni|building-info|datanewton|rusprofile|checko|list-org|zachestnyibiznes|sbis|audit-it|vbankcenter|zoon|2gis|yandex\.ru/maps"


def reclass(v: dict) -> dict:
    """строже: УК — только если управляющая/ТСН в заголовке; справочник юрлиц — «юрлицо» (его собственные контакты не берём);
    статьи/форумы/каталоги — убрать"""
    if not v.get("сайт") or re.search(JUNK_SITES, v["сайт"], re.I):
        return {**v, "что это": "", "сайт": "", "телефоны": "", "почты": ""}
    if re.search(REG, v["сайт"], re.I):
        mails = ", ".join(re.findall(r"[\w.+-]+@[\w-]+\.[a-z]{2,}(?:\.[a-z]{2,})?", v["сниппет"]))  # почта юрлица из сниппета справочника
        return {**v, "что это": "юрлицо / справочник", "телефоны": "", "почты": mails}
    strict = re.search(r"управляющ|(?<![а-яё])ук(?![а-яё])|эксплуатац|служба заказчика|тсн", v["заголовок"], re.I)
    return {**v, "что это": "УК" if strict else "сайт посёлка"}


def main():
    if "--reclass" in sys.argv:  # пересортировать последнюю выгрузку без запросов
        f = sorted((ROOT / "data" / "raw").glob("uk_2*.json"))[-1]
        res = {k: reclass(v) for k, v in json.loads(f.read_text(encoding="utf-8")).items()}
        f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        from collections import Counter
        return print(Counter(v["что это"] or "—" for v in res.values()))
    kat = pd.read_csv(ROOT / "data" / "lists" / "poselki_katalog.tsv", sep="\t").fillna("")
    kat = kat[kat["наша территория"].astype(str) == "True"]
    kat = kat.assign(_p=(kat["наш список"] != "") * 1000 + kat["домов на Циане"].astype(int)).sort_values("_p", ascending=False)
    if "--limit" in sys.argv:
        kat = kat.head(int(sys.argv[sys.argv.index("--limit") + 1]))
    token = env("BRIGHTDATA_API_TOKEN")
    part = ROOT / "data" / "raw" / "uk_partial.json"  # пишется по ходу: при обрыве следующий запуск продолжит с места
    res = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {}
    rows = [r for r in kat.to_dict("records") if r["посёлок"] not in res]
    print(f"уже есть {len(res)}, осталось {len(rows)}", flush=True)
    with ThreadPoolExecutor(16) as pool:
        for n, (r, v) in enumerate(zip(rows, pool.map(lambda r: one(r, token), rows)), 1):
            res[r["посёлок"]] = reclass(v)
            if n % 10 == 0 or n == len(rows):
                part.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(rows)}", flush=True)
    out = ROOT / "data" / "raw" / f"uk_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    part.unlink()
    v = list(res.values())
    print(f"посёлков {len(v)}: УК {sum(x['что это'] == 'УК' for x in v)}, сайт посёлка {sum(x['что это'] == 'сайт посёлка' for x in v)}, "
          f"с телефоном {sum(bool(x['телефоны']) for x in v)}, с почтой {sum(bool(x['почты']) for x in v)} → {out}")


if __name__ == "__main__":
    main()
