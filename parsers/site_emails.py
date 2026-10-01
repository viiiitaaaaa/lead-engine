"""Почты и телефоны с сайтов организаций базы, у которых почты ещё нет. Обычные запросы, бесплатно.

python parsers/site_emails.py
Берёт сайты из последней базы, по каждому домену — главная и /contacts. Пишет data/raw/site_contacts.json
({домен: {"почты": […], "телефоны": […]}}) каждые 20 доменов и продолжает с места; build_base.py подмешивает его к почтам.
"""
import glob
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import pandas as pd

from yandex_maps_bd import ROOT
from yandex_search_bd import site_contacts

OUT = ROOT / "data" / "raw" / "site_contacts.json"


def domain(u: str) -> str:
    u = u.strip().strip("[]'\" ")
    return urlparse(u if "//" in u else "http://" + u).netloc.lower().removeprefix("www.")


def main():
    base_x = max(glob.glob(r"G:\Мой диск\Мои задачи\Лидогенерация — коттеджи и подрядчики\база_lead_engine_*.xlsx"))
    b = pd.read_excel(base_x, sheet_name="организации").fillna("")
    sites = {}
    for s, mail in zip(b["сайт"].astype(str), b["почты"].astype(str)):
        if mail or not s:
            continue
        for u in s.split(","):
            d = domain(u)
            if d and "." in d and not any(x in d for x in ("vk.com", "instagram", "t.me", "yandex", "google", "wa.me", "taplink")):
                sites.setdefault(d, u.strip().strip("[]'\" "))
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [(d, u if "//" in u else "https://" + u) for d, u in sites.items() if d not in done]
    print(f"доменов без почты {len(sites)}, уже проверено {len(sites) - len(todo)}, осталось {len(todo)}", flush=True)
    with ThreadPoolExecutor(12) as pool:
        for n, ((d, _), (ph, ml)) in enumerate(zip(todo, pool.map(lambda x: site_contacts(x[1]), todo)), 1):
            done[d] = {"почты": [m for m in ml.split(", ") if m], "телефоны": [p for p in ph.split(", ") if p]}
            if n % 20 == 0 or n == len(todo):
                OUT.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(todo)}, с почтой {sum(bool(v['почты']) for v in done.values())}", flush=True)


if __name__ == "__main__":
    main()
