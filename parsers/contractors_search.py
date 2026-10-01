"""Подрядчики, которые уже работают в наших посёлках: поиск Яндекса (Bright Data) «строительство / отделка дома в <посёлок>»
→ сайты компаний, у которых в заголовке или сниппете и название посёлка, и стройка/отделка/инженерия → сводка по компаниям
(в скольких посёлках «засветилась») + телефоны и почты с их сайтов (бесплатно).

python parsers/contractors_search.py            # посёлки нашей территории (каталог) + элит/бизнес Циана
python parsers/contractors_search.py --limit 10 # проба
python parsers/contractors_search.py --reparse  # пересобрать сводку из сохранённой выдачи, без запросов
Итог: data/raw/contractors_<время>.json (выдача по посёлкам) + data/lists/podryadchiki_poselkov.tsv; показывает панель.
"""
import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

from yandex_maps_bd import ROOT, env
from villages_merge import key
from yandex_search_bd import REGISTRY, SKIP, serp, site_contacts
from uk_search import NOISE

WORK = (r"строител|строим|строй|построй|под ключ|отделк|ремонт|дизайн|интерьер|инженер|отоплен|водоснабж|вентиляц|кондиц|"
        r"электромонтаж|умный дом|бассейн|кровл|фасад|фундамент|ландшафт|остеклен|окна|двери|лестниц|сауна|баня")
MORE_NOISE = (r"|realty|estate|недвиж|nedvizh|zagorod|kottedzh|poselk|village|domofond|n1\.ru|kvadroom|gdeetotdom|rbc|forbes|kommersant|"
              r"vedomosti|ria\.ru|tass|mk\.ru|riamo|360tv|inmosreg|market\.yandex|ozon|wildberries|profi\.ru|youdo|houzz|forumhouse|"
              r"stroi\.ru|stroiki|krovlya|gosuslugi|mos\.ru|mosreg|torgi|zakupki|rosreestr|hh\.ru|superjob|otzovik|irecommend|flamp|"
              r"vk\.ru|zoon|yell\.ru|spravker|orgpage|cataloxy|firmy|tiu\.ru|pulscen|blizko|pikabu|drive2|livejournal|reddit|wiki|dom\.ru|domclick|kp\.ru|sob\.ru|arendator|move\.ru|mirkvartir|restate|bn\.ru")


def villages() -> list:
    """посёлки нашей территории из каталога + элит/бизнес Циана; без повторов по ключу названия; важные — первыми"""
    kat = pd.read_csv(ROOT / "data" / "lists" / "poselki_katalog.tsv", sep="\t").fillna("")
    kat = kat[kat["наша территория"].astype(str) == "True"]
    out = {}
    for r in kat.to_dict("records"):
        out.setdefault(key(r["посёлок"]), {"посёлок": r["посёлок"], "шоссе": r["шоссе"],
                                           "вес": (r["наш список"] != "") * 1000 + int(r["домов на Циане"] or 0)})
    cvp = ROOT / "data" / "lists" / "cian_poselki.tsv"
    if cvp.exists():
        cv = pd.read_csv(cvp, sep="\t", dtype=str).fillna("")
        for r in cv[cv["класс"].isin(["элит", "бизнес"])].to_dict("records"):
            name = re.sub(r"\s*\(.*?\)", "", r["посёлок"]).strip()
            v = out.setdefault(key(name), {"посёлок": name, "шоссе": r["шоссе"], "вес": 0})
            v["вес"] += int(float(r["строится объектов"] or 0)) + 50
    return sorted((v for k, v in out.items() if len(k) >= 4), key=lambda v: -v["вес"])


def picks(village: str, items: list) -> list:
    k = key(village)[:8]
    res = []
    for i in items:
        host = urlparse(i["url"]).netloc.lower().removeprefix("www.")
        text = i["title"] + " " + i["snippet"]
        if not host or re.search(NOISE + MORE_NOISE + "|" + SKIP + "|" + REGISTRY, i["url"], re.I):
            continue
        if k in key(host):  # сайт самого посёлка — не подрядчик
            continue
        if k in key(text) and re.search(WORK, text, re.I):
            res.append({"сайт": host, "url": i["url"], "заголовок": i["title"][:150], "сниппет": i["snippet"][:300]})
    return res


def one(v: dict, token: str) -> list:
    return serp(f'строительство и отделка дома под ключ в коттеджном поселке {v["посёлок"]}', token) or []


