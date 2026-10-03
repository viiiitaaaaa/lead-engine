"""Поиск Яндекса для досье без Bright Data (денег нет, 03.10): запросы идут в Chrome (ya.ru, fetch + DOMParser, пауза 10–14 с),
результат скачивается файлом в Загрузки; здесь он раскладывается по досье теми же фильтрами, что в list_dossier.search:
отзывы на площадках, статьи, вопросы на форумах, клиенты/кейсы — с отсевом тёзок по бренду, домену и юрлицу.

python parsers/dossier_chrome_search.py montazhniki ds_search.json
Вход: [{"пункт", "вид": "отзывы|статьи|вопросы|клиенты", "items": [{url, title, snippet}]}]
"""
import json
import re
import sys
from pathlib import Path

from list_dossier import FORUMS, MEDIA_NOT, REVIEW_SITES, brand_keys, found
from villages_merge import key
from yandex_maps_bd import ROOT


def main():
    grp, fn = sys.argv[1], sys.argv[2]
    f = ROOT / f"data/raw/dossier_{grp}.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    got = json.loads((Path.home() / "Downloads" / fn).read_text(encoding="utf-8"))
    n = {}
    for r in got:
        v = d.get(r["пункт"])
        if not v:
            continue
        keys = brand_keys(r["пункт"], v["сайты"], v.get("юрлицо") or {})
        items = [i for i in r["items"] if "yabs.yandex" not in i["url"]
                 and any(k in key(i["title"] + " " + i["snippet"]) or k in re.sub(r"[^a-z0-9]", "", i["url"].lower()) for k in keys)]
        k = r["вид"]
        if k == "отзывы":
            items = [i for i in items if re.search(REVIEW_SITES, i["url"], re.I) or re.search(r"отзыв", i["title"], re.I)]
        elif k == "статьи":
            items = [i for i in items if not re.search(MEDIA_NOT, i["url"], re.I)]
        elif k == "вопросы":
            items = [i for i in items if re.search(FORUMS, i["url"], re.I)]
        v[k] = found(items[:8], k)
        n[k] = n.get(k, 0) + len(v[k])
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print("найдено:", n)


if __name__ == "__main__":
    main()
