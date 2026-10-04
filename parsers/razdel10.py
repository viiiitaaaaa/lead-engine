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
JUNK = r"ya\.ru/alice|alice_deeplink|Быстрый ответ|tripadvisor|ozon\.by|booking\.com"  # тёзки (глазами 04.10: отель «Аляска», очиститель Fresh Air)


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
    st = lambda v: v.get("ставит чужое", "")
    good = {n: v for n, v in parts.items() if st(v).startswith("ставит чужое")}
    md += (f"**Проверка «ставят чужое»** (по сайтам: марки чужого оборудования и признаки своего производства): "
           f"ставят чужое — {sum(st(v) == 'ставит чужое' for v in parts.values())}, ставят чужое и что-то производят сами — "
           f"{sum(st(v).startswith('ставит чужое и') for v in parts.values())}, производят сами (не партнёры, скорее конкуренты) — "
           f"{sum(st(v).startswith('сам производит') for v in parts.values())}, проверить звонком — {sum(st(v).startswith(('неясно', 'сайт не')) for v in parts.values())}. "
           f"У подходящих ({len(good)}): ИНН — у {sum(bool(v.get('ИНН')) for v in good.values())}, телефон — у {sum(bool(v.get('телефоны')) for v in good.values())}, "
           f"почта — у {sum(bool(v.get('почты')) for v in good.values())}.\n\n")
    mk = lambda v: "; ".join(", ".join(m[:6]) for m in (v.get("марки") or {}).values())
    for who in ("элитные дома", "коммерция и квартиры"):
        rows = sorted([(n, v) for n, v in good.items() if v.get("кому партнёр") == who],
                      key=lambda kv: (kv[1]["профиль"], -len(gis.get(kv[0], {}).get("отзывы", []))))
        md += (f"**{'Работают на элитных домах' if who == 'элитные дома' else 'Вентиляция и климат для коммерции'} — {len(rows)}**\n\n"
               "| Компания | Профиль | Ставит (марки) | ИНН | Телефон | Почта | Наши посёлки на сайте | Отзывов 2ГИС | Где ещё о них пишут |\n|---|---|---|---|---|---|---|---|---|\n")
        for n, v in rows:
            s_ = site_of(v)
            g = gis.get(n, {}).get("отзывы", [])
            avg = sum(x["оценка"] for x in g if x.get("оценка")) / max(1, sum(1 for x in g if x.get("оценка")))
            places = ", ".join((s_.get("упоминает наши места") or [])[:3] + (s_.get("КП в тексте") or [])[:2])
            site = s_.get("сайт", "")
            name = f"[{n}]({site})" if site else n
            note = " (и своё производство — уточнить)" if st(v).startswith("ставит чужое и") else ""
            md += (f"| {name}{note} | {v['профиль']} | {mk(v)} | {v.get('ИНН', '')} | {(v.get('телефоны') or [''])[0]} | {(v.get('почты') or [''])[0]} | {places} | "
                   f"{len(g)}{f' · {avg:.1f}'.replace('.', ',') if g else ''} | {links(v.get('отзывы'), 2)} |\n")
        md += "\n"
    chk = [(n, v) for n, v in parts.items() if not st(v).startswith("ставит чужое")]
    md += ("**Не подтвердилось или нужен звонок**\n\n| Компания | Статус | Телефон | Сайт |\n|---|---|---|---|\n"
           + "".join(f"| {n} | {st(v)} | {(v.get('телефоны') or [''])[0]} | {site_of(v).get('сайт', '')} |\n" for n, v in sorted(chk, key=lambda kv: st(kv[1]))) + "\n")

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

    # что о конкурентах пишут на форумах (её задача 04.10, «очень важно»): parsers/konkurenty_forumy.py → разметка по смыслу (…_checked.tsv)
    fc = ROOT / "data/lists/konkurenty_otzyvy_forumy_checked.tsv"
    fa = ROOT / "data/lists/konkurenty_otzyvy_forumy.tsv"
    if fc.exists() or fa.exists():
        o = pd.read_csv(fc if fc.exists() else fa, sep="\t", dtype=str).fillna("")
        checked = fc.exists()
        if checked:
            o = o[(o["о бренде?"] == "да") & (o["оценка (проверено)"] != "нейтрально")]
            o["оц"], o["тм"] = o["оценка (проверено)"], o["тема (проверено)"]
        else:
            o["оц"], o["тм"] = o["оценка"], o["тема"]
        md += (f"\n### Что о конкурентах пишут на форумах и в отзывах ({len(o)} мнений)\n"
               "ForumHouse, Мастерград, АВОК, iXBT, iRecommend, отзывы Яндекса и магазинов; Отзовик — только отрывки из выдачи (сайт закрыт проверкой «Вы робот?»). "
               + ("Каждая фраза размечена по смыслу: плюс, минус, о том ли бренде речь, тема; вопросы и реклама продавцов убраны. " if checked else
                  "Разметка автоматическая по словам (примерно 2 из 3 верно) — цитаты читать глазами. ")
               + "Полный список с цитатами и ссылками — data/lists/konkurenty_otzyvy_forumy" + ("_checked" if checked else "") + ".tsv.\n\n"
               "| Конкурент | Мнений | Плюсов | Минусов | За что ругают (темы) | За что хвалят (темы) | Пример минуса | Пример плюса |\n|---|---|---|---|---|---|---|---|\n")
        def top(g):
            c = pd.Series([t.strip() for x in g["тм"] for t in x.split(",") if t.strip()]).value_counts().head(3)
            return ", ".join(f"{k} ({v})" for k, v in c.items())
        def ex(g):
            g = g.assign(l=g["фраза"].str.len()).sort_values("l")
            g = g[g["l"].between(40, 260)]
            return f"«{g.iloc[len(g) // 2]['фраза']}» ([{g.iloc[len(g) // 2]['где']}]({g.iloc[len(g) // 2]['ссылка']}))" if len(g) else ""
        for b, g in sorted(o.groupby("конкурент"), key=lambda kv: -len(kv[1])):
            mn, pl = g[g["оц"].str.contains("минус")], g[g["оц"].str.startswith("плюс")]
            md += f"| {b} | {len(g)} | {len(pl)} | {len(mn)} | {top(mn)} | {top(pl)} | {ex(mn)} | {ex(pl)} |\n"
        allm = o[o["оц"].str.contains("минус")]
        md += f"\n**Главное, за что ругают всех вместе:** {top(allm)}. Это то, что Frivent должен закрыть в обещании и доказательствах.\n"

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
