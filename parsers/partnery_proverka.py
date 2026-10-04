"""Партнёры точно ставят чужое? (её задача 04.10, «очень важно») + ИНН, телефоны, сайты, почты подходящих.
По тексту сайта (sayty_obhod.py): какие марки чужого оборудования упомянуты и есть ли признаки своего производства.
Статус: «ставит чужое» (марки есть, своего производства нет) / «ставит чужое и производит своё» / «сам производит» /
«неясно» (марок нет и производства нет — проверить звонком). Контакты: сайт + карточки 2ГИС (items/byid).
ИНН: с сайта (реквизиты, политика конфиденциальности, оферта) → ЕГРЮЛ по одному.

python parsers/partnery_proverka.py [--egrul]
Итог: data/lists/partnery_proverka.tsv; поля «ставит чужое», «марки», «телефоны», «почты», «ИНН» в data/raw/dossier_montazhniki.json
"""
import json
import re
import sys
import time

import pandas as pd

from build_base import domain
from gis_reviews import SEARCH_KEY, j
from yandex_maps_bd import ROOT

BRANDS = {  # чужое оборудование, которое ставят монтажники (вентиляция, климат, бассейны, отопление, вода)
    "вентиляция": r"breezart|бризарт|turkov|турков|systemair|системэйр|komfovent|комфовент|zehnder|salda|shuft|шуфт|ventmachine|вентмашин|minibox|минибокс|"
                  r"тион|tion\b|vakio|royal clima|naveka|навека|ballu|electrolux|dantex|lessar|vents\b|вентс|blauberg|ostberg|korf|арктика|веза|арктос|ровен|rowen|clever-air|aerostar|airone|wolter|"
                  r"frivent|фривент|dimplex|swegon|flakt|daikin modular|mitsubishi lossnay|lossnay|аэростар|euroclimat",
    "кондиционеры": r"daikin|дайкин|mitsubishi|мицубиси|митсубиси|toshiba|тошиба|haier|хайер|midea|мидеа|gree|грии|lg\b|samsung|panasonic|fujitsu|general climate|"
                    r"hisense|kentatsu|кентатсу|hitachi|хитачи|carrier|aux\b|tcl\b|funai|jax|axioma|ecostar|energolux|rovex|centek|zanussi|quattroclima|lessar|dahatsu",
    "бассейны и осушение": r"dantherm|calorex|калорекс|mycond|майконд|fairland|microwell|emaux|kripsol|hayward|pahlen|fluidra|astralpool|aquaviva|aquant|behncke|"
                           r"zodiac|maytronics|dolphin|ospa|bwt|prominent|seko|dryair|osf|speck|pentair|sta-rite|aquavent|акванет|bayrol",
    "отопление и вода": r"viessmann|висман|buderus|будерус|vaillant|вайлант|baxi|бакси|bosch|бош|wolf\b|protherm|протерм|kiturami|navien|навьен|ariston|аристон|"
                        r"grundfos|грундфос|wilo|вило|джилекс|jeelex|aquaphor|аквафор|гейзер|geyser|ecosoft|clack|runxin|kinetico|rehau|uponor|valtec|stout|kermi|purmo|"
                        r"de dietrich|immergas|ferroli|thermona|mitsubishi ecodan|stiebel|nibe",
}
OWN = (r"собственн\w* (производств|завод|цех)|наш\w* (завод|производств\w*|цех)|мы производим|производим (вентиляц|оборудован|установк|приточн|осушит|рекупер|кондиц)|"
       r"изготавлива\w* (вентиляц|приточн|оборудован|установк)")  # без «российский производитель», «завод-изготовитель», «производственная вентиляция» — проверено глазами 04.10
OWN_OK = r"производств\w* (чаш|бассейн|композит|полипропилен|воздуховод|фасон|вентиляционн\w* (короб|решет))"  # свои чаши/воздуховоды — монтажник, оборудование чужое


def contacts_2gis(name: str, site: str) -> dict:
    inst = json.loads((ROOT / "data/raw/klimat_montazhniki.json").read_text(encoding="utf-8"))
    ids = [cid for cid, c in inst.items() if c.get("сайт") and domain(c["сайт"]) == domain(site)]
    ph, ml = set(), set()
    for cid in ids[:4]:
        r = j(f"https://catalog.api.2gis.com/3.0/items/byid?id={cid}&fields=items.contact_groups&key={SEARCH_KEY}")
        for it in (r.get("result") or {}).get("items") or []:
            for g in it.get("contact_groups") or []:
                for c in g.get("contacts") or []:
                    if c.get("type") == "phone" and c.get("value"):
                        ph.add("+7" + re.sub(r"\D", "", c["value"])[-10:])
                    elif c.get("type") == "email" and c.get("value"):
                        ml.add(c["value"].lower())
        time.sleep(0.3)
    return {"телефоны 2ГИС": sorted(ph), "почты 2ГИС": sorted(ml), "карточек 2ГИС": len(ids)}


