"""Тендеры (госзакупки, 44-ФЗ и 223-ФЗ) на нашей территории по нашим видам работ — zakupki.gov.ru, бесплатно.
Ветка схемы «AI-мониторинг тендеров»: благоустройство, ландшафт, строительство, ремонт, отделка, инженерия, бассейн/SPA, мебель.

python parsers/tenders_zakupki.py          # только этап «Подача заявок» (по чему можно участвовать сейчас)
python parsers/tenders_zakupki.py --done   # + завершённые за последние ~3 мес. (кто выигрывает — конкуренты/партнёры)
Итог: data/raw/tenders_<время>.json + data/lists/tendery.tsv; показывает панель.
Фильтр региона в адресе ЕИС не работает (код региона подгружается формой) — ищем по заказчикам/адресам территории,
а территорию и вид работ проверяем по тексту сами.
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd

from yandex_maps_bd import ROOT

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36", "Accept-Language": "ru"}
BASE = "https://zakupki.gov.ru"
PLACES = ["Одинцовского городского округа", "Одинцовский", "Звенигород", "Кубинка", "Голицыно", "Власиха", "Барвиха", "Жуковка",
          "Николина Гора", "Рублево", "Успенское", "Горки-10", "Архангельское Красногорск", "Красногорск", "Нахабино", "Истра",
          "Истринский", "Дедовск", "Павловская Слобода", "Новорижское"]
TERR = (r"одинцов|звенигород|кубинк|голицын|власих|барвих|жуковк|николин\w* гор|рубл[её]в|горки-?10|архангельское|"
        r"красногорск|нахабин|(?<![а-яё])истр[аыеуо]?(?![а-яё])|истринск|дедовск|павловск\w* слобод|новориж|лесной городок|заречье")
KINDS = {
    "благоустройство и ландшафт": r"благоустр|озелен|ландшафт|газон|посадк\w* деревьев|детск\w* (?:игров\w* )?площадк|малых архитектурн|сквер|парк",
    "строительство и реконструкция": r"строительств|реконструкц|возведени|капитальн\w* строит",
    "ремонт и отделка": r"капитальн\w* ремонт|текущ\w* ремонт|ремонт\w* (?:помещ|здан|кабинет|фасад|кровл)|отделочн|ремонтн\w* работ",
    "инженерия": r"инженерн|вентиляц|кондиционир|отоплен|водоснабж|водоотвед|канализ|электромонтаж|слаботочн|котельн|насосн|тепловой пункт",
    "бассейн / SPA / спорт": r"бассейн|спа\b|сауна|фитнес|спортивн\w* (?:зал|площадк|комплекс)",
    "мебель и оснащение": r"мебел|(?<!до)оснащени|оборудовани\w* (?:для|кухн)|сантехни|светильник",
    "проектирование": r"проектн\w* работ|проектировани|проектно-сметн|изыскани",
}
NOT_OURS = (r"медицинск\w* издел|лекарств|продукт\w* питани|горюче|бензин|страхован|охран\w* (?:объект|услуг)|вывоз\w* (?:мусор|отход)|"
            r"транспортн\w* услуг|питани[ея] учащ|"
            r"\bЛЭП\b|\bВЛИ\b|\bВЛЗ\b|\bВЛ-|\bКЛ-|\bКТП|\bМТП|\bТП-|\bПС[ -]|\bкВ\b|трансформатор|"  # электросети — не наше
            r"автодорог|проезж\w* част|скоростн\w* полос|дорожн\w* покрыт|обустройств\w* дорог|"  # дороги (тротуары и дорожки — оставляем)
            r"освещени|сол[иь] |реагент|топлив|ледов\w* кат[оа]?к|парковочн\w* систем|автотранспорт|коммунальн\w* услуг|холодн\w* водоснабж|"
            r"водоснабжени\w* и водоотведени|охран\w* |кладбищ|брянск|ВЗУ|водозабор|обезжелез|газопровод|теплосет|котельн\w* тепловой мощн|"
            r"кислородн|экспозици")


def get(url: str) -> str:
    for n in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60).read().decode("utf-8", "ignore")
        except Exception:
            time.sleep(5 * (n + 1))
    return ""


def clean(s: str) -> str:
    s = re.sub(r"</?(?:span|b|em|mark)[^>]*>", "", s)  # подсветка совпадений рвёт слова («Одинцовск ая», «АДМИН ИСТР АЦИЯ») — склеиваем
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def field(b: str, title: str) -> str:
    m = re.search(re.escape(title) + r".*?(?:value|href)[^>]*>(.*?)</(?:div|a)>", b, re.S)
    return clean(m.group(1)) if m else ""


def parse(t: str) -> list:
    out = []
    for b in re.split(r'class="search-registry-entry-block', t)[1:]:
        num = re.search(r"regNumber=(\d+)", b)
        if not num:
            continue
        x = clean(b)  # чистый текст карточки: поля берём между подписями
        link = re.search(r'href="(/epz/order/notice/[^"]*?/view/common-info\.html\?regNumber=\d+)"', b)
        price = re.search(r"Начальная цена\s*([\d\s ]+,\d{2})", x)
        dates = dict(re.findall(r"(Размещено|Обновлено|Окончание подачи заявок)\s+(\d{2}\.\d{2}\.\d{4})", x))
        between = lambda a, z: (re.search(a + r"\s+(.*?)\s+(?:" + z + ")", x) or [None, ""])[1].strip()
        out.append({"номер": num.group(1), "закон": "44-ФЗ" if "44-ФЗ" in x[:200] else "223-ФЗ" if "223-ФЗ" in x[:200] else "",
                    "способ": between(r"(?:44|223)-ФЗ", r"Закупка является|№"),
                    "этап": (re.search(r"(Подача заявок|Работа комиссии|Определение поставщика завершено|Закупка отменена|Закупка завершена)", x) or [None, ""])[1],
                    "объект": between("Объект закупки", "Заказчик|Организация, осуществляющая размещение"),
                    "заказчик": between("(?:Заказчик|Организация, осуществляющая размещение)", "Начальная цена|Размещено"),
                    "цена, ₽": float(re.sub(r"[\s ]", "", price.group(1)).replace(",", ".")) if price else None,
                    "размещено": dates.get("Размещено", ""), "окончание подачи": dates.get("Окончание подачи заявок", ""),
                    "ссылка": BASE + link.group(1) if link else f"{BASE}/epz/order/notice/printForm/view.html?regNumber={num.group(1)}"})
    return out


def search(q: str, stage: str) -> list:
    rows = []
    for p in range(1, 21):  # до 1000 записей на запрос
        u = (f"{BASE}/epz/order/extendedsearch/results.html?searchString={urllib.parse.quote(q)}&morphology=on&{stage}"
             f"&fz44=on&fz223=on&recordsPerPage=_50&pageNumber={p}&sortBy=UPDATE_DATE&sortDirection=false")
        got = parse(get(u))
        rows += got
        if len(got) < 50:
            break
    return rows


B2B_WORDS = ["коттеджный поселок", "Одинцово", "Одинцовский", "Истра", "Красногорск", "Звенигород", "Новая Рига", "Новорижское",
             "Рублево", "Барвиха", "Жуковка", "Николина Гора", "Нахабино", "Ильинское шоссе", "Павловская Слобода",
             "благоустройство Подмосковье", "ландшафт Подмосковье", "отделка коттедж", "загородный дом", "бассейн Подмосковье"]


def b2b() -> list:
    """коммерческие тендеры B2B-Center (застройщики, УК, ТСН): без входа видна 1 страница по слову; территорию проверяем
    по тексту страницы закупки"""
    c = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
    found = {}
    for w in B2B_WORDS:
        t = get(f"https://www.b2b-center.ru/market/?f_keyword={urllib.parse.quote(w)}&searching=1")
        for m in re.finditer(r'href="(/app/market-next/[^"#]*?tender-(\d+)/)[^"]*"[^>]*>(.*?)</a>\s*</td>\s*<td>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>', t, re.S):
            title = c(m.group(3))
            found.setdefault(m.group(2), {"номер": m.group(2), "площадка": "B2B-Center", "закон": "коммерческий",
                                          "способ": title.split(" № ")[0], "этап": "Подача заявок",
                                          "объект": re.sub(r"^.*?№ \d+\s*", "", title), "заказчик": c(m.group(4)),
                                          "цена, ₽": None, "размещено": c(m.group(5))[:10], "окончание подачи": c(m.group(6))[:10],
                                          "ссылка": "https://www.b2b-center.ru" + m.group(1), "запросы": []})["запросы"].append(w)
        print(f"B2B «{w}»: всего {len(found)}", flush=True)

    def detail(r):  # текст страницы закупки — для проверки территории и цены
        x = c(get(r["ссылка"]))
        p = re.search(r"(?:Начальная цена|Стоимость|Цена)[^0-9]{0,40}([\d\s ]{4,}(?:[.,]\d{2})?)\s*(?:руб|₽)", x)
        r["цена, ₽"] = float(re.sub(r"[\s ]", "", p.group(1)).replace(",", ".")) if p else None
        r["текст"] = x[:20000]
        return r
    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(detail, found.values()))
    return rows


def kind(text: str) -> str:
    return ", ".join(k for k, p in KINDS.items() if re.search(p, text, re.I))


def main():
    stages = ["af=on"] + (["pc=on"] if "--done" in sys.argv else [])
    qs = [(q, s) for q in PLACES for s in stages]
    found = {}
    t0 = time.time()
    with ThreadPoolExecutor(4) as pool:
        for n, ((q, s), rows) in enumerate(zip(qs, pool.map(lambda x: search(*x), qs)), 1):
            for r in rows:
                found.setdefault(r["номер"], {**r, "запросы": []})["запросы"].append(q)
            print(f"запросов {n} из {len(qs)}, закупок {len(found)}, {time.time() - t0:.0f} с", flush=True)
    rows = list(found.values()) + b2b()
    out = ROOT / "data" / "raw" / f"tenders_{datetime.now():%Y-%m-%d_%H-%M}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    table(rows)


def table(rows: list) -> None:
    keep = []
    for r in rows:
        text = r["объект"] + " " + r["заказчик"] + " " + r.get("текст", "")  # у B2B территория — в тексте страницы закупки
        if not re.search(TERR, text, re.I) or re.search(NOT_OURS, r["объект"], re.I):
            continue
        k = kind(r["объект"])
        if k:
            keep.append({**{x: v for x, v in r.items() if x != "текст"}, "площадка": r.get("площадка", "ЕИС"),
                         "вид работ": k, "запросы": ", ".join(r["запросы"][:3])})
    df = pd.DataFrame(keep)
    if df.empty:
        return print("подходящих закупок нет")
    df["_d"] = pd.to_datetime(df["окончание подачи"], format="%d.%m.%Y", errors="coerce")
    # ЕИС годами держит «Подача заявок» у старых закрытых аукционов (срок 2019–2021) — срок прошёл, значит не актуально
    df = df[~((df["этап"] == "Подача заявок") & (df["_d"] < pd.Timestamp.now().normalize()))]
    df = df.sort_values(["этап", "_d"]).drop(columns="_d")
    df.to_csv(ROOT / "data" / "lists" / "tendery.tsv", sep="\t", index=False)
    print(f"всего найдено {len(rows)}, по территории и нашим работам {len(df)}; сумма НМЦ {df['цена, ₽'].sum() / 1e6:.0f} млн ₽")
    print(df["вид работ"].str.split(", ").explode().value_counts().to_dict())
    print(df["этап"].value_counts().to_dict())


if __name__ == "__main__":
    if "--retable" in sys.argv:
        table(json.loads(sorted((ROOT / "data" / "raw").glob("tenders_2*.json"))[-1].read_text(encoding="utf-8")))
    else:
        main()
