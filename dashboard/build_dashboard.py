"""Панель лидогенерации для Chrome: одна HTML-страница из единой базы (Яндекс Карты + 2ГИС + почты с сайтов +
Авито + Telegram) и карты болей (отзывы, размеченные по темам).

python dashboard/build_dashboard.py          # собрать и открыть в Chrome
python dashboard/build_dashboard.py --no-open

Страница локальная (в ней телефоны) — в git не попадает, копия кладётся на Google Диск рядом с выгрузками.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "parsers"))
from yandex_maps_bd import DRIVE, LISTS, PLACES  # noqa: E402

OUT = ROOT / "dashboard" / "панель_лидогенерации.html"
TEMPLATE = ROOT / "dashboard" / "template.html"

# сегменты по виду деятельности (Карты иногда отвечают по-казахски — IP выхода Bright Data)
SEGMENTS = [
    ("Нерелевантное", r"АЖҚС|АЗС|аралас тауар|продукт|аптек|кафе|ресторан"),
    ("Посёлки", r"коттеджн\w* пос|коттедж қалашығы|жилой комплекс|тұрғын үй кешені"),
    ("УК и недвижимость", r"управляющ|недвижимост|жылжымайтын|риелтор"),
    ("Инженерия", r"водо|вод[аы]|фильтр|отоплен|вентиляц|кондицион|климат|электр|умный дом|инженер|скважин|септик|канализ|бассейн|су тазарту|жылыту"),
    ("Дизайн и архитектура", r"дизайн|архитект|проектн|сәулет"),
    ("Мебель и сантехника", r"мебел|сантехн|кухн|жиһаз|свет|двер"),
    ("Строительство и отделка", r"строит|отделоч|ремонт|құрылыс|өңдеу|бань|коттедж және саяжай"),
]
PAINS = [
    ("Сроки", r"срок|затян|задерж|опозда|тянул|дедлайн"),
    ("Качество и брак", r"брак|криво|трещин|протек|переделыв|некачеств|плохо сдела|халтур"),
    ("Деньги и смета", r"предоплат|смет|перерасход|доплат|обман|вернуть деньг|кинул|дороже"),
    ("Связь и отношение", r"не отвеча|не перезвон|трубку|игнор|хам|груб|не берут"),
    ("Гарантия", r"гаранти"),
    ("Инженерия", r"отоплен|вентиляц|котел|котёл|канализ|электрик|скважин|септик|водоснаб|фильтр"),
    ("Посёлок и УК", r"дорог[аиуе]\b|въезд|проезд|охран|шлагбаум|управляющ|\bУК\b|мусор|освещен"),
    ("Поставки и оборудование", r"поставк|доставк|оригинал|подделк|комплектац"),
]
# каналы схемы воронки (docs/schema_voronka.jpg) и где мы сейчас
CHANNELS = [
    ("Яндекс Карты", "собрано", "организации с телефонами, сайтами, мессенджерами"),
    ("Отзывы Яндекс Карт", "собрано", "карта болей клиентов, без имён авторов"),
    ("Поиск Яндекса", "собрано", "10 компаний из списка, которых нет на Картах: сайты, почты"),
    ("Каталоги посёлков", "собрано", "Villagio + ONEHOUSE: 508 посёлков, 418 на Новой Риге, Рублёвке и Ильинском ш."),
    ("2ГИС", "собрано", "158 организаций, которых нет на Яндекс Картах"),
    ("Почты с сайтов", "собрано", "почта у 632 организаций — со всех сайтов базы"),
    ("Авито", "собрано", "200 объявлений подрядчиков"),
    ("Циан", "собрано", "622 дома от 50 млн ₽ на Рублёвке и Новой Риге, 152 продавца"),
    ("Клубы (фитнес, SPA)", "собрано", "Яндекс Карты: клубы, школы, сады, бьюти, рестораны, ветклиники, антиквариат вдоль трёх шоссе"),
    ("Telegram", "собрано", "45 отобрано; участники 21 чата (хэши): жители сидят в «Собаки Новая Рига», «Автолюбители НР и Рублёвка», «Мамы Новой Риги»"),
    ("Дизайн-бюро", "собрано", "274 бюро разобраны по сайтам: загородный премиум 61 (у 44 — наши посёлки, 42 без своей комплектации); дальше — персональный оффер"),
    ("Партнёры: застройщики", "собрано", "Циан: 307 посёлков до 60 км, застройщик у 201, 1 345 объектов в стройке"),
    ("Партнёры: подрядчики", "собрано", "205 компаний, уже работающих в наших посёлках (168 новых в базе)"),
    ("Брокеры", "собрано", "Циан: 63 агентства (сайт 56, почта 40) и 87 риелторов"),
    ("Блогеры", "собрано", "Telegram, YouTube, ВК, Дзен территории — блок «СМИ и блогеры»; крупнейший «Капитал Рублёвки» ~90 тыс."),
    ("УК и консьержи", "собрано", "418 посёлков проверено: УК 20, сайт посёлка 185, телефон или почта у 142"),
    ("Редакции и СМИ", "собрано", "107 находок: 70 сайтов СМИ, почта у 32 — блок «СМИ и блогеры»"),
    ("ВК и FORUMHOUSE", "собрано", "104 группы ВК в 84 посёлках (маленькие), 14 веток FORUMHOUSE"),
    ("Instagram конкурентов", "собрано", "66 аккаунтов бюро и подрядчиков: подписчики, живость; аудиторию не собираем"),
    ("Сводка по посёлкам", "собрано", "521 посёлок в одной строке: застройщик, УК, стройка, Telegram, ВК, подрядчики"),
    ("Тендеры", "пропущено", "ваше решение 01.10"),
    ("Автоворонка кейсов", "план", "единая точка входа"),
    ("Лендинг / бот", "план", "под каждый выпуск"),
    ("Bitrix24", "план", "CRM, UTM источника"),
    ("ИИ-оценка воронки", "план", "стоимость лида по каналам"),
]


TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              ["a","b","v","g","d","e","e","zh","z","i","i","k","l","m","n","o","p","r","s","t","u","f","h","ts","ch","sh","sch","","y","","e","yu","ya"]))


def lat(x: str) -> str:
    """в латиницу и без пробелов/знаков — чтобы «Агаларов естейт» совпал с «Агаларов Эстейт», «Берг» с «Bergh»"""
    return re.sub(r"[^a-z0-9]", "", "".join(TR.get(c, c) for c in x.lower()))


def segment(kind: str) -> str:
    for name, rx in SEGMENTS:
        if re.search(rx, kind or "", re.I):
            return name
    return "Прочее"


def latest(pattern: str) -> Path:
    return max(DRIVE.glob(pattern), key=lambda p: p.stat().st_mtime)


def s(v) -> str:
    return "" if pd.isna(v) else str(v)


BASE_GLOB = "база_lead_engine_*.xlsx"
THEMES = {"Пропадают, не отвечают после оплаты": "Связь и отношение", "Брак, плохое качество": "Качество и брак",
          "Сорваны сроки": "Сроки", "Смета растёт, доплаты": "Деньги и смета", "Гарантия только на бумаге": "Гарантия",
          "Обман, деньги не вернули": "Обман и возврат денег", "Инженерия дома (котёл, вода, вентиляция, электрика)": "Инженерия дома",
          "Поставки и комплектация (не то, подделка, некомплект)": "Поставки и оборудование",
          "Коммуникации посёлка (газ, свет, дороги, вода)": "Коммуникации посёлка", "Отдел продаж обещает то, чего нет": "Обещания отдела продаж",
          "Управляющая компания и платежи": "УК и платежи"}


def main():
    base_x = max(DRIVE.parent.glob(BASE_GLOB), key=lambda p: p.stat().st_mtime)
    rev_x, pain_x = latest("яндекс_отзывы_*.xlsx"), latest("карта_болей_*.xlsx")
    base = pd.read_excel(base_x, sheet_name="организации")
    tg = pd.read_excel(base_x, sheet_name="Telegram-каналы")
    avito = pd.read_excel(base_x, sheet_name="Авито")
    cian = pd.read_excel(base_x, sheet_name="Циан")
    cian_s = pd.read_excel(base_x, sheet_name="Циан-продавцы").fillna("")
    rev = pd.read_excel(rev_x, sheet_name="отзывы")
    compl = pd.read_excel(pain_x, sheet_name="жалобы")

    base["сегмент"] = base["вид деятельности"].map(lambda k: segment(s(k)))
    club = base["тип"] == "клуб / досуг"
    base.loc[club, "сегмент"] = "Клубы и досуг"
    # массовые сети и общепит без премиум-аудитории — в нерелевантное
    chain = base["название"].fillna("").str.contains(r"Тануки|Чайхона|Globus|Глобус|Додо|Вкусно|KFC|Бургер|Шоколадница|Якитория|Fish Point|Ростикс|Теремок|Pro\. Khinkali|Хинкал", case=False)
    base.loc[club & chain, "сегмент"] = "Нерелевантное"
    rev["neg"] = rev["оценка"].between(0, 3)
    neg_share = rev.groupby("карточка")["neg"].mean()
    seg_by_card = dict(zip(base["ссылка"], base["сегмент"]))

    # боли — разметка помощниками (карта_болей_*.xlsx, лист «жалобы»)
    compl["темы"] = compl["темы (по-русски)"].fillna("").str.split("; ")
    ex = compl.explode("темы")
    ex = ex[ex["темы"].isin(THEMES)]
    ex["ntheme"] = ex["темы (по-русски)"].str.count(";") + 1
    ex["len"] = ex["отзыв"].fillna("").str.len()
    pains, used = [], set()
    for theme, grp in ex.groupby("темы"):
        pick = grp[~grp["отзыв"].isin(used) & grp["len"].between(60, 600)].sort_values(["ntheme", "дата"], ascending=[True, False]).head(3)
        used |= set(pick["отзыв"])
        split = grp["тип запроса"].map(lambda k: "посёлки" if k == "посёлок" else "подрядчики").value_counts().to_dict()
        pains.append({"name": THEMES[theme], "n": len(grp), "split": split,
                      "quotes": [{"t": (t[:260] + "…") if len(t) > 260 else t, "o": o, "d": str(d)[:10], "why": w}
                                 for t, o, d, w in pick[["отзыв", "организация", "дата", "суть"]].itertuples(index=False)]})
    pains.sort(key=lambda p: -p["n"])

    # её список: что нашлось в базе
    names = list(dict.fromkeys(l.strip() for l in LISTS.read_text(encoding="utf-8").splitlines() if l.strip()))
    cover = []
    for n in names:
        hit = base[base["наш список"] == n]
        marks = set(hit["новая?"])
        status = ("точно" if any(m.startswith("из нашего списка") for m in marks) else "местность" if "новая, в местности из списка" in marks
                  else "похожие" if marks else "нет")
        cover.append({"name": n, "kind": "посёлок/местность" if n in PLACES else "компания", "n": len(hit), "status": status,
                      "top": ", ".join(hit["название"].astype(str).head(3))})

    first = lambda v: s(v).split(", ")[0]
    rows = [{
        "name": s(r["название"]), "new": s(r["новая?"]), "list": s(r["наш список"]), "seg": r["сегмент"],
        "kind": s(r["вид деятельности"]), "src": s(r["источник"]), "addr": s(r["адрес"]),
        "phone": s(r["телефоны"]) or s(r["телефоны с сайта"]), "mail": s(r["почты"]),
        "site": first(r["сайт"]), "wa": first(r["WhatsApp"]), "tg": first(r["Telegram"]), "vk": first(r["ВК"]),
        "rating": None if pd.isna(r["рейтинг"]) else round(float(r["рейтинг"]), 1),
        "reviews": 0 if pd.isna(r["отзывов"]) else int(r["отзывов"]),
        "neg": None if r["ссылка"] not in neg_share else round(float(neg_share[r["ссылка"]]) * 100),
        "card": s(r["ссылка"]),
    } for _, r in base.iterrows()]

    tg_rows = [{"ch": s(r["канал"]), "title": s(r["название"]), "posts": int(r["постов найдено"]),
                "subs": None if pd.isna(r["подписчиков"]) else int(r["подписчиков"]), "ex": s(r["пример"])[:200]}
               for _, r in tg.head(60).iterrows()]
    tgo = pd.read_csv(ROOT / "data" / "lists" / "tg_poselki_otbor.tsv", sep="	").fillna("")
    tgo_rows = [{"g": r["группа"], "url": r["ссылка"], "title": r["название"], "type": r["тип"], "n": int(r["людей"] or 0),
                 "note": r["заметка"], "desc": r["описание"][:220]} for _, r in tgo.iterrows()]
    ov_p = ROOT / "data" / "lists" / "tg_overlap.tsv"
    ov = pd.read_csv(ov_p, sep="	").fillna("") if ov_p.exists() else pd.DataFrame()
    ov_rows = [{"chat": r["чат"], "title": r["название"], "kind": r["вид"], "size": int(r["участников в чате"] or 0),
                "got": int(r["собрано"]), "n": int(r["жителей посёлков"]), "pct": r["доля, %"]} for _, r in ov.iterrows()]
    members = sorted((ROOT / "data" / "raw").glob("tg_members_*.json"))
    village = {u.replace("https://t.me/", "") for u in tgo[tgo["группа"].str.startswith("1.")]["ссылка"]}
    ov_res = len(set().union(set(), *(set(v["h"]) for f in members for k, v in json.loads(f.read_text(encoding="utf-8")).items() if k in village)))
    bf = sorted((ROOT / "data" / "raw").glob("brokers_*.json"))  # сайты и почты агентств: parsers/brokers_contacts.py
    br = json.loads(bf[-1].read_text(encoding="utf-8")) if bf else {}
    cs_rows = [{"name": s(r["продавец"]), "who": s(r["кто"]), "n": int(r["домов"]), "phone": s(r["телефоны"]), "price": s(r["цены, млн ₽"]),
                "hw": s(r["шоссе"]), "where": s(r["где продаёт"]), "site": (br.get(r["продавец"]) or {}).get("сайт", ""),
                "mail": (br.get(r["продавец"]) or {}).get("почты", "")} for _, r in cian_s.iterrows()]
    ch_rows = [{"place": s(r["посёлок/место"]), "hw": s(r["шоссе"]), "km": s(r["до МКАД, км"]), "price": None if pd.isna(r["цена, млн ₽"]) else float(r["цена, млн ₽"]),
                "what": s(r["что"]), "seller": s(r["продавец"]), "who": s(r["кто продаёт"]), "phone": s(r["телефон"]), "url": s(r["ссылка"])}
               for _, r in cian.iterrows()]
    cian_places = cian["посёлок/место"].fillna("").loc[lambda x: x != ""].value_counts().head(20).to_dict()
    kat = pd.read_csv(ROOT / "data" / "lists" / "poselki_katalog.tsv", sep="	").fillna("")
    kat_rows = [{"name": s(r["посёлок"]), "hw": s(r["шоссе"]), "km": None if r["км до МКАД"] == "" else int(float(r["км до МКАД"])),
                 "ours": s(r["наш список"]), "cian": int(r["домов на Циане"]), "vil": int(r["объектов у Villagio"] or 0),
                 "tg": s(r["Telegram"]), "exp": s(r["эксперты Villagio"]), "ck": s(r.get("контакт: что", "")), "cs": s(r.get("контакт: сайт", "")), "cp": s(r.get("контакт: телефоны", "")), "cm": s(r.get("контакт: почты", "")), "u1": s(r["Villagio"]), "u2": s(r["ONEHOUSE"]), "terr": bool(r["наша территория"])} for _, r in kat.iterrows()]
    cvp = ROOT / "data" / "lists" / "cian_poselki.tsv"  # застройщики посёлков: parsers/cian_villages.py
    cv = pd.read_csv(cvp, sep="	", dtype=str).fillna("") if cvp.exists() else pd.DataFrame()
    num = lambda v: int(float(v)) if v not in ("", None) else 0
    cv_rows = [{"name": r["посёлок"], "hw": r["шоссе"], "km": num(r["км до МКАД"]) or None, "cls": r["класс"], "dev": r["застройщик"],
                "phone": r["телефон застройщика"] or r.get("телефоны с сайта", ""), "mail": r.get("почты с сайта", ""), "site": r["сайт"], "st": r["статус продаж"], "fy": r["сдача"],
                "land": num(r["участков в продаже"]), "cot": num(r["коттеджей в продаже"]), "th": num(r["таунхаусов в продаже"]),
                "bld": num(r["строится объектов"]), "ha": r["площадь, га"], "mat": r["материал"], "fin": r["что пишет застройщик об отделке"],
                "url": r["Циан"]} for _, r in cv.iterrows()]
    sbp = ROOT / "data" / "lists" / "soobshchestva_poselkov.tsv"  # ВК и FORUMHOUSE посёлков: parsers/residents_search.py
    sb = pd.read_csv(sbp, sep="	", dtype=str).fillna("") if sbp.exists() else pd.DataFrame()
    sb_rows = [{"v": r["посёлок"], "kind": r["вид"], "url": r["ссылка"], "title": r["название"], "snip": r["сниппет"][:220],
                "n": int(float(r["участников"])) if r["участников"] else None} for _, r in sb.iterrows()]
    dbp = ROOT / "data" / "lists" / "dizain_byuro.tsv"  # разбор сайтов дизайн-бюро: parsers/design_bureaus.py
    db = pd.read_csv(dbp, sep="	", dtype=str).fillna("") if dbp.exists() else pd.DataFrame()
    db_rows = [{"name": r["бюро"], "site": r["сайт"], "g": r["группа"], "prof": r.get("профиль", ""), "src": r["источник"], "zag": int(r["загородка"] or 0),
                "flat": int(r["квартиры"] or 0), "places": r["наши места"], "prem": int(r["премиум"] or 0),
                "kompl": r["комплектация"] == "True", "nadzor": r["надзор"] == "True", "phone": r["телефоны"], "mail": r["почты"],
                "ig": r["instagram"].split(", ")[0], "tg": r["telegram"].split(", ")[0], "title": r["заголовок сайта"]} for _, r in db.iterrows()]
    pdp = ROOT / "data" / "lists" / "podryadchiki_poselkov.tsv"  # подрядчики в посёлках: parsers/contractors_search.py
    pd_ = pd.read_csv(pdp, sep="	", dtype=str).fillna("") if pdp.exists() else pd.DataFrame()
    pd_rows = [{"site": r["сайт"], "n": int(r["посёлков"]), "where": r["посёлки"], "title": r["заголовок"], "snip": r["сниппет"][:220],
                "url": r["пример страницы"], "phone": r["телефоны"], "mail": r["почты"], "inbase": r["уже в базе"] == "True",
                "kind": r.get("вид", ""), "doubt": r.get("сомнительно", "") == "True"} for _, r in pd_.iterrows()]
    svp = ROOT / "data" / "lists" / "poselki_svod.tsv"  # строка = посёлок: parsers/poselki_svod.py
    sv = pd.read_csv(svp, sep="	", dtype=str).fillna("") if svp.exists() else pd.DataFrame()
    toint = lambda v: int(float(v)) if v not in ("", None) else 0
    sv_rows = [{"name": r["посёлок"], "hw": r["шоссе"], "km": toint(r["км до МКАД"]) or None, "ours": r["наш список"], "cls": r["класс"],
                "dev": r["застройщик"], "dsite": r["сайт застройщика"], "dph": r["телефоны застройщика"], "dml": r["почты застройщика"],
                "st": r["статус продаж"], "fy": r["сдача"], "land": toint(r["участков в продаже"]), "bld": toint(r["строится объектов"]),
                "cian": toint(r["домов на Циане (от 50 млн)"]), "uk": r["УК / сайт посёлка"], "usite": r["сайт посёлка"],
                "uph": r["телефоны посёлка"], "uml": r["почты посёлка"], "tg": r["Telegram"], "vk": toint(r["групп ВК"]),
                "vku": r["ВК"].split(", ")[0], "fh": toint(r["веток FORUMHOUSE"]), "pod": toint(r["подрядчиков работает"]),
                "pods": r["подрядчики"], "u1": r["Villagio"], "u2": r["ONEHOUSE"], "u3": r["Циан"]} for _, r in sv.iterrows()]
    igp = ROOT / "data" / "lists" / "instagram_konkurenty.tsv"  # Instagram конкурентов: parsers/instagram_profiles.py
    ig = pd.read_csv(igp, sep="	", dtype=str).fillna("") if igp.exists() else pd.DataFrame()
    ig_rows = [{"h": r["аккаунт"], "who": r["чей"], "what": r["кто это"], "n": toint(r["подписчиков"]), "posts": toint(r["постов"]),
                "last": r["последний пост"], "bio": r["о себе"][:200]} for _, r in ig.iterrows()]
    adp = ROOT / "data" / "lists" / "ad100_2026.tsv"  # AD100 2026 (США), справочно: собран в Chrome
    ad_rows = pd.read_csv(adp, sep="	").fillna("").values.tolist() if adp.exists() else []
    mf = sorted((ROOT / "data" / "raw").glob("media_*.json"))  # СМИ и блогеры: parsers/media_search.py
    media = json.loads(mf[-1].read_text(encoding="utf-8")) if mf else []
    md_rows = [{"kind": m["вид"], "grp": m["группа"], "title": m["название"], "url": m["ссылка"], "snip": m["сниппет"][:220],
                "n": m.get("людей"), "mail": m.get("почты", ""), "phone": m.get("телефоны", "")} for m in media]
    av_rows = [{"title": s(r.get("title")), "phone": s(r.get("phone")), "url": s(r.get("url")),
                "seller": s(r.get("seller.name") if "seller.name" in avito.columns else r.get("seller"))[:80]}
               for _, r in avito.iterrows()]

    nonempty = lambda c: int((base[c].fillna("").astype(str) != "").sum())
    data = {
        "built": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "sources": [base_x.name, rev_x.name, pain_x.name],
        "kpi": {"orgs": len(base), "new": int(base["новая?"].str.startswith("новая").sum()),
                "phone": int(((base["телефоны"].fillna("") != "") | (base["телефоны с сайта"].fillna("") != "")).sum()),
                "mail": nonempty("почты"), "site": nonempty("сайт"),
                "msg": int(((base["WhatsApp"].fillna("") != "") | (base["Telegram"].fillna("") != "")).sum()),
                "villages": int((base["тип"] == "посёлок").sum()), "reviews": len(rev),
                "neg": int(rev["neg"].sum()), "complaints": len(compl)},
        "segments": base["сегмент"].value_counts().to_dict(),
        "sources_n": base["источник"].value_counts().to_dict(),
        "pains": pains, "cover": cover, "channels": CHANNELS, "rows": rows, "tg": tg_rows, "tgo": tgo_rows, "md": md_rows, "kat": kat_rows, "cv": cv_rows, "sv": sv_rows, "ig": ig_rows, "ad": ad_rows, "pdr": pd_rows, "sb": sb_rows, "db": db_rows, "cs": cs_rows, "ch": ch_rows, "cplaces": cian_places, "chouses": len(cian), "ov": ov_rows, "ovres": ov_res, "avito": av_rows,
        "spend": [("Apify", "≈15.7 из 19 $ (Starter, до 29.10)"), ("Apify: Циан", "≈1.7 $ за 616 домов"), ("Bright Data", "≈0.7 $ (Карты, отзывы, поиск Яндекса)")],
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    drive_copy = DRIVE.parent / OUT.name
    shutil.copy(OUT, drive_copy)
    print(f"панель: {OUT}; копия: {drive_copy}")
    if "--no-open" not in sys.argv:
        subprocess.Popen(["cmd", "/c", "start", "chrome", str(OUT)])


if __name__ == "__main__":
    main()
