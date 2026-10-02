"""Instagram конкурентов и партнёров: профили по ссылкам, уже найденным на сайтах и в карточках (база + дизайн-бюро).
Apify apify/instagram-profile-scraper, потолок трат --cap (по умолчанию 1 $). Аудиторию (подписчиков) не собираем.

python parsers/instagram_profiles.py [--cap 1]
Итог: data/raw/instagram_profiles_<время>.json + data/lists/instagram_konkurenty.tsv; показывает панель.
"""
import json
import re
import sys
from datetime import datetime

import pandas as pd

from apify_run import ROOT, run
from build_base import DRIVE

SKIP = {"p", "explore", "reel", "reels", "stories", "accounts", "direct", "tv", "instagram", "share"}
H = r"instagram\.com/([A-Za-z0-9_.]+)"


def handles() -> dict:
    """{аккаунт: (чей, откуда)} из базы организаций и разбора дизайн-бюро"""
    out = {}
    bx = max(DRIVE.glob("база_lead_engine_*.xlsx"), key=lambda p: p.stat().st_mtime)
    b = pd.read_excel(bx, sheet_name="организации", dtype=str).fillna("")
    for r in b.to_dict("records"):
        for h in re.findall(H, r["другие соцсети"]):
            out.setdefault(h.lower().rstrip("."), (r["название"], r["вид деятельности"][:80]))
    dz = ROOT / "data" / "lists" / "dizain_byuro.tsv"
    if dz.exists():
        for r in pd.read_csv(dz, sep="\t", dtype=str).fillna("").to_dict("records"):
            for h in re.findall(H, r["instagram"]):
                out.setdefault(h.lower().rstrip("."), (r["бюро"][:80], f'дизайн-бюро · {r["группа"]}'))
    return {h: v for h, v in out.items() if h not in SKIP and len(h) > 2}


def main():
    if "--rebuild" in sys.argv:  # пересобрать таблицу из последней выгрузки без запросов
        f = sorted((ROOT / "data" / "raw").glob("instagram_profiles_2*.json"))[-1]
        return table(json.loads(f.read_text(encoding="utf-8")), handles(), {"status": "из файла"}, f)
    cap =float(sys.argv[sys.argv.index("--cap") + 1]) if "--cap" in sys.argv else 1.0
    hs = handles()
    print(f"профилей {len(hs)}, потолок {cap} $", flush=True)
    items, info = run("apify/instagram-profile-scraper", {"usernames": list(hs)}, cap)
    out = ROOT / "data" / "raw" / f"instagram_profiles_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    table(items, hs, info, out)


def table(items: list, hs: dict, info: dict, out) -> None:
    rows = []
    for it in items:
        h = (it.get("username") or "").lower()
        if not h:
            continue
        who, what = hs.get(h, ("", ""))
        posts = it.get("latestPosts") or []
        last = max((p.get("timestamp") or "" for p in posts), default="")[:10]
        rows.append({"аккаунт": h, "ссылка": f"https://instagram.com/{h}", "чей": who, "кто это": what, "имя в профиле": it.get("fullName", ""),
                     "подписчиков": it.get("followersCount"), "постов": it.get("postsCount"), "последний пост": last,
                     "категория": it.get("businessCategoryName") or "", "сайт в профиле": it.get("externalUrl") or "",
                     "о себе": re.sub(r"\s+", " ", it.get("biography") or "")[:250]})
    df = pd.DataFrame(rows).sort_values("подписчиков", ascending=False)
    df = df[~df["кто это"].str.contains(r"АЖҚС|АЗС", regex=True) & ~df["аккаунт"].isin(["onlinerby"])]  # случайные: АЗС, белорусское СМИ
    df.to_csv(ROOT / "data" / "lists" / "instagram_konkurenty.tsv", sep="\t", index=False)
    print(f"получено {len(df)} из {len(hs)}; статус {info.get('status')}, потрачено {info.get('usageTotalUsd')} $ → {out}")


if __name__ == "__main__":
    main()
