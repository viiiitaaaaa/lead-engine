"""Коммерческие объекты территории (клубы, SPA, рестораны, школы, сады — тип «клуб / досуг» в базе): отзывы 2ГИС бесплатно
(открытые ключи веб-версии, как в gis_reviews.py) → жалобы на помещение и инженерию (вентиляция, духота, холод, бассейн, вода, протечки…).
Проверяет гипотезу «коммерческим объектам нужна наша инженерия». Имена авторов НЕ сохраняются.

python parsers/commercial_reviews.py            # сбор (продолжает с места) + разбор
python parsers/commercial_reviews.py --reparse  # только разбор, без запросов
Итог: data/raw/gis_reviews_clubs.json, data/lists/kommercheskie_boli.tsv (строка = жалоба по теме) → панель и основа лендинга.
"""
import glob
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from build_base import domain
from gis_reviews import SEARCH_KEY, j, reviews
from villages_merge import key
from yandex_maps_bd import DRIVE, ROOT

OUT = ROOT / "data/raw/gis_reviews_clubs.json"
CHAIN = r"Тануки|Чайхона|Globus|Глобус|Додо|Вкусно|KFC|Бургер|Шоколадница|Якитория|Fish Point|Ростикс|Теремок|Pro\. Khinkali|Хинкал"
# темы помещения и инженерии: то, что мы можем закрыть
THEMES = {
    "вентиляция, духота, запах": r"душн|вентиляц|нечем дышать|спёрт|сперт|запах|воня|вонь|кондицион|жарк|жара|пар[ ,.]|духот",
    "холодно, отопление": r"холодно|холоднее|холодном помещ|холодный (зал|предбанник|бассейн|душ|хаммам)|замёрз|замерз|отоплен|сквозняк|дует из|градус",
    "бассейн, вода, душ": r"бассейн|хлорк|хлор|мутн.{0,10}вод|душ |душев|горяч.{0,10}вод|нет воды|напор|бойлер",
    "протечки, сырость, плесень": r"протек|протеч|теч[её]т крыш|теч[её]т потол|сырост|плесен|влажно",
    "канализация, туалет": r"канализ|туалет.{0,30}(не работ|сломан|грязн|засор)|засор",
    "электричество, свет": r"электрич|свет отключ|без света|выбивает|проводк|темно",
    "ремонт, состояние помещения": r"требует ремонт|нужен ремонт|старый ремонт|ремонт не дела|обшарпан|облезл|разваливает|плитка отвал|ржавчин|трещин",
}


def places() -> list:
    f = sorted(glob.glob(str(DRIVE.parent / "база_lead_engine_*.xlsx")))[-1]
    b = pd.read_excel(f, sheet_name=0, dtype=str).fillna("")
    c = b[(b["тип"] == "клуб / досуг") & ~b["название"].str.contains(CHAIN, case=False)]
    return [{"name": r["название"], "kind": r["вид деятельности"].split(",")[0], "site": r["сайт"], "addr": r["адрес"]} for _, r in c.iterrows()]


