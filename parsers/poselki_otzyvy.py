"""Отзывы, статьи, плюсы, минусы и боли по посёлкам из её списка (её «собери по ним всю инфу: отзывы, статьи, боли, плюсы, минусы»).
Источники: поиск Яндекса в её Chrome (Загрузки\\serp_poselki_otzyvy.json: по 3 запроса на посёлок — отзывы жителей, статьи, плюсы и минусы)
→ скачиваем найденные страницы → делим по виду источника:
  ЛЮДИ — отзывы с её карточек Яндекс Карт, форумы и отзовики → плюсы и минусы;
  СМИ — статьи (список + плюсы и минусы, которые там названы);
  ПРОДАВЦЫ — сайты агентств и застройщиков: это реклама, плюсов «от их имени» не считаем, только «что обещают».
Перепроверено 03.10: тёзки (Барвиха на Щёлковском ш., ЖК «Усово Парк», ЖК «Ромашково»), шаблоны отзовиков и рекламные фразы отсеиваются.

python parsers/poselki_otzyvy.py            # скачать страницы (кэш data/raw/poselki_pages.json) + разбор
python parsers/poselki_otzyvy.py --reparse  # только разбор
Итог: data/raw/poselki_otzyvy.json → досье посёлков в панели.
"""
import glob
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from partner_pains import get
from yandex_maps_bd import DRIVE, ROOT

CACHE = ROOT / "data/raw/poselki_pages.json"
SKIP = r"yandex\.|youtube|rutube|vk\.com/video|avito\.|hh\.ru|/sale/suburban/|kupit-|market\."
NAMES = {  # как посёлок пишут в текстах (корни)
    "Жуковка": r"жуковк", "Барвиха": r"барвих", "Раздоры": r"раздор", "Шульгино": r"шульгин", "Подушкино": r"подушкин",
    "Николина Гора": r"николин\w* гор", "Усово": r"усов", "Солослово": r"солослов", "Пирогово": r"пирогов", "Дарьино": r"дарьин",
    "Лапино": r"лапин", "Серебряный бор": r"серебрян\w* бор", "Ромашково": r"ромашков",
}
RUB = r"рубл[её]в|одинцов|успенск|ильинск|подушкин|москв\w*[- ]рек"
LOC = {"Пирогово": r"мытищ|клязьм|пирогов\w* водохр|дмитровск|осташковск", "Серебряный бор": r"хорош[её]в|сзао|таманск",
       "Лапино": r"одинцов|можайск|минск|лапин\w* (кп|коттедж)", "Дарьино": RUB + r"|darino\.club"}
BAD = (r"щ[её]лков|красногорск|ярослав|воскресенск|владимирск|пушкинск|тверск|ленинградск|домодедов|ступин|раменск|ногинск"
       r"|балаших|подольск|зеленоград|(?<![а-яё])жк(?![а-яё])|многоэтажн|квартир")
BOILER = r"(Достоинства|Недостатки|Комментарий|Цена/качество|Транспортная доступность|Инфраструктура поселка|Инфраструктура рядом|Архитектура)\s*"
NOISE = r"нет отзывов|ваш отзыв может стать первым|записаться на просмотр|получить консультацию|узнать цену|заказать обратный|скачать презентацию|подписывайтесь|\{|\}|var |button"
# вид источника по домену
MEDIA = (r"rg\.ru|lenta\.ru|kommersant|vedomosti|360\.ru|msk1\.ru|ng\.ru|vc\.ru|rbc\.ru|forbes|tass\.ru|ria\.ru|mk\.ru|kp\.ru|izvestia|"
         r"gazeta\.ru|banki\.ru|interfax|bfm\.ru|the-village|oinfo\.ru|odintsovo|inodintsovo|riamo|mosregtoday|realty\.rbc|cian\.ru/stati|dzen\.ru")
