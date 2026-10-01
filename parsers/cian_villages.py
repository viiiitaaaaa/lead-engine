"""Коттеджные посёлки Циана по нашим шоссе: застройщик, его сайт, статус продаж, годы сдачи, что продаётся (участки = без подряда),
класс, материал. Бесплатно: список и карточки Циан отдаёт обычным запросом.

python parsers/cian_villages.py           # все посёлки по Новорижскому, Рублёво-Успенскому, Ильинскому
python parsers/cian_villages.py --limit 5 # проба
Итог: data/raw/cian_villages_<время>.json (карточки целиком) + data/lists/cian_poselki.tsv; показывает панель.
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from yandex_maps_bd import ROOT

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36", "Accept-Language": "ru"}
ROADS = {19: "Новорижское", 27: "Рублёво-Успенское", 9: "Ильинское"}  # 807 — другое «Ильинское», 1500 чужих посёлков
STATUS = {"opened": "застройщик продаёт", "closed": "распродан, обжит", "soon": "скоро старт", "pending": ""}
CLASS = {"elite": "элит", "business": "бизнес", "comfort": "комфорт", "economy": "эконом"}
MATERIAL = {"monolith": "монолит", "brick": "кирпич", "wood": "дерево", "timber": "брус", "log": "бревно", "frame": "каркас",
            "block": "блоки", "aerocreteBlock": "газобетон", "gasSilicateBlock": "газобетон", "foamConcreteBlock": "пеноблок", "ceramicBlock": "керамоблок"}


def get(url: str) -> str:
    for n in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=40).read().decode("utf-8", "ignore")
        except Exception as e:
            if getattr(e, "code", 0) == 404:
                return ""
            time.sleep(3 + 5 * n)
    return ""


def json_after(t: str, key: str, start: int = 0):
    j = t.find(key, start)
    return json.JSONDecoder().raw_decode(t, j + len(key))[0] if j >= 0 else None


def village_list() -> dict:
    """{id: (seo-ссылка, шоссе)} со всех страниц списка по каждому шоссе"""
    found = {}
    for road, name in ROADS.items():
        p, pages = 1, 1
        while p <= pages:
            t = get(f"https://www.cian.ru/kottedzhnye-poselki/?objectType%5B0%5D=5&road={road}&p={p}")
            pages = int((re.search(r'"totalPages":(\d+)', t) or [0, 0])[1])
            for v in json_after(t, '"villageList":', max(t.find('"totalPages"'), 0)) or []:
                found.setdefault(v["id"], (v["seo"]["url"], name))
            p += 1
        print(f"{name} ({road}): страниц {pages}, всего посёлков {len(found)}", flush=True)
    return found


def card(url: str) -> dict:
    t = get("https://www.cian.ru" + url)
    i = t.find('"builder":{"phone"')
    if i < 0:
        i = t.find('"builder":{')
    dec = json.JSONDecoder()
    for st in [m.start() for m in re.finditer(r"\{", t[:i])][::-1][:20000] if i >= 0 else []:
        try:
            x, e = dec.raw_decode(t, st)
        except ValueError:
            continue
        if e > i and isinstance(x, dict) and "builder" in x and "counterSet" in x:
            for k in ("gallery", "thumbnailList", "videoList", "seo", "offersSeo", "resaleOffersSeo", "builderOffersSeo", "geo"):
                x.pop(k, None)
            x["builder"].pop("seo", None)
            return x
    return {}


def row(v: dict, road: str) -> dict:
    b, c = v.get("builder") or {}, v.get("counterSet") or {}
    dev = "" if "не определен" in (b.get("name") or "") else b.get("name", "")
    road_km = next((r.get("distanceCity") for r in v.get("roadInfoList", []) if r.get("name", "").replace("ё", "е") == road.replace("ё", "е")), "")
    cats = v.get("newobjectCategorySet") or {}
    fy = sorted({y for y in (v.get("finishYearMin"), v.get("finishYearMax")) if y})
    return {
        "посёлок": v.get("name", ""), "шоссе": road, "км до МКАД": road_km, "класс": CLASS.get(v.get("villageClass"), v.get("villageClass", "")),
        "застройщик": dev, "телефон застройщика": b.get("phone", "") if b.get("displayPhone") else "",
        "сайт": v.get("siteUrl", ""), "статус продаж": STATUS.get(v.get("saleStatus"), v.get("saleStatus", "")),
        "сдача": "–".join(map(str, fy)), "участков в продаже": c.get("onSaleLandplot", 0),
        "коттеджей в продаже": c.get("onSaleCottage", 0), "таунхаусов в продаже": c.get("onSaleTownhouse", 0),
        "строится объектов": c.get("underConstruction", 0), "площадь, га": v.get("areaHectare", ""),
        "материал": ", ".join(MATERIAL.get(m, m) for m in v.get("houseMaterialList", [])),
        "что пишет застройщик об отделке": " | ".join(re.sub(r"\s+", " ", x.get("description", ""))[:200] for x in cats.values() if isinstance(x, dict) and re.search(r"отдел|ремонт|ключ|коробк|контур|white", x.get("description", ""), re.I)),
        "адрес": v.get("fullAddress", ""), "обновлено": (v.get("updated") or "")[:10],
        "Циан": f"https://www.cian.ru/kottedzhnyj-poselok-{v.get('id')}/" if not v.get("_url") else "https://www.cian.ru" + v["_url"],
    }


def main():
    raw = ROOT / "data" / "raw"
    if "--rebuild" in sys.argv:  # пересобрать таблицу из последней выгрузки, без запросов
        out = sorted(raw.glob("cian_villages_2*.json"))[-1]
        return table(json.loads(out.read_text(encoding="utf-8")), out)
    part = raw / "cian_villages_partial.json"  # пишется по ходу: при обрыве следующий запуск продолжит с места
    res = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {}
    lst = village_list()
    todo = [(i, u, r) for i, (u, r) in lst.items() if str(i) not in res]
    if "--limit" in sys.argv:
        todo = todo[: int(sys.argv[sys.argv.index("--limit") + 1])]
    print(f"уже есть {len(res)}, осталось {len(todo)}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(6) as pool:
        for n, ((i, u, r), v) in enumerate(zip(todo, pool.map(lambda x: card(x[1]), todo)), 1):
            res[str(i)] = {**v, "_url": u, "_road": r}
            if n % 10 == 0 or n == len(todo):
                part.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(todo)}, осталось ≈{(time.time() - t0) / n * (len(todo) - n) / 60:.0f} мин", flush=True)
    out = raw / f"cian_villages_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    part.unlink(missing_ok=True)
    table(res, out)


def site_root(u: str) -> str:
    m = re.match(r"https?://(?:www\.)?[^/?#]+", u or "")
    return m.group(0).replace("://www.", "://") if m else ""


def contacts(df: pd.DataFrame) -> dict:
    """телефоны и почты с сайтов посёлков/застройщиков, бесплатно; кэш data/raw/cian_villages_contacts.json, продолжает с места"""
    from yandex_search_bd import site_contacts
    f = ROOT / "data" / "raw" / "cian_villages_contacts.json"
    got = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    todo = sorted({site_root(u) for u in df["сайт"] if site_root(u)} - set(got))
    print(f"сайтов: кэш {len(got)}, осталось {len(todo)}", flush=True)
    with ThreadPoolExecutor(12) as pool:
        for n, (u, (ph, ml)) in enumerate(zip(todo, pool.map(lambda u: site_contacts(u), todo)), 1):
            got[u] = {"телефоны": ph, "почты": ml}
            if n % 10 == 0 or n == len(todo):
                f.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
                print(f"сайты: сделано {n} из {len(todo)}", flush=True)
    return got


JUNK = r"79991234567|79876543210|71234567|ivanov@|example\.|@domain|@mail\.com$|sentry|wixpress|@2x\."


def table(res: dict, out) -> None:
    df = pd.DataFrame([row(v, v["_road"]) for v in res.values() if v.get("name")])
    df = df[pd.to_numeric(df["км до МКАД"], errors="coerce").fillna(999) <= 60]  # наша территория — до 60 км
    df["застройщик"] = df["застройщик"].str.replace(r"\.\s*Офис продаж.*$", "", regex=True)
    got = contacts(df)
    clean = lambda s: ", ".join(x for x in s.split(", ") if x and not re.search(JUNK, x))
    df["телефоны с сайта"] = df["сайт"].map(lambda u: clean((got.get(site_root(u)) or {}).get("телефоны", "")))
    df["почты с сайта"] = df["сайт"].map(lambda u: clean((got.get(site_root(u)) or {}).get("почты", "")))
    df = df.sort_values(["шоссе", "км до МКАД"], key=lambda s: s.astype(str).str.zfill(4))
    df.to_csv(ROOT / "data" / "lists" / "cian_poselki.tsv", sep="\t", index=False)
    print(f"посёлков {len(df)}: застройщик {(df['застройщик'] != '').sum()}, сайт {(df['сайт'] != '').sum()}, "
          f"застройщик продаёт {(df['статус продаж'] == 'застройщик продаёт').sum()}, с участками {(df['участков в продаже'] > 0).sum()}, "
          f"строится {(df['строится объектов'] > 0).sum()}, пустых карточек {sum(not v.get('name') for v in res.values())} → {out}")


if __name__ == "__main__":
    main()
