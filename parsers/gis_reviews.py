"""Все отзывы 2ГИС по её списку (и группам досье): поиск карточек 2ГИС (catalog.api.2gis.com, открытый ключ сайта) с отсевом тёзок
по названию и сайту → все отзывы карточки (public-api.reviews.2gis.com, по 50 со сдвигом). Имена авторов НЕ сохраняются.

python parsers/gis_reviews.py                 # её список (из data/raw/dossier.json)
python parsers/gis_reviews.py --group premium # группа досье (data/raw/dossier_premium.json)
Итог: data/raw/gis_reviews[_группа].json = {пункт: {"карточки": [...], "отзывы": [...]}}; панель показывает в досье.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from build_base import domain
from list_dossier import brand_keys
from villages_merge import key
from yandex_maps_bd import ROOT

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36", "Referer": "https://2gis.ru/", "Origin": "https://2gis.ru"}
SEARCH_KEY, REVIEWS_KEY = "ruregt3044", "37c04fe6-a560-4549-b459-02309cf643ad"  # открытые ключи веб-версии 2gis.ru (проверено 03.10)
REGIONS = (32,)  # Москва и область


def j(u: str):
    for n in range(3):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=40).read())
        except Exception:
            time.sleep(3 * (n + 1))
    return {}


# проверено глазами 03.10: карточки-тёзки, которые проходят по названию и рубрике
NOT_CARDS = {"М9development": r"^Rdi", "Группа Самолет": r"Самолет Плюс", "Ландшафт": r"ландшафтная компания", "Велес Строй": r"Велесстрой"}
OURS = (r"строительн|строительств|ремонт|отделк|дизайн|архитект|проектирован|инженер|климат|вентиляц|кондицион|сантехн|мебел|коттедж"
        r"|посёл|посел|недвижим|загородн|застройщик|девелоп|земельн")
DEV = r"застройщик|девелоп|строительств\w* (дач|коттедж|дом)|продажа (коттедж|загородн|земельн)|земельн|коттеджн\w* посёл|коттеджн\w* посел"


def find(name: str, keys: set, sites: list, vid: str, dev: bool = False) -> list:
    """Проверка карточки (перепроверено 03.10 после ошибки «Велес Строй» — тёзка-нефтегаз по названию):
    совпал сайт → наша; у карточки свой сайт, отличный от сайта компании → тёзка; иначе название + профильная рубрика.
    У посёлков сайт брокерский, у застройщиков (dev) в базе сайт посёлка — для них сайт не сравниваем, рубрика строже (DEV)."""
    q = name + (" коттеджный посёлок" if vid == "посёлок" else "")
    out = []
    for reg in REGIONS:
        r = j(f"https://catalog.api.2gis.com/3.0/items?q={urllib.parse.quote(q)}&region_id={reg}&page_size=10"
              f"&fields=items.reviews,items.contact_groups,items.address,items.rubrics&key={SEARCH_KEY}")
        for it in (r.get("result") or {}).get("items") or []:
            card_sites = {domain(c.get("url") or c.get("text") or "") for g in it.get("contact_groups") or [] for c in g.get("contacts") or []
                          if c.get("type") == "website"} - {""}
            our = {domain(s) for s in sites} - {""}
            same_site = bool(card_sites & our)
            same_name = any(k in key(it.get("name", "")) for k in keys)
            n = (it.get("reviews") or {}).get("general_review_count") or 0
            rub = " ".join(x.get("name", "") for x in it.get("rubrics") or []) + " " + it.get("name", "")
            if not n:
                continue
            if vid == "посёлок" or dev:
                ok = same_site or (same_name and re.search(DEV if dev else OURS, rub, re.I))
            elif same_site:
                ok = True
            elif card_sites and our:  # у обоих свои сайты, и они разные — тёзка
                ok = False
            else:
                ok = same_name and re.search(OURS, rub, re.I)
            if ok and not re.search(NOT_CARDS.get(name, r"$^"), it.get("name", ""), re.I):
                out.append({"название": it.get("name", ""), "id": str(it.get("id", "")).split("_")[0], "отзывов": n,
                            "рейтинг": (it.get("reviews") or {}).get("general_rating"), "адрес": it.get("address_name", ""),
                            "сайт карточки": ", ".join(sorted(card_sites)), "рубрика": rub[:120],
                            "совпало": "сайт" if same_site else "название", "ссылка": f"https://2gis.ru/moscow/firm/{str(it.get('id', '')).split('_')[0]}"})
    return sorted({x["id"]: x for x in out}.values(), key=lambda x: (x["совпало"] != "сайт", -x["отзывов"]))[:3]


def reviews(bid: str, cap: int = 600) -> list:
    out = []
    for off in range(0, cap, 50):
        r = j(f"https://public-api.reviews.2gis.com/2.0/branches/{bid}/reviews?limit=50&offset={off}&is_advertiser=false"
              f"&sort_by=date_edited&key={REVIEWS_KEY}&locale=ru_RU")
        got = r.get("reviews") or []
        for x in got:
            ans = (x.get("official_answer") or {}).get("text") or ""
            out.append({"оценка": x.get("rating"), "дата": (x.get("date_created") or "")[:10], "текст": re.sub(r"\s+", " ", x.get("text") or "")[:1500],
                        "ответ компании": re.sub(r"\s+", " ", ans)[:600]})
        if len(got) < 50:
            break
    return out


def main():
    grp = sys.argv[sys.argv.index("--group") + 1] if "--group" in sys.argv else ""
    src = json.loads((ROOT / f"data/raw/dossier{'_' + grp if grp else ''}.json").read_text(encoding="utf-8"))
    out_f = ROOT / f"data/raw/gis_reviews{'_' + grp if grp else ''}.json"
    res = json.loads(out_f.read_text(encoding="utf-8")) if out_f.exists() else {}
    todo = [v for v in src.values() if v["пункт"] not in res]
    print(f"пунктов {len(src)}, осталось {len(todo)}", flush=True)

    def one(v):
        sites = [s["сайт"] for s in v["сайты"] if s.get("сайт")]
        cards = find(v["пункт"], brand_keys(v["пункт"], v["сайты"], v.get("юрлицо") or {}), sites, v["вид"], dev=grp == "developers")
        rv = [dict(r, карточка=c["название"]) for c in cards for r in reviews(c["id"])]
        return v["пункт"], {"карточки": cards, "отзывы": rv}
    with ThreadPoolExecutor(4) as pool:
        for n, (name, r) in enumerate(pool.map(one, todo), 1):
            res[name] = r
            out_f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            if n % 5 == 0 or n == len(todo):
                print(f"сделано {n} из {len(todo)}", flush=True)
    vs = list(res.values())
    print(f"готово: карточек 2ГИС у {sum(bool(v['карточки']) for v in vs)} из {len(vs)}, отзывов {sum(len(v['отзывы']) for v in vs)}")


if __name__ == "__main__":
    main()
