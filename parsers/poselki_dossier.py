"""Досье по посёлкам, которые она подтвердила ссылками 03.10 («вот эти посёлки, по ним собирай всю инфу»).
Свод всего, что есть, в одну карточку на посёлок: Циан (карточка КП — класс, км, описание, застройщик, инфраструктура, коммуникации,
объекты в продаже, цены), наша сводка посёлков (УК, сайт, контакты, Telegram, ВК, FORUMHOUSE), дома от 50 млн ₽ в продаже и их
продавцы, участники групп ВК, подрядчики с объектами в посёлке, отзывы с её подтверждённых карточек.

python parsers/poselki_dossier.py
Итог: data/raw/poselki_dossier.json → панель (блок «Посёлки из списка — досье»).
"""
import json
import re
from pathlib import Path

import pandas as pd

from cian_villages import card
from villages_merge import key
from yandex_maps_bd import ROOT

# её ссылки 03.10 (Циан) + дополнительные: сайт или карточка карт
VILLAGES = {
    "Жуковка": {"cian": "/kottedzhnyj-poselok-zhukovka-66910/", "site": "https://zhukovka.moscow"},
    "Барвиха": {"cian": "/kottedzhnyj-poselok-barviha-71753/"},
    "Раздоры": {"cian": "/kottedzhnyj-poselok-razdory-75834/"},
    "Шульгино": {"cian": "/kottedzhnyj-poselok-shulgino-10242/"},
    "Подушкино": {"cian": "/kottedzhnyj-poselok-podushkino-79687/"},
    "Николина Гора": {"cian": "/kottedzhnyj-poselok-nikolina-gora-75830/"},
    "Усово": {"cian": "/kottedzhnyj-poselok-usovo-66920/"},
    "Солослово": {"cian": "/kottedzhnyj-poselok-soloslovo-75828/"},
    "Пирогово": {"cian": "/kottedzhnyj-poselok-kurort-pirogovo-10299/", "site": "https://pirogovo.ru"},
    "Дарьино": {"site": "https://darino.club"},
    "Лапино": {"card": "https://yandex.ru/maps/org/novoye_lapino/145926408068/", "site": "http://novoe-lapino.ru"},
}
SERP_SKIP = r"yandex\.|avito\.|youtube|rutube|hh\.ru|market\."
CLASS = {"elite": "элит", "business": "бизнес", "comfort": "комфорт", "economy": "эконом"}
STATUS = {"closed": "продажи завершены / вторичка", "active": "застройщик продаёт", "soon": "скоро старт"}


def names(x) -> list:
    """списки Циана бывают строками или словарями — берём читаемое имя"""
    out = []
    for v in x or []:
        out.append(v if isinstance(v, str) else (v.get("name") or v.get("title") or v.get("type") or json.dumps(v, ensure_ascii=False)[:60]))
    return out


