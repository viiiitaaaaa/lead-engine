"""Что хвалят и что ругают в проектах и у застройщиков посёлков её списка (её «отзывы, минусы, плюсы — всю инфу», 03.10).
По каждой карточке из data/raw/proekty_ratings.json + собственные карточки посёлков (Пирогово, Лапино) берём отзывы целиком
(yrev_full.json — полные из Chrome, иначе первые 50 из выгрузки) → фразы → тема + плюс/минус (по словам фразы, при равенстве — по оценке).

python parsers/proekty_temy.py
Итог: data/raw/proekty_temy.json {посёлок: [{проект, плюсы: {тема: n}, минусы: {тема: n}, цитаты…}]} → панель и раздел 9.
"""
import glob
import json
import re

import pandas as pd

from poselki_otzyvy import NEG, POS, THEMES
from yandex_maps_bd import DRIVE, ROOT

THEMES = {**THEMES,
          "качество домов и стройки": r"трещин|протек|протеч|теч[её]т|брак|качеств|переделыв|продува|промерза|плесен|строител|отделк",
          "персонал и сервис": r"менеджер|персонал|сотрудник|агент|риелтор|риэлтор|администрац|отношени|вежлив|хамск|грубо|помогл|подсказ",
          "сделка и документы": r"сделк|документ|договор|оформлен|юрист|ипотек"}
NEG2 = (r"проблем|отсутств|плох|ужас|кошмар|отключ|не хватает|разбит|грязн|жалоб|(?<![а-яё])минус|недостат|не работа|сломан|задерж|"
        r"обман|пробк|невозможно|не советую|не рекоменд|разочар|хуже|опасн|хамск|отвратит|тюрьм|вонюч|некорректн|противозакон|завышен|нет газа")
NOT_GOOD = r"(?<![а-яё])не\s+(?:самы\w*\s+|очень\s+)?(?:лучш|хорош|удобн|красив|обустро|понрав|хотят)|тормоз|занудн"
OWN = {"Пирогово": [{"name": "Курорт Пирогово (карточка посёлка)", "card": "/maps/org/kurort_pirogovo/108011223567"}],
       "Лапино": [{"name": "Новое Лапино (карточка посёлка)", "card": "/maps/org/novoye_lapino/145926408068"}],
       "Виджион": [{"name": "VISION (карточка посёлка)", "card": "/maps/org/vision/210162961171"}]}


def reviews(card: str, full: dict, rev: pd.DataFrame) -> list:
    cid = card.rstrip("/").split("/")[-1]
    fr = next((v for k, v in full.items() if f"/{cid}/" in k + "/"), None)
    if fr is not None:
        return [(x.get("оценка"), str(x.get("текст", ""))) for x in fr]
    r = rev[rev["id"] == cid]
    return [(x["оценка"], str(x["отзыв"])) for _, x in r.iterrows()]


def analyse(revs: list) -> dict:
    plus, minus = {}, {}
    for rating, txt in revs:
        rt = pd.to_numeric(rating, errors="coerce")
        if pd.isna(rt) or not txt or txt == "nan":
            continue
        for s in re.split(r"(?<=[.!?…\n])\s+", txt):
            s = s.strip()
            if not 20 <= len(s) <= 300:
                continue
            th = [t for t, rx in THEMES.items() if re.search(rx, s, re.I)]
            if not th:
                continue
            # плюс/минус — по оценке отзыва (4–5 / 1–3); слова фразы ошибались («постоянно на связи», «нет шума» → минус).
            # Цитатой берём только фразу, чей смысл совпадает с оценкой (проверено глазами 03.10).
            n = len(re.findall(NEG2, s, re.I)) + 2 * len(re.findall(NOT_GOOD, s, re.I))
            p = len(re.findall(POS, s, re.I))
            pol = "плюс" if rt >= 4 else "минус"
            fits = (p > n) if pol == "плюс" else (n > p)
            for t in th[:2]:
                d = plus if pol == "плюс" else minus
                d.setdefault(t, {"n": 0, "q": []})
                d[t]["n"] += 1
                if fits:
                    d[t]["q"].append(s)
    top = lambda d: [{"тема": t, "сколько": v["n"], "цитаты": sorted(set(v["q"]), key=len)[len(set(v["q"])) // 3:][:2]}
                     for t, v in sorted(d.items(), key=lambda kv: -kv[1]["n"])[:4]]
    return {"плюсы": top(plus), "минусы": top(minus)}


def main():
    pr = json.loads((ROOT / "data/raw/proekty_ratings.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "data/raw/yrev_full.json").read_text(encoding="utf-8"))
    rev = pd.read_excel(sorted(glob.glob(str(DRIVE / "яндекс_отзывы_*.xlsx")))[-1], sheet_name="отзывы")
    rev["id"] = rev["карточка"].astype(str).str.extract(r"/(\d{6,})/?$")[0]
    out = {}
    for village, cards in list(pr.items()) + [(k, v) for k, v in OWN.items()]:
        for c in cards:
            if c.get("площадка") == "2ГИС":
                continue
            rv = reviews(c["card"], full, rev)
            a = analyse(rv)
            out.setdefault(village, []).append({"проект": c["name"], "тип": c.get("тип", "посёлок"), "отзывов разобрано": len(rv), **a})
            print(f"{village:12} | {c['name'][:42]:42} | отзывов {len(rv):3} | + {', '.join(x['тема'] + ' ' + str(x['сколько']) for x in a['плюсы'][:3])}"
                  f" | − {', '.join(x['тема'] + ' ' + str(x['сколько']) for x in a['минусы'][:3])}")
    (ROOT / "data/raw/proekty_temy.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
