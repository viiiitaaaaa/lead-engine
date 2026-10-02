"""Участники открытых Telegram-чатов → только хэши id (без имён, логинов, телефонов). Для пересечений групп.

python parsers/tg_members.py zhukodin ilyinskoeusovo --max 600 --cap 0.5   # --cap — на все чаты вместе (02.10: было на каждый, переплата 2.18 $ вместо 1.2)
Итог: data/raw/tg_members_<время>.json = {чат: {"size": …, "hidden": …, "h": [хэши], "bots": n}}.
Правило: жителям не пишем (docs/telegram_auditoriya.md). Выгрузка в Apify удаляется сразу после скачивания.
"""
import argparse
import hashlib
import json
import secrets
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from apify_run import API, ROOT, run, token

ACTOR = "agentx/telegram-member-scraper"


def salt() -> str:
    env = ROOT / ".env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("TG_HASH_SALT="):
            return line.split("=", 1)[1].strip()
    s = secrets.token_hex(16)
    with env.open("a", encoding="utf-8") as f:
        f.write(f"\nTG_HASH_SALT={s}\n")
    return s


def collect(chat: str, n: int, cap: float, sl: str) -> dict:
    items, r = run(ACTOR, {"telegram_url": chat, "max_results": n, "deep_search": True}, cap, wait=3600)
    urllib.request.urlopen(urllib.request.Request(f"{API}/datasets/{r['defaultDatasetId']}", method="DELETE",
                                                  headers={"Authorization": "Bearer " + token()}))
    people = [i for i in items if i.get("type") != "bot" and i.get("id")]
    first = items[0] if items else {}
    return {"size": first.get("group_member_count"), "hidden": first.get("group_members_hidden"),
            "title": first.get("group_title"), "status": r["status"], "usd": r.get("usageTotalUsd"),
            "bots": len(items) - len(people),
            "h": sorted({hashlib.sha256(f"{sl}:{i['id']}".encode()).hexdigest()[:16] for i in people})}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("chats", nargs="+")
    a.add_argument("--max", type=int, default=600, help="сколько участников брать из чата")
    a.add_argument("--cap", type=float, default=0.5, help="потолок трат на ВЕСЬ запуск, $ (делится поровну между чатами)")
    o = a.parse_args()
    sl = salt()
    with ThreadPoolExecutor(5) as pool:
        res = dict(zip(o.chats, pool.map(lambda c: collect(c, o.max, round(o.cap / len(o.chats), 2), sl), o.chats)))
    out = ROOT / "data" / "raw" / f"tg_members_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    for c, v in res.items():
        print(f"{c}: {v['status']}, собрано {len(v['h'])} из {v['size']} (список скрыт: {v['hidden']}), ${v['usd']:.3f}")
    print(f"всего ${sum(v['usd'] or 0 for v in res.values()):.2f} → {out}")


if __name__ == "__main__":
    main()
