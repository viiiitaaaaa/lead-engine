"""Поиск Яндекса через Bright Data (serp_api1) + контакты с найденного сайта компании.

python parsers/yandex_search_bd.py "Брайер строй" "Гелиус строительство"
Итог: data/raw/ysearch_<время>.json и таблица в Google Диск → Выгрузки\\яндекс_поиск_<время>.xlsx
Реклама (yabs.yandex.ru) и справочники (checko, rusprofile…) идут отдельно: из справочников берём юрлицо/ИНН.
"""
import html as H
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from yandex_maps_bd import DRIVE, ROOT, env

REGISTRY = r"checko|rusprofile|audit-it|companies\.rbc|list-org|sbis|zachestnyibiznes|egrul|kontur|spark|vbankcenter|orgpage"
SKIP = r"yabs\.yandex|yandex\.|instagram|vk\.com|t\.me|youtube|dzen|avito|cian|2gis|hh\.ru|wikipedia|pinterest|ok\.ru"


def clean(z):
    return H.unescape(re.sub(r"<[^>]+>", "", z or "")).strip()


def serp(query, token):
    body = json.dumps({"zone": "serp_api1", "url": "https://yandex.ru/search/?lr=213&text=" + urllib.parse.quote(query),
                       "format": "raw"}).encode()
    for _ in range(3):
        try:
            h = urllib.request.urlopen(urllib.request.Request(
                "https://api.brightdata.com/request", data=body, method="POST",
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}), timeout=150).read().decode("utf-8", "ignore")
        except Exception:
            continue
        out = []
        for it in re.findall(r'<li[^>]*class="serp-item[^"]*"[^>]*>(.*?)</li>', h, re.S):
            a = re.search(r'href="(https?://[^"]+)"', it)
            if not a:
                continue
            out.append({"url": H.unescape(a.group(1)), "title": clean((re.search(r"<h2[^>]*>(.*?)</h2>", it, re.S) or [None, ""])[1]),
                        "snippet": clean((re.search(r"OrganicTextContentSpan[^>]*>(.*?)</span>", it, re.S) or [None, ""])[1])})
        if out:
            return out
    return []


def site_contacts(url):
    """телефоны и почты с главной и /contacts сайта — обычным запросом, бесплатно"""
    phones, mails = set(), set()
    root = re.match(r"https?://[^/]+", url).group(0)
    for u in (root, root + "/contacts", root + "/kontakty", root + "/contacts/"):
        try:
            t = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
        except Exception:
            continue
        mails |= {m.lower() for m in re.findall(r"[a-zA-Z0-9._+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?(?![a-zA-Z])", t)
                  if not re.search(r"\.(png|jpg|svg|webp)$|sentry|example|wixpress", m, re.I)}
        for p in re.findall(r"(?<!\d)(?:\+7|8)[\s(-]{0,2}\d{3}[\s)-]{0,2}\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)", t):
            d = "7" + re.sub(r"\D", "", p)[1:]
            if len(d) == 11 and d[1] in "3489" and len(set(d[1:])) > 3:
                phones.add(d)
    return ", ".join(sorted(phones)), ", ".join(sorted(mails))


def main():
    token = env("BRIGHTDATA_API_TOKEN")
    qs = sys.argv[1:]
    with ThreadPoolExecutor(5) as pool:
        res = list(pool.map(lambda q: serp(q, token), qs))
    rows, raw = [], {}
    for q, items in zip(qs, res):
        raw[q] = items
        sites = [i for i in items if not re.search(SKIP + "|" + REGISTRY, i["url"])]
        regs = [i for i in items if re.search(REGISTRY, i["url"])]
        socials = [i["url"] for i in items if re.search(r"instagram|vk\.com|t\.me|youtube|dzen", i["url"])]
        site = sites[0] if sites else {}
        ph, ml = site_contacts(site["url"]) if site else ("", "")
        rows.append({"запрос": q, "сайт": site.get("url", ""), "что на сайте": site.get("title", ""), "описание": site.get("snippet", ""),
                     "телефоны с сайта": ph, "почты с сайта": ml, "соцсети": ", ".join(socials[:4]),
                     "юрлицо (справочник)": regs[0]["title"] if regs else "", "справочник": regs[0]["url"] if regs else "",
                     "что пишут о юрлице": regs[0]["snippet"] if regs else "",
                     "другие результаты": "\n".join(f'{i["title"]} — {i["url"]}' for i in sites[1:5])})
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    (ROOT / "data" / "raw" / f"ysearch_{stamp}.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    out = DRIVE / f"яндекс_поиск_{stamp}.xlsx"
    pd.DataFrame(rows).to_excel(out, index=False)
    for r in rows:
        print(f'{r["запрос"]} → {r["сайт"] or "—"} | тел: {r["телефоны с сайта"][:40] or "—"} | почта: {r["почты с сайта"][:50] or "—"} | {r["юрлицо (справочник)"][:50]}')
    print(out)


if __name__ == "__main__":
    main()
