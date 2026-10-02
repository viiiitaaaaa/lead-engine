"""Дособор досье по её списку (после list_dossier.py):
  1) юрлица без ИНН: ИНН со страниц политики/оферты/реквизитов их сайтов + поиск «"домен" ИНН», «"бренд" ИНН ОГРН» →
     ЕГРЮЛ по ИНН; у посёлков — юрлица застройщика и УК (из сводки посёлков) по названию в ЕГРЮЛ;
  2) выручка и сотрудники по найденным ИНН (сниппеты справочников в поиске Яндекса);
  4) тексты отзывов со страниц площадок (2ГИС, Zoon, Отзовик, Flamp, Yell…) из досье: разметка schema.org (reviewBody);
  5) пункты с пустым поиском (VISION, KUB хаус) — поиск по альтернативным названиям и домену.
python parsers/dossier_enrich.py
Итог: дописывает data/raw/dossier.json (поля «юрлицо», «юрлица посёлка», «выручка кратко», «отзывы: тексты»).
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import pandas as pd

from build_base import domain
from list_dossier import H, brand_keys, egrul, get, search, text
from yandex_maps_bd import ROOT, env
from yandex_search_bd import serp

F = ROOT / "data/raw/dossier.json"
LEGAL_PAGES = r"politik|privacy|policy|konfiden|оферт|oferta|dogovor|договор|rekviz|реквизит|soglas|согласие|personal|персональн|legal|terms|usloviya|uslovia"
ALT = {"Виджион": ["VISION Villagio", "коттеджный поселок VISION Новорижское", "vision-villagio"], "KUB хаус": ["KUB House", "kub.house", "KUB team строительство"]}


def bd_get(url: str, token: str) -> str:
    body = json.dumps({"zone": "serp_api1", "url": url, "format": "raw"}).encode()
    for n in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request("https://api.brightdata.com/request", data=body, method="POST",
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}), timeout=150).read().decode("utf-8", "ignore")
        except Exception:
            time.sleep(5 * (n + 1))
    return ""


def inns_from_site(site: str) -> set:
    root = (re.match(r"https?://[^/]+", site) or [None])[0]
    if not root:
        return set()
    first = get(root)
    pages = {urljoin(root, h) for h in re.findall(r'href="([^"#]+)"', first) if re.search(LEGAL_PAGES, h, re.I)}
    pages |= {root + p for p in ("/policy", "/privacy", "/politika-konfidencialnosti", "/rekvizity", "/oferta")}
    found = set()
    for u in list(pages)[:10]:
        found |= set(re.findall(r"ИНН[\s:/№]*(?:/\s*КПП)?[\s:]*(\d{10}|\d{12})(?!\d)", text(get(u))))
    return found


def find_legal(v: dict, token: str) -> tuple:
    """ИНН компании: страницы политики/оферты + поиск по домену и бренду; выбираем ИНН, чьё юрлицо похоже на бренд или встречен вместе с доменом"""
    from villages_merge import key
    sites = [s["сайт"] for s in v["сайты"] if s.get("сайт")]
    cand = {}
    for s in sites[:2]:
        for i in inns_from_site(s):
            cand[i] = cand.get(i, 0) + 3  # со своего сайта — самый надёжный
    qs = [f'"{domain(s)}" ИНН' for s in sites[:2]] + [f'"{v["пункт"]}" ИНН ОГРН']
    for q in qs:
        for it in serp(q, token) or []:
            t = it["title"] + " " + it["snippet"]
            for i in re.findall(r"ИНН[\s:]*(\d{10}|\d{12})(?!\d)", t):
                cand[i] = cand.get(i, 0) + (2 if any(domain(s) in t.lower() or domain(s) in it["url"] for s in sites) else 1)
    keys = brand_keys(v["пункт"], v["сайты"], {})
    best = None
    for inn, score in sorted(cand.items(), key=lambda x: -x[1])[:5]:
        rows = [r for r in egrul(inn) if not r["ликвидировано"]]
        if not rows:
            continue
        r = rows[0]
        sim = any(k in key(r["юрлицо"]) for k in keys)
        s = score + (3 if sim else 0)
        if not best or s > best[0]:
            best = (s, r, "ИНН со страниц сайта" if score >= 3 else ("поиск по домену/бренду, название совпадает" if sim else "поиск по домену/бренду — проверить"))
    return (best[1], best[2]) if best and best[0] >= 3 else ({}, "")


def village_legals(name: str, sv: pd.DataFrame) -> list:
    """юрлица посёлка: застройщики из сводки → ЕГРЮЛ (только если единственное действующее совпадение)"""
    out = []
    for dev in sorted(set(sv.loc[sv["наш список"] == name, "застройщик"]) - {""}):
        rows = [r for r in egrul(re.sub(r"[«»\"]|ООО|ГК|группа компаний", "", dev).strip()) if not r["ликвидировано"]]
        if len(rows) == 1:
            out.append({"роль": "застройщик", "как в Циане": dev, **rows[0]})
        elif rows:
            out.append({"роль": "застройщик", "как в Циане": dev, "юрлицо": f"тёзки в ЕГРЮЛ: {len(rows)}", "ИНН": ""})
    return out


def money(inn: str, token: str) -> tuple:
    rev = " ".join(i["snippet"] for i in (serp(f"ИНН {inn} выручка сотрудники", token) or []))
    m = re.search(r"[Вв]ыручка[^.]{0,60}?(\d[\d\s,.]*\s*(?:млрд|млн|тыс)\.?\s*(?:руб|₽)?)", rev)
    e = re.search(r"(\d+)\s*сотрудник", rev)
    return (m.group(1).strip() if m else ""), (e.group(1) if e else "")


def review_texts(url: str, token: str) -> list:
    """тексты отзывов со страницы площадки: schema.org (JSON-LD reviewBody / itemprop=reviewBody)"""
    h = get(url) or bd_get(url, token)
    out = []
    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try:
            data = json.loads(blk)
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if o.get("reviewBody"):
                    rt = o.get("reviewRating") or {}
                    out.append({"оценка": rt.get("ratingValue", "") if isinstance(rt, dict) else "", "дата": str(o.get("datePublished", ""))[:10],
                                "текст": re.sub(r"\s+", " ", html.unescape(str(o["reviewBody"])))[:600]})
                stack += [x for x in o.values() if isinstance(x, (dict, list))]
            elif isinstance(o, list):
                stack += o
    if not out:
        out = [{"оценка": "", "дата": "", "текст": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))[:600]}
               for t in re.findall(r'itemprop="reviewBody"[^>]*>(.*?)</', h, re.S)]
    return out[:30]


def main():
    res = json.loads(F.read_text(encoding="utf-8"))
    sv = pd.read_csv(ROOT / "data/lists/poselki_svod.tsv", sep="\t", dtype=str).fillna("")
    token = env("BRIGHTDATA_API_TOKEN")
    todo = list(res.values())

    def work(v):
        if v["вид"] == "компания" and (not v["юрлицо"] or "проверить" in v.get("юрлицо: как найдено", "") or "ТСН" in v["юрлицо"].get("юрлицо", "")):
            legal, how = find_legal(v, token)
            if legal:
                v["юрлицо"], v["юрлицо: как найдено"] = legal, how
        if v["вид"] == "посёлок":
            v["юрлица посёлка"] = village_legals(v["пункт"], sv)
        if v["юрлицо"].get("ИНН") and not v.get("выручка кратко"):
            v["выручка кратко"], v["сотрудников"] = money(v["юрлицо"]["ИНН"], token)
        if not any(v.get(k) for k in ("отзывы", "статьи", "вопросы", "клиенты")) and v["пункт"] in ALT:
            for alt in ALT[v["пункт"]]:
                s = search(alt, v["вид"], v["юрлицо"].get("ИНН", ""), token, brand_keys(alt, v["сайты"], v["юрлицо"]) | {"vision", "kubhouse", "kubteam"})
                for k in ("отзывы", "статьи", "вопросы", "клиенты"):
                    v[k] = (v.get(k) or []) + [x for x in s.get(k, []) if x["ссылка"] not in {y["ссылка"] for y in v.get(k) or []}]
        texts = []
        for r in (v.get("отзывы") or [])[:6]:
            if re.search(r"2gis|zoon|otzovik|flamp|yell|irecommend|spr\.ru|orgpage|profi", r["ссылка"]):
                for t in review_texts(r["ссылка"], token):
                    texts.append({**t, "откуда": domain(r["ссылка"]), "ссылка": r["ссылка"]})
        v["отзывы: тексты"] = texts
        return v

    t0 = time.time()
    with ThreadPoolExecutor(3) as pool:
        for n, v in enumerate(pool.map(work, todo), 1):
            res[v["пункт"]] = v
            F.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            if n % 5 == 0 or n == len(todo):
                print(f"сделано {n} из {len(todo)}, осталось ≈{(time.time() - t0) / n * (len(todo) - n) / 60:.0f} мин", flush=True)
    vs = list(res.values())
    print(f"готово: юрлицо у {sum(bool(x['юрлицо']) for x in vs)} компаний/пунктов, юрлица посёлков у "
          f"{sum(bool(x.get('юрлица посёлка')) for x in vs)}, выручка у {sum(bool(x.get('выручка кратко')) for x in vs)}, "
          f"текстов отзывов {sum(len(x.get('отзывы: тексты') or []) for x in vs)}")


if __name__ == "__main__":
    main()
