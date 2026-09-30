"""Единая база: Яндекс Карты (Bright Data) + 2ГИС + почты с сайтов + Авито + Циан + Telegram-каналы.

python parsers/build_base.py  →  Google Диск: база_lead_engine_<дата>.xlsx
"""
import glob
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DRIVE = Path(r"G:\Мой диск\Мои задачи\Лидогенерация — коттеджи и подрядчики")
OUT = DRIVE / "Выгрузки"
JUNK = r"АЗС|заправ|интернет-провайдер|туропер|турагент|ателье|кафе|ресторан|продукт|автосервис|шиномонтаж|аптек|банк|гостиниц|отел|салон красоты|такси|торгов"


def last_raw(key):
    f = sorted(glob.glob(str(ROOT / "data" / "raw" / f"{key}_*.json")))[-1]
    return json.loads(Path(f).read_text(encoding="utf-8"))


def domain(u):
    try:
        return urlparse(u.strip() if "://" in u else "http://" + u.strip()).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def digits(p):
    d = re.sub(r"\D", "", str(p))
    return "7" + d[1:] if len(d) == 11 and d[0] in "78" else d


ALIASES = {"миллениум": ["millennium", "миллениум"], "виладжио": ["villagio", "виладжио", "вилладжио"],
           "агаларов": ["agalarov", "агаларов"], "papushevo": ["papushevo", "папушево"], "берг хаус": ["бергхаус", "берг хаус", "berghaus"],
           "one house": ["one house", "onehouse", "уан хаус"], "kub": ["kub", "куб хаус"], "render house": ["render house", "рендер хаус"],
           "rotenstein": ["rotenstein", "ротенштейн"], "arhion": ["arhion", "архион"], "aurumv": ["aurum", "аурум"],
           "ge arch": ["ge arch", "гe arch"], "ieo": ["ieo"], "трувиль": ["трувиль", "trouville"]}


def norm(x):
    return re.sub(r"[^a-zа-я0-9 ]", " ", str(x).lower().replace("ё", "е")).strip()


