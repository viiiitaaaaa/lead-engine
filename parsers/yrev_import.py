"""Полные отзывы Яндекс Карт (сверх 50), собранные в Chrome прокруткой и сохранённые в «Загрузки» (yrev*_<id>.json):
по каждой карточке берём самый полный файл, где больше всего отзывов с текстом → data/raw/yrev_full.json {ссылка карточки: [отзывы]}.
Имён авторов в файлах нет. Панель подменяет отзывы этих карточек полными.
python parsers/yrev_import.py
"""
import json
from pathlib import Path

from yandex_maps_bd import ROOT

DL = Path.home() / "Downloads"


def main():
    best = {}
    for f in DL.glob("yrev*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        card = "https://yandex.ru" + d["card"].rstrip("/") + "/"
        good = sum(bool(r.get("текст")) for r in d["reviews"])
        if good > best.get(card, (0, None))[0]:
            best[card] = (good, d["reviews"])
    out = {c: r for c, (_, r) in best.items()}
    (ROOT / "data/raw/yrev_full.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    for c, r in out.items():
        print(f"{len(r):>4}  {c}")
    print(f"карточек {len(out)}, отзывов {sum(map(len, out.values()))}")


if __name__ == "__main__":
    main()
