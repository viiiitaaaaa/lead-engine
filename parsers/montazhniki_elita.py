"""Партнёры — монтажники элитных объектов (её решение 04.10: «больше всё-таки монтажники и прочие подрядчики, но которые
занимаются только элитной недвижимостью»). Берёт досье монтажников (list_dossier.py --group montazhniki --no-search)
и раскладывает по сегменту по их сайтам: наши посёлки и КП в тексте, премиальные слова (коттедж, особняк, бассейн, резиденция…)
против массовых (квартира, бризер, недорого). Прикрепляет отзывы 2ГИС для панели.

python parsers/montazhniki_elita.py          # сегменты, отзывы 2ГИС, таблица
python parsers/montazhniki_elita.py --egrul  # + юрлицо из ЕГРЮЛ по одному (элитный и смешанный сегмент)
Итог: сегмент в data/raw/dossier_montazhniki.json; data/raw/gis_reviews_montazhniki.json; data/lists/partnery_montazhniki.tsv
"""
import json
import re
import sys

import pandas as pd

from build_base import domain
from yandex_maps_bd import ROOT

DOS = ROOT / "data/raw/dossier_montazhniki.json"


# проверено глазами 04.10 по рубрикам элитного и смешанного сегмента
NOT_OURS = r"септик|septik|потолкович|мир хомутов|строймаркт|первый пассаж|золотые ворота|апельсин|^стройка$|санэлкреп|^зерн$|газ$|^одингаз|ледпром|антил[её]д|детск|прудторг|лига проектов|профэлектрика|элмстрой|протечка"
SHOP = r"^bwt$|джилекс|zodiac|экономстрой|^vakio$|^daikin$|минибокс|mirсli|mircli|русклимат|даичи"  # производители и магазины — конкуренты/поставщики, не монтажники


def profile(name: str, rub: str) -> str:
    if re.search(NOT_OURS, name, re.I) or re.search(r"^Локальные очистные|^Строительство и обслуживание наружного газ", rub):
        return "не наш профиль"
    if re.search(SHOP, name, re.I):
        return "производитель или магазин"
    if re.search(r"бассейн|бань|саун|гидромассаж", rub, re.I):
        return "бассейны и SPA"
    if re.search(r"климат|вентиляц|кондиционер", rub, re.I):
        return "вентиляция и климат"
    if re.search(r"отоплен|котел|котел|котельн|тёплые полы|теплые полы", rub, re.I):
        return "отопление и котлы"
    if re.search(r"очистки воды", rub, re.I):
        return "водоподготовка"
    return "другое"


def segment(v: dict) -> tuple:
    s = next((x for x in v["сайты"] if x.get("ответ") == "ок"), {})
    if not s:
        return "сайт недоступен", ""
    places, kp = s.get("упоминает наши места") or [], s.get("КП в тексте") or []
    prem, mass = s.get("премиум-слова", 0), s.get("масс-слова", 0)
    why = f"наши места: {', '.join(places[:5]) or '—'}; КП: {', '.join(kp[:3]) or '—'}; премиум-слов {prem}, массовых {mass}"
    if (places or kp) and prem >= mass:
        return "элитный", why
    if prem >= 10 and prem >= 2 * mass:
        return "элитный", why
    if prem >= 20 or (prem >= 3 and prem * 2 >= mass):
        return "смешанный", why
    if prem + mass < 3 and not places:  # сайт на скриптах — текст не читается (проверено глазами 04.10)
        return "не определить", why
    return "массовый", why