PEOPLE = r"forumhouse|otzovik|irecommend|zoon\.ru|yell\.ru|flamp|domzamkad\.ru|restate\.ru|pikabu|vk\.com|t\.me|otzyvy|otziv|отзыв"
CARDS = {"Пирогово": "kurort_pirogovo/108011223567", "Лапино": "novoye_lapino/145926408068"}  # её подтверждённые карточки
THEMES = {
    "дороги и транспорт": r"дорог[аиуе]\b|дорогам|подъезд|пробк|трасс|транспорт|электричк|автобус|до москвы|до мкад|ехать|метро",
    "газ": r"(?<![а-яё])газ",
    "электричество": r"электричеств|свет[аоу]? (нет|отключ)|отключени\w* свет|мощност|квт|подстанц",
    "вода и канализация": r"(?<![а-яё])вод[аыуо](?![а-яё])|водоснаб|водопровод|скважин|канализ|септик|очистн",
    "интернет и связь": r"интернет|связь|сотов|оптоволок",
    "УК, платежи, взносы": r"управляющ|(?<![а-яё])ук(?![а-яё])|взнос|тариф|платеж|платёж|эксплуатац",
    "охрана и безопасность": r"охран|кпп|шлагбаум|безопасн|видеонаблюд|ограждени|забор|пропуск",
    "инфраструктура": r"магазин|школ|детск\w* сад|аптек|поликлиник|ресторан|кафе|клуб|спорт|фитнес|инфраструктур|пляж",
    "природа и экология": r"(?<![а-яё])лес[аеу]?(?![а-яё])|сосн|(?<![а-яё])рек[аиеу](?![а-яё])|озер|природ|воздух|эколог|тишин",
    "соседи и шум": r"сосед|(?<![а-яё])шум|стройк\w* (рядом|вокруг)",
    "застройщик и стройка": r"застройщик|подрядчик|достро|(?<![а-яё])сдач|обещ",
    "цены и стоимость": r"(?<![а-яё])цен[аыуе](?![а-яё])|стоимост|дорог(о|ие|ая|ое)(?![а-яё])|дешев",
}
NEG = (r"проблем|(?<![а-яё])нет(?![а-яё])|отсутств|плох|ужас|кошмар|отключ|не хватает|разбит|грязн|жалоб|(?<![а-яё])минус|недостат|не работа|"
       r"постоянно|сломан|задерж|не сдан|обман|пробк|шумн|невозможно|не советую|не рекоменд|разочар|хуже|опасн|хамск|по-хамски|по хамски|ждать")
POS = (r"отличн|хорош|красив|(?<![а-яё])чист|удобн|уютн|(?<![а-яё])тих|безопасн|(?<![а-яё])плюс|преимуществ|нрав|прекрасн|рекоменд|доволь|комфорт|"
       r"живописн|ухожен|лучш|неплох|приятн|замечательн|вкусн")


def kind(url: str) -> str:
    if url == "отзыв Яндекс Карт" or re.search(PEOPLE, url, re.I):
        return "люди"
    return "СМИ" if re.search(MEDIA, url, re.I) else "продавцы"


def classify(s: str, rating=None):
    th = [t for t, rx in THEMES.items() if re.search(rx, s, re.I)]
    n, p = len(re.findall(NEG, s, re.I)), len(re.findall(POS, s, re.I))
    if n == p and rating is not None:  # по самой фразе не ясно — смотрим на оценку отзыва
        pol = "плюс" if float(rating) >= 4 else "минус"
    else:
        pol = "минус" if n > p else ("плюс" if p > n else "")
    return th, pol


def collect():
    serp = []
    for f in sorted(glob.glob(str(Path.home() / "Downloads" / "serp_poselki_otzyvy*.json"))):
        serp += json.loads(Path(f).read_text(encoding="utf-8"))
    if "--reparse" in sys.argv:
        return serp
    urls = sorted({x["url"].split("#")[0] for r in serp for x in r["items"] if not re.search(SKIP, x["url"], re.I)})
    res = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [u for u in urls if u not in res]
    print(f"ссылок {len(urls)}, скачать {len(todo)}", flush=True)
    with ThreadPoolExecutor(8) as pool:
        for u, t in zip(todo, pool.map(get, todo)):
            res[u] = t[:80000]
    CACHE.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return serp


def card_reviews(cid: str) -> list:
    full = json.loads((ROOT / "data/raw/yrev_full.json").read_text(encoding="utf-8"))
    for k, v in full.items():
        if cid in k:
            return v
    rev = pd.read_excel(sorted(glob.glob(str(DRIVE / "яндекс_отзывы_*.xlsx")))[-1], sheet_name="отзывы")
    r = rev[rev["карточка"].astype(str).str.contains(cid.split("/")[1])]
    return [{"оценка": x["оценка"], "текст": str(x["отзыв"]), "дата": x["дата"]} for _, x in r.iterrows()]


