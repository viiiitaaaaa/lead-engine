"""Её список (46 названий от Андрея): раздел 9 основы лендинга + страница сверки «кого я взяла по каждому названию».
Статусы — data/lists/spisok_status.tsv (её подтверждения ссылками, «проверьте», «не нашла»…); кто не указан — «сайт и карточка совпадают».
Запускать после любой её поправки: python parsers/spisok_otzyvy_dolya.py && python parsers/spisok_razdel9.py
"""
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from yandex_maps_bd import DRIVE, ROOT

sys.path.insert(0, str(ROOT / "dashboard"))
from build_landing_doc import CSS  # noqa: E402

dom = lambda u: urlparse(u if "://" in u else "http://" + u).netloc.lower().removeprefix("www.") if u else ""
CLS = {"подтвердили вы": "ok", "сайт и карточка совпадают": "hi", "проверьте": "mid", "карточка без отзывов": "mid",
       "посёлок без карточки": "mid", "не нашла": "low"}


def main():
    names = [l.strip() for l in (ROOT / "data/lists/компании_и_поселки_2026-09-30.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    st = pd.read_csv(ROOT / "data/lists/spisok_status.tsv", sep="\t", dtype=str).fillna("").set_index("пункт")
    dol = pd.read_csv(ROOT / "data/lists/spisok_otzyvy_dolya.tsv", sep="\t").set_index("пункт")
    d = json.loads((ROOT / "data/raw/dossier.json").read_text(encoding="utf-8"))
    base = pd.read_excel(max(DRIVE.parent.glob("база_lead_engine_*.xlsx"), key=lambda p: p.stat().st_mtime), sheet_name="организации").fillna("")
    dop = pd.read_csv(ROOT / "data/lists/spisok_karty_dop.tsv", sep="\t", dtype=str).fillna("")
    isk = pd.read_csv(ROOT / "data/lists/spisok_karty_iskl.tsv", sep="\t", dtype=str).fillna("")  # её уточнения: не её посёлки

    # страница сверки
    rows = ""
    for i, n in enumerate(names, 1):
        v = d.get(n, {})
        sites = ", ".join(dict.fromkeys(dom(s.get("сайт", "")) for s in v.get("сайты", []) if s.get("сайт")))
        g = base[(base["наш список"] == n) & ~base["новая?"].str.startswith("отсеяно")]
        if v.get("вид") == "посёлок":
            g = g[(g["тип"] == "посёлок") | g["вид деятельности"].str.contains(r"коттеджн|посёл|посел|управляющ", case=False, regex=True)]
        for rx in isk[isk["пункт"] == n]["название содержит"]:
            g = g[~g["название"].astype(str).str.contains(rx, case=False, regex=True)]
        cards = [f"{r['название'][:30]} ({str(r['адрес'])[:40] or dom(str(r['сайт']).split(',')[0])})" for _, r in g.head(3).iterrows()]
        cards += [f"карточка: {u.split('/org/')[1].split('/')[0]}" for u in dop[dop["пункт"] == n]["ссылка"]]
        s = st.loc[n] if n in st.index else None
        status, note = (s["статус"], s["пояснение"]) if s is not None else ("сайт и карточка совпадают", "")
        nrev = int(dol.loc[n, "отзывов"]) if n in dol.index else 0
        rev = f"{nrev} отз. · {int(dol.loc[n, 'плюс %'])}% плюсов" if nrev else "отзывов нет"
        rows += (f"<tr class='{CLS.get(status, 'mid')}'><td>{i}</td><td><b>{html.escape(n)}</b><div class='k'>{html.escape(v.get('вид', ''))}</div></td>"
                 f"<td>{html.escape(sites) or '—'}</td><td class='k'>{html.escape('; '.join(cards)) or '—'}</td><td class='k'>{rev}</td>"
                 f"<td><b>{html.escape(status)}</b><div class='k'>{html.escape(note)}</div></td></tr>")
    cnt = {c: rows.count(f"<tr class='{c}'>") for c in ("ok", "hi", "mid", "low")}
    css = CSS + ".k{color:var(--muted);font-size:13px}tr.low td{background:#fbeceb}tr.mid td{background:#fdf6e3}tr.ok td{background:#e3f1e3}tr.hi td{background:#f1f8f1}"
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Сверка списка</title><style>{css}</style></head><body><main>
<h1>Сверка списка: кого я взяла по каждому названию</h1><p class="sub">В списке были только названия — компании и посёлки за ними определяла я. Подтвердили вы — {cnt['ok']}, сайт и карточка совпадают — {cnt['hi']}, проверьте — {cnt['mid']}, не нашла — {cnt['low']}.</p>
<table><thead><tr><th>№</th><th>Из списка</th><th>Сайт</th><th>Карточки на картах</th><th>Отзывы</th><th>Статус</th></tr></thead><tbody>{rows}</tbody></table></main></body></html>"""
    out = ROOT / "dashboard/сверка_списка.html"
    out.write_text(page, encoding="utf-8")
    shutil.copy(out, DRIVE.parent / out.name)

    # раздел 9
    t = pd.read_csv(ROOT / "data/lists/spisok_otzyvy_dolya.tsv", sep="\t")
    has = t[t["отзывов"] > 0]
    tot = int(has["отзывов"].sum())
    pl = (has["плюс %"] * has["отзывов"]).sum() / tot
    f = lambda x: f"{x:.1f}".replace(".", ",")
    md = (f"## 9. Компании и посёлки из списка — плюсы и минусы в отзывах\n"
          f"Отзывы Яндекс Карт, 2ГИС и Zoon по пунктам списка: плюс — оценка 4–5, минус — 1–3. В списке были только названия; карточки засчитаны, "
          f"если совпал сайт или карточку подтвердили. Отзывы есть у {len(has)} пунктов из {len(t)}, всего {tot:,} отзывов; "
          f"в среднем **{pl:.0f}% плюсов и {100 - pl:.0f}% минусов**.\n\n".replace(f"{tot:,}", f"{tot:,}".replace(",", " ")) +
          "Рейтинг на Яндекс Картах — то, что видит любой человек: средняя по всем оценкам, в том числе без текста. Плюсы и минусы — по отзывам "
          "с текстом (Яндекс, 2ГИС, Zoon): недовольные чаще пишут текст, поэтому по отзывам картина строже.\n\n"
          "| Компания / посёлок | Вид | Рейтинг на Яндекс Картах (оценок) | Отзывов с текстом | Плюсы | Минусы |\n|---|---|---|---|---|---|\n")
    for _, r in has.sort_values(["минус %", "отзывов"], ascending=[False, False]).iterrows():
        yrt = f"**{f(r['рейтинг Яндекса'])}** ({int(r['оценок на Яндексе'])})" if pd.notna(r.get("рейтинг Яндекса")) else "—"
        md += (f"| {r['пункт']} | {r['вид']} | {yrt} | {int(r['отзывов'])} | <span class=\"bar\" style=\"--w:{int(r['плюс %']) * 0.9:.0f}px;background:#5b8a5a\"></span> "
               f"{int(r['плюс %'])}% | <span class=\"bar\" style=\"--w:{int(r['минус %']) * 0.9:.0f}px;background:#b5523b\"></span> **{int(r['минус %'])}%** |\n")
    pf = ROOT / "data/lists/spisok_proekty.tsv"  # проекты и застройщики внутри посёлков: parsers/spisok_proekty.py
    if pf.exists():
        pj = pd.read_csv(pf, sep="\t")
        md += ("\n**Проекты и застройщики внутри посёлков.** Посёлок на картах — это место; рейтинг и отзывы есть у конкретных проектов и у тех, кто "
               "там строит и продаёт (по Циану). Отзывы проектов входят в итог посёлка в таблице выше.\n\n"
               "| Посёлок | Проект / застройщик | Рейтинг на картах (оценок) | Отзывов на карте | Плюсы | Минусы |\n|---|---|---|---|---|---|\n")
        for _, r in pj.iterrows():
            rt = f"**{f(r['рейтинг Яндекса'])}** ({int(r['оценок'])})" + (" · 2ГИС" if r.get("площадка") == "2ГИС" else "") if pd.notna(r["рейтинг Яндекса"]) else "—"
            pp = f"{int(r['плюс %'])}%" if pd.notna(r["плюс %"]) else "—"
            mm = f"**{int(r['минус %'])}%**" if pd.notna(r["минус %"]) else "—"
            md += f"| {r['посёлок']} | [{r['проект']}]({r['карточка']}) | {rt} | {int(r['отзывов на карте'])} | {pp} | {mm} |\n"
    zf = ROOT / "data/raw/zastroyshchiki_boli.json"  # минусы в постройках застройщиков посёлков (её задача 03.10): parsers/zastroyshchiki_boli.py
    if zf.exists():
        zb = json.loads(zf.read_text(encoding="utf-8"))
        tot_z = sum(v["отзывов разобрано"] for k, v in zb.items() if not k.startswith("_"))
        ANSWER = {"вентиляция, влажность, плесень": "вентиляция с рекуперацией Frivent, осушение, кондиционирование — расчёт под дом, пусконаладка, сервис",
                  "отопление и котлы": "котлы, тёплые полы, радиаторы, автоматика — подбор и поставка комплектом",
                  "водоподготовка и насосы": "фильтры и водоподготовка, насосные станции, водонагреватели",
                  "сантехника и комплектация": "комплектация инженерии и сантехники по проекту, с документами",
                  "гарантия и устранение дефектов": "приёмка оборудования с актом и фото, гарантия и сервис"}
        rows = [(dev, v) for dev, v in zb.items() if not dev.startswith("_") and v["боли"]]
        md += ("\n**Минусы в постройках застройщиков — что можем закрыть мы.** Разобраны отзывы о застройщиках посёлков и об их проектах "
               f"(2ГИС и Яндекс Карты, {tot_z} отзывов); искали только жалобы на инженерное оборудование домов: вентиляцию, влажность и плесень, "
               "отопление, водоподготовку, сантехнику, гарантию. Дороги, лес, охрана, газ, свет, септики и сама коробка дома — не наша зона.\n")
        if rows:
            md += "\n| Застройщик | Его проекты в посёлках | Что не так (из отзывов) | Чем закрываем мы |\n|---|---|---|---|\n"
            for dev, v in rows:
                q = "<br>".join(f"{t}: «{x['цитаты'][0]['фраза'][:150]}»" for t, x in list(v["боли"].items())[:3])
                a = "<br>".join(ANSWER.get(t, "") for t in list(v["боли"])[:3])
                md += f"| {dev} | {v['посёлки']} | {q} | {a} |\n"
        else:
            md += ("\n**Итог: жалоб на инженерное оборудование в этих отзывах нет ни у одного застройщика.** Покупатели элитных домов пишут о месте, "
                   "охране, сроках сдачи и отделе продаж, а не о вентиляции и котлах; владельцы и вовсе пишут мало — за них решают ассистенты. "
                   "Значит, боли по нашему оборудованию берём не из отзывов о застройщиках, а из жалоб на подрядчиков (разделы 5 и 7), "
                   "коммерческих объектов с бассейнами и из первых разговоров с ассистентами, монтажниками и проектировщиками.\n")
    hi = has[(has["минус %"] >= 19) & (has["отзывов"] >= 10)].sort_values("минус %", ascending=False)
    md += "\nБольше всего минусов: " + ", ".join(f"{r['пункт']} ({int(r['минус %'])}%)" for _, r in hi.iterrows()) + ". Если отзывов меньше 10, процент не показатель.\n"
    md += ("У Велес Строя (Велесстрой, velesstroy.com) отзывов от заказчиков почти нет (около 10 из 223): 68 отзывов — от рабочих о вахте, общежитиях и условиях "
           "труда (среди негативных — 34 из 78), остальные короткие без подробностей.\n"
           "У Пирогово (КП «Курорт Пирогово») отзывы — с карточки курорта: в основном про гольф, отель и рестораны, о домах и посёлке — около 32 из 323.\n")
    zero = set(t[t["отзывов"] == 0]["пункт"])
    dvid = dict(zip(t["пункт"], t["вид"]))
    grp = lambda s: [n for n in names if n in zero and n in st.index and st.loc[n, "статус"] == s]
    lines = [("карточка на картах есть, отзывов нет", grp("карточка без отзывов")),
             ("нашлись похожие карточки — нужно подтверждение", grp("проверьте")),
             ("на картах не найдены", grp("не нашла")),
             ("посёлки без карточки организации — на картах есть только как место; нужно уточнить проект", grp("посёлок без карточки")),
             ("посёлки подтверждены по Циану, но на Яндекс Картах и в 2ГИС посёлок отмечен только как место — своей карточки с рейтингом и "
              "отзывами нет; отзывы есть у отдельных проектов внутри (например, в Барвихе — Барвиха Хиллс и Барвиха XXI), по вашим ссылкам они не учитываются",
              [n for n in names if n in zero and n in st.index and st.loc[n, "статус"] == "подтвердили вы" and dvid.get(n) == "посёлок"]),
             ("компании: карточка есть или подтверждена, но отзывов на ней нет",
              [n for n in names if n in zero and n in st.index and st.loc[n, "статус"] == "подтвердили вы" and dvid.get(n) != "посёлок"])]
    md += "\n**Остальные пункты:**\n" + "".join(f"- {h}: {', '.join(ns)};\n" for h, ns in lines if ns)
    p = ROOT / "docs/лендинг_основа.md"
    s = p.read_text(encoding="utf-8")
    p.write_text(s[:s.index("## 9. Компании и посёлки из списка")].rstrip() + "\n\n" + md.rstrip(";\n") + ".\n", encoding="utf-8")
    print(f"сверка: {cnt}; раздел 9: {len(has)} пунктов, {tot} отзывов, {pl:.0f}% плюсов")


if __name__ == "__main__":
    main()
