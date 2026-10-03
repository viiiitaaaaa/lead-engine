"""Форумы для карты болей по нашему оборудованию (её задача 03.10, пункты 1 и 5): темы ForumHouse, Мастерграда и АВОК,
найденные поиском Яндекса в Chrome (site:… + запрос о проблеме). ForumHouse отдаёт страницы только браузеру — его сообщения
собираются в Chrome и приходят файлом fh_posts.json в Загрузки; Мастерград и АВОК — обычным запросом отсюда.
Цитаты чужих сообщений вырезаются, имена авторов не сохраняются.

python parsers/klimat_forumy.py fr_search.json [fh_posts.json]
Итог: data/raw/klimat_forumy.json = {url темы: {форум, тема, запросы, посты: [...]}}
"""
import json
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

from partner_terms import get
from yandex_maps_bd import ROOT

OUT = ROOT / "data/raw/klimat_forumy.json"
DL = Path.home() / "Downloads"


def posts(h: str, sel: str, quote: str) -> list:
    soup = BeautifulSoup(h or "", "html.parser")
    out = []
    for d in soup.select(sel):
        for q in d.select(quote):
            q.decompose()
        t = re.sub(r"\s+", " ", d.get_text(" ", strip=True))
        if len(t) > 30:
            out.append(t[:3000])
    return out


def norm(u: str) -> str:
    """АВОК: тема целиком на облегчённой странице lofiversion; Мастерград: без параметров; вложения и блоги — мимо"""
    if "abok" in u:
        m = re.search(r"showtopic=(\d+)|/t(\d+)\.html", u)
        return f"https://forum.abok.ru/lofiversion/index.php/t{m.group(1) or m.group(2)}.html" if m else ""
    if "mastergrad" in u:
        return re.sub(r"[?#].*", "", u) if "/forums/" in u else ""
    return re.sub(r"[?#].*", "", u)


def main():
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    search = json.loads((DL / sys.argv[1]).read_text(encoding="utf-8"))
    threads = {}
    for r in search:
        for it in r["items"]:
            u = norm(it["url"])
            if not u:
                continue
            th = threads.setdefault(u, {"форум": r["s"], "тема": it["title"], "запросы": [], "сниппет": it.get("snip", "")})
            if r["q"] not in th["запросы"]:
                th["запросы"].append(r["q"])
    if len(sys.argv) > 2:  # ForumHouse из Chrome
        for u, p in json.loads((DL / sys.argv[2]).read_text(encoding="utf-8")).items():
            u = re.sub(r"[?#].*", "", u)
            if u in threads:
                res[u] = dict(threads[u], посты=p)
    todo = [u for u, t in threads.items() if t["форум"] != "forumhouse.ru" and u not in res]
    print(f"тем: {len(threads)} (ForumHouse {sum(t['форум'] == 'forumhouse.ru' for t in threads.values())}), "
          f"Мастерград и АВОК к загрузке {len(todo)}", flush=True)
    for n, u in enumerate(todo, 1):
        try:
            h = get(u)
        except Exception:
            h = ""
        p = posts(h, "div.postcontent", "div.quotetop, div.quotemain") if "abok" in u else posts(h, "div.pagetext", "blockquote, .bbcode_quote, .quote")
        res[u] = dict(threads[u], посты=p)
        if n % 10 == 0 or n == len(todo):
            OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            print(f"  {n} из {len(todo)}, сообщений {sum(len(x['посты']) for x in res.values())}", flush=True)
        time.sleep(1.5)
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