def find(p: dict) -> list:
    parts = [re.sub(r"^(деревня|посёлок|поселок|село|рабочий посёлок|коттеджный посёлок|д\.|п\.|с\.)\s+", "", w.strip(), flags=re.I)
             for w in re.split(r",\s*", p["addr"])]
    town = next((w for w in parts if w and not re.search(
        r"област|округ|район|улиц|шоссе|проспект|переул|бульвар|\d|region|district|highway|ulitsa|prospekt|street|lane|okrug|moscow|москва", w, re.I)), "")
    items = []
    for q in ([f'{p["name"]} {town}'] if town else []) + [p["name"]]:
        r = j(f"https://catalog.api.2gis.com/3.0/items?q={urllib.parse.quote(q)}&region_id=32&page_size=10"
              f"&fields=items.reviews,items.contact_groups,items.address,items.rubrics,items.adm_div&key={SEARCH_KEY}")
        items = (r.get("result") or {}).get("items") or []
        if items:
            break
    out = []
    for it in items:
        web = " ".join(c.get("value", "") for g in it.get("contact_groups") or [] for c in g.get("contacts") or [] if c.get("type") == "website")
        same_site = bool(domain(p["site"])) and domain(p["site"]) in web
        same_name = key(p["name"]) and (key(p["name"]) in key(it.get("name", "")) or key(it.get("name", "")) in key(p["name"]))
        where = (it.get("address_name", "") + " " + str(it.get("full_name", "")) + " " + " ".join(x.get("name", "") for x in it.get("adm_div") or [])).lower()
        same_town = bool(town) and town.lower()[:6] in where
        n = (it.get("reviews") or {}).get("general_review_count") or 0
        if n and (same_site or (same_name and (same_town or not town))):
            out.append({"название": it.get("name", ""), "id": str(it.get("id", "")).split("_")[0], "отзывов": n,
                        "рейтинг": (it.get("reviews") or {}).get("general_rating"), "адрес": it.get("address_name", ""),
                        "ссылка": f"https://2gis.ru/moscow/firm/{str(it.get('id', '')).split('_')[0]}"})
    return out[:1]


def collect():
    ps = places()
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [p for p in ps if p["name"] + "|" + p["addr"] not in res]
    print(f"мест {len(ps)}, осталось {len(todo)}", flush=True)

    def one(p):
        cards = find(p)
        return p, {"вид": p["kind"], "адрес": p["addr"], "карточки": cards,
                   "отзывы": [r for c in cards for r in reviews(c["id"], cap=300)]}
    with ThreadPoolExecutor(4) as pool:
        for n, (p, r) in enumerate(pool.map(one, todo), 1):
            res[p["name"] + "|" + p["addr"]] = dict(r, название=p["name"])
            OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            if n % 20 == 0 or n == len(todo):
                print(f"сделано {n} из {len(todo)}", flush=True)


# проверено глазами 03.10: карточка 2ГИС другого вида, чем место в базе (ресторан → рынок, школа → медцентр и т.п.)
WRONG = {"Hamlet", "Ветерок", "Семья", "Луна и Лотос", "Сосны", "Уколов-центр"}


def reparse():
    res = json.loads(OUT.read_text(encoding="utf-8"))
    rows, total, neg_total = [], 0, 0
    for v in res.values():
        if re.search(r"автосалон|автоцентр|car dealer", v["вид"], re.I) or v["название"] in WRONG:  # «ремонт» там — ремонт машин
            continue
        for r in v["отзывы"]:
            total += 1
            if (r.get("оценка") or 5) > 3:
                continue
            neg_total += 1
            for th, rx in THEMES.items():
                m = re.search(rx, r["текст"], re.I)
                if m:
                    a = max(0, m.start() - 120)
                    rows.append({"место": v["название"], "вид": v["вид"], "тема": th, "оценка": r.get("оценка"), "дата": r.get("дата"),
                                 "суть": r["текст"][a:a + 300], "карточка": v["карточки"][0]["ссылка"] if v["карточки"] else ""})
    d = pd.DataFrame(rows)
    (ROOT / "data/lists").mkdir(exist_ok=True)
    d.to_csv(ROOT / "data/lists/kommercheskie_boli.tsv", sep="\t", index=False)
    found = sum(bool(v["карточки"]) for v in res.values())
    nrev = d.drop_duplicates(["место", "дата", "суть"]).shape[0] if len(d) else 0
    print(f"мест {len(res)}, карточка 2ГИС у {found}, отзывов {total}, негативных {neg_total}, отзывов с жалобой на помещение/инженерию ≈{nrev}, совпадений тем {len(d)} "
          f"(мест с такими жалобами {d['место'].nunique() if len(d) else 0})")
    if len(d):
        print(d.groupby("тема")["место"].agg(["count", "nunique"]).sort_values("count", ascending=False).to_string())
        print(d.groupby("вид")["место"].nunique().sort_values(ascending=False).head(12).to_string())


if __name__ == "__main__":
    if "--reparse" not in sys.argv:
        collect()
    reparse()
