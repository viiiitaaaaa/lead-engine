"""Её список (46 компаний и посёлков, «наш список» в базе): доля положительных и отрицательных отзывов по каждому пункту —
Яндекс Карты (выгрузка отзывов + полные отзывы из Chrome, yrev_full.json) и 2ГИС (gis_reviews.json). Плюс — оценка 4–5, минус — 1–3.
Карточки пункта — как в панели (досье): для посёлка только сам посёлок, УК, застройщик, без школ и салонов местности.

python parsers/spisok_otzyvy_dolya.py
Итог: data/lists/spisok_otzyvy_dolya.tsv → основа лендинга (раздел «Ваш список — плюсы и минусы»).
"""
import glob
import json

import pandas as pd

from yandex_maps_bd import DRIVE, ROOT


def main():
    base = pd.read_excel(max(DRIVE.parent.glob("база_lead_engine_*.xlsx"), key=lambda p: p.stat().st_mtime), sheet_name="организации")
    rev = pd.read_excel(sorted(glob.glob(str(DRIVE / "яндекс_отзывы_*.xlsx")))[-1], sheet_name="отзывы")
    full = json.loads((ROOT / "data/raw/yrev_full.json").read_text(encoding="utf-8"))
    add = pd.DataFrame([{"оценка": pd.to_numeric(r.get("оценка"), errors="coerce"), "карточка": c} for c, rs in full.items() for r in rs])
    rev = pd.concat([rev[~rev["карточка"].isin(full)], add], ignore_index=True)
    rev["оценка"] = pd.to_numeric(rev["оценка"], errors="coerce")
    dos = json.loads((ROOT / "data/raw/dossier.json").read_text(encoding="utf-8"))
    gis = json.loads((ROOT / "data/raw/gis_reviews.json").read_text(encoding="utf-8"))
    rows = []
    for name, d in dos.items():
        g = base[(base["наш список"] == name) & ~base["новая?"].fillna("").str.startswith("отсеяно")]
        if d["вид"] == "посёлок":
            g = g[(g["тип"] == "посёлок") | g["вид деятельности"].fillna("").str.contains(r"коттеджн|посёл|посел|управляющ", case=False, regex=True)]
        # тёзки вне нашей территории и чужие проекты: «Фонтенбло» (Пушкинский р-н) у Жуковки, «ЭкоКвартал Пирогово» у Пирогово Коллекции
        g = g[~g["адрес"].fillna("").str.contains("Пушкинск") & ~g["название"].fillna("").str.contains(r"ЭкоКвартал|ИП ", regex=True)]
        ym = rev[rev["карточка"].isin(set(g["ссылка"]))]["оценка"].dropna()
        gv = pd.Series([x.get("оценка") for x in (gis.get(name) or {}).get("отзывы", [])], dtype=float).dropna()
        allr = pd.concat([ym, gv])
        n = len(allr)
        rows.append({"пункт": name, "вид": d["вид"], "отзывов": n, "Яндекс": len(ym), "2ГИС": len(gv),
                     "плюс %": round((allr >= 4).mean() * 100) if n else None, "минус %": round((allr <= 3).mean() * 100) if n else None,
                     "средняя оценка": round(allr.mean(), 1) if n else None})
    out = pd.DataFrame(rows).sort_values(["отзывов"], ascending=False)
    out.to_csv(ROOT / "data/lists/spisok_otzyvy_dolya.tsv", sep="\t", index=False)
    has = out[out["отзывов"] > 0]
    allp = (has["плюс %"] * has["отзывов"]).sum() / has["отзывов"].sum()
    print(f"пунктов {len(out)}, с отзывами {len(has)}, отзывов {has['отзывов'].sum()}, в среднем плюс {allp:.0f}% / минус {100 - allp:.0f}%")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