def our_names():
    names = [l.strip() for l in (ROOT / "data" / "lists" / "компании_и_поселки_2026-09-30.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    keys = []
    for n in names:
        nn = norm(n).replace("группа компаний ", "").replace("ателье элитных проектов ", "")
        variants = next((v for k, v in ALIASES.items() if k in nn), [nn])
        keys.append((n, [norm(v) for v in variants]))
    return keys


def in_list(title, keys):
    t = norm(title)
    for n, variants in keys:
        if any(v and re.search(r"(^|\s)" + re.escape(v) + r"($|\s|\d)", t) for v in variants):
            return n
    return ""


def kind(cat, q):
    if "посёлок" in str(cat).lower():
        return "посёлок"
    if q == "компания":
        return "компания"
    return "подрядчик / поставщик"


def main():
    ymaps = pd.read_excel(max(OUT.glob("яндекс_карты_BD_*.xlsx"), key=lambda p: p.stat().st_mtime), sheet_name="организации")
    ymaps = ymaps[~ymaps["вид деятельности"].fillna("").str.contains(JUNK, case=False)]
    rows = []
    for r in ymaps.to_dict("records"):
        rows.append({"название": r["название"], "тип": kind(r["вид деятельности"], r["тип запроса"]),
                     "вид деятельности": r["вид деятельности"], "адрес": r["адрес"],
                     "телефоны": r["телефоны"] or "", "сайт": r["сайт"] or "", "WhatsApp": r["WhatsApp"],
                     "Telegram": r["Telegram"], "ВК": r["ВК"], "другие соцсети": r["другие соцсети"],
                     "рейтинг": r["рейтинг"], "отзывов": r["отзывов"], "источник": "Яндекс Карты", "ссылка": r["карточка"]})
    seen_phones = {digits(p) for x in rows for p in str(x["телефоны"]).split(",") if digits(p)}
    seen_names = {str(x["название"]).lower() for x in rows}
    for g in last_raw("2gis"):
        cat = ", ".join(g.get("rubrics") or [])
        if re.search(JUNK, cat, re.I):
            continue
        phones = [p for p in str(g.get("phoneValue") or g.get("phoneText") or "").replace(";", ",").split(",") if p.strip()]
        if str(g.get("title", "")).lower() in seen_names or any(digits(p) in seen_phones for p in phones):
            continue
        socials = g.get("socials") or []
        soc = lambda t: ", ".join(s.get("url", "") for s in socials if isinstance(s, dict) and t in str(s.get("type", "")).lower())
        rows.append({"название": g.get("title"), "тип": kind(cat, g.get("searchString")) if g.get("searchString") not in
                     ("отделка коттеджей", "ремонт загородного дома", "дизайн интерьера", "инженерные системы",
                      "водоподготовка", "вентиляция", "умный дом", "коттеджный посёлок") else kind(cat, ""),
                     "вид деятельности": cat, "адрес": ", ".join(x for x in (g.get("city"), g.get("address")) if x),
                     "телефоны": ", ".join(phones), "сайт": g.get("website") or "", "WhatsApp": soc("whatsapp"),
                     "Telegram": soc("telegram"), "ВК": soc("vk"), "другие соцсети": "",
                     "рейтинг": g.get("totalScore"), "отзывов": g.get("reviewsCount"), "источник": "2ГИС",
                     "ссылка": g.get("url"), "почта 2ГИС": g.get("email")})
    base = pd.DataFrame(rows)
    # почты и телефоны с сайтов — по домену
    mails = {}
    for c in last_raw("contact_info_scraper__vdrmota"):
        d = c.get("domain") or domain(c.get("originalStartUrl", ""))
        m = mails.setdefault(d, {"почты": set(), "телефоны с сайта": set()})
        m["почты"].update(c.get("emails") or [])
        m["телефоны с сайта"].update(c.get("phones") or [])
    def site_info(s, field):
        vals = set()
        for u in str(s).split(","):
            vals |= mails.get(domain(u), {}).get(field, set()) if u.strip() else set()
        return ", ".join(sorted(vals))
    base["почты"] = [", ".join(x for x in (site_info(s, "почты"), e if isinstance(e, str) else "") if x)
                     for s, e in zip(base["сайт"], base.get("почта 2ГИС", [""] * len(base)))]
    base["телефоны с сайта"] = [site_info(s, "телефоны с сайта") for s in base["сайт"]]
    base = base.drop(columns=["почта 2ГИС"], errors="ignore")
    keys = our_names()
    places = ["Пирогово", "Завидово", "Серебряный бор", "Жуковка", "Барвиха", "Раздоры", "Шульгино", "Подушкино",
              "Ромашково", "Николина Гора", "Усово", "Дарьино", "Лапино", "Солослово", "Трувиль"]
    fits = r"строит|ремонт|дизайн|архитект|инженер|отдел|недвиж|посёл|посел|девелоп|климат|вентиляц|мебел|сантех|проект|дом|котт|благоустр|отоплен|кондицион"
    marks, lists = [], []
    for t, cat, addr in zip(base["название"], base["вид деятельности"].fillna(""), base["адрес"].fillna("")):
        m = in_list(t, keys)
        if m and m not in places and not re.search(fits, cat, re.I):
            marks.append("проверить: совпало только название"); lists.append(m)
        elif m:
            marks.append("из нашего списка"); lists.append(m)
        else:
            p = next((pl for pl in places if norm(pl) in norm(addr)), "")
            marks.append("новая, в местности из списка" if p else "новая"); lists.append(p)
    base["наш список"], base["новая?"] = lists, marks
    cols = ["название", "новая?", "наш список", "тип", "вид деятельности", "телефоны", "почты", "телефоны с сайта", "сайт", "WhatsApp",
            "Telegram", "ВК", "другие соцсети", "адрес", "рейтинг", "отзывов", "источник", "ссылка"]
    base = base[cols].sort_values(["тип", "отзывов"], ascending=[True, False])

    # Telegram: каналы, где упоминаются посёлки
    tg = last_raw("telegram_keyword_search_scraper__lofomachines")
    ch = {}
    for p in tg:
        m = re.search(r"t\.me/s/([^/?]+)", p.get("source_url") or "")
        name = m.group(1) if m else (p.get("source_name") or "?")
        c = ch.setdefault(name, {"канал": f"https://t.me/{name}", "название": p.get("source_name"), "постов найдено": 0,
                                 "подписчиков": (p.get("channel_info") or {}).get("subscribers"), "пример": ""})
        c["постов найдено"] += 1
        if not c["пример"]:
            c["пример"] = (p.get("text") or "")[:300]
    tg_df = pd.DataFrame(ch.values()).sort_values("постов найдено", ascending=False)

    avito = pd.concat([pd.read_excel(f) for f in sorted(OUT.glob("авито_*.xlsx"))], ignore_index=True)
    avito = avito[[c for c in ("title", "phone", "url", "seller.name", "seller", "snippet") if c in avito.columns]]
    cian = pd.read_excel(max(OUT.glob("циан_*.xlsx"), key=lambda p: p.stat().st_mtime))

    out = DRIVE / f"база_lead_engine_{datetime.now():%Y-%m-%d}.xlsx"
    with pd.ExcelWriter(out) as w:
        base.to_excel(w, sheet_name="организации", index=False)
        tg_df.to_excel(w, sheet_name="Telegram-каналы", index=False)
        avito.to_excel(w, sheet_name="Авито", index=False)
        cian.to_excel(w, sheet_name="Циан", index=False)
    print(f"организаций: {len(base)} ({base['источник'].value_counts().to_dict()})")
    print(base["тип"].value_counts().to_dict())
    print(f"с телефоном: {(base['телефоны'] != '').sum()}, с почтой: {(base['почты'] != '').sum()}")
    print(f"Telegram-каналов: {len(tg_df)}, Авито: {len(avito)}, Циан: {len(cian)}")
    print(out)


if __name__ == "__main__":
    main()
