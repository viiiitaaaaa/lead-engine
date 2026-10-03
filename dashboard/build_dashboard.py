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
    ("Тендеры", "собрано", "госзакупки + Fabrikant: 19 открытых на нашей территории (в основном муниципалка); Тендерплан — ключ на новые закупки, пробный до 16.10"),
    ("Автоворонка кейсов", "план", "единая точка входа"),
    ("Лендинг / бот", "план", "под каждый выпуск"),
    ("Bitrix24", "план", "CRM, UTM источника"),
    ("ИИ-оценка воронки", "план", "стоимость лида по каналам"),
]


# что делать с каждым блоком данных: (блок, что делать, куда в схеме воронки, первый шаг); жителям не пишем, оффер бюро — отменён ею 02.10
USE = [
    ("Организации и сегменты (база 1 436)", "Разложить по веткам схемы: партнёры, бюро, брокеры, клубы, УК, СМИ. Это общий список «кому и через какой канал».",
     "CRM (Bitrix24), AI-сегментация базы", "Загрузить базу в Bitrix24 компаниями с полями «сегмент» и «источник», чтобы потом считать цену лида по каналам."),
    ("Боли клиентов из отзывов", "Готовые тексты: 11 болей = 11 ответов «как у нас иначе» (фиксированная смета, технадзор, один ответственный за инженерию, поставки с документами).",
     "Лендинг / бот, Автоворонка кейсов, экспертный SEO-контент", "Сделать структуру лендинга по болям и под каждую боль подобрать один кейс."),
    ("Ваш список — что нашлось, досье, все контакты", "Первые цели: к каждому разговору — юрлицо, выручка, отзывы, клиенты из досье; контакты — кому звонить и писать.",
     "Персональный outreach партнёров → CRM-пайплайн", "Завести карточку на каждый пункт в Bitrix24, досье во вложение, ответственный и дата касания."),
    ("Досье групп: бюро, подрядчики, застройщики", "Квалификация партнёров: кто крупный (выручка), живой (соцсети, свежие посты), в каких посёлках работает, на что жалуются его клиенты.",
     "AI-поиск партнёров → AI-сегментация → партнёрский мини-лендинг", "Отсортировать по выручке и числу посёлков, взять верхние 20 в каждой группе."),
    ("Дизайн-бюро — загородка премиум", "61 бюро делают загородный премиум, у 42 нет своей комплектации — им нужен исполнитель по инженерии и поставкам.",
     "Ветка «Дизайн-бюро»: партнёрский мини-лендинг → тестовый проект → CRM с UTM", "Партнёрская страница для бюро: кейсы, условия, вознаграждение (персональный оффер не делаем — ваше решение)."),
    ("Подрядчики в наших посёлках", "Двойная роль: конкуренты (их отзывы = боли рынка) и партнёры — генподрядчик без своей инженерии отдаёт её нам на субподряд.",
     "AI-поиск партнёров, тестовое сотрудничество", "Отобрать работающих в 5+ посёлках (Олимпстройсервис 47, domrnr 31) и проверить, делают ли они инженерию сами."),
    ("Застройщики посёлков (Циан)", "Кто продаёт участки без подряда (129) — его покупателям нужна стройка и отделка. «Распродан, обжит» — жители переходят к ремонту.",
     "AI-поиск партнёров → мини-лендинг «рекомендация застройщика»", "Начать с посёлков, где идёт стройка (Villagio 314 объектов, Kensington 135, NewRigaLand 100)."),
    ("Посёлки — всё в одной строке", "Карта территории: где идёт стройка, кто застройщик и УК, есть ли Telegram или ВК, какие подрядчики уже там работают.",
     "Гео для рекламы (Яндекс Карты, Директ) + выбор приоритетных посёлков", "Отметить 20 посёлков-приоритетов: элит/бизнес, есть стройка, есть контакт."),
    ("УК посёлков", "Управляющая компания может советовать жителям проверенного подрядчика, ей это закрывает их жалобы.",
     "Ветка «УК и консьержи»: партнёрский PDF → мини-лендинг → UTM", "Сделать PDF «сервис инженерии для жителей» и начать с 20 УК, у которых есть контакт."),
    ("Брокеры и продавцы Циана", "Покупатель дома за 50+ млн почти всегда делает ремонт — брокер может дать нашу ссылку при сделке.",
     "Ветка «Брокеры»: персональный outreach → CRM-пайплайн партнёров с UTM", "Начать с агентств, у которых больше всего домов (Whitewill и др.), у 40 есть почта."),
    ("Telegram — чаты и каналы посёлков", "Каналы — размещать экспертный контент и кейсы через админов. Чаты жителей — только читать вопросы и боли, жителям не пишем.",
     "Ветка «Telegram», контент-мониторинг", "Список 16 местных каналов (≈82 тыс.) → узнать условия размещения у админов."),
    ("Где ещё сидят жители", "Показывает, где реально наша аудитория: «Собаки Новая Рига», «Автолюбители НР и Рублёвка», «Мамы Новой Риги».",
     "Telegram, клубы — места для поста или партнёрства", "Договориться о посте-кейсе в 2–3 таких чатах через админов."),
    ("ВКонтакте и FORUMHOUSE", "ВК-группы посёлков маленькие (61 группа меньше 100 человек) — низкий приоритет. FORUMHOUSE — место для экспертных ответов про инженерию.",
     "Экспертный SEO-контент", "Взять 28 групп ВК, где 1000+ участников, под посты; 14 веток FORUMHOUSE — для экспертных ответов."),
    ("Клубы, SPA, школы (сегмент базы)", "Премиальные места, где бывает аудитория: можно договориться о партнёрстве «клуб рекомендует».",
     "Ветка «Клубы и SPA»: outreach → мини-лендинг → UTM/QR", "Выбрать 10 клубов на Новой Риге и Рублёвке, где сидит премиальная аудитория."),
    ("Редакции, СМИ и блогеры", "PR: экспертные статьи (rr-life.ru, houses.ru, Interior.ru), интеграции у блогеров территории («Капитал Рублёвки» ~90 тыс.).",
     "Ветки «Редакции» и «Блогеры»: AI PR-outreach → публикация → лендинг", "Предложить 2–3 редакциям тему статьи по самой частой боли (сроки, смета)."),
    ("Instagram конкурентов", "Что заходит у конкурентов: форматы, рилсы, частота постов. Отсюда же — кандидаты на коллаборации.",
     "Ветка «Instagram»: контент-план, коллаборации", "Выписать 10 самых живых аккаунтов и их лучшие форматы."),
    ("Авито (200 объявлений)", "Цены и формулировки конкурентов, свободные ниши; основа для нашего профиля на Авито.",
     "Ветка «Авито»: профиль и объявления → лендинг/бот", "Составить 3 объявления по болям (инженерия, отделка, комплектация)."),
    ("Тендеры", "Госзакупки — в основном муниципальный ремонт, не наш клиент. Коммерческие закупки — мониторинг в Тендерплане.",
     "Ветка «AI-мониторинг тендеров»", "≈15.10 проверить ключ в Тендерплане (пробный период до 16.10)."),
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

    # полные отзывы Яндекс Карт (сверх 50) для карточек, собранных в Chrome: parsers/yrev_import.py → подменяют первые 50
    yf = ROOT / "data" / "raw" / "yrev_full.json"
    if yf.exists():
        full = json.loads(yf.read_text(encoding="utf-8"))
        names = dict(zip(base["ссылка"], base["название"]))
        add = pd.DataFrame([{"организация": names.get(c, ""), "оценка": pd.to_numeric(r.get("оценка"), errors="coerce"), "дата": r.get("дата", ""),
                             "отзыв": r.get("текст", ""), "ответ компании": r.get("ответ", ""), "карточка": c} for c, rs in full.items() for r in rs])
        if len(add):
            rev = pd.concat([rev[~rev["карточка"].isin(full)], add], ignore_index=True)
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
    vkp = ROOT / "data" / "raw" / "vk_members.json"  # участники групп ВК: собраны в Chrome из её вкладки vk.com (members_count)
    vkm = json.loads(vkp.read_text(encoding="utf-8")) if vkp.exists() else {}
    vkn = lambda u: (vkm.get((re.search(r"vk\.(?:com|ru)/([A-Za-z0-9_.]+)", u) or [None, ""])[1]) or {}).get("members")
    sbp = ROOT / "data" / "lists" / "soobshchestva_poselkov.tsv"  # ВК и FORUMHOUSE посёлков: parsers/residents_search.py
    sb = pd.read_csv(sbp, sep="	", dtype=str).fillna("") if sbp.exists() else pd.DataFrame()
    sb_rows = [{"v": r["посёлок"], "kind": r["вид"], "url": r["ссылка"], "title": r["название"], "snip": r["сниппет"][:220],
                "n": vkn(r["ссылка"]) or (int(float(r["участников"])) if r["участников"] else None)} for _, r in sb.iterrows()]
    dbp = ROOT / "data" / "lists" / "dizain_byuro.tsv"  # разбор сайтов дизайн-бюро: parsers/design_bureaus.py
    db = pd.read_csv(dbp, sep="	", dtype=str).fillna("") if dbp.exists() else pd.DataFrame()
    db_rows = [{"name": r["бюро"], "site": r["сайт"], "g": r["группа"], "prof": r.get("профиль", ""), "ad": r.get("AD List", "") == "True", "src": r["источник"], "zag": int(r["загородка"] or 0),
                "flat": int(r["квартиры"] or 0), "places": r["наши места"], "prem": int(r["премиум"] or 0),
                "kompl": r["комплектация"] == "True", "nadzor": r["надзор"] == "True", "phone": r["телефоны"], "mail": r["почты"],
                "ig": r["instagram"].split(", ")[0], "tg": r["telegram"].split(", ")[0], "title": r["заголовок сайта"]} for _, r in db.iterrows()]
    pdp = ROOT / "data" / "lists" / "podryadchiki_poselkov.tsv"  # подрядчики в посёлках: parsers/contractors_search.py
    pd_ = pd.read_csv(pdp, sep="	", dtype=str).fillna("") if pdp.exists() else pd.DataFrame()
    pd_rows = [{"site": r["сайт"], "n": int(r["посёлков"]), "where": r["посёлки"], "title": r["заголовок"], "snip": r["сниппет"][:220],
                "url": r["пример страницы"], "phone": r["телефоны"], "mail": r["почты"], "inbase": r["уже в базе"] == "True",
                "kind": r.get("вид", ""), "doubt": r.get("сомнительно", "") == "True",
                "obj": int(float(r.get("посёлков с объектом") or 0))} for _, r in pd_.iterrows()]
    skp = ROOT / "data" / "lists" / "spisok_kontakty.tsv"  # все контакты по её списку: parsers/list_contacts.py
    sk = pd.read_csv(skp, sep="	", dtype=str).fillna("") if skp.exists() else pd.DataFrame()
    sk_rows = []
    for name, g in (sk.groupby("пункт", sort=False) if len(sk) else []):
        cont = lambda k: [{"v": r["значение"], "br": r["брокер?"] == "True", "src": r["откуда"]} for _, r in g[g["контакт"] == k].iterrows()]
        sk_rows.append({"name": name, "vid": g["вид пункта"].iloc[0], "vil": g["посёлки"].iloc[0], "ph": cont("телефон"), "ml": cont("почта")})
    # досье: её список + группы (parsers/list_dossier.py --group premium|contractors|developers), пока идёт сбор — _partial
    dos, gis = [], {}
    for grp, title in (("", "ваш список"), ("premium", "дизайн-бюро премиум"), ("contractors", "подрядчики"), ("developers", "застройщики")):
        sfx = "_" + grp if grp else ""
        dsp = ROOT / "data" / "raw" / f"dossier{sfx}.json"
        dsp = dsp if dsp.exists() else ROOT / "data" / "raw" / f"dossier{sfx}_partial.json"
        dos += [(title, name, d) for name, d in (json.loads(dsp.read_text(encoding="utf-8")) if dsp.exists() else {}).items()]
        gsp = ROOT / "data" / "raw" / f"gis_reviews{sfx}.json"  # все отзывы 2ГИС: parsers/gis_reviews.py
        gis[title] = json.loads(gsp.read_text(encoding="utf-8")) if gsp.exists() else {}
    ds_rows = []
    for grp, name, d in dos:
        gv = gis[grp].get(name) or {"карточки": [], "отзывы": []}
        grev = gv["отзывы"]
        gneg = [x for x in grev if (x.get("оценка") or 5) <= 3]
        g = base[(base["наш список"] == name) & ~base["новая?"].fillna("").str.startswith("отсеяно")]
        if d["вид"] == "посёлок":  # у посёлка — только сам посёлок/УК, не все организации местности
            g = g[(g["тип"] == "посёлок") | g["вид деятельности"].fillna("").str.contains(r"коттеджн|посёл|посел|управляющ", case=False, regex=True)]
        r = rev[rev["карточка"].isin(set(g["ссылка"]))]
        c = compl[compl["организация"].isin(set(g["название"]))]
        th = pd.Series([t for x in c["темы (по-русски)"] for t in str(x).split("; ") if t]).value_counts().head(4)
        ds_rows.append({"name": name, "grp": grp, "vid": d["вид"], "vil": d.get("посёлки", ""), "legal": d.get("юрлицо") or {}, "cand": d.get("юрлицо-кандидат") or {},
                        "ln": d.get("юрлицо: как найдено", ""), "twins": len(d.get("тёзки ЕГРЮЛ") or []),
                        "sites": d.get("сайты") or [], "rev": d.get("отзывы") or [], "art": d.get("статьи") or [],
                        "q": d.get("вопросы") or [], "cl": d.get("клиенты") or [], "money": d.get("выручка кратко", ""),
                        "staff": d.get("сотрудников", ""), "vleg": d.get("юрлица посёлка") or [], "rtx": (d.get("отзывы: тексты") or [])[:40],
                        "aud": d.get("соцсети: аудитория") or [],
                        "gis": {"cards": gv["карточки"], "n": len(grev), "neg": len(gneg),
                                "items": sorted(grev, key=lambda x: (x.get("оценка") or 5, x.get("дата") or ""))[:40]}, "ym": {"n": len(r), "neg": int(r["neg"].sum()) if len(r) else 0,
                        "rating": None if g["рейтинг"].dropna().empty else float(pd.to_numeric(g["рейтинг"], errors="coerce").max()),
                        "themes": [f"{k} ({v})" for k, v in th.items()],
                        "quotes": [s[:220] for s in c.sort_values("дата", ascending=False)["суть"].head(3)]}})
    svp = ROOT / "data" / "lists" / "poselki_svod.tsv"  # строка = посёлок: parsers/poselki_svod.py
    sv = pd.read_csv(svp, sep="	", dtype=str).fillna("") if svp.exists() else pd.DataFrame()
    toint = lambda v: int(float(v)) if v not in ("", None) else 0
    sv_rows = [{"name": r["посёлок"], "hw": r["шоссе"], "km": toint(r["км до МКАД"]) or None, "ours": r["наш список"], "cls": r["класс"],
                "dev": r["застройщик"], "dsite": r["сайт застройщика"], "dph": r["телефоны застройщика"], "dml": r["почты застройщика"],
                "st": r["статус продаж"], "fy": r["сдача"], "land": toint(r["участков в продаже"]), "bld": toint(r["строится объектов"]),
                "cian": toint(r["домов на Циане (от 50 млн)"]), "uk": r["УК / сайт посёлка"], "usite": r["сайт посёлка"],
                "uph": r["телефоны посёлка"], "uml": r["почты посёлка"], "tg": r["Telegram"], "vk": toint(r["групп ВК"]),
                "vku": r["ВК"].split(", ")[0], "vkn": sum(vkn(u) or 0 for u in r["ВК"].split(", ") if u) or None, "fh": toint(r["веток FORUMHOUSE"]), "pod": toint(r["подрядчиков работает"]),
                "pods": r["подрядчики"], "oh": r.get("раздел ONEHOUSE", ""), "u1": r["Villagio"], "u2": r["ONEHOUSE"], "u3": r["Циан"]} for _, r in sv.iterrows()]
    igp = ROOT / "data" / "lists" / "instagram_konkurenty.tsv"  # Instagram конкурентов: parsers/instagram_profiles.py
    ig = pd.read_csv(igp, sep="	", dtype=str).fillna("") if igp.exists() else pd.DataFrame()
    ig_rows = [{"h": r["аккаунт"], "who": r["чей"], "what": r["кто это"], "n": toint(r["подписчиков"]), "posts": toint(r["постов"]),
                "last": r["последний пост"], "bio": r["о себе"][:200]} for _, r in ig.iterrows()]
    adp = ROOT / "data" / "lists" / "ad100_2026.tsv"  # AD100 2026 (США), справочно: собран в Chrome
    ad_rows = pd.read_csv(adp, sep="	").fillna("").values.tolist() if adp.exists() else []
    tdp = ROOT / "data" / "lists" / "tendery.tsv"  # тендеры: parsers/tenders_zakupki.py (+ коммерческие площадки)
    td = pd.read_csv(tdp, sep="	", dtype=str).fillna("") if tdp.exists() else pd.DataFrame()
    td_rows = [{"num": r["номер"], "src": r.get("площадка", "") or "ЕИС (госзакупки)", "law": r["закон"], "how": r["способ"], "st": r["этап"],
                "obj": r["объект"][:300], "cust": r["заказчик"][:150], "price": float(r["цена, ₽"]) if r["цена, ₽"] else None,
                "end": r["окончание подачи"], "kind": r["вид работ"], "url": r["ссылка"]} for _, r in td.iterrows()]
    mf = sorted((ROOT / "data" / "raw").glob("media_*.json"))  # СМИ и блогеры: parsers/media_search.py
    media = json.loads(mf[-1].read_text(encoding="utf-8")) if mf else []
    md_rows = [{"kind": m["вид"], "grp": m["группа"], "title": m["название"], "url": m["ссылка"], "snip": m["сниппет"][:220],
                "n": m.get("людей"), "mail": m.get("почты", ""), "phone": m.get("телефоны", "")} for m in media]
    av_rows = [{"title": s(r.get("title")), "phone": s(r.get("phone")), "url": s(r.get("url")),
                "seller": s(r.get("seller.name") if "seller.name" in avito.columns else r.get("seller"))[:80]}
               for _, r in avito.iterrows()]

    lfp = ROOT / "docs" / "лендинг_основа.md"  # основа лендинга: запрос → боль → решение (пишется вручную по отзывам)
    try:
        import markdown
        landing = markdown.markdown(lfp.read_text(encoding="utf-8"), extensions=["tables"]) if lfp.exists() else ""
    except ImportError:
        landing = ""
    pdp = ROOT / "data" / "raw" / "poselki_dossier.json"  # досье посёлков из её списка (её ссылки 03.10): parsers/poselki_dossier.py
    vd_rows = list(json.loads(pdp.read_text(encoding="utf-8")).values()) if pdp.exists() else []
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
        "pains": pains, "cover": cover, "channels": CHANNELS, "use": USE, "landing": landing, "rows": rows, "tg": tg_rows, "tgo": tgo_rows, "md": md_rows, "kat": kat_rows, "cv": cv_rows, "sv": sv_rows, "sk": sk_rows, "ds": ds_rows, "vd": vd_rows, "td": td_rows, "ig": ig_rows, "ad": ad_rows, "pdr": pd_rows, "sb": sb_rows, "db": db_rows, "cs": cs_rows, "ch": ch_rows, "cplaces": cian_places, "chouses": len(cian), "ov": ov_rows, "ovres": ov_res, "avito": av_rows,
        "spend": [("Apify", "≈18.5 из 19 $ (Starter, до 29.10)"), ("Apify: Циан", "≈1.7 $ за 616 домов"), ("Apify: Instagram", "0.16 $ за 70 профилей"),
                  ("Apify: Telegram 02.10", "2.18 $ за 3 чата (переплата: потолок был на каждый чат)"),
                  ("Bright Data", "≈3 $ (Карты, отзывы, поиск Яндекса: УК, подрядчики, ВК, бюро, застройщики)")],
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
