"""Ключевые слова, наиболее близкие к нам (её задача 04.10): из заголовков (title, h1–h3), meta description/keywords и
текста сайтов конкурентов, монтажников-партнёров и самого Frivent (sayty_obhod.py) + заголовков форумных тем.
Фразы 2–4 слова, в которых есть наша тема (вентиляция, рекуперация, осушение, бассейн, кондиционирование, отопление,
водоподготовка…); слова приводятся к начальной форме (pymorphy3), чтобы падежи считались вместе.
Ранжирование: на скольких сайтах встречается (не сколько раз) — так видно общий язык рынка, а не повторы одного сайта.

python parsers/klyuchevye_slova.py
Итог: data/lists/klyuchevye_slova.tsv (фраза, тема, сайтов всего, у конкурентов, у монтажников, у Frivent, пример)
"""
import json
import re
from collections import Counter, defaultdict

import pandas as pd
import pymorphy3

from yandex_maps_bd import ROOT

M = pymorphy3.MorphAnalyzer()
TOPIC = {
    "вентиляция и рекуперация": r"вентиляц|приточн|вытяжн|рекуперат|рекуперац|воздухообмен|бризер|воздуховод|вентустанов|пву|пвву|свежий воздух|теплоутилиз",
    "бассейн и осушение": r"бассейн|осуш|влажност|аквапарк|спа|сауна|аквазон",
    "кондиционирование и климат": r"кондицион|сплит|мультизон|vrf|vrv|чиллер|фанкойл|климат|охлажд",
    "отопление": r"отоплен|котел|котёл|котельн|тепловой насос|теплый пол|тёплый пол|радиатор|бойлер|водонагрев",
    "водоподготовка": r"водоподгот|водоочист|очистк\w* вод|обезжелез|умягч|фильтр\w* для вод|осмос",
    "автоматика и сервис": r"автоматик|щит управлен|шкаф управлен|диспетчериз|умный дом|сервисн|обслуживан|пусконалад|шеф-монтаж|монтаж|проектирован|подбор",
}
OBJ = r"дом|коттедж|квартир|офис|ресторан|кафе|кухн|бассейн|магазин|тц|торгов|склад|производств|клиник|медицин|школ|детск|спорт|фитнес|гостиниц|отел|серверн|цод|загородн|частн"
NOT_OURS = r"монтаж|ремонт|строительств|построить|сплит|химия|магазин|заправк|чистк|установка кондиционер"  # не наше (мы не монтируем, не строим бассейны)
STOP = set("и в во на с со для по от до из к о об при под над за без или а но что как это все всё наш ваш мы вы мск москва московский область цена цены купить "
           "заказать недорого рублей руб тел телефон главная каталог услуга услуги компания компании сайт меню контакты о нас г ооо".split())


def lemma(w: str) -> str:
    return M.parse(w)[0].normal_form


def phrases(text: str) -> set:
    out = set()
    for part in re.split(r"[.,;:!?|()\[\]«»\"/–—\-•·\n]+", text.lower()):
        ws = [w for w in re.findall(r"[а-яёa-z0-9]+", part) if len(w) > 1]
        for n in (2, 3, 4):
            for i in range(len(ws) - n + 1):
                g = ws[i:i + n]
                if g[0] in STOP or g[-1] in STOP or any(w.isdigit() for w in g):
                    continue
                ph = " ".join(g)
                if any(re.search(rx, ph) for rx in TOPIC.values()):
                    out.add(ph)
    return out


def main():
    sites = json.loads((ROOT / "data/raw/sayty_obhod.json").read_text(encoding="utf-8"))
    df, by, example = Counter(), defaultdict(Counter), defaultdict(Counter)
    cache = {}
    for s, v in sites.items():
        if v.get("ответ") != "ок":
            continue
        grp = v["группа"]
        src = " | ".join(v.get("заголовки", [])) + " | " + v.get("мета", "")
        lem = set()
        for ph in phrases(src):
            key = " ".join(cache.setdefault(w, lemma(w)) for w in ph.split())
            lem.add(key)
            example[key][ph] += 1
        for k in lem:
            df[k] += 1
            by[k][grp] += 1
    ff = ROOT / "data/raw/konkurenty_forumy.json"  # заголовки форумных тем — язык покупателей
    forum = Counter()
    if ff.exists():
        for u, v in json.loads(ff.read_text(encoding="utf-8")).items():
            for ph in phrases(v.get("заголовок", "")):
                key = " ".join(cache.setdefault(w, lemma(w)) for w in ph.split())
                forum[key] += 1
                example[key][ph] += 1
    rows = []
    for k, n in df.items():
        if n < 3:
            continue
        theme = next((t for t, rx in TOPIC.items() if re.search(rx, k)), "")
        rows.append({"фраза": example[k].most_common(1)[0][0], "начальная форма": k, "тема": theme, "объект": ", ".join(sorted(set(re.findall(OBJ, k)))),
                     "сайтов всего": n, "у конкурентов": by[k]["конкуренты"], "у монтажников": by[k]["монтажники"], "у Frivent": by[k]["мы"],
                     "в заголовках форумов": forum.get(k, 0), "слов": len(k.split()),
                     "у Frivent нет — возможность": "да" if by[k]["мы"] == 0 and (by[k]["конкуренты"] + by[k]["монтажники"]) >= 5
                     and not re.search(NOT_OURS, k) else ""})
    t = pd.DataFrame(rows)
    # вложенные фразы: короткую убираем, если длинная встречается почти так же часто (≥80%) — оставляем точную формулировку
    t = t.sort_values(["сайтов всего", "слов"], ascending=[False, False])
    keep = []
    for _, r in t.iterrows():
        if not any(r["начальная форма"] in x["начальная форма"] and x["сайтов всего"] >= 0.8 * r["сайтов всего"] for x in keep):
            keep.append(r)
    t = pd.DataFrame(keep).sort_values(["тема", "сайтов всего"], ascending=[True, False])
    t.to_csv(ROOT / "data/lists/klyuchevye_slova.tsv", sep="\t", index=False)
    print(f"фраз {len(t)} (из {len(df)} кандидатов), сайтов {sum(1 for v in sites.values() if v.get('ответ') == 'ок')}")
    for th, g in t.groupby("тема"):
        print(f"\n== {th}: {len(g)}")
        print(g.sort_values("сайтов всего", ascending=False).head(12)[["фраза", "сайтов всего", "у конкурентов", "у монтажников", "у Frivent"]].to_string(index=False))


