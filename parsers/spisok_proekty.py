"""Проекты внутри посёлков её списка (её решение 03.10: «отзывы у отдельных проектов внутри мест — да, такие нужны, именно проекты»).
Строка = проект (карточка Яндекс Карт): рейтинг и число оценок на карте (собрано в Chrome → data/raw/proekty_ratings.json),
отзывы с текстом (полные из Chrome — yrev_full.json, иначе первые 50 из выгрузки), доля плюсов (4–5) и минусов (1–3).
Проект привязан к посёлку, если место указано в адресе карточки.

python parsers/spisok_proekty.py
Итог: data/lists/spisok_proekty.tsv → раздел 9 основы лендинга (таблица «Проекты внутри посёлков»).
"""
import glob
import json

import pandas as pd

from yandex_maps_bd import DRIVE, ROOT


def main():
    pr = json.loads((ROOT / "data/raw/proekty_ratings.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "data/raw/yrev_full.json").read_text(encoding="utf-8"))
    rev = pd.read_excel(sorted(glob.glob(str(DRIVE / "яндекс_отзывы_*.xlsx")))[-1], sheet_name="отзывы")
    rev["id"] = rev["карточка"].astype(str).str.extract(r"/(\d{6,})/?$")[0]
    rows = []
    for village, cards in pr.items():
        for c in cards:
            cid = c["card"].rstrip("/").split("/")[-1]
            fr = next((v for k, v in full.items() if f"/{cid}/" in k + "/"), None)
            marks = pd.to_numeric(pd.Series([x.get("оценка") for x in fr]) if fr is not None else rev[rev["id"] == cid]["оценка"], errors="coerce").dropna()
            n = len(marks)
            rows.append({"посёлок": village, "проект": c["name"], "тип": c.get("тип", "проект"), "площадка": c.get("площадка", "Яндекс"),
                         "карточка": c["card"] if c["card"].startswith("http") else "https://yandex.ru" + c["card"] + "/",
                         "рейтинг Яндекса": round(c["rating"], 1) if c["ratings"] else None, "оценок": c["ratings"], "отзывов на карте": c["reviews"],
                         "отзывов с текстом у нас": n, "плюс %": round((marks >= 4).mean() * 100) if n else None,
                         "минус %": round((marks <= 3).mean() * 100) if n else None, "полные отзывы": fr is not None})
    d = pd.DataFrame(rows)
    d.to_csv(ROOT / "data/lists/spisok_proekty.tsv", sep="\t", index=False)
    print(d[["посёлок", "проект", "рейтинг Яндекса", "оценок", "отзывов на карте", "отзывов с текстом у нас", "плюс %"]].to_string(index=False))


if __name__ == "__main__":
    main()
