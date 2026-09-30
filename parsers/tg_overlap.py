"""Пересечения аудитории: сколько жителей посёлков (участники чатов группы 1) сидит в каждом тематическом чате.

python parsers/tg_overlap.py
Берёт все data/raw/tg_members_*.json (только хэши), чаты посёлков — группа 1 из data/lists/tg_poselki_otbor.tsv.
Итог: data/lists/tg_overlap.tsv — чат, собрано, из них жителей, доля; его читает панель.
"""
import json

import pandas as pd

from apify_run import ROOT

otbor = pd.read_csv(ROOT / "data" / "lists" / "tg_poselki_otbor.tsv", sep="\t")
VILLAGE = {u.replace("https://t.me/", "") for u in otbor[otbor["группа"].str.startswith("1.")]["ссылка"]}


def main():
    chats = {}
    for f in sorted((ROOT / "data" / "raw").glob("tg_members_*.json")):
        chats.update(json.loads(f.read_text(encoding="utf-8")))
    residents = set().union(*(set(v["h"]) for k, v in chats.items() if k in VILLAGE))
    rows = []
    for k, v in chats.items():
        h = set(v["h"])
        own = k in VILLAGE
        # для чата посёлка считаем жителей других посёлков, иначе доля всегда 100%
        other = set().union(*(set(chats[o]["h"]) for o in chats if o in VILLAGE and o != k)) if own else residents
        n = len(h & other)
        rows.append({"чат": k, "название": v.get("title") or "", "вид": "чат посёлка" if own else "тематический",
                     "участников в чате": v.get("size"), "собрано": len(h), "жителей посёлков": n,
                     "доля, %": round(n / len(h) * 100, 1) if h else 0})
    df = pd.DataFrame(rows).sort_values(["вид", "жителей посёлков"], ascending=[False, False])
    df.to_csv(ROOT / "data" / "lists" / "tg_overlap.tsv", sep="\t", index=False)
    print(f"жителей (уникальных) в чатах посёлков: {len(residents)}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
