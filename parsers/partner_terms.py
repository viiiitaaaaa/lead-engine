"""Условия рынка для партнёров: на сайтах организаций базы ищем страницы «Дизайнерам / Архитекторам / Партнёрам / Сотрудничество /
Агентам / Подрядчикам / Оптовикам» и вытаскиваем условия — % вознаграждения, скидки, отсрочка, бонусы, шоурум, выезд. Бесплатно, обычные запросы.
Проверяет гипотезы основы лендинга о том, что рынок предлагает дизайнерам, подрядчикам, брокерам.

python parsers/partner_terms.py            # сбор (кэш HTML: data/raw/partner_pages.json, продолжает с места) + разбор
python parsers/partner_terms.py --reparse  # только разбор
Итог: data/lists/partnery_usloviya.tsv (строка = страница с условиями) → панель и основа лендинга.
"""
import glob
import html as H
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import pandas as pd

from build_base import domain
from yandex_maps_bd import DRIVE, ROOT

CACHE = ROOT / "data/raw/partner_pages.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
LINK = r"дизайнер|архитектор|партн[её]р|сотрудничеств|агент|подрядчик|оптов|для профессионал|designer|architect|partner|b2b|trade|pro\b"
WHO = {"дизайнерам": r"дизайнерам|архитекторам|декораторам|для дизайнер|для архитектор|designers|architects|/designer|/architect|/for-design",
       "подрядчикам": r"подрядчикам|строителям|монтажникам|для подрядчик|для строител|/contractor",
       "агентам и брокерам": r"агентам|риелторам|риэлторам|брокерам|агентск\w* программ|/agent|/realtor",
       "партнёрам (общее)": r"партн[её]рам|партн[её]рская программ|сотрудничеств|для профессионал|/partner|/b2b|/trade|/pro\b",
       "оптовикам": r"оптовикам|дилерам|/opt|/wholesale|/dealer"}
TERMS = {
    "вознаграждение %": r"(\d{1,2}(?:[.,]\d)?)\s?%[^.]{0,60}(вознагражд|комисси|агентск|бонус|кэшбэк|кешбэк|от суммы|от заказа|от стоимости)"
                        r"|(вознагражд|комисси|агентск|бонус|кэшбэк|кешбэк)[^.]{0,60}?(\d{1,2}(?:[.,]\d)?)\s?%",
    "скидка %": r"скидк[аиу][^.]{0,40}?(\d{1,2})\s?%|(\d{1,2})\s?%[^.]{0,20}скидк",
    "отсрочка": r"отсрочк|постоплат|оплата по факту",
    "личный менеджер": r"персональн\w* менеджер|личн\w* менеджер|выделенн\w* менеджер",
    "шоурум, образцы": r"шоу-?рум|образц|выставочн",
    "3D-модели, библиотеки": r"3d-модел|3d модел|3д-модел|модели для (3ds|archicad|sketchup|revit)|библиотек\w* модел|bim",
    "выезд, замер": r"выезд|замер",
    "обучение, мероприятия": r"обучен|семинар|мероприят|клуб дизайнер|вебинар",
    "сопровождение проекта": r"сопровожд\w* проект|авторск\w* надзор|помощь в (подборе|комплектац)",
    "конфиденциальность": r"конфиденциальн\w* (сотрудничеств|условия|скидк|цен)|клиент[^.]{0,20}не узна|от имени дизайнер",
}


def get(u: str) -> str:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20)
        b = r.read(800_000)
        cs = (re.search(r"charset=([\w-]+)", r.headers.get("Content-Type", "")) or [None, "utf-8"])[1]
        return b.decode(cs, "ignore")
    except Exception:
        return ""


