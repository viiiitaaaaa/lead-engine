"""Раздел «10. Партнёры, конкуренты и клиенты-коммерция» основы лендинга (её «собери всё», 04.10; «не нашла в обновлённом документе»).
Источники: data/raw/dossier_montazhniki.json (montazhniki_elita.py), data/raw/dossier_konkurenty.json, data/lists/kommerciya_klienty.tsv.
Вставляется между метками <!-- r10 --> … <!-- /r10 --> в конец документа.

python parsers/razdel10.py
"""
import json
import re

import pandas as pd

from yandex_maps_bd import ROOT

MD = ROOT / "docs/лендинг_основа.md"
JUNK = r"ya\.ru/alice|alice_deeplink|Быстрый ответ"


def links(items: list, n: int = 2) -> str:
    items = [i for i in items or [] if not re.search(JUNK, i["ссылка"] + i["заголовок"])]
    host = lambda u: re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
    return ", ".join(f"[{host(i['ссылка'])}]({i['ссылка']})" for i in items[:n])


def site_of(v: dict) -> dict:
    return next((x for x in v["сайты"] if x.get("ответ") == "ок"), v["сайты"][0] if v["сайты"] else {})


def main():
    m = json.loads((ROOT / "data/raw/dossier_montazhniki.json").read_text(encoding="utf-8"))
    gis = json.loads((ROOT / "data/raw/gis_reviews_montazhniki.json").read_text(encoding="utf-8"))
    k = json.loads((ROOT / "data/raw/dossier_konkurenty.json").read_text(encoding="utf-8"))
    kc = pd.read_csv(ROOT / "data/lists/kommerciya_klienty.tsv", sep="\t", dtype=str).fillna("")
    parts = {n: v for n, v in m.items() if v.get("партнёр?")}
    md = ("## 10. Партнёры, конкуренты и клиенты-коммерция\n"
          "Полные списки с телефонами, почтами и отзывами — в панели (блоки «Досье» → группы «монтажники — партнёры» и «конкуренты», «Коммерция — клиенты»).\n\n")

    md += (f"### Партнёры — монтажные и климатические компании «под ключ» ({len(parts)})\n"
           f"Сами оборудование не производят, ставят чужое — мы можем стать их постоянным поставщиком. Отобраны из {len(m)} компаний Москвы и области (2ГИС) по их сайтам; "
           "производители, магазины, септики и газ исключены. «Элитные дома» — на сайте наши посёлки, коттеджи, бассейны, премиальные объекты; "
           "«коммерция» — вентиляция и климат для бизнеса и квартир.\n\n")
    for who in ("элитные дома", "коммерция и квартиры"):
        rows = sorted([(n, v) for n, v in parts.items() if v.get("кому партнёр") == who],
                      key=lambda kv: (kv[1]["профиль"], -len(gis.get(kv[0], {}).get("отзывы", []))))
        md += (f"**{'Работают на элитных домах' if who == 'элитные дома' else 'Вентиляция и климат для коммерции'} — {len(rows)}**\n\n"
               "| Компания | Профиль | Чем подтверждено | Юрлицо | Отзывов 2ГИС | Где ещё о них пишут |\n|---|---|---|---|---|---|\n")
        for n, v in rows:
            s = site_of(v)
            g = gis.get(n, {}).get("отзывы", [])
            avg = sum(x["оценка"] for x in g if x.get("оценка")) / max(1, sum(1 for x in g if x.get("оценка")))
            proof = "; ".join(x for x in (", ".join((s.get("упоминает наши места") or [])[:3]), ", ".join((s.get("КП в тексте") or [])[:2])) if x)
            L = v.get("юрлицо") or {}
            legal = f"ИНН {L['ИНН']}, с {L.get('регистрация', '')[-4:]}" if L.get("ИНН") else ""
            site = s.get("сайт", "")
            name = f"[{n}]({site})" if site else n
            md += (f"| {name} | {v['профиль']} | {proof or ('премиальных слов на сайте: ' + str(s.get('премиум-слова', 0)))} | {legal} | "
                   f"{len(g)}{f' · {avg:.1f}'.replace('.', ',') if g else ''} | {links(v.get('отзывы'), 2)}{'; форум: ' + links(v.get('вопросы'), 1) if links(v.get('вопросы'), 1) else ''} |\n")
        md += "\n"

    md += (f"### Конкуренты ({len(k)})\n"
           "Производители вентиляции, осушения бассейнов и водоподготовки и крупные дилеры — те, у кого монтажник покупает вместо нас.\n\n"
           "| Конкурент | Кто это | Юрлицо | Отзывы | Статьи и интервью | Объекты и клиенты |\n|---|---|---|---|---|---|\n")
    for n, v in k.items():
        s = site_of(v)
        L = v.get("юрлицо") or {}
        legal = f"с {L.get('регистрация', '')[-4:]}" if L.get("ИНН") else "—"
        site = s.get("сайт", "")
        md += (f"| {f'[{n}]({site})' if site else n} | {v.get('рубрики', '')} | {legal} | {links(v.get('отзывы'))} | "
               f"{links(v.get('статьи'))} | {links(v.get('клиенты'))} |\n")

    t = kc
    md += (f"\n### Клиенты-коммерция на территории ({len(t)})\n"
           "2ГИС, Одинцовский, Красногорский и Истринский округа. Сети закупают централизованно — с ними разговор через головной офис; одиночные объекты — напрямую и через монтажников.\n\n"
           "| Сегмент | Что ему нужно | Всего | Одиночных | Сетей | Одинцовский | Красногорский | Истринский |\n|---|---|---|---|---|---|---|---|\n")
    need = {"Общепит": "вытяжки горячих цехов, приток в залы", "ТЦ и магазины": "воздухообмен больших площадей",
            "Медицина": "фильтрация, стерильность (клиники, лаборатории, аптеки)", "Фитнес и спорт": "приток при нагрузках, осушение бассейнов"}
    for cat, g in t.groupby("категория"):
        o = g["округ"]
        md += (f"| {cat} | {need.get(cat, '')} | {len(g)} | {(g['сеть'] != 'True').sum()} | {(g['сеть'] == 'True').sum()} | "
               f"{o.str.startswith('Одинцов').sum()} | {o.str.startswith('Красногорск').sum()} | {o.str.startswith('Истра').sum()} |\n")
    md += ("| Серверные и ЦОД | вентиляция и охлаждение оборудования | единицы | | | дата-центр Фонда «Сколково», ЦОД Сбера в Сколково | | |\n\n"
           f"Контакты: телефон есть у {(t['телефоны'] != '').sum()}, сайт — у {(t['сайт'] != '').sum()}, почта — у {(t['почты'] != '').sum()}.\n")
    top = t[(t["сеть"] != "True")].copy()
    top["n"] = pd.to_numeric(top["отзывов"], errors="coerce").fillna(0)
    md += "\nКрупнейшие одиночные объекты по числу отзывов (больше посетителей — выше нагрузка на вентиляцию):\n\n| Объект | Сегмент | Адрес | Отзывов |\n|---|---|---|---|\n"
    for _, r in top.sort_values("n", ascending=False).groupby("категория").head(5).sort_values(["категория", "n"], ascending=[True, False]).iterrows():
        md += f"| {r['название']} | {r['категория']} | {r['адрес']} | {int(r['n'])} |\n"

    s = MD.read_text(encoding="utf-8")
    s = re.sub(r"\n*<!-- r10 -->.*?<!-- /r10 -->\n?", "\n", s, flags=re.S).rstrip() + f"\n\n<!-- r10 -->\n{md}<!-- /r10 -->\n"
    MD.write_text(s, encoding="utf-8")
    print("раздел 10:", len(parts), "партнёров,", len(k), "конкурентов,", len(t), "объектов")


if __name__ == "__main__":
    main()