def main():
    L = ROOT / "data/lists"
    sv = pd.read_csv(L / "poselki_svod.tsv", sep="\t", dtype=str).fillna("")
    doma = pd.read_csv(L / "cian_doma.tsv", sep="\t", dtype=str).fillna("")
    pod = pd.read_csv(L / "podryadchiki_poselkov.tsv", sep="\t", dtype=str).fillna("")
    tg = pd.read_csv(L / "tg_poselki_otbor.tsv", sep="\t", dtype=str).fillna("")
    sb = pd.read_csv(L / "soobshchestva_poselkov.tsv", sep="\t", dtype=str).fillna("")
    dol = pd.read_csv(L / "spisok_otzyvy_dolya.tsv", sep="\t").set_index("пункт")
    vkm = json.loads((ROOT / "data/raw/vk_members.json").read_text(encoding="utf-8"))
    vkn = lambda u: (vkm.get((re.search(r"vk\.(?:com|ru)/([A-Za-z0-9_.]+)", u) or [None, ""])[1]) or {}).get("members")
    sf = Path.home() / "Downloads" / "serp_poselki.json"  # поиск Яндекса в её Chrome, по 2 запроса на посёлок (03.10)
    serp = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else []
    out = {}
    for name, src in VILLAGES.items():
        k = key(name)
        d = {"посёлок": name, "источники": src}
        if src.get("cian"):
            v = card(src["cian"])
            b = v.get("builder") or {}
            c = v.get("counterSet") or {}
            road = (v.get("roadInfoList") or [{}])[0]
            d["Циан"] = {
                "ссылка": "https://www.cian.ru" + src["cian"], "адрес": v.get("fullAddress", ""), "шоссе": road.get("name", ""),
                "км до МКАД": road.get("distanceCity", ""), "класс": CLASS.get(v.get("villageClass"), v.get("villageClass", "")),
                "статус продаж": STATUS.get(v.get("saleStatus"), v.get("saleStatus", "")), "площадь, га": v.get("areaHectare", ""),
                "сдача": "–".join(sorted({str(y) for y in (v.get("finishYearMin"), v.get("finishYearMax")) if y})),
                "этажность": "–".join(sorted({str(y) for y in (v.get("floorCountMin"), v.get("floorCountMax")) if y})),
                "в продаже": {"коттеджей": c.get("onSaleCottage", 0), "таунхаусов": c.get("onSaleTownhouse", 0), "участков": c.get("onSaleLandplot", 0),
                              "строится": c.get("underConstruction", 0), "всего": c.get("total", 0)},
                "цены, млн ₽": [round(x / 1e6) for x in (v.get("priceMin"), v.get("priceMax")) if x],
                "материал": v.get("houseMaterialList", []), "сайт": v.get("siteUrl", ""),
                "застройщик": "" if "не определен" in (b.get("name") or "") else b.get("name", ""),
                "о застройщике": (b.get("description") or "")[:400], "телефон застройщика": b.get("phone", "") if b.get("displayBuilderPhone") or b.get("displayPhone") else "",
                "описание": re.sub(r"\s+", " ", v.get("description", ""))[:1500],
                "инфраструктура": names(v.get("infrastructureList")), "рядом": names(v.get("neighbourhoodList")),
                "коммуникации": v.get("communicationSet") or {}, "особенности": names(v.get("featureList")),
                "станции": [s.get("name") for s in v.get("stationInfoList") or [] if isinstance(s, dict)],
            }
        r = sv[sv["посёлок"].map(key) == k]
        if len(r):
            r = r.iloc[0]
            d["сводка"] = {c: r[c] for c in ("застройщик", "сайт застройщика", "телефоны застройщика", "почты застройщика", "УК / сайт посёлка",
                                             "сайт посёлка", "телефоны посёлка", "почты посёлка", "Telegram", "ВК", "FORUMHOUSE", "контакты брокеров") if c in r and r[c]}
        hs = doma[doma["посёлок/место"].map(key).str.contains(k, regex=False)]
        if len(hs):
            d["дома в продаже (от 50 млн ₽)"] = {"объявлений": len(hs), "продавцы": hs["продавец"].value_counts().head(8).to_dict(),
                                                  "кто продаёт": hs["кто продаёт"].value_counts().to_dict()}
        d["Telegram"] = [{"название": x["название"], "ссылка": x["ссылка"], "тип": x["тип"], "людей": x["людей"]}
                         for _, x in tg.iterrows() if k in key(x["название"] + " " + x["заметка"] + " " + x["описание"])][:10]
        d["ВК и FORUMHOUSE"] = [{"вид": x["вид"], "название": x["название"], "ссылка": x["ссылка"], "участников": vkn(x["ссылка"]) or x["участников"]}
                                for _, x in sb.iterrows() if key(x["посёлок"]) == k or k in key(x["посёлок"])][:15]
        pp = pod[pod["посёлки"].map(key).str.contains(k, regex=False)]
        d["подрядчики"] = {"в поиске по посёлку": len(pp),
                           "с объектами (портфолио, кейсы)": [{"сайт": x["сайт"], "телефоны": x["телефоны"], "почты": x["почты"]}
                                                              for _, x in pp.iterrows() if float(x.get("посёлков с объектом") or 0) > 0][:15]}
        if name in dol.index and dol.loc[name, "отзывов"] > 0:
            d["отзывы"] = {c: dol.loc[name, c] for c in ("отзывов", "Яндекс", "2ГИС", "плюс %", "минус %", "средняя оценка")}
        sr = [r for r in serp if r["n"] == name]
        d["поиск"] = {kind: [{"url": x["url"], "title": x.get("title") or "", "snip": x.get("snip") or ""} for r in sr if r["kind"] == kind
                             for x in r["items"] if not re.search(SERP_SKIP, x["url"], re.I)][:8] for kind in ("ук", "жители")}
        out[name] = d
        cz = d.get("Циан", {})
        print(f"{name:14} | {cz.get('класс', ''):7} | {cz.get('км до МКАД', '')} км | в продаже {cz.get('в продаже', {}).get('всего', '—')} | "
              f"застройщик: {cz.get('застройщик') or (d.get('сводка') or {}).get('застройщик', '—')} | TG {len(d['Telegram'])} | ВК/FH {len(d['ВК и FORUMHOUSE'])} | "
              f"подрядчики {d['подрядчики']['в поиске по посёлку']}/{len(d['подрядчики']['с объектами (портфолио, кейсы)'])} | дома {d.get('дома в продаже (от 50 млн ₽)', {}).get('объявлений', 0)}")
    (ROOT / "data/raw/poselki_dossier.json").write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
