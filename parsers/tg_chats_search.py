"""Чаты и каналы посёлков в Telegram через поиск Яндекса (Bright Data): «site:t.me <посёлок> чат».

python parsers/tg_chats_search.py
Итог: data/raw/tgsearch_<время>.json — ссылки t.me с заголовком и сниппетом по каждому запросу.
Правило: жителям не пишем — ссылки нужны только для пересечений участников (docs/telegram_auditoriya.md).
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from yandex_maps_bd import ROOT, env
from yandex_search_bd import serp

VILLAGES = ["Жуковка", "Барвиха", "Раздоры", "Шульгино", "Подушкино", "Ромашково", "Николина Гора", "Усово", "Дарьино",
            "Лапино", "Солослово", "Трувиль", "Пирогово", "Завидово", "Серебряный бор", "Горки-2", "Горки-10", "Знаменское",
            "Ильинское", "Архангельское", "Петрово-Дальнее", "Павловская Слобода", "Agalarov Estate", "Papushevo Park",
            "Фаворит", "Мидлтон", "Rubleff", "Маслово", "Бремен", "ParkVille", "Фонтенбло", "Резиденция Рублево",
            "Ла-Манш", "Довиль", "Маленькая Шотландия", "Березки River Village", "Антоновка", "Ренессанс Парк",
            "Белый берег", "Клуб 2071", "Кембридж", "Широкая река", "Новая Дятловка", "Ефимоново", "Юрьево",
            "Море Хаус", "Рига Фэмили", "Нордик", "Русская деревня"]
TERRITORY = ["Рублевка чат жителей", "Новая Рига чат жителей", "Ильинское шоссе чат", "Рублево-Успенское шоссе чат",
             "Новорижское шоссе коттеджный поселок чат", "коттеджный поселок Одинцовский чат жителей",
             "коттеджный поселок Истра чат жителей", "коттеджный поселок Красногорск чат жителей"]


def main():
    token = env("BRIGHTDATA_API_TOKEN")
    qs = [f"site:t.me {v} поселок чат" for v in VILLAGES] + [f"site:t.me {t}" for t in TERRITORY]
    with ThreadPoolExecutor(6) as pool:
        res = list(pool.map(lambda q: serp(q, token), qs))
    raw = {q: [i for i in items if re.search(r"t\.me/", i["url"])] for q, items in zip(qs, res)}
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out = ROOT / "data" / "raw" / f"tgsearch_{stamp}.json"
    out.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    print(f"запросов {len(qs)}, пустых {sum(not v for v in raw.values())}, ссылок {sum(map(len, raw.values()))} → {out}")


if __name__ == "__main__":
    main()
