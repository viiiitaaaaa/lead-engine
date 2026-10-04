"""Частоты Яндекс Вордстата к ключевым словам (её задача 04.10). Сбор — в Chrome под её входом в Яндекс
(wordstat.yandex.ru/wordstat/api/getTable, регион 1 = Москва и область, все устройства, пауза 1,2 с) → файл в Загрузках.
WS: {фраза: запросов в месяц}; WP: {тема Frivent: {total, popular: [[запрос, число]], assoc: [[похожий запрос, число]]}}.

python parsers/wordstat_import.py ws_res.json
Итог: колонка «запросов в месяц (Мск+МО)» в data/lists/klyuchevye_slova.tsv; data/lists/wordstat_temy.tsv (что реально ищут по темам Frivent)
"""
import json
import sys
from pathlib import Path

import pandas as pd

from yandex_maps_bd import ROOT


def main():
    d = json.loads((Path.home() / "Downloads" / sys.argv[1]).read_text(encoding="utf-8"))
    ws, wp = d["WS"], d["WP"]
    f = ROOT / "data/lists/klyuchevye_slova.tsv"
    t = pd.read_csv(f, sep="\t", dtype=str).fillna("")
    t["запросов в месяц (Мск+МО)"] = t["фраза"].map(lambda x: ws.get(x, ""))
    t.to_csv(f, sep="\t", index=False)
    rows = []
    for seed, v in wp.items():
        for q, n in v.get("popular", []):
            rows.append({"тема Frivent": seed, "вид": "запрос со словами", "запрос": q, "запросов в месяц (Мск+МО)": n})
        for q, n in v.get("assoc", []):
            rows.append({"тема Frivent": seed, "вид": "похожий запрос", "запрос": q, "запросов в месяц (Мск+МО)": n})
    w = pd.DataFrame(rows)
    w.to_csv(ROOT / "data/lists/wordstat_temy.tsv", sep="\t", index=False)
    (ROOT / "data/raw/wordstat_0410.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    got = sum(1 for x in ws.values() if isinstance(x, int) and x >= 0)
    print(f"частоты: {got} из {len(t)} фраз; тем Frivent {len(wp)}, запросов по темам {len(w)}")
    print(pd.DataFrame([{"тема": s, "в месяц": v.get("total")} for s, v in wp.items()]).to_string(index=False))


if __name__ == "__main__":
    main()
