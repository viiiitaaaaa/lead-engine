"""Клиенты-коммерция на нашей территории (её список 04.10): общепит (вытяжки горячих цехов + приток в залы), ТЦ и магазины,
медицина (клиники, лаборатории, аптеки — фильтрация и стерильность), фитнес и спорт, серверные и ЦОД.
2ГИС (открытый ключ, бесплатно): поиск по городам и посёлкам Одинцовского, Красногорского и Истринского округов,
отбор по округу из adm_div; контакты организации (сайт, телефоны, почты), отзывы и рейтинг, признак сети.

python parsers/kommerciya_klienty.py
Итог: data/raw/kommerciya_klienty.json, data/lists/kommerciya_klienty.tsv
"""
import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from gis_reviews import SEARCH_KEY, j
from yandex_maps_bd import ROOT

CATS = {
    "Общепит": ["ресторан", "кафе", "столовая", "пиццерия", "кофейня", "фабрика-кухня"],
    "ТЦ и магазины": ["торговый центр", "торгово-развлекательный центр", "супермаркет", "гипермаркет", "строительный гипермаркет"],
    "Медицина": ["медицинский центр", "клиника", "стоматология", "лаборатория анализы", "аптека", "больница"],
    "Фитнес и спорт": ["фитнес-клуб", "спортивный комплекс", "бассейн", "ледовая арена"],
    "Серверные и ЦОД": ["дата-центр", "центр обработки данных", "серверная", "ЦОД"],
}
PLACES = ["Одинцово", "Красногорск", "Истра", "Звенигород", "Дедовск", "Нахабино", "Барвиха", "Жуковка", "Немчиновка",
          "Новоивановское", "Лесной Городок", "Голицыно", "Кубинка", "Снегири", "Павловская Слобода", "Ильинское", "Архангельское",
          "Опалиха", "Горки-2", "Усово", "Рублёво-Успенское шоссе", "Новорижское шоссе", "Ильинское шоссе"]
OKRUG = r"Одинцовский|Красногорск|Истра"
OUT = ROOT / "data/raw/kommerciya_klienty.json"
# первая рубрика 2ГИС должна быть профильной (проверено глазами 04.10: в выдачу попадают кассы, гостиницы, кофейные автоматы, стройматериалы;
# настоящих дата-центров на территории в 2ГИС нет — «Сетевое оборудование» это магазины)
RUB_OK = {
    "Общепит": r"^(Кафе|Рестораны|Быстрое питание|Пиццерии|Столовые|Кофейни|Суши-бары|Бары|Пекарни|Кондитерские|Банкетные залы|Доставка готовых блюд|Кафе-кондитерские|Пабы|Гастропабы|Чайхана)",
    "ТЦ и магазины": r"^(Супермаркеты|Торговые центры|Торгово-развлекательные центры|Гипермаркеты|Строительные гипермаркеты|Продуктовые магазины|Универмаги)",
    "Медицина": r"^(Аптеки|Частные стоматологии|Многопрофильные медицинские центры|Больницы|Медицинская диагностика|Медицинские анализы|Ветеринарные клиники|Частные детские стоматологии|Поликлиники|Медицинские центры|Косметология|Родильные дома|Лаборатории)",
    "Фитнес и спорт": r"^(Фитнес-клубы|Бассейны|Спортивные секции|Тренажёрные залы|Каток|Ледовые дворцы|Спортивные комплексы|Йога|Спа-салоны)",
    "Серверные и ЦОД": r"^(Дата-центры|Центры обработки данных)",
}


def search(q: str) -> list:
    out = []
    for page in range(1, 6):
        r = j(f"https://catalog.api.2gis.com/3.0/items?q={urllib.parse.quote(q)}&region_id=32&page_size=10&page={page}"
              f"&fields=items.adm_div,items.rubrics,items.reviews,items.contact_groups,items.full_address_name,items.org&key={SEARCH_KEY}")
        items = (r.get("result") or {}).get("items") or []
        out += items
        if len(items) < 10:
            break
    return out


def main():
    jobs = [(cat, f"{q} {p}") for cat, qs in CATS.items() for q in qs for p in PLACES]
    print(f"запросов {len(jobs)}", flush=True)
    res = {}
    with ThreadPoolExecutor(6) as pool:
        for n, ((cat, q), items) in enumerate(zip(jobs, pool.map(lambda jb: search(jb[1]), jobs)), 1):
            for it in items:
                if it.get("type") != "branch":
                    continue
                adm = it.get("adm_div") or []
                okr = next((a["name"] for a in adm if a.get("type") == "district_area"), "")
                if not re.search(OKRUG, okr):
                    continue
                rub = ", ".join(x.get("name", "") for x in it.get("rubrics") or [])
                cont = [c for g in it.get("contact_groups") or [] for c in g.get("contacts") or []]
                site = next((c.get("text") for c in cont if c.get("type") == "website" and "max.ru" not in (c.get("text") or "")), "")
                rv = it.get("reviews") or {}
                e = res.setdefault(it["id"].split("_")[0], {
                    "категория": cat, "название": it.get("name", ""), "рубрики": rub[:200], "адрес": it.get("full_address_name", ""), "округ": okr,
                    "населённый пункт": next((a["name"] for a in adm if a.get("type") in ("city", "settlement")), ""),
                    "сайт": site, "телефоны": "; ".join(sorted({c.get("text", "") for c in cont if c.get("type") == "phone"}))[:120],
                    "почты": "; ".join(sorted({c.get("text", "") for c in cont if c.get("type") == "email"}))[:120],
                    "отзывов": int(rv.get("general_review_count") or 0), "рейтинг": rv.get("general_rating"),
                    "сеть": bool(re.search(r",\s*сеть\b", it.get("name", ""))) or int((it.get("org") or {}).get("branch_count") or 1) > 3,
                    "филиалов у сети": int((it.get("org") or {}).get("branch_count") or 1), "запрос": q})
            if n % 50 == 0 or n == len(jobs):
                OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(jobs)}, объектов {len(res)}", flush=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    table(res)


def table(res: dict):
    res = {k: v for k, v in res.items() if re.search(RUB_OK[v["категория"]], v["рубрики"])}
    t = pd.DataFrame(res.values()).sort_values(["категория", "сеть", "отзывов"], ascending=[True, True, False])
    t.to_csv(ROOT / "data/lists/kommerciya_klienty.tsv", sep="\t", index=False)
    print(pd.crosstab(t["категория"], t["округ"], margins=True).to_string())
    print("с сайтом", (t["сайт"] != "").sum(), "| с телефоном", (t["телефоны"] != "").sum(), "| с почтой", (t["почты"] != "").sum(), "| сетей", t["сеть"].sum())


if __name__ == "__main__":
    import sys
    table(json.loads(OUT.read_text(encoding="utf-8"))) if "--table" in sys.argv else main()