def summary(res: dict) -> pd.DataFrame:
    by = defaultdict(lambda: {"посёлки": [], "заголовок": "", "сниппет": "", "url": ""})
    for village, items in res.items():
        for p in picks(village, items):
            b = by[p["сайт"]]
            if village not in b["посёлки"]:
                b["посёлки"].append(village)
            if not b["заголовок"]:
                b.update({k: p[k] for k in ("заголовок", "сниппет", "url")})
    rows = [{"сайт": s, "посёлков": len(b["посёлки"]), "посёлки": ", ".join(b["посёлки"]), "заголовок": b["заголовок"],
             "сниппет": b["сниппет"], "пример страницы": b["url"]} for s, b in by.items()]
    return pd.DataFrame(rows).sort_values("посёлков", ascending=False) if rows else pd.DataFrame()


def finish(res: dict) -> None:
    df = summary(res)
    if df.empty:
        return print("подрядчиков не найдено")
    f = ROOT / "data" / "raw" / "contractors_contacts.json"  # кэш контактов с сайтов, продолжает с места
    got = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    todo = [s for s in df["сайт"] if s not in got]
    with ThreadPoolExecutor(12) as pool:
        for n, (s, (ph, ml)) in enumerate(zip(todo, pool.map(lambda s: site_contacts("https://" + s), todo)), 1):
            got[s] = {"телефоны": ph, "почты": ml}
            if n % 10 == 0 or n == len(todo):
                f.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
                print(f"сайты: сделано {n} из {len(todo)}", flush=True)
    df["телефоны"] = df["сайт"].map(lambda s: got.get(s, {}).get("телефоны", ""))
    df["почты"] = df["сайт"].map(lambda s: got.get(s, {}).get("почты", ""))
    from build_base import DRIVE  # сверка с общей базой организаций: есть ли этот сайт там
    bx = max(DRIVE.glob("база_lead_engine_*.xlsx"), key=lambda p: p.stat().st_mtime)
    urls = pd.read_excel(bx, sheet_name="организации", dtype=str)["сайт"].fillna("")
    sites = {urlparse(u if "//" in u else "https://" + u).netloc.lower().removeprefix("www.") for x in urls for u in x.split(", ") if u}
    df["уже в базе"] = df["сайт"].isin(sites)
    text = df["заголовок"] + " " + df["сниппет"]
    kinds = {"инженерия": r"инженер|отоплен|водоснабж|вентиляц|кондиц|электромонтаж|умный дом|бассейн",
             "отделка и ремонт": r"отделк|ремонт|интерьер",
             "архитектор / дизайн": r"архитект|дизайн|проектирован",
             "стройка": r"строител|строим|строй|построй|под ключ|фундамент|кровл|фасад|брус|каркас|кирпич|газобетон"}
    df["вид"] = text.map(lambda t: ", ".join(k for k, p in kinds.items() if re.search(p, t, re.I)) or "прочее")
    # «Проект дома Подушкино» — типовой проект, названный по посёлку, а не работа в нём
    df["сомнительно"] = (df["посёлков"] == 1) & df["заголовок"].str.contains(r"^Проект\w*\s|проект дома|проект \w+ дома", case=False, regex=True)
    df.to_csv(ROOT / "data" / "lists" / "podryadchiki_poselkov.tsv", sep="\t", index=False)
    print(f"подрядчиков {len(df)}: в 2+ посёлках {(df['посёлков'] >= 2).sum()}, с телефоном {(df['телефоны'] != '').sum()}, "
          f"с почтой {(df['почты'] != '').sum()}, уже в базе {df['уже в базе'].sum()}")


def main():
    raw = ROOT / "data" / "raw"
    if "--reparse" in sys.argv:
        f = sorted(raw.glob("contractors_2*.json"))[-1]
        return finish(json.loads(f.read_text(encoding="utf-8")))
    vs = villages()
    if "--limit" in sys.argv:
        vs = vs[: int(sys.argv[sys.argv.index("--limit") + 1])]
    token = env("BRIGHTDATA_API_TOKEN")
    part = raw / "contractors_partial.json"  # пишется по ходу: при обрыве следующий запуск продолжит с места
    res = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {}
    todo = [v for v in vs if v["посёлок"] not in res]
    print(f"посёлков {len(vs)}: уже есть {len(res)}, осталось {len(todo)}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(16) as pool:
        for n, (v, items) in enumerate(zip(todo, pool.map(lambda v: one(v, token), todo)), 1):
            res[v["посёлок"]] = [{k: i[k] for k in ("url", "title", "snippet")} for i in items]
            if n % 10 == 0 or n == len(todo):
                part.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(todo)}, осталось ≈{(time.time() - t0) / n * (len(todo) - n) / 60:.0f} мин", flush=True)
    out = raw / f"contractors_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    part.unlink(missing_ok=True)
    print(f"выдача → {out}")
    finish(res)


if __name__ == "__main__":
    main()