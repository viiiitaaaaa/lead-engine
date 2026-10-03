"""Боли партнёров их же словами: выдача Яндекса собрана в Chrome (её вкладка, ~16 запросов, без капчи) → Загрузки\\serp_partnery*.json
→ открываем найденные статьи и форумы обычным запросом → фразы с маркерами проблем, по сегментам (дизайнер, подрядчик, застройщик, УК и брокер,
коммерческий объект). Бесплатно.

python parsers/partner_pains.py            # статьи (кэш data/raw/partner_articles.json) + фразы
python parsers/partner_pains.py --reparse  # только фразы
Итог: data/lists/boli_partnerov.tsv (строка = фраза: сегмент, тема, источник).
"""
import html as H
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from yandex_maps_bd import ROOT

CACHE = ROOT / "data/raw/partner_articles.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
SKIP = r"yandex\.|youtube|rutube|vk\.com/video|market\.|ozon|wildberries|avito|hh\.ru|superjob|zarplata"
THEMES = {
    "сроки и срывы": r"срыв\w* срок|сорвал|затяну|опозда|задерж|не успева",
    "не по проекту, переделки": r"не по проект|отступ\w* от проект|переделыв|самодеятельн|своему усмотрен|упрощ\w* реш|заменил\w* без",
    "поставки и комплектация": r"поставк|поставщик|комплектац|привез\w* не то|некомплект|пересорт|подделк|брак\w* товар|сроки производств",
    "деньги и вознаграждение": r"вознагражд|процент|комисси|агентск|откат|бонус|не заплат|не оплат|доплат|смет\w* выросл",
    "ответственность и отношения": r"ответственност|крайн\w* (оказ|станов)|винов|перекладыва|подстав|репутац|клиент\w* (жалу|обвин|недовол)",
    "коммуникация": r"не отвеча|пропада|не на связи|игнор|не бер\w* трубк|договорит\w* невозможно",
    "качество работ": r"качеств|брак|криво|халтур|косяк|нарушени\w* технолог",
    "инженерия": r"инженер|вентиляц|отоплен|электрик|сантехник|водоснаб|умный дом|котел|котёл",
}
PAIN = r"проблем|бесит|раздража|боль|сложност|трудност|худш|ужас|кошмар|страда|жалу|подвел|подвёл|обман|сорвал|не (могу|может|хочет|успева|отвеча)"


def get(u: str) -> str:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25)
        b = r.read(2_000_000)
        cs = (re.search(r"charset=([\w-]+)", r.headers.get("Content-Type", "")) or [None, "utf-8"])[1]
        h = b.decode(cs, "ignore")
        h = re.sub(r"<(script|style|noscript|nav|footer|header)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
        return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
    except Exception:
        return ""


def serp() -> list:
    out = []
    for f in sorted((Path.home() / "Downloads").glob("serp_partnery*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            for it in r.get("items") or []:
                if it.get("url") and not re.search(SKIP, it["url"], re.I):
                    out.append({"сегмент": r["seg"], "запрос": r["q"], "url": it["url"].split("#")[0], "заголовок": it.get("title") or "",
                                "сниппет": it.get("snip") or ""})
    return list({(x["сегмент"], x["url"]): x for x in out}.values())


def collect():
    items = serp()
    res = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [x for x in items if x["url"] not in res]
    print(f"ссылок {len(items)}, скачать {len(todo)}", flush=True)
    with ThreadPoolExecutor(8) as pool:
        for x, t in zip(todo, pool.map(lambda x: get(x["url"]), todo)):
            res[x["url"]] = t[:60000]
    CACHE.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


def reparse():
    items, res = serp(), json.loads(CACHE.read_text(encoding="utf-8"))
    rows = []
    for x in items:
        t = res.get(x["url"], "") or x["сниппет"]
        for s in re.split(r"(?<=[.!?…])\s+", t):
            if not 40 <= len(s) <= 400 or not re.search(PAIN, s, re.I):
                continue
            for th, rx in THEMES.items():
                if re.search(rx, s, re.I):
                    rows.append({"сегмент": x["сегмент"], "тема": th, "фраза": s, "источник": x["url"], "заголовок": x["заголовок"]})
                    break
    d = pd.DataFrame(rows).drop_duplicates(["сегмент", "фраза"])
    d.to_csv(ROOT / "data/lists/boli_partnerov.tsv", sep="\t", index=False)
    ok = sum(bool(res.get(x["url"])) for x in items)
    print(f"ссылок {len(items)}, открылось {ok}, фраз-болей {len(d)}")
    print(d.groupby(["сегмент", "тема"]).agg(фраз=("фраза", "count"), источников=("источник", "nunique")).to_string())


if __name__ == "__main__":
    if "--reparse" not in sys.argv:
        collect()
    reparse()
