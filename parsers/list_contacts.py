"""ВСЕ телефоны и почты по её списку (компании и посёлки из компании_и_поселки_2026-09-30.txt) — «телефонов и почт мало, надо вообще все».
Источники по каждому пункту: 1) все карточки базы (Карты, 2ГИС) и сводки посёлков; 2) глубокий обход их сайтов (до 12 страниц:
контакты, о компании, офисы, команда, подвал, tel:/mailto:); 3) поиск Яндекса «<название> телефон e-mail» (Bright Data) — из сниппетов;
4) справочники юрлиц (checko / rusprofile / list-org) из той же выдачи — официальные контакты.

python parsers/list_contacts.py
Итог: data/lists/spisok_kontakty.tsv — строка = контакт (пункт списка, вид, значение, откуда); панель показывает блок «Ваш список — все контакты».
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd

from build_base import DRIVE, digits, domain
from yandex_maps_bd import ROOT, env
from yandex_search_bd import REGISTRY, serp

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36", "Accept-Language": "ru"}
PH = r"(?<![\d])(?:\+7|8)[\s(\-]{0,2}\d{3}[\s)\-]{0,2}\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)"
ML = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
JUNK_ML = r"\.(png|jpe?g|svg|webp|gif)$|sentry|example|wixpress|@2x|domain\.|yourmail|email@|mail@mail|test@|noreply|no-reply|ivanov@|user@"
JUNK_PH = r"^7(9991234567|9876543210|1234567|0000000|8005553535)"
BROKERS = r"whitewill|knightfrank|kf\.expert|nfgroup|aimrealty|barn-estate|tweed|kayra|vesco|metrium|kalinka|intermark|zhukovka\.moscow|villagio-vip|onehouse|domclick|cian"
LINK = r"контакт|contact|kontakt|о-компании|o-kompanii|about|о-нас|company|kompani|офис|ofis|office|команд|team|связ|svyaz|feedback|rekvizit|реквизит"


def get(u: str) -> str:
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return ""


def norm_ph(p: str) -> str:
    d = digits(p)
    return d if len(d) == 11 and d[0] == "7" and d[1] in "3489" and not re.search(JUNK_PH, d) and len(set(d[1:])) > 3 else ""


def extract(t: str) -> tuple[set, set]:
    ph = {norm_ph(m) for m in re.findall(PH, t)} | {norm_ph(m) for m in re.findall(r'href="tel:([^"]+)"', t)}
    ml = {m.lower() for m in re.findall(ML, html.unescape(t)) if not re.search(JUNK_ML, m, re.I)}
    ml |= {m.lower().split("?")[0] for m in re.findall(r'href="mailto:([^"]+)"', t) if "@" in m}
    return {p for p in ph if p}, ml


def crawl(site: str) -> tuple[set, set]:
    """главная + до 11 внутренних страниц про контакты/компанию/офисы"""
    root = re.match(r"https?://[^/]+", site if "://" in site else "https://" + site)
    if not root:
        return set(), set()
    root = root.group(0)
    first = get(root) or get(root.replace("https://", "http://"))
    pages = {root} | {root + p for p in ("/contacts", "/contacts/", "/kontakty", "/contact", "/about", "/o-kompanii")}
    pages |= {urljoin(root, h) for h in re.findall(r'href="([^"#]+)"', first)
              if domain(urljoin(root, h)) == domain(root) and re.search(LINK, h, re.I)}
    ph, ml = extract(first)
    for u in list(pages - {root})[:11]:
        a, b = extract(get(u))
        ph |= a
        ml |= b
    return ph, ml


def items() -> list:
    """пункты её списка: имя, вид (компания/посёлок), сайты, уже известные телефоны/почты (из ВСЕХ карточек)"""
    lst = list(dict.fromkeys(l.strip() for l in (ROOT / "data/lists/компании_и_поселки_2026-09-30.txt").read_text(encoding="utf-8").splitlines() if l.strip()))
    b = pd.read_excel(max(DRIVE.glob("база_lead_engine_*.xlsx"), key=lambda p: p.stat().st_mtime), sheet_name="организации", dtype=str).fillna("")
    b = b[~b["новая?"].str.startswith("отсеяно")]
    sv = pd.read_csv(ROOT / "data/lists/poselki_svod.tsv", sep="\t", dtype=str).fillna("")
    out = []
    for n in lst:
        v = sv[sv["наш список"] == n]
        g = b[b["наш список"] == n]
        if len(v):  # для посёлка — только сам посёлок, его УК и застройщик, а не все школы/салоны, что в нём находятся
            g = g[(g["тип"] == "посёлок") | g["вид деятельности"].str.contains(r"коттеджн|посёл|посел|управляющ|ТСН|ДНП|застройщ", case=False, regex=True)]
        known = []
        for _, r in g.iterrows():
            for p in re.split(r"[,;]\s*", r["телефоны"] + "," + r["телефоны с сайта"]):
                if norm_ph(p):
                    known.append(("телефон", norm_ph(p), "карточка: " + r["источник"]))
            for m in re.findall(ML, r["почты"]):
                known.append(("почта", m.lower(), "сайт / карточка"))
        for _, r in v.iterrows():
            for c, kind in (("телефоны застройщика", "телефон"), ("телефоны посёлка", "телефон"), ("почты застройщика", "почта"), ("почты посёлка", "почта")):
                for x in r[c].split(", "):
                    val = norm_ph(x) if kind == "телефон" else x.lower()
                    if val:
                        known.append((kind, val, f"сводка посёлков: {r['посёлок']}"))
        sites = {s.strip() for x in g["сайт"] for s in x.split(",") if s.strip()}
        sites |= {u for c in ("сайт застройщика", "сайт посёлка") for u in v[c] if u}
        sites = {s for s in sites if not re.search(BROKERS + "|" + REGISTRY + r"|zoon|my-gkh|2gis|yandex", s, re.I)}
        out.append({"пункт": n, "вид": "посёлок" if len(v) else "компания", "посёлки": ", ".join(v["посёлок"]), "сайты": sorted(sites), "known": known})
    return out


def one(it: dict, token: str) -> dict:
    found = list(it["known"])
    for s in it["сайты"][:6]:
        ph, ml = crawl(s)
        found += [("телефон", p, "сайт " + domain(s)) for p in ph] + [("почта", m, "сайт " + domain(s)) for m in ml]
    q = f'"{it["пункт"]}" {"коттеджный поселок" if it["вид"] == "посёлок" else "компания"} телефон e-mail'
    for i in serp(q, token) or []:
        t = i["title"] + " " + i["snippet"]
        ph, ml = extract(t)
        src = ("справочник юрлиц " if re.search(REGISTRY, i["url"]) else "поиск Яндекса ") + domain(i["url"])
        if re.search(BROKERS, i["url"], re.I):
            src += " (брокер)"
        found += [("телефон", p, src) for p in ph] + [("почта", m, src) for m in ml]
    return {**it, "found": found}


def main():
    its = items()
    old = pd.DataFrame()
    if "--only" in sys.argv:  # пересобрать только один вид пунктов (посёлок / компания), остальное взять из прошлого файла
        vid = sys.argv[sys.argv.index("--only") + 1]
        its = [i for i in its if i["вид"] == vid]
        p = ROOT / "data/lists/spisok_kontakty.tsv"
        old = pd.read_csv(p, sep="\t", dtype=str).fillna("")
        old = old[old["вид пункта"] != vid]
    token = env("BRIGHTDATA_API_TOKEN")
    print(f"пунктов списка {len(its)}", flush=True)
    res = []
    t0 = time.time()
    with ThreadPoolExecutor(8) as pool:
        for n, r in enumerate(pool.map(lambda it: one(it, token), its), 1):
            res.append(r)
            if n % 5 == 0 or n == len(its):
                print(f"сделано {n} из {len(its)}, {time.time() - t0:.0f} с", flush=True)
    rows = []
    for r in res:
        seen = {}
        for kind, val, src in r["found"]:
            seen.setdefault((kind, val), []).append(src)
        for (kind, val), srcs in seen.items():
            rows.append({"пункт": r["пункт"], "вид пункта": r["вид"], "посёлки": r["посёлки"], "контакт": kind, "значение": val,
                         "брокер?": bool(re.search(BROKERS, val + " " + " ".join(srcs), re.I)),
                         "откуда": "; ".join(dict.fromkeys(srcs))[:200], "источников": len(set(srcs))})
    df = pd.concat([old, pd.DataFrame(rows).astype(str)], ignore_index=True)
    # заглушки с сайтов (ivanov@ivan.ru, 79991234567) могли прийти из уже известных контактов, минуя extract()
    bad = ((df["контакт"] == "почта") & df["значение"].str.contains(JUNK_ML + r"|ivan\.ru", case=False, regex=True)) | \
          ((df["контакт"] == "телефон") & df["значение"].str.match(JUNK_PH))
    df = df[~bad]
    df["источников"] = pd.to_numeric(df["источников"])
    df = df.sort_values(["пункт", "контакт", "источников"], ascending=[True, True, False])
    df.to_csv(ROOT / "data/lists/spisok_kontakty.tsv", sep="\t", index=False)
    s = df.groupby("пункт")["контакт"].value_counts().unstack(fill_value=0)
    print(f"контактов {len(df)}: телефонов {(df['контакт'] == 'телефон').sum()}, почт {(df['контакт'] == 'почта').sum()}; "
          f"пунктов без телефона {(s.get('телефон', 0) == 0).sum()}, без почты {(s.get('почта', 0) == 0).sum()}")


if __name__ == "__main__":
    main()
