"""Боли по нашему оборудованию (её задача 03.10, пункт 2): отзывы о монтажниках и сервисах вентиляции, кондиционирования, отопления,
водоподготовки и бассейнов по Москве и области — 2ГИС (открытые ключи, бесплатно). Жалобы их клиентов = наши боли,
сами компании = будущие покупатели оборудования. Имена авторов не сохраняются.

python parsers/klimat_montazhniki.py          # поиск карточек + отзывы, сохраняет после каждой карточки
Итог: data/raw/klimat_montazhniki.json = {id: {название, рубрики, адрес, сайт, отзывов, запрос, отзывы: [...]}}
"""
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from gis_reviews import SEARCH_KEY, j, reviews
from yandex_maps_bd import ROOT

OUT = ROOT / "data/raw/klimat_montazhniki.json"
TOPICS = ["монтаж вентиляции", "приточная вентиляция с рекуперацией", "вентиляция и кондиционирование", "монтаж кондиционеров",
          "оборудование для бассейнов", "строительство бассейнов", "осушение бассейна", "монтаж отопления", "котельная под ключ",
          "водоподготовка", "водоочистка для коттеджа", "инженерные системы под ключ", "обслуживание котлов", "сервис вентиляции"]
PLACES = ["", "Одинцово", "Красногорск", "Истра", "Химки", "Звенигород", "Москва запад", "Новая Рига", "Рублёво-Успенское шоссе"]
OK_RUB = r"вентиляц|кондицион|климат|отоплен|котл|котел|водоочист|водоподгот|бассейн|инженерн|сантехн|тепловые насосы|бойлер"
CHAINS = r"леруа|leroy|м\.видео|мвидео|эльдорадо|днс|dns|obi|петрович|ситилинк|касторама|максидом|ozon|wildberries|яндекс маркет|авито|hoff|оби|vseinstrumenti|все инструменты|бытовой техники|гипермаркет|лемана|бауцентр|дом лента|колорлон|строительный рынок|^руки$"


def search(q: str) -> list:
    out = []
    for page in range(1, 6):
        r = j(f"https://catalog.api.2gis.com/3.0/items?q={urllib.parse.quote(q)}&region_id=32&page_size=10&page={page}"
              f"&fields=items.reviews,items.rubrics,items.address,items.contact_groups&key={SEARCH_KEY}")
        items = (r.get("result") or {}).get("items") or []
        out += items
        if len(items) < 10:
            break
    return out


def main():
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    cards = {}
    qs = [f"{t} {p}".strip() for t in TOPICS for p in PLACES]
    with ThreadPoolExecutor(4) as pool:
        for n, (q, items) in enumerate(zip(qs, pool.map(search, qs)), 1):
            for it in items:
                rub = ", ".join(x.get("name", "") for x in it.get("rubrics") or [])
                nrev = int((it.get("reviews") or {}).get("general_review_count") or 0)
                if it.get("type") != "branch" or nrev < 1 or not re.search(OK_RUB, rub + " " + it.get("name", ""), re.I) \
                        or re.search(CHAINS, it.get("name", ""), re.I):
                    continue
                site = next((c.get("text") or c.get("url") for g in it.get("contact_groups") or [] for c in g.get("contacts") or []
                             if c.get("type") == "website"), "")
                cards.setdefault(it["id"].split("_")[0], {"название": it.get("name", ""), "рубрики": rub, "адрес": it.get("address_name", ""),
                                                          "сайт": site, "отзывов": nrev, "запрос": q})
            if n % 20 == 0 or n == len(qs):
                print(f"поиск: {n} из {len(qs)} запросов, карточек {len(cards)}", flush=True)
    todo = [(k, v) for k, v in cards.items() if k not in res]
    print(f"карточек {len(cards)}, отзывов на них {sum(v['отзывов'] for v in cards.values())}, осталось собрать {len(todo)}", flush=True)
    if "--dry" in sys.argv:
        return

    def one(kv):
        k, v = kv
        return k, dict(v, отзывы=reviews(k, cap=300))
    with ThreadPoolExecutor(4) as pool:
        for n, (k, v) in enumerate(pool.map(one, todo), 1):
            res[k] = v
            if n % 10 == 0 or n == len(todo):
                OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"отзывы: {n} из {len(todo)} карточек, отзывов {sum(len(x['отзывы']) for x in res.values())}", flush=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
