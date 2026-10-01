"""Редакции, СМИ и блогеры территории (Рублёвка, Новая Рига, Ильинское ш.) — поиск Яндекса через Bright Data.

python parsers/media_search.py
python parsers/media_search.py --clean   # убрать шум из последней выгрузки без запросов
Итог: data/raw/media_<время>.json — [{вид, название, ссылка, сниппет, запросы, почты, телефоны, людей}]; показывает панель.
Сайты СМИ — почты и телефоны со страницы; Telegram — число подписчиков с t.me. Только результаты про территорию/загородную жизнь.
"""
import html
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse

from yandex_maps_bd import ROOT, env
from yandex_search_bd import REGISTRY, serp, site_contacts

MEDIA = ["журнал Новая Рига", "журнал Рублевка", "журнал о жизни на Рублевке", "портал Новорижское шоссе новости",
         "новости Одинцовского округа сайт", "новости Истры сайт", "новости Красногорска сайт", "журнал загородная жизнь",
         "журнал загородная недвижимость", "журнал интерьер загородного дома", "журнал элитная загородная недвижимость Подмосковье",
         "Villagio Magazine", "газета Рублевка", "издание для жителей коттеджных поселков", "журнал ландшафтный дизайн"]
BLOGS = ["блогер Рублевка", "блог жизнь на Рублевке", "блогер Новая Рига", "telegram канал Рублевка", "telegram канал Новая Рига",
         "youtube канал жизнь на Рублевке", "youtube обзоры коттеджных поселков", "блог о загородном доме", "vk сообщество Рублевка",
         "vk сообщество Новая Рига", "дзен канал загородная жизнь", "блогер дизайн интерьера загородного дома",
         "блог строительство дома Подмосковье", "мамы Рублевки блог"]
GEO = r"рубл[её]в|нов\w* риг|новориж|одинцов|истр|красногорск|барвих|жуковк|ильинск|загород|коттедж|интерьер|ландшафт|поселк|посёлк|усадьб|дом"
NOISE = REGISTRY + (r"|yabs\.yandex|yandex\.ru/search|news\.google|ria\.ru|bplarussia|divan\.ru|vesti\.ru|regions\.ru|pressa\.ru"
                    r"|mymagazines|smartik|inmyroom|rosdocs")
NOISE += r"|avito|cian|realty\.yandex|domclick|hh\.ru|wikipedia|yandex\.ru/maps|2gis|zoon|market|ozon|wildberries|pinterest"


def kind(url: str) -> str:
    d = urlparse(url).netloc.lower()
    return ("Telegram" if "t.me" in d else "ВК" if "vk." in d else "YouTube" if "youtube" in d or "rutube" in d
            else "Дзен" if "dzen" in d else "Instagram" if "instagram" in d else "сайт / СМИ")


def tg_size(url: str) -> int | None:
    m = re.search(r"(?<![a-z-])t\.me/(?:s/|channel/)?([A-Za-z0-9_]{4,})", url.replace("search-t.me/channel/", "t.me/"))
    if not m:
        return None
    try:
        t = urllib.request.urlopen(urllib.request.Request("https://t.me/" + m.group(1), headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
        ex = re.search(r'tgme_page_extra">(.*?)</div>', t, re.S)
        return int(re.sub(r"\D", "", html.unescape(ex.group(1)).split("subscriber")[0].split("member")[0]) or 0) if ex else None
    except Exception:
        return None


def clean(rows: list) -> list:
    """убрать шум из готовой выгрузки и пересчитать подписчиков Telegram (каталог search-t.me → сам канал)"""
    out = []
    for r in rows:
        if re.search(NOISE, r["ссылка"]):
            continue
        if "search-t.me/channel/" in r["ссылка"]:
            r["ссылка"] = r["ссылка"].replace("search-t.me/channel/", "t.me/")
            r["людей"] = tg_size(r["ссылка"])
        if "villagio-premium" in r["ссылка"]:
            r["почты"] = ""  # на странице почта энергосбыта, не Villagio
        out.append(r)
    return out


def main():
    if "--clean" in sys.argv:
        f = sorted((ROOT / "data" / "raw").glob("media_*.json"))[-1]
        rows = clean(json.loads(f.read_text(encoding="utf-8")))
        f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return print(f"осталось {len(rows)}")
    token = env("BRIGHTDATA_API_TOKEN")
    qs = [("СМИ", q) for q in MEDIA] + [("блогеры", q) for q in BLOGS]
    print(f"запросов {len(qs)}", flush=True)
    found = {}
    with ThreadPoolExecutor(8) as pool:
        for n, ((grp, q), items) in enumerate(zip(qs, pool.map(lambda x: serp(x[1], token), qs)), 1):
            for i in items:
                if re.search(NOISE, i["url"]) or not re.search(GEO, i["title"] + " " + i["snippet"], re.I):
                    continue
                k = kind(i["url"])
                key = i["url"].split("?")[0].rstrip("/") if k != "сайт / СМИ" else urlparse(i["url"]).netloc.lower().removeprefix("www.")
                e = found.setdefault(key, {"вид": k, "группа": grp, "название": i["title"], "ссылка": i["url"], "сниппет": i["snippet"][:300], "запросы": []})
                e["запросы"].append(q)
            if n % 5 == 0 or n == len(qs):
                print(f"запросов сделано {n} из {len(qs)}, находок {len(found)}", flush=True)
    rows = list(found.values())
    print(f"контакты и подписчики для {len(rows)}…", flush=True)

    def enrich(r):
        if r["вид"] == "сайт / СМИ":
            ph, ml = site_contacts(r["ссылка"])
            r["телефоны"], r["почты"] = ph, ml
        elif r["вид"] == "Telegram":
            r["людей"] = tg_size(r["ссылка"])
        return r
    with ThreadPoolExecutor(10) as pool:
        rows = clean(list(pool.map(enrich, rows)))
    out = ROOT / "data" / "raw" / f"media_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(Counter(r["вид"] for r in rows), f"с почтой {sum(bool(r.get('почты')) for r in rows)} → {out}")


if __name__ == "__main__":
    main()
