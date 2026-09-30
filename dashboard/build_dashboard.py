"""Панель лидогенерации для Chrome: одна HTML-страница из последних выгрузок (Яндекс Карты + отзывы).

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
    ("Каталоги посёлков", "разведка", "villagio-vip.ru — HTML, onehouse.ru — Tilda"),
    ("2ГИС · Авито · Циан", "план", "сборщики Apify подобраны"),
    ("Telegram", "план", "только пересечения аудиторий групп, жителям не пишем"),
    ("Дизайн-бюро", "план", "AI-поиск → анализ → персональный оффер"),
    ("Партнёры", "план", "сегментация базы → мини-лендинг"),
    ("Брокеры", "план", "персональный outreach"),
    ("Блогеры", "план", "интеграционный пакет"),
    ("УК и консьержи", "план", "мини-лендинг + PDF"),
    ("Клубы (фитнес, SPA)", "план", "outreach с полезной темой"),
    ("Редакции и СМИ", "план", "контент-мониторинг → PR"),
    ("YouTube · Instagram", "план", "разборы объектов, Reels"),
    ("Тендеры", "план", "AI-мониторинг объектов и закупок"),
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


def main():
    maps_x, rev_x = latest("яндекс_карты_BD_*.xlsx"), latest("яндекс_отзывы_*.xlsx")
    orgs = pd.read_excel(maps_x, sheet_name="организации")
    byq = pd.read_excel(maps_x, sheet_name="по запросам")
    rev = pd.read_excel(rev_x, sheet_name="отзывы")

    orgs["сегмент"] = orgs["вид деятельности"].map(lambda k: segment(s(k)))
    rev["neg"] = rev["оценка"].between(1, 3)
    neg_share = rev.groupby("карточка")["neg"].mean()

    # боли — только отзывы с оценкой 1–3
    neg = rev[rev["neg"] & rev["отзыв"].notna()].copy()
    neg["seg"] = neg["карточка"].map(dict(zip(orgs["карточка"], orgs["сегмент"])))
    # цитаты: сперва отзывы про одну тему (длинные жалобы подходят ко всем), без повторов между темами
    neg["themes"] = sum(neg["отзыв"].str.contains(rx, case=False, regex=True).astype(int) for _, rx in PAINS)
    pains, used = [], set()
    for name, rx in PAINS:
        hit = neg[neg["отзыв"].str.contains(rx, case=False, regex=True)]
        pick = hit[~hit.index.isin(used)].sort_values(["themes", "дата"], ascending=[True, False]).head(3)
        used |= set(pick.index)
        quotes = [{"t": (t[:260] + "…") if len(t) > 260 else t, "o": o, "d": d}
                  for t, o, d in pick[["отзыв", "организация", "дата"]].itertuples(index=False)]
        pains.append({"name": name, "n": len(hit), "answered": round(hit["ответ компании"].notna().mean() * 100) if len(hit) else 0,
                      "seg": hit["seg"].value_counts().head(3).to_dict(), "quotes": quotes})
    pains.sort(key=lambda p: -p["n"])

    # её список: что нашлось
    names = list(dict.fromkeys(l.strip() for l in LISTS.read_text(encoding="utf-8").splitlines() if l.strip()))
    cover = []
    for n in names:
        q = f"коттеджные посёлки {n}" if n in PLACES else f"{n} Москва"
        got = byq[byq["запрос"] == q]
        keys = {lat(w)[:4] for w in (n.split()[0], n.split()[-1]) if len(lat(w)) >= 3}
        exact = got[got["название"].fillna("").map(lat).map(lambda t: any(k in t for k in keys))]
        status = "нет" if got.empty else ("точно" if len(exact) or n in PLACES else "похожие")
        cover.append({"name": n, "kind": "посёлок" if n in PLACES else "компания", "n": len(got), "status": status,
                      "top": s(got["название"].iloc[0]) if len(got) else ""})

    rows = [{
        "name": s(r["название"]), "seg": r["сегмент"], "kind": s(r["вид деятельности"]), "src": s(r["тип запроса"]),
        "addr": s(r["адрес"]), "phone": s(r["телефоны"]), "site": s(r["сайт"]).split(", ")[0],
        "wa": s(r["WhatsApp"]).split(", ")[0], "tg": s(r["Telegram"]).split(", ")[0], "vk": s(r["ВК"]).split(", ")[0],
        "rating": None if pd.isna(r["рейтинг"]) else float(r["рейтинг"]),
        "reviews": 0 if pd.isna(r["отзывов"]) else int(r["отзывов"]),
        "neg": None if r["карточка"] not in neg_share else round(float(neg_share[r["карточка"]]) * 100),
        "card": s(r["карточка"]),
    } for _, r in orgs.iterrows()]

    has = lambda c: int((orgs[c].fillna("") != "").sum())
    data = {
        "built": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "sources": [maps_x.name, rev_x.name],
        "kpi": {"orgs": len(orgs), "phone": has("телефоны"), "site": has("сайт"),
                "msg": int(((orgs["WhatsApp"].fillna("") != "") | (orgs["Telegram"].fillna("") != "")).sum()),
                "villages": int((orgs["сегмент"] == "Посёлки").sum()), "reviews": len(rev),
                "neg": int(rev["neg"].sum()), "reply": round(rev.loc[rev["neg"], "ответ компании"].notna().mean() * 100)},
        "segments": orgs["сегмент"].value_counts().to_dict(),
        "pains": pains, "cover": cover, "channels": CHANNELS, "rows": rows,
        "spend": [("Apify", "5.86 из 6 $ (бесплатный тариф, месяц)"), ("Bright Data", "≈0.6 $ (≈400 запросов × 1.5 $/1000)")],
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    drive_copy = DRIVE.parent / OUT.name
    shutil.copy(OUT, drive_copy)
    print(f"панель: {OUT}\nкопия: {drive_copy}")
    if "--no-open" not in sys.argv:
        subprocess.Popen(["cmd", "/c", "start", "chrome", str(OUT)])


if __name__ == "__main__":
    main()