def main():
    serp = collect()
    pages = json.loads(CACHE.read_text(encoding="utf-8"))
    out = {}
    for name, rx in NAMES.items():
        mine = [r for r in serp if r["n"] == name]
        urls = list(dict.fromkeys(x["url"].split("#")[0] for r in mine for x in r["items"] if not re.search(SKIP, x["url"], re.I)))
        loc = LOC.get(name, RUB)
        used = [u for u in urls if re.search(rx, pages.get(u, ""), re.I)
                and len(re.findall(loc, pages.get(u, ""), re.I)) > len(re.findall(BAD, pages.get(u, ""), re.I))]
        res = {"люди": {"плюс": {}, "минус": {}}, "СМИ": {"плюс": {}, "минус": {}}}
        promises, seen = [], set()
        for u in used:
            k = kind(u)
            for s in re.split(r"(?<=[.!?…])\s+", pages[u]):
                s = re.sub(r"\s+", " ", re.sub(BOILER, " ", s)).strip()
                if not 40 <= len(s) <= 320 or s in seen or not re.search(rx, s, re.I) or re.search(BAD + "|" + NOISE, s, re.I):
                    continue
                if re.search(r"недостатк\w*\W+нет(?![а-яё])|нет (никаких )?недостатк|минусов нет", s, re.I):
                    continue
                seen.add(s)
                th, pol = classify(s)
                if not th:
                    continue
                if k == "продавцы":
                    if pol == "плюс" and len(promises) < 6:
                        promises.append({"фраза": s, "источник": u})
                    continue
                if pol:
                    for t in th[:2]:
                        res[k][pol].setdefault(t, []).append({"фраза": s, "источник": u})
        nrev = 0
        if name in CARDS:
            for r in card_reviews(CARDS[name]):
                txt, rt = str(r.get("текст", "")), r.get("оценка")
                if not txt or rt in ("", None) or pd.isna(rt):
                    continue
                nrev += 1
                for s in re.split(r"(?<=[.!?…])\s+", txt):
                    s = s.strip()
                    if 25 <= len(s) <= 320:
                        th, pol = classify(s, rt)
                        for t in th[:2]:
                            if pol:
                                res["люди"][pol].setdefault(t, []).append({"фраза": s, "источник": "отзыв Яндекс Карт"})
        arts = [{"title": x.get("title") or "", "url": x["url"], "snip": (x.get("snip") or "")[:220]} for r in mine
                for x in r["items"] if x["url"].split("#")[0] in used and kind(x["url"]) == "СМИ"]
        arts = list({a["url"]: a for a in arts}.values())[:10]
        srt = lambda d: dict(sorted(((t, v[:5]) for t, v in d.items()), key=lambda kv: -len(d[kv[0]])))
        cnt = lambda d: {t: len(v) for t, v in sorted(d.items(), key=lambda kv: -len(kv[1]))}
        out[name] = {
            "люди: плюсы": srt(res["люди"]["плюс"]), "люди: минусы": srt(res["люди"]["минус"]),
            "люди: плюсы, сколько": cnt(res["люди"]["плюс"]), "люди: минусы, сколько": cnt(res["люди"]["минус"]),
            "СМИ: плюсы": srt(res["СМИ"]["плюс"]), "СМИ: минусы": srt(res["СМИ"]["минус"]), "статьи": arts,
            "что обещают продавцы": promises, "отзывов с карт": nrev, "страниц про посёлок": len(used),
            "из них люди / СМИ / продавцы": [sum(kind(u) == k for u in used) for k in ("люди", "СМИ", "продавцы")],
        }
        o = out[name]
        print(f"{name:14} | страниц {len(used):2} (люди/СМИ/продавцы {o['из них люди / СМИ / продавцы']}) | отзывов карт {nrev:3} | "
              f"люди +{sum(o['люди: плюсы, сколько'].values())} −{sum(o['люди: минусы, сколько'].values())} | "
              f"СМИ +{sum(map(len, res['СМИ']['плюс'].values()))} −{sum(map(len, res['СМИ']['минус'].values()))} | статей {len(arts)}")
    (ROOT / "data/raw/poselki_otzyvy.json").write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
