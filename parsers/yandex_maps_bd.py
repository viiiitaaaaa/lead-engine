"""Яндекс Карты через Bright Data (зона serp_api1): поисковая выдача Карт → организации с контактами.

Страница Карт содержит JSON (<script class="state-view">) с ~20 организациями: телефоны, сайт, соцсети,
рейтинг, число отзывов, часы, адрес. Одна выдача = один запрос Bright Data.

python parsers/yandex_maps_bd.py                 # весь план запросов (список + ключевые слова)
python parsers/yandex_maps_bd.py "Калита Москва"  # отдельные запросы
python parsers/yandex_maps_bd.py --merge          # собрать одну таблицу из всех прошлых выгрузок data/raw/ymaps_*.json
Итог: data/raw/ymaps_<время>.json и таблица в Google Диск → Выгрузки.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DRIVE = Path(r"G:\Мой диск\Мои задачи\Лидогенерация — коттеджи и подрядчики\Выгрузки")
LISTS = ROOT / "data" / "lists" / "компании_и_поселки_2026-09-30.txt"

# названия из её списка, которые являются посёлками/локациями, а не компаниями
PLACES = {"Пирогово", "Завидово", "Серебряный бор", "Жуковка", "Барвиха", "Раздоры", "Шульгино", "Подушкино",
          "Ромашково", "Николина Гора", "Усово", "Дарьино", "Лапино", "Солослово", "Трувиль", "PAPUSHEVO PARK"}
KEYWORDS = ["отделка домов под ключ", "ремонт коттеджей премиум", "дизайн интерьера загородного дома",
            "комплектация дома под ключ", "инженерные системы коттеджа", "водоподготовка для дома",
            "вентиляция загородного дома", "умный дом коттедж", "итальянская мебель под заказ",
            "европейская сантехника", "элитный коттеджный посёлок", "управляющая компания коттеджного посёлка"]
AREAS = ["Новорижское шоссе", "Рублёво-Успенское шоссе"]


def env(name: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"')
    sys.exit(f"нет {name} в .env")


def plan() -> list[tuple[str, str]]:
    """(тип, запрос) — список заказчицы + ключевые слова × направления."""
    out = []
    for name in dict.fromkeys(l.strip() for l in LISTS.read_text(encoding="utf-8").splitlines() if l.strip()):
        out.append(("посёлок", f"коттеджные посёлки {name}") if name in PLACES else ("компания", f"{name} Москва"))
    out += [("ключевое", f"{k} {a}") for k in KEYWORDS for a in AREAS]
    return out


def fetch(query: str, token: str) -> list[dict]:
    url = "https://yandex.ru/maps/?text=" + urllib.parse.quote(query)
    body = json.dumps({"zone": "serp_api1", "url": url, "format": "raw"}).encode()
    for _ in range(3):  # пустой ответ бывает — повторить
        req = urllib.request.Request("https://api.brightdata.com/request", data=body, method="POST",
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            html = urllib.request.urlopen(req, timeout=150).read().decode("utf-8", "ignore")
        except Exception:
            continue
        m = re.search(r'<script[^>]*class="state-view"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            continue
        state = json.loads(m.group(1))
        items = []
        for s in state.get("stack", []):
            items += (s.get("results") or {}).get("items") or []
            if s.get("response"):  # карточка одной организации вместо списка
                items.append(s["response"])
        return [i for i in items if i.get("type") == "business"]
    return []


def row(kind: str, query: str, o: dict) -> dict:
    r = o.get("ratingData") or {}
    socials = o.get("socialLinks") or []
    return {
        "тип запроса": kind,
        "запрос": query,
        "название": o.get("title"),
        "вид деятельности": ", ".join(c.get("name", "") for c in o.get("categories") or []),
        "адрес": o.get("fullAddress") or o.get("address"),
        "телефоны": ", ".join(p.get("number", "") for p in o.get("phones") or []),
        "сайт": ", ".join(o.get("urls") or []),
        "WhatsApp": ", ".join(s["href"].split("?")[0] for s in socials if s.get("type") == "whatsapp"),
        "Telegram": ", ".join(s["href"] for s in socials if s.get("type") == "telegram"),
        "ВК": ", ".join(s["href"] for s in socials if s.get("type") == "vkontakte"),
        "другие соцсети": ", ".join(s["href"] for s in socials if s.get("type") not in ("whatsapp", "telegram", "vkontakte")),
        "рейтинг": round(r["ratingValue"], 1) if r.get("ratingValue") else None,
        "оценок": r.get("ratingCount"),
        "отзывов": r.get("reviewCount"),
        "часы": o.get("workingTimeText"),
        "карточка": f"https://yandex.ru/maps/org/{o.get('seoname', 'org')}/{o.get('id')}/",
        "id": o.get("id"),
    }


def main():
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    kinds = dict((q, k) for k, q in plan())
    if sys.argv[1:] == ["--merge"]:
        results = {}
        for f in sorted((ROOT / "data" / "raw").glob("ymaps_*.json")):
            for q, v in json.loads(f.read_text(encoding="utf-8")).items():
                q = q.strip()
                if q.startswith("коттеджный посёлок ") and q[19:] in PLACES:
                    continue  # старая форма запроса: Карты отдают местность, а не посёлки
                items = v["items"] if isinstance(v, dict) else v
                if items or q not in results:
                    results[q] = (kinds.get(q) or (v.get("kind") if isinstance(v, dict) else None) or "ручной", items)
        results = [((k, q), items) for q, (k, items) in results.items()]
    else:
        token = env("BRIGHTDATA_API_TOKEN")
        queries = [(kinds.get(q.strip(), "ручной"), q.strip()) for q in sys.argv[1:]] or plan()
        print(f"запросов: {len(queries)}")
        with ThreadPoolExecutor(5) as pool:
            results = list(pool.map(lambda kq: (kq, fetch(kq[1], token)), queries))
        rawp = ROOT / "data" / "raw" / f"ymaps_{stamp}.json"
        rawp.parent.mkdir(parents=True, exist_ok=True)
        rawp.write_text(json.dumps({q: {"kind": k, "items": items} for (k, q), items in results},
                                   ensure_ascii=False), encoding="utf-8")
    rows, empty = [], []
    for (kind, q), items in results:
        if not items:
            empty.append(q)
        rows += [row(kind, q, o) for o in items]
    df = pd.DataFrame(rows)
    uniq = df.drop_duplicates("id").drop(columns=["запрос"]) if len(df) else df
    DRIVE.mkdir(parents=True, exist_ok=True)
    out = DRIVE / f"яндекс_карты_BD_{stamp}.xlsx"
    with pd.ExcelWriter(out) as w:
        uniq.to_excel(w, sheet_name="организации", index=False)
        df.to_excel(w, sheet_name="по запросам", index=False)
        pd.DataFrame({"запрос без результатов": empty}).to_excel(w, sheet_name="пусто", index=False)
    print(f"строк: {len(df)}, уникальных организаций: {len(uniq)}, пустых запросов: {len(empty)}")
    print(f"с телефоном: {(uniq['телефоны'] != '').sum() if len(uniq) else 0}, с сайтом: {(uniq['сайт'] != '').sum() if len(uniq) else 0}")
    print(f"таблица: {out}")


if __name__ == "__main__":
    main()