def main():
    dos_f = ROOT / "data/raw/dossier_montazhniki.json"
    d = json.loads(dos_f.read_text(encoding="utf-8"))
    sites = json.loads((ROOT / "data/raw/sayty_obhod.json").read_text(encoding="utf-8"))
    rows = []
    for n, v in d.items():
        if not v.get("партнёр?"):
            continue
        site = next((x.get("сайт") for x in v["сайты"] if x.get("сайт")), "")
        s = sites.get(site) or next((x for k, x in sites.items() if domain(k) == domain(site)), {})
        t = (s.get("текст", "") + " " + " ".join(s.get("заголовки", [])) + " " + s.get("мета", "")).lower()
        # граница слова слева всегда, справа — для латиницы (у русских марок падежи: «Туркова»); проверено 04.10: «уровень», «правило», «-tion», «agree»
        marks = {g: sorted({m.group(1).lower() for m in re.finditer(r"(?<![а-яёa-z])(" + rx + r")(?![a-z])", t, re.I)
                            if not re.fullmatch(r"вило|ровен|тион", m.group(1).lower()) or not re.match(r"[а-яё]", t[m.end():m.end() + 1] or " ")})
                 for g, rx in BRANDS.items()}
        marks = {g: m for g, m in marks.items() if m}
        nb = sum(len(m) for m in marks.values())
        fa = lambda rx: [m.group(0).lower() for m in re.finditer(rx, t, re.I)]
        own = sorted(set(fa(OWN)) - set(fa(OWN_OK)))
        own_hits = len(fa(OWN)) - len(fa(OWN_OK))
        if s.get("ответ") != "ок":
            st = "сайт не открылся — проверить звонком"
        elif nb >= 1 and own_hits <= 1:
            st = "ставит чужое"
        elif nb >= 1:
            st = "ставит чужое и производит своё — уточнить"
        elif own_hits > 1:
            st = "сам производит — не партнёр"
        else:
            st = "неясно — марок на сайте нет, проверить звонком"
        c2 = contacts_2gis(n, site) if site else {}
        L = v.get("юрлицо") or {}
        inn = L.get("ИНН") or next(iter(s.get("ИНН", [])), "")
        v.update({"ставит чужое": st, "марки": marks, "своё производство": own[:5], "телефоны": [x for x in dict.fromkeys(c2.get("телефоны 2ГИС", []) + s.get("телефоны", []))  # 2ГИС первыми; только живые коды (проверено 04.10: «+71020000000»)
                                if re.fullmatch(r"\+7[489]\d{9}", x) and not re.search(r"(\d){5}", x)][:8],
                  "почты": sorted(set(s.get("почты", [])) | set(c2.get("почты 2ГИС", [])))[:6], "ИНН": inn})
        rows.append({"компания": n, "статус": st, "кому партнёр": v.get("кому партнёр", ""), "профиль": v.get("профиль", ""),
                     "марки, которые ставят": "; ".join(f"{g}: {', '.join(m[:8])}" for g, m in marks.items()),
                     "своё производство (фразы)": "; ".join(own[:3]), "ИНН": inn, "юрлицо": L.get("юрлицо", ""),
                     "сайт": site, "телефоны": ", ".join(v["телефоны"]), "почты": ", ".join(v["почты"]), "страниц прочитано": s.get("страниц", 0)})
        print(f"{len(rows):3} {st[:30]:30} {n[:30]}", flush=True)
    if "--egrul" in sys.argv:  # юрлицо по новым ИНН с сайта — по одному
        from list_dossier import egrul
        for r in rows:
            v = d[r["компания"]]
            if r["ИНН"] and not (v.get("юрлицо") or {}).get("юрлицо"):
                eg = [e for e in egrul(r["ИНН"]) if not e["ликвидировано"]]
                if eg:
                    v["юрлицо"], v["юрлицо: как найдено"] = eg[0], "по ИНН с сайта"
                    r["юрлицо"] = eg[0]["юрлицо"]
    dos_f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    t = pd.DataFrame(rows)
    t.to_csv(ROOT / "data/lists/partnery_proverka.tsv", sep="\t", index=False)
    print(t["статус"].value_counts().to_string())
    ok = t[t["статус"].str.startswith("ставит чужое")]
    print(f"подходят {len(ok)}: ИНН {(ok['ИНН'] != '').sum()}, телефон {(ok['телефоны'] != '').sum()}, почта {(ok['почты'] != '').sum()}")


if __name__ == "__main__":
    main()