def main():
    d = json.loads(DOS.read_text(encoding="utf-8"))
    inst = json.loads((ROOT / "data/raw/klimat_montazhniki.json").read_text(encoding="utf-8"))
    by_dom = {}
    for cid, c in inst.items():
        if c.get("сайт"):
            by_dom.setdefault(domain(c["сайт"]), []).append((cid, c))
    gis, rows = {}, []
    for name, v in d.items():
        seg, why = segment(v)
        v["сегмент"], v["сегмент: почему"] = seg, why
        v["профиль"] = profile(name, v.get("рубрики", ""))
        # партнёр: элитный/смешанный сегмент любого нашего профиля + (её дополнение 04.10) все монтажники вентиляции и климата «под ключ»
        ok_prof = v["профиль"] not in ("не наш профиль", "производитель или магазин", "другое")
        v["партнёр?"] = ok_prof and (seg in ("элитный", "смешанный") or v["профиль"] == "вентиляция и климат")
        v["кому партнёр"] = "элитные дома" if seg in ("элитный", "смешанный") else ("коммерция и квартиры" if v["партнёр?"] else "")
        cards = by_dom.get(domain(v["сайты"][0]["сайт"] if v["сайты"] else ""), [])
        rv = list({x["текст"]: dict(x, карточка=c["название"]) for _, c in cards for x in c["отзывы"]}.values())
        gis[name] = {"карточки": [{"id": cid, "название": c["название"], "адрес": c["адрес"], "отзывов": c["отзывов"]} for cid, c in cards], "отзывы": rv}
        neg = [x for x in rv if (x.get("оценка") or 5) <= 3]
        s = next((x for x in v["сайты"] if x.get("ответ") == "ок"), v["сайты"][0] if v["сайты"] else {})
        L = v.get("юрлицо") or {}
        rows.append({"компания": name, "партнёр?": "да" if v["партнёр?"] else "", "кому партнёр": v["кому партнёр"], "профиль": v["профиль"], "сегмент": seg, "почему": why, "сайт": s.get("сайт", ""), "рубрики": v.get("рубрики", ""),
                     "юрлицо": L.get("юрлицо", ""), "ИНН": L.get("ИНН", ""), "руководитель": L.get("руководитель", ""), "регистрация": L.get("регистрация", ""),
                     "отзывов 2ГИС": len(rv), "негатив": len(neg), "средняя оценка": round(sum(x["оценка"] for x in rv if x.get("оценка")) / max(1, sum(1 for x in rv if x.get("оценка"))), 1) if rv else "",
                     "соцсети": "; ".join(u for us in (s.get("соцсети") or {}).values() for u in us),
                     "наши места": ", ".join(s.get("упоминает наши места") or []), "КП": ", ".join(s.get("КП в тексте") or []),
                     "страниц проектов": s.get("страниц проектов", 0), "адреса": "; ".join(v.get("адреса") or [])[:200]})
    if "--egrul" in sys.argv:
        from list_dossier import egrul
        need = [(n, v) for n, v in d.items() if v["партнёр?"] and not v.get("юрлицо")]
        for k, (n, v) in enumerate(need, 1):
            inn = next((i for x in v["сайты"] for i in x.get("ИНН с сайта", [])), "")
            eg = [e for e in (egrul(inn) if inn else egrul(n)) if not e["ликвидировано"]]
            v["юрлицо"] = eg[0] if inn and eg else {}
            v["юрлицо-кандидат"] = eg[0] if not inn and len(eg) == 1 else {}
            v["юрлицо: как найдено"] = "по ИНН с сайта" if v["юрлицо"] else ("по названию — одно юрлицо, НЕ подтверждено" if v["юрлицо-кандидат"] else
                                                                             (f"тёзки: {len(eg)} действующих" if eg else "не найдено"))
            DOS.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            print(f"ЕГРЮЛ: {k} из {len(need)}", flush=True)
        for r in rows:
            L = d[r["компания"]].get("юрлицо") or {}
            r.update({"юрлицо": L.get("юрлицо", ""), "ИНН": L.get("ИНН", ""), "руководитель": L.get("руководитель", ""), "регистрация": L.get("регистрация", "")})
    DOS.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    (ROOT / "data/raw/gis_reviews_montazhniki.json").write_text(json.dumps(gis, ensure_ascii=False), encoding="utf-8")
    t = pd.DataFrame(rows).sort_values(["партнёр?", "сегмент", "профиль", "отзывов 2ГИС"], ascending=[False, True, True, False])
    t.to_csv(ROOT / "data/lists/partnery_montazhniki.tsv", sep="\t", index=False)
    print(t["сегмент"].value_counts().to_string())
    pt = t[t["партнёр?"] == "да"]
    print(f"\nПАРТНЁРЫ: {len(pt)}"); print(pd.crosstab(pt["профиль"], pt["сегмент"]).to_string())
    print("юрлицо по ИНН с сайта:", (t["ИНН"] != "").sum(), "| соцсети:", (t["соцсети"] != "").sum())


if __name__ == "__main__":
    main()
