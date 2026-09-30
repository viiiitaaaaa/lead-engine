"""Единый список посёлков: каталоги Villagio + ONEHOUSE, отметки «наш список», дома на Циане, Telegram.

python parsers/villages_merge.py
Берёт последний data/raw/villagio_*.json, data/lists/onehouse_poselki.tsv (собран в Chrome — сайт не пускает запросы),
data/lists/cian_doma.tsv и tg_poselki_otbor.tsv. Итог: data/lists/poselki_katalog.tsv — его показывает панель.
"""
import json
import re

import pandas as pd

from apify_run import ROOT

TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "i", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "h", "ts",
               "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
HW = [("Новорижск", "Новорижское"), ("Рубл", "Рублёво-Успенское"), ("Успенск", "Рублёво-Успенское"), ("Ильинск", "Ильинское"),
      ("Минск", "Минское"), ("Киевск", "Киевское"), ("Можайск", "Можайское"), ("Калужск", "Калужское"), ("Волоколамск", "Волоколамское"),
      ("Дмитровск", "Дмитровское"), ("Пятницк", "Пятницкое"), ("Ленинградск", "Ленинградское")]
OURS = r"новая рига|новорижск|рубл|успенск|ильинск"


def key(name: str) -> str:
    n = re.sub(r"\(.*?\)|[«»\"]|коттеджный пос[её]лок|\bкп\b|^\s*(?:д|пос|с|дер)\.\s*|river village|village|estate|эстейт|эстэйт|естейт",
               " ", re.sub(r"[«»\"]", "", str(name)).lower().strip())
    return re.sub(r"[^a-z0-9]", "", "".join(TR.get(c, c) for c in n))


def hw(x: str) -> str:
    return next((v for k, v in HW if k in str(x)), str(x).replace(" шоссе", "").strip())


def main():
    vf = sorted((ROOT / "data" / "raw").glob("villagio_*.json"))[-1]
    vil = pd.DataFrame(json.loads(vf.read_text(encoding="utf-8")))
    vil = vil[~vil["посёлок"].str.contains("Жилой комплекс|ЖК|Фонд|апартамент", case=False, na=False)]
    one = pd.read_csv(ROOT / "data" / "lists" / "onehouse_poselki.tsv", sep="\t")
    rows = {}
    for _, r in vil.iterrows():
        k = key(r["посёлок"])
        rows[k] = {"посёлок": r["посёлок"].strip("«»"), "шоссе": hw(r["шоссе"]), "км до МКАД": r["км до МКАД"],
                   "Villagio": r["ссылка"], "ONEHOUSE": "", "объектов у Villagio": r["объектов в продаже"],
                   "эксперты Villagio": r.get("эксперты Villagio") or ""}
    for _, r in one.iterrows():
        k = key(r["посёлок"])
        e = rows.setdefault(k, {"посёлок": r["посёлок"], "шоссе": hw(r["шоссе"]), "км до МКАД": r["км до МКАД"],
                                "Villagio": "", "объектов у Villagio": 0, "эксперты Villagio": ""})
        e["ONEHOUSE"] = f"https://onehouse.ru/estate/village/{r['slug']}"
        if pd.isna(e.get("км до МКАД")) and not pd.isna(r["км до МКАД"]):
            e["км до МКАД"] = r["км до МКАД"]
        if r["из списка каталога"] == 1 or not e.get("шоссе"):  # у ONEHOUSE карточка списка точнее описания
            e["шоссе"], e["км до МКАД"] = hw(r["шоссе"]), r["км до МКАД"]
    df = pd.DataFrame(rows.values())
    df["шоссе"] = df["шоссе"].replace("", "?")
    df["посёлок"] = df["посёлок"].str.replace(r'^(?:КП|д\.|с\.|пос\.)\s*|["«»]', "", regex=True).str.strip()

    lists = [l.strip() for l in (ROOT / "data" / "lists" / "компании_и_поселки_2026-09-30.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    lk = {key(l): l for l in lists}
    df["наш список"] = df["посёлок"].map(lambda n: lk.get(key(n), ""))
    cian = pd.read_csv(ROOT / "data" / "lists" / "cian_doma.tsv", sep="	")
    ck = cian["посёлок/место"].fillna("").map(lambda p: key(re.sub(r"\(КП\)|^(д|пос|с)\.\s*", "", p))).value_counts().to_dict()
    df["домов на Циане"] = df["посёлок"].map(lambda n: ck.get(key(n), 0))
    tg = pd.read_csv(ROOT / "data" / "lists" / "tg_poselki_otbor.tsv", sep="\t").fillna("")
    tgt = [(key(f'{r["название"]} {r["заметка"]}'), r["ссылка"]) for _, r in tg.iterrows()]
    df["Telegram"] = df["посёлок"].map(lambda n: next((u for t, u in tgt if len(key(n)) > 4 and key(n) in t), ""))
    df["наша территория"] = df["шоссе"].str.contains("Новорижск|Рублёво|Ильинск")
    df = df.sort_values(["наша территория", "домов на Циане", "объектов у Villagio"], ascending=False)
    df.to_csv(ROOT / "data" / "lists" / "poselki_katalog.tsv", sep="\t", index=False)
    t = df[df["наша территория"]]
    print(f"посёлков {len(df)}, на нашей территории {len(t)}; в обоих каталогах {((df['Villagio'] != '') & (df['ONEHOUSE'] != '')).sum()}")
    print(t["шоссе"].value_counts().to_dict(), "| из нашего списка:", (df["наш список"] != "").sum(),
          "| с домами на Циане:", (t["домов на Циане"] > 0).sum(), "| с Telegram:", (df["Telegram"] != "").sum())


if __name__ == "__main__":
    main()