def text(h: str) -> str:
    h = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def orgs() -> list:
    f = sorted(glob.glob(str(DRIVE.parent / "база_lead_engine_*.xlsx")))[-1]
    b = pd.read_excel(f, sheet_name=0, dtype=str).fillna("")
    b = b[(b["сайт"] != "") & ~b["новая?"].str.startswith("отсеяно") & (b["тип"] != "клуб / досуг")]
    seen, out = set(), []
    for _, r in b.iterrows():
        d = domain(r["сайт"].split(",")[0])
        if d and d not in seen and not re.search(r"vk\.|t\.me|instagram|yandex|avito|cian|2gis|wa\.me|ok\.ru", d):
            seen.add(d)
            out.append({"name": r["название"], "kind": r["вид деятельности"].split(",")[0], "site": "https://" + d})
    return out


def one(o: dict) -> dict:
    h = get(o["site"])
    links = []
    for href, label in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', h, re.S | re.I):
        lab = text(label)
        u = urljoin(o["site"] + "/", href)
        if urlparse(u).netloc.removeprefix("www.") != urlparse(o["site"]).netloc.removeprefix("www."):
            continue
        if re.search(LINK, lab + " " + href, re.I) and not re.search(r"\.(jpg|png|pdf|webp)$|политик|privacy|cookie|ваканс", u, re.I):
            links.append((lab[:80], u))
    links = list(dict.fromkeys(links))[:4]
    pages = [{"заголовок": lab, "ссылка": u, "текст": text(get(u))[:12000]} for lab, u in links]
    return {**o, "главная": bool(h), "страницы": pages}


def collect():
    os_ = orgs()
    res = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [o for o in os_ if o["site"] not in res]
    print(f"сайтов {len(os_)}, осталось {len(todo)}", flush=True)
    with ThreadPoolExecutor(10) as pool:
        for n, r in enumerate(pool.map(one, todo), 1):
            res[r["site"]] = r
            if n % 25 == 0 or n == len(todo):
                CACHE.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(todo)}", flush=True)
    CACHE.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


def reparse():
    res = json.loads(CACHE.read_text(encoding="utf-8"))
    rows = []
    for o in res.values():
        for p in o["страницы"]:
            t = re.sub(r"политик\w* конфиденциальн\w*|согласи\w* на обработку[^.]*", " ", p["текст"], flags=re.I)
            if len(t) < 200:
                continue
            who = [k for k, rx in WHO.items() if re.search(rx, p["заголовок"] + " " + p["ссылка"], re.I)]  # только по названию/адресу страницы
            if not who:
                continue
            row = {"организация": o["name"], "вид": o["kind"], "кому": ", ".join(who), "страница": p["ссылка"]}
            any_term = False
            for k, rx in TERMS.items():
                m = re.search(rx, t, re.I)
                if k.endswith("%"):
                    nums = [g for g in (m.groups() if m else []) if g and re.fullmatch(r"\d{1,2}(?:[.,]\d)?", g)]
                    row[k] = nums[0].replace(",", ".") if nums else ""
                    if m:
                        row[k + " — цитата"] = t[max(0, m.start() - 80):m.end() + 80]
                else:
                    row[k] = "да" if m else ""
                any_term |= bool(m)
            if any_term:
                rows.append(row)
    d = pd.DataFrame(rows).drop_duplicates(["организация", "кому"]) if rows else pd.DataFrame()
    d.to_csv(ROOT / "data/lists/partnery_usloviya.tsv", sep="\t", index=False)
    print(f"сайтов {len(res)}, открылось {sum(o['главная'] for o in res.values())}, со страницей для партнёров "
          f"{sum(bool(o['страницы']) for o in res.values())}, с условиями {len(d)}")
    if len(d):
        for who in WHO:
            g = d[d["кому"].str.contains(who, regex=False)]
            if not len(g):
                continue
            pct = pd.to_numeric(g["вознаграждение %"], errors="coerce").dropna()
            print(f"\n{who}: {len(g)} компаний; вознаграждение указано у {len(pct)}"
                  + (f" — от {pct.min():g}% до {pct.max():g}%, обычно {pct.median():g}%" if len(pct) else ""))
            for k in TERMS:
                if not k.endswith("%"):
                    print(f"   {k}: {(g[k] == 'да').sum()}")


if __name__ == "__main__":
    if "--reparse" not in sys.argv:
        collect()
    reparse()
