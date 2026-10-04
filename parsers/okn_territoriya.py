"""Объекты культурного наследия на нашей территории (её список 04.10: «объекты культурного наследия» как клиенты-коммерция).
Источник — реестр ОКН в Викигиде (ru.wikivoyage.org, «Культурное наследие России/Московская область/<район>», бесплатно):
Одинцовский, Красногорский, Истринский районы + их подсписки по городам. Берём только здания (type=architecture),
верхний уровень (без частей комплексов) и не утраченные. Реставрация ОКН = вентиляция и климат под музейные условия.

python parsers/okn_territoriya.py
Итог: data/lists/okn_territoriya.tsv
"""
import re
import urllib.parse
import urllib.request

import pandas as pd

from yandex_maps_bd import ROOT

DISTRICTS = ["Одинцовский район", "Красногорский район", "Истринский район"]
BASE = "Культурное наследие России/Московская область/"
KIND = [  # порядок важен — первое совпадение (проверено глазами 04.10)
    ("парк — не наш", r"^парк|: парк|парк с прудом|^аллея|^пруд|место гибели"),
    ("усадьба, дворец", r"усадьб|дворец|дворц|барский дом|главный дом"),
    ("храм, монастырь", r"церк|храм|собор|часовн|монастыр|колокольн"),
    ("дача, жилой дом", r"дача|дачи|жилой дом|дом |особняк"),
    ("промышленное", r"фабрик|мануфактур|завод|мельниц|водонапорн|депо|вокзал"),
    ("общественное", r"школ|училищ|больниц|госпитал|клуб|театр|санатор|дом отдыха|земск|усадебн|корпус|здание"),
]


def raw(title: str) -> str:
    u = "https://ru.wikivoyage.org/w/index.php?action=raw&title=" + urllib.parse.quote(title)
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "lead-engine/1.0"}), timeout=60).read().decode("utf-8")


def field(block: str, name: str) -> str:
    m = re.search(rf"\|\s*{name}\s*=\s*([^|\n]*)", block)
    return m.group(1).strip() if m else ""


def main():
    rows, seen = [], set()
    for d in DISTRICTS:
        todo, done = [BASE + d], set()
        while todo:
            t = todo.pop()
            if t in done:
                continue
            done.add(t)
            s = raw(t)
            # подсписки по городам: [[Культурное наследие России/Московская область/Истра|Истра]]
            todo += [m for m in re.findall(r"\[\[(" + re.escape(BASE) + r"[^|\]]+)", s) if m not in done and not m.endswith("район")]
            for b in re.findall(r"\{\{monument\s*\|.*?\n\}\}", s, re.S):
                knid = field(b, "knid")
                if field(b, "type") != "architecture" or field(b, "complex") not in ("", knid) or field(b, "status") in ("destroyed", "demolished") or knid in seen:
                    continue
                seen.add(knid)
                name = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", field(b, "name"))
                rows.append({"название": name, "вид": next((k for k, rx in KIND if re.search(rx, name, re.I)), "прочее"),
                             "район": d, "населённый пункт": field(b, "municipality"), "адрес": field(b, "address"),
                             "год": field(b, "year"), "охрана": {"Ф": "федеральный", "Р": "региональный", "М": "местный", "В": "выявленный"}.get(field(b, "protection"), field(b, "protection")),
                             "номер ЕГРОКН": knid})
        print(d, "страниц", len(done), "зданий всего", len(rows), flush=True)
    t = pd.DataFrame(rows)
    t = t[t["вид"] != "парк — не наш"]
    t.to_csv(ROOT / "data/lists/okn_territoriya.tsv", sep="\t", index=False)
    print(pd.crosstab(t["вид"], t["район"], margins=True).to_string())


if __name__ == "__main__":
    main()
