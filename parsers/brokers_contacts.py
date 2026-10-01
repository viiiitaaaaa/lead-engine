"""Агентства-продавцы с Циана → сайт, почты и телефоны с сайта (поиск Яндекса через Bright Data).

python parsers/brokers_contacts.py
python parsers/brokers_contacts.py --recheck   # убрать чужие сайты из последней выгрузки
Берёт агентства из data/lists/cian_prodavcy.tsv. Итог: data/raw/brokers_<время>.json — {агентство: {сайт, заголовок, почты, телефоны}};
его показывает панель в таблице продавцов Циана.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from yandex_maps_bd import ROOT, env
from villages_merge import TR
from yandex_search_bd import REGISTRY, SKIP, serp, site_contacts

WRONG = {"ESTETICA": "estetica.ru"}  # тёзки: магазин дизайнерских столов, не агентство
NOISE = SKIP + r"|zoon|yell|flamp|spr\.ru|orgpage|otzyv|irecommend|hh\.ru|superjob|rusprofile|list-org"


def lat(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", "".join(TR.get(c, c) for c in x.lower()))


def same(name: str, url: str, title: str) -> bool:
    """сайт того же агентства: слово названия (от 3 букв, латиницей) есть в домене или заголовке"""
    if name in WRONG and WRONG[name] in url:
        return False
    stop = {"estate", "realty", "zagorodnaya", "nedvizhimost", "group", "gruppa", "company", "agentstvo", "ofis", "real", "international", "villa", "white", "all", "home"}
    words = [lat(w) for w in re.split(r"[\s.\-–|]+", name) if len(lat(w)) >= 3 and lat(w) not in stop]
    where = lat(url) + lat(title)
    first = lat(re.split(r"[\s.\-–|]+", name)[0])
    host = lat(re.sub(r"^https?://(www\.)?", "", url))
    return any(w in where for w in words) or (2 <= len(first) <= 3 and host.startswith(first))


def one(name: str, token: str) -> dict:
    items = [i for i in serp(f"{name} агентство загородной недвижимости официальный сайт", token)
             if not re.search(NOISE + "|" + REGISTRY, i["url"])]
    pick = next((i for i in items if same(name, i["url"], i["title"])), {})
    ph, ml = site_contacts(pick["url"]) if pick else ("", "")
    return {"сайт": re.match(r"https?://[^/]+", pick["url"]).group(0) if pick else "", "заголовок": pick.get("title", ""),
            "почты": ml, "телефоны": ph}


def main():
    if "--recheck" in sys.argv:  # перепроверить последнюю выгрузку без новых запросов
        f = sorted((ROOT / "data" / "raw").glob("brokers_*.json"))[-1]
        res = json.loads(f.read_text(encoding="utf-8"))
        for n, v in res.items():
            if v["сайт"] and not same(n, v["сайт"], v["заголовок"]):
                res[n] = {"сайт": "", "заголовок": "", "почты": "", "телефоны": ""}
        f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        return print(f"осталось с сайтом {sum(bool(x['сайт']) for x in res.values())} из {len(res)}")
    s = pd.read_csv(ROOT / "data" / "lists" / "cian_prodavcy.tsv", sep="\t").fillna("")
    names = s[s["кто"] == "агентство"]["продавец"].tolist()
    token = env("BRIGHTDATA_API_TOKEN")
    with ThreadPoolExecutor(5) as pool:
        res = dict(zip(names, pool.map(lambda n: one(n, token), names)))
    out = ROOT / "data" / "raw" / f"brokers_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    v = list(res.values())
    print(f"агентств {len(v)}: с сайтом {sum(bool(x['сайт']) for x in v)}, с почтой {sum(bool(x['почты']) for x in v)} → {out}")


if __name__ == "__main__":
    main()
