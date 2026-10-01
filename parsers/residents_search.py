"""Сообщества жителей посёлков вне Telegram: группы ВКонтакте (все посёлки) и ветки FORUMHOUSE (важные посёлки)
через поиск Яндекса (Bright Data) «<посёлок> коттеджный поселок <шоссе> шоссе группа вконтакте жители», «forumhouse … отзывы жителей».
Оператор site: через Bright Data с 02.10 отдаёт пустую выдачу — не использовать.
Правило: жителям не пишем, имён и телефонов не собираем — только ссылки на сообщества и их размер.

python parsers/residents_search.py            # все посёлки (ВК) + первые 200 по важности (FORUMHOUSE)
python parsers/residents_search.py --limit 10 # проба
python parsers/residents_search.py --reparse  # пересобрать список из сохранённой выдачи, без запросов
Итог: data/raw/residents_<время>.json + data/lists/soobshchestva_poselkov.tsv; показывает панель.
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from contractors_search import villages
from villages_merge import key
from yandex_maps_bd import ROOT, env
from yandex_search_bd import serp

FH_TOP = 200
VK_SKIP = r"vk\.(?:com|ru)/(?:wall|video|photo|topic|album|market|doc|search|feed|away|clip|music|@)|vk\.com/\w+\?w=|/wall-?\d"
WRONG_PLACE = (r"\bЖК\b|жилой комплекс|дольщик|russiancommunity|Раменск|Брянск|Кольчугин|Богданово|Новосиб|Самар|Казан|Челны|Елабуг|Санкт|"
               r"Питер|Ленинград|Тюмен|Екатеринбург|Краснодар|Воронеж|Тульск|Калуж|Ярослав|Нижегород|Пермь|Уфа|Башкир|Татарстан|Крым|"
               r"Сочи|Ростов|Владимирск|Тверск|Рязан|Смолен|Сергиев|Пушкин|Мытищ|Домодедов|Подольск|Ногинск|Щёлков|Щелков|Раменское")
NOT_RESIDENTS =r"продаж|продам|купить|недвижим|риелтор|агентств|строител|строим|ремонт|отделк|под ключ|дизайн|архитект|участки от|ипотек"


def kind(i: dict) -> str:
    u, t = i["url"], i["title"] + " " + i["snippet"]
    if "forumhouse" in u:
        return "FORUMHOUSE"
    if re.search(NOT_RESIDENTS, t, re.I):
        return "ВК: продажи / услуги"
    return "ВК: сообщество"


def size(t: str):
    m = re.search(r"(\d[\d\s.,]*)\s*(тыс\.?)?\s*(?:участник|подписчик|member)", t, re.I)
    if not m:
        return None
    n = float(re.sub(r"\s", "", m.group(1)).replace(",", "."))
    return int(n * 1000) if m.group(2) else int(n)


def picks(village: str, items: list) -> list:
    k = key(village)[:8]
    out = []
    for i in items:
        u = i["url"]
        if not re.search(r"vk\.(?:com|ru)/|forumhouse\.ru/threads", u) or re.search(VK_SKIP, u):
            continue
        if k not in key(i["title"] + " " + i["snippet"] + " " + u):
            continue
        if re.search(WRONG_PLACE, i["title"] + " " + i["snippet"] + " " + u, re.I):  # тёзки из других районов, ЖК
            continue
        u = re.sub(r"[?#].*$", "", u).replace("m.vk.com", "vk.com").replace("vk.ru", "vk.com")
        out.append({"посёлок": village, "вид": kind(i), "ссылка": u, "название": i["title"][:150], "сниппет": i["snippet"][:300],
                    "участников": size(i["title"] + " " + i["snippet"])})
    return out


def one(v: dict, fh: bool, token: str) -> dict:
    r = {"vk": serp(f'{v["посёлок"]} коттеджный поселок {v["шоссе"]} шоссе группа вконтакте жители', token) or []}
    if fh:
        r["fh"] = serp(f'forumhouse коттеджный поселок {v["посёлок"]} {v["шоссе"]} отзывы жителей', token) or []
    return r


def finish(res: dict) -> None:
    rows, seen = [], set()
    for village, r in res.items():
        for p in picks(village, r.get("vk", []) + r.get("fh", [])):
            if p["ссылка"] not in seen:
                seen.add(p["ссылка"])
                rows.append(p)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "data" / "lists" / "soobshchestva_poselkov.tsv", sep="\t", index=False)
    vk = df[df["вид"] == "ВК: сообщество"]
    print(f"найдено {len(df)}: {df['вид'].value_counts().to_dict()}; посёлков с группой ВК {vk['посёлок'].nunique()}, "
          f"людей в группах ВК (где видно) ≈{int(vk['участников'].fillna(0).sum())}")


def main():
    raw = ROOT / "data" / "raw"
    if "--reparse" in sys.argv:
        f = sorted(raw.glob("residents_2*.json"))[-1]
        return finish(json.loads(f.read_text(encoding="utf-8")))
    vs = villages()
    if "--limit" in sys.argv:
        vs = vs[: int(sys.argv[sys.argv.index("--limit") + 1])]
    fh = {v["посёлок"] for v in vs[:FH_TOP]}
    token = env("BRIGHTDATA_API_TOKEN")
    part = raw / "residents_partial.json"  # пишется по ходу: при обрыве следующий запуск продолжит с места
    res = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {}
    if "--retry" in sys.argv and not res:  # переспросить пустые ответы последней выгрузки (Bright Data сбоит под нагрузкой)
        res = json.loads(sorted(raw.glob("residents_2*.json"))[-1].read_text(encoding="utf-8"))
    res = {k: v for k, v in res.items() if v.get("vk")}  # пустой ответ = сбой, переспрашиваем
    todo = [v for v in vs if v["посёлок"] not in res]
    print(f"посёлков {len(vs)} (FORUMHOUSE у {len(fh)}): уже есть {len(res)}, осталось {len(todo)}", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(12) as pool:  # при 24 потоках Bright Data отдавал пустые ответы на 97% запросов
        for n, (v, r) in enumerate(zip(todo, pool.map(lambda v: one(v, v["посёлок"] in fh, token), todo)), 1):
            res[v["посёлок"]] = {k: [{x: i[x] for x in ("url", "title", "snippet")} for i in items] for k, items in r.items()}
            if n % 10 == 0 or n == len(todo):
                part.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(todo)}, осталось ≈{(time.time() - t0) / n * (len(todo) - n) / 60:.0f} мин", flush=True)
    out = raw / f"residents_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    part.unlink(missing_ok=True)
    print(f"выдача → {out}")
    finish(res)


if __name__ == "__main__":
    main()
