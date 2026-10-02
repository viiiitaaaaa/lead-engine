"""AD List TOP 100 — каталог российских дизайнеров и архитекторов журнала AD (admagazine.ru/adlist, 2017–2022).
Сам сайт закрыт для всех (403 Fastly и с VPN, и напрямую), поэтому карточки берём из веб-архива (web.archive.org), бесплатно.

python parsers/ad_list.py
Итог: data/lists/ad_list.tsv (бюро, специализация, город/адрес, телефон, почта, сайт, стиль, год, снимок) — подхватывает design_bureaus.py.
"""
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from yandex_maps_bd import ROOT

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
NOT_THEIRS = r"admagazine|condenast|architecturaldigest|ad-magazin|admexico|adstyle|revistaad|youtube|instagram\.com/adrussia|plus\.google|twitter|vk\.com/public36420241|web\.archive|facebook\.com/ADRussia|facebook\.com/adrussia|t\.me/admagazine"


def get(u: str) -> str:
    for n in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=90).read().decode("utf-8", "ignore")
        except Exception:
            time.sleep(5 * (n + 1))
    return ""


def snapshots() -> dict:
    """{slug: (снимок, адрес)} — самый свежий снимок каждой карточки"""
    cdx = json.loads(get("https://web.archive.org/cdx/search/cdx?url=admagazine.ru/adlist/participant/*&output=json"
                         "&fl=timestamp,original&filter=statuscode:200&limit=5000"))[1:]
    best = {}
    for ts, orig in cdx:
        m = re.search(r"/participant/([a-z0-9-]+)", orig)
        if m and (m.group(1) not in best or ts > best[m.group(1)][0]):
            best[m.group(1)] = (ts, f"https://www.admagazine.ru/adlist/participant/{m.group(1)}")
    return best


CACHE = ROOT / "data" / "raw" / "ad_list_html"  # скачанные карточки: правка разбора без повторного скачивания


def card(slug: str, ts: str, url: str) -> dict:
    CACHE.mkdir(exist_ok=True)
    cf = CACHE / f"{slug}.html"
    t = cf.read_text(encoding="utf-8") if cf.exists() else get(f"https://web.archive.org/web/{ts}id_/{url}")
    if t and not cf.exists():
        cf.write_text(t, encoding="utf-8")
    if not t:
        return {"slug": slug, "ошибка": "не скачалось"}
    x = re.sub(r"\s+", " ", html.unescape(re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", t, flags=re.S)))
    name = re.sub(r"\s*\|\s*AD Magazine.*$", "", html.unescape((re.search(r"<title>(.*?)</title>", t, re.S) or [None, slug])[1])).strip()
    body = x.split("AD List TOP 100", 1)[-1]
    contacts = (re.search(r"Позвонить.{0,40}?Сайт\s+(.{0,400})", body) or [None, ""])[1]
    phones = sorted(set(re.sub(r"[^\d+]", "", p) for p in re.findall(r"\+7[\d\s()\-]{9,16}\d", contacts or body[:1500])))
    mails = sorted(set(m.lower() for m in re.findall(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", contacts or body[:1500]) if not re.search(NOT_THEIRS, m)))
    sites = [s for s in re.findall(r'href="(https?://[^"]+)"', t) if not re.search(NOT_THEIRS, s, re.I)]
    www = re.search(r"(?:https?://)?(www\.[a-z0-9.-]+\.[a-z]{2,}[^\s]*)", contacts or "")  # сайт текстом в блоке контактов
    own = [s for s in sites if not re.search(r"facebook|instagram|vk\.com|t\.me|pinterest|houzz|behance", s, re.I)]
    free = r"@(gmail|mail|yandex|ya|bk|inbox|list|rambler|icloud|hotmail|outlook)\."
    site = ("http://" + www.group(1)) if www else own[0] if own else next(("https://" + m.split("@")[1] for m in mails if not re.search(free, m)), "")
    addr = (re.search(r"Сайт\s+(.*?)\s+\+7", body) or [None, ""])[1][:120]
    spec = (re.search(r"(Дизайн интерьера|Архитектура|Дизайн|Декор|Ландшафт\w*|Строительство)\s", contacts[-200:] if contacts else "") or [None, ""])[1]
    return {"slug": slug, "бюро": name, "специализация": spec,
            "город / адрес": addr, "телефоны": ", ".join(phones), "почты": ", ".join(mails),
            "сайт": site, "instagram": next((s for s in sites if "instagram" in s), ""),
            "стиль": (re.search(r"Стиль\s*:\s*([^А-Я]{0,60}?)(?:\s+Позвонить|\s+Год|$)", body) or [None, ""])[1].strip(),
            "год основания": (re.search(r"Год основания\s*:\s*(\d{4})", body) or [None, ""])[1],
            "снимок": ts[:8], "карточка в архиве": f"https://web.archive.org/web/{ts}/{url}"}


def main():
    snaps = snapshots()
    print(f"карточек в архиве: {len(snaps)}", flush=True)
    out = []
    with ThreadPoolExecutor(4) as pool:  # бережно к архиву
        for n, r in enumerate(pool.map(lambda kv: card(kv[0], *kv[1]), snaps.items()), 1):
            out.append(r)
            if n % 20 == 0 or n == len(snaps):
                print(f"сделано {n} из {len(snaps)}", flush=True)
    df = pd.DataFrame(out).fillna("").astype(str)
    df["сайт"] = df["сайт"].str.replace(r"/+$", "", regex=True)
    df.to_csv(ROOT / "data" / "lists" / "ad_list.tsv", sep="\t", index=False)
    print(f"готово {len(df)}: сайт {(df['сайт'] != '').sum()}, телефон {(df['телефоны'] != '').sum()}, почта {(df['почты'] != '').sum()}, "
          f"Москва {df['город / адрес'].str.contains('Москв', case=False).sum()}")


if __name__ == "__main__":
    main()