def razdel():
    """раздел 11 основы лендинга между метками <!-- r11 --> … <!-- /r11 -->"""
    t = pd.read_csv(ROOT / "data/lists/klyuchevye_slova.tsv", sep="\t", dtype=str).fillna("")
    for c in ("сайтов всего", "у конкурентов", "у монтажников", "у Frivent"):
        t[c] = t[c].astype(int)
    fq = "запросов в месяц (Мск+МО)"
    has_ws = fq in t.columns and (t[fq] != "").any()
    t["q"] = pd.to_numeric(t[fq], errors="coerce").fillna(-1) if has_ws else -1
    md = ("## 11. Ключевые слова — язык рынка и что реально ищут\n"
          "Фразы из заголовков, разделов и описаний страниц 235 сайтов конкурентов, монтажников-партнёров и Frivent: на скольких сайтах встречается "
          "(так видно, какими словами рынок называет то, что мы продаём; падежи сведены вместе)"
          + (" и сколько раз в месяц её ищут в Яндексе по Москве и области (Вордстат, все устройства)" if has_ws else "") + ". "
          f"Полный список — data/lists/klyuchevye_slova.tsv ({len(t)} фраз). «Возможность» — фраза есть у 5+ конкурентов и монтажников, "
          "а на сайте Frivent её нет: тема для страницы, статьи или рекламы (монтаж, ремонт и строительство — не наше, не отмечены).\n\n")
    wt = ROOT / "data/lists/wordstat_temy.tsv"
    if wt.exists():
        w = pd.read_csv(wt, sep="\t", dtype=str).fillna("")
        w["n"] = pd.to_numeric(w["запросов в месяц (Мск+МО)"], errors="coerce").fillna(0).astype(int)
        md += ("### Что реально ищут по темам Frivent (Вордстат, Москва и область, в месяц)\n"
               "Первое число — все запросы с этими словами; дальше — самые частые конкретные запросы людей.\n\n"
               "| Тема | Всего | Самые частые запросы |\n|---|---|---|\n")
        tot = []
        for seed, g in w[w["вид"] == "запрос со словами"].groupby("тема Frivent", sort=False):
            g = g.sort_values("n", ascending=False)
            tot.append((seed, int(g["n"].iloc[0]) if len(g) else 0, g))
        for seed, n, g in sorted(tot, key=lambda x: -x[1]):
            md += f"| {seed} | **{n:,}** | ".replace(",", " ") + "; ".join(f"{r['запрос']} ({r['n']:,})".replace(",", " ") for _, r in g.iloc[1:9].iterrows()) + " |\n"
        md += "\n"
    for th, g in t[t["тема"] != ""].groupby("тема"):
        g = g.sort_values(["q", "сайтов всего"] if has_ws else ["сайтов всего"], ascending=False).head(15)
        md += (f"**{th}**\n\n| Фраза | {'Ищут в месяц | ' if has_ws else ''}Сайтов | У конкурентов | У монтажников | У Frivent | Возможность |\n"
               f"|---|{'---|' if has_ws else ''}---|---|---|---|---|\n"
               + "".join(f"| {r['фраза']} | {(str(int(r['q'])) if r['q'] >= 0 else '') + ' | ' if has_ws else ''}{r['сайтов всего']} | {r['у конкурентов']} | "
                         f"{r['у монтажников']} | {'есть' if r['у Frivent'] else '—'} | {'да' if r['у Frivent нет — возможность'] else ''} |\n" for _, r in g.iterrows()) + "\n")
    gap = t[t["у Frivent нет — возможность"] == "да"].sort_values(["q", "сайтов всего"], ascending=False).head(30)
    md += ("**Чего нет на сайте Frivent, а у рынка есть (первые 30" + (", по частоте запросов" if has_ws else "") + "):** "
           + ", ".join(f"{r['фраза']} ({int(r['q']) if has_ws and r['q'] >= 0 else r['сайтов всего']})" for _, r in gap.iterrows()) + ".\n")
    MD = ROOT / "docs/лендинг_основа.md"
    s = MD.read_text(encoding="utf-8")
    s = re.sub(r"\n*<!-- r11 -->.*?<!-- /r11 -->\n?", "\n", s, flags=re.S).rstrip() + f"\n\n<!-- r11 -->\n{md}<!-- /r11 -->\n"
    MD.write_text(s, encoding="utf-8")
    print("раздел 11 записан")


if __name__ == "__main__":
    import sys
    if "--razdel" not in sys.argv:
        main()
    razdel()
