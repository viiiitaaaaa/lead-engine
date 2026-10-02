"""Дизайн-бюро и архитекторы: поиск новых (Яндекс, Bright Data) + разбор сайтов всех бюро (бесплатно) —
кто делает загородные дома премиум, работает ли на нашей территории, делает ли сам комплектацию и надзор.
Это шаг «AI-анализ дизайн-бюро» из схемы воронки.

python parsers/design_bureaus.py            # поиск + разбор (разбор продолжает с места, кэш data/raw/design_sites.json)
python parsers/design_bureaus.py --no-find  # только разбор сайтов (бюро из базы + из прошлого поиска)
Итог: data/lists/dizain_byuro.tsv; показывает панель.
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin, urlparse

import pandas as pd

from build_base import DRIVE, domain
from yandex_maps_bd import ROOT, env
from yandex_search_bd import REGISTRY, serp, site_contacts

QUERIES = [f"{w} {g}" for w in ("дизайн интерьера загородного дома", "архитектурное бюро загородные дома", "дизайн интерьера коттеджа")
           for g in ("Рублевка", "Новая Рига", "Барвиха", "Жуковка", "Новорижское шоссе", "Одинцово", "Истра", "премиум Подмосковье")]
QUERIES += ["бюро дизайна интерьера резиденции Подмосковье", "архитектор частных резиденций Москва"]
NOISE = REGISTRY + (r"|yabs\.yandex|yandex\.|avito|cian|domclick|hh\.ru|wikipedia|2gis|zoon|market|ozon|wildberries|pinterest|houzz|"
                    r"profi\.ru|youdo|vk\.com|vk\.ru|t\.me|instagram|youtube|dzen|rutube|admagazine|elledecoration|interior\.ru|ivd\.ru|"
                    r"inmyroom|houses\.ru|forumhouse|villagio|onehouse|kalinka|barn-estate|knightfrank|whitewill|realty|estate|"
                    r"pinwin|designboom|archdaily|archi\.ru|behance|tildacdn|tilda\.ws|rbc|kp\.ru|mk\.ru|forbes|kommersant|sravni|otzovik")
DESIGN = r"дизайн|архитект|интерьер|проектирован|design|architect|interior"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36", "Accept-Language": "ru"}

ZAG = r"загородн|коттедж|частн\w* дом|резиденц|усадьб|особняк|вилл[аы]|таунхаус|дом в кп|\bкп\b|посёлк|поселк|country house|villa|residence"
FLAT = r"квартир|апартамент|пентхаус|новостро|жк\b|жилой комплекс|apartment|flat"
B = r"(?<![а-яёa-z])"  # начало слова: «истр» не должно ловиться в «регистрация», «усов» — в «ресурсов»
PLACES = B + (r"(?:рубл[её]в|нов\w* риг|новориж|барвих|жуковк|усово|николин\w* гор|раздор|шульгин|подушкин|дарьин|солослов|"
              r"петрово-дальн|ильинско\w* шосс|истр[аеуыо]?(?![а-яё])|истринск|архангельское|агаларов|papushevo|папушев|"
              r"горки-(?:2|8|10)|миллениум парк|millennium park|villagio|вилладжио|madison park|мэдисон|ренессанс парк|futuro park|футуро парк)")
PREMIUM = r"премиум|элитн|luxury|люкс|эксклюзив|ad\s?100|ad magazine|elle decoration|interior\+design|наград|премии|award"
KOMPL = r"комплектац|поставк\w* мебел|подбор мебел|закупк"
NADZOR = r"авторск\w* надзор|авторское сопровожд"
BUILD = r"строим дом|строительство дом|строительн\w* компани|построим|фундамент|кровл|каркасн|газобетон|из бруса|под ключ от|каталог проектов|готовые проекты"
SALE = r"купить дом|продажа дом|участк\w* от|стоимость участ|цена участ|ипотек|в продаже|отдел продаж"
INTER = r"дизайн[ -]интерьер|интерьер|дизайн-проект|дизайнер"
ARCH = r"архитектурн|архитектор|проектирован"
LINK = r"portfolio|portfolio|project|proekt|проект|портфолио|works|raboty|работы|кейс|cases|objects|объект|interior|интерьер"


def find(token: str) -> dict:
    found = {}
    with ThreadPoolExecutor(8) as pool:
        for n, (q, items) in enumerate(zip(QUERIES, pool.map(lambda q: serp(q, token), QUERIES)), 1):
            for i in items:
                if re.search(NOISE, i["url"], re.I) or not re.search(DESIGN, i["title"] + " " + i["snippet"], re.I):
                    continue
                d = domain(i["url"])
                e = found.setdefault(d, {"название": i["title"][:120], "сниппет": i["snippet"][:300], "запросы": []})
                e["запросы"].append(q)
            print(f"поиск: {n} из {len(QUERIES)}, бюро {len(found)}", flush=True)
    return found


def get(url: str) -> str:
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return ""


def text(h: str) -> str:
    h = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", h, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).lower()


def analyze(site: str) -> dict:
    """главная + до 3 страниц портфолио/проектов: счёт загородных и квартирных слов, наши места, премиум, комплектация, надзор, соцсети"""
    root = "https://" + site
    h = get(root) or get("http://" + site)
    if not h:
        return {"ответ": "недоступен"}
    pages, hs = [root], [h]
    for href in re.findall(r'href="([^"#]+)"', h):
        u = urljoin(root, href)
        if domain(u) == site and re.search(LINK, u, re.I) and u not in pages and len(pages) < 4 and not re.search(r"\.(jpg|png|pdf|webp)$", u, re.I):
            pages.append(u)
            hs.append(get(u))
    raw = " ".join(hs)
    soc = lambda p: ", ".join(sorted(set(re.findall(p, raw))))[:200]
    # текст сайта храним в кэше — правила ниже можно менять и пересчитывать без повторного скачивания
    return {"ответ": "ок", "страниц": len(pages), "текст": " ".join(text(x) for x in hs)[:80000],
            "instagram": soc(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+"), "telegram": soc(r"https?://t\.me/[A-Za-z0-9_]{4,}"),
            "заголовок сайта": text((re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I) or [None, ""])[1])[:120]}


def metrics(a: dict) -> dict:
    if a.get("ответ") != "ок":
        return a
    t = a["текст"]
    n = lambda p: len(re.findall(p, t, re.I))
    places = sorted(set(m.lower() for m in re.findall(PLACES, t, re.I)))
    return {**a, "загородка": n(ZAG), "квартиры": n(FLAT), "наши места": ", ".join(places), "премиум": n(PREMIUM),
            "комплектация": bool(re.search(KOMPL, t, re.I)), "надзор": bool(re.search(NADZOR, t, re.I)),
            "стройка": n(BUILD), "продажа": n(SALE), "интерьер": n(INTER), "архитектура": n(ARCH)}


def category(a: dict) -> str:
    if a.get("ответ") != "ок":
        return "сайт недоступен"
    design = a["интерьер"] + a["архитектура"]
    head = a.get("заголовок сайта", "")
    if re.search(r"^строительство|каталог проектов|готовых проектов|купить|продажа|автополив|полив|забор", head, re.I) and not re.search(INTER, head, re.I):
        return "стройка / продажа домов"
    if (a["продажа"] >= 5 and a["продажа"] > design) or (a["стройка"] >= 5 and a["стройка"] > a["интерьер"] and a["стройка"] > a["архитектура"]):
        return "стройка / продажа домов"
    zag, flat = a["загородка"], a["квартиры"]
    if zag >= 3 and zag >= flat and (a["наши места"] or a["премиум"] >= 2):
        return "1. загородный премиум"
    if zag >= 3 and zag >= flat:
        return "2. загородка"
    if zag >= 2:
        return "3. квартиры и дома"
    return "4. квартиры / общее"


def from_base() -> pd.DataFrame:
    bx = max(DRIVE.glob("база_lead_engine_*.xlsx"), key=lambda p: p.stat().st_mtime)
    b = pd.read_excel(bx, sheet_name="организации", dtype=str).fillna("")
    b = b[b["вид деятельности"].str.contains(r"дизайн|архитект|проектн", case=False) & (b["сайт"] != "")]
    b = b[~b["новая?"].str.startswith("отсеяно")]
    b["site"] = b["сайт"].map(lambda s: domain(s.split(",")[0]))
    return b.drop_duplicates("site")


def main():
    raw = ROOT / "data" / "raw"
    ff = raw / "design_found.json"
    if "--no-find" not in sys.argv:
        found = find(env("BRIGHTDATA_API_TOKEN"))
        ff.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    found = json.loads(ff.read_text(encoding="utf-8")) if ff.exists() else {}
    base = from_base()
    rows = [{"site": r["site"], "название": r["название"], "источник": "база: " + r["источник"], "телефоны": r["телефоны"] or r["телефоны с сайта"],
             "почты": r["почты"], "адрес": r["адрес"], "карточка": r["ссылка"]} for _, r in base.iterrows()]
    have = {r["site"] for r in rows}
    new = [d for d in found if d not in have and d]
    rows += [{"site": d, "название": found[d]["название"], "источник": "поиск Яндекса (новое)", "телефоны": "", "почты": "", "адрес": "",
              "карточка": "", "сниппет": found[d]["сниппет"]} for d in new]
    # AD List TOP 100 (parsers/ad_list.py, веб-архив журнала AD): добавляем бюро с сайтом, которых ещё нет
    adl = ROOT / "data" / "lists" / "ad_list.tsv"
    ad_sites = set()
    if adl.exists():
        for r in pd.read_csv(adl, sep="\t", dtype=str).fillna("").to_dict("records"):
            d = domain(r["сайт"]) if r["сайт"] else ""
            if not d:
                continue
            ad_sites.add(d)
            if d not in have and d not in new:
                new.append(d)
                rows.append({"site": d, "название": r["бюро"], "источник": "AD List TOP 100 (архив)", "телефоны": r["телефоны"],
                             "почты": r["почты"], "адрес": r["город / адрес"], "карточка": r["карточка в архиве"]})
    print(f"бюро к разбору: из базы {len(have)}, новых из поиска и AD List {len(new)}", flush=True)

    cf = raw / "design_sites.json"  # кэш разбора (с текстом сайтов): продолжает с места
    cache = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    todo = [r["site"] for r in rows if r["site"] not in cache or (cache[r["site"]].get("ответ") == "ок" and "текст" not in cache[r["site"]])]
    t0 = time.time()
    with ThreadPoolExecutor(12) as pool:
        for n, (s, a) in enumerate(zip(todo, pool.map(analyze, todo)), 1):
            if a.get("ответ") == "ок" and s in new and not cache.get(s, {}).get("телефоны"):
                a["телефоны"], a["почты"] = site_contacts("https://" + s)
            cache[s] = {**{k: v for k, v in cache.get(s, {}).items() if k in ("телефоны", "почты")}, **a}
            if n % 10 == 0 or n == len(todo):
                cf.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                print(f"сайты: сделано {n} из {len(todo)}, осталось ≈{(time.time() - t0) / n * (len(todo) - n) / 60:.0f} мин", flush=True)

    out = []
    for r in rows:
        a = metrics(cache.get(r["site"], {}))
        prof = "" if a.get("ответ") != "ок" else max((("ландшафт", len(re.findall(r"ландшафт|озеленен|сад[аоы]?\b", a["текст"]))),
                                                     ("интерьер", a["интерьер"]), ("архитектура", a["архитектура"])), key=lambda x: x[1])[0]
        grp = category(a)
        if grp != "сайт недоступен" and re.search(r"residences|hills|poselok|kp-|village|estate", r["site"]) and prof != "интерьер":
            grp = "стройка / продажа домов"  # сайт посёлка или застройщика, а не бюро
        out.append({"бюро": r["название"], "сайт": r["site"], "группа": grp, "профиль": prof, "AD List": r["site"] in ad_sites, "источник": r["источник"],
                    "загородка": a.get("загородка", 0), "квартиры": a.get("квартиры", 0), "наши места": a.get("наши места", ""),
                    "премиум": a.get("премиум", 0), "комплектация": a.get("комплектация", False), "надзор": a.get("надзор", False),
                    "телефоны": r["телефоны"] or a.get("телефоны", ""), "почты": r["почты"] or a.get("почты", ""),
                    "instagram": a.get("instagram", ""), "telegram": a.get("telegram", ""), "заголовок сайта": a.get("заголовок сайта", ""),
                    "адрес": r["адрес"], "карточка": r["карточка"]})
    df = pd.DataFrame(out).sort_values(["группа", "загородка"], ascending=[True, False])
    df.to_csv(ROOT / "data" / "lists" / "dizain_byuro.tsv", sep="\t", index=False)
    print(df["группа"].value_counts().to_dict())
    print(f"новых из поиска {len(new)}; с нашими местами {(df['наши места'] != '').sum()}; делают комплектацию {df['комплектация'].sum()} → data/lists/dizain_byuro.tsv")


if __name__ == "__main__":
    main()
