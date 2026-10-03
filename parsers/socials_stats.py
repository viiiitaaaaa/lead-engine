"""Аудитория соцсетей по досье: Telegram (t.me — подписчики, t.me/s — дата последнего поста) и ВКонтакте (участники, последний пост).
Бесплатно, обычные страницы.
python parsers/socials_stats.py [--group premium]
Итог: дописывает в data/raw/dossier[_группа].json поле «соцсети: аудитория» = [{сеть, ссылка, подписчиков, последний пост}].
"""
import html
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from yandex_maps_bd import ROOT

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36", "Accept-Language": "ru"}
SKIP = r"vk\.(com|ru)/(js|rtrg|video_ext\.php|group|privacy|widget\w*|app\d+_?)|dzen\.ru/(id|embed|a)/?$|t\.me/(share|joinchat|\+)|vk\.(com|ru)/(video|share|away|wall|photo|club\d+\?|feed)|vk\.(com|ru)/?$"


def get(u):
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=25).read().decode("utf-8", "ignore")
    except Exception:
        return ""


def num(s: str):
    s = re.sub(r"(?<=\d)[\s\xa0 ](?=\d)", "", html.unescape(s).replace("\xa0", " "))  # «2 718» → «2718»
    m = re.search(r"([\d.,]+)\s*([KkКк]|тыс\.?)?", s)
    if not m:
        return None
    n = float(m.group(1).replace(" ", "").replace(",", "."))
    return int(n * 1000) if m.group(2) else int(n)


def tg(u: str) -> dict:
    h = re.search(r"t\.me/([A-Za-z0-9_]{4,})", u).group(1)
    t = get("https://t.me/" + h)
    ex = re.search(r'tgme_page_extra">(.*?)</div>', t, re.S)
    s = get("https://t.me/s/" + h)
    dates = re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})', s)
    return {"сеть": "Telegram", "ссылка": "https://t.me/" + h, "подписчиков": num(ex.group(1)) if ex else None,
            "последний пост": max(dates) if dates else ""}


def vk(u: str) -> dict:
    h = re.search(r"vk\.(?:com|ru)/([A-Za-z0-9_.]+)", u).group(1)
    vkf = ROOT / "data/raw/vk_members.json"  # собрано в Chrome из её вкладки vk.com: без входа ВК счётчик не отдаёт
    known = (json.loads(vkf.read_text(encoding="utf-8")) if vkf.exists() else {}).get(h) or {}
    if known.get("members") is not None:
        return {"сеть": "ВКонтакте", "ссылка": "https://vk.com/" + h, "подписчиков": known["members"], "последний пост": ""}
    t = get("https://m.vk.com/" + h) or get("https://vk.com/" + h)  # мобильная версия чаще отдаёт счётчик без входа
    m = re.search(r"(\d[\d\s\xa0.,]*\s*(?:K|тыс\.?)?)\s*(?:участник|подписчик)", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    dates = re.findall(r'"date":(\d{10})', t)
    import datetime as dt
    last = dt.datetime.fromtimestamp(max(map(int, dates))).strftime("%Y-%m-%d") if dates else ""
    return {"сеть": "ВКонтакте", "ссылка": "https://vk.com/" + h, "подписчиков": num(m.group(1)) if m else None, "последний пост": last}


def main():
    grp = sys.argv[sys.argv.index("--group") + 1] if "--group" in sys.argv else ""
    f = ROOT / f"data/raw/dossier{'_' + grp if grp else ''}.json"
    res = json.loads(f.read_text(encoding="utf-8"))
    jobs = []
    for name, v in res.items():
        for s in v["сайты"]:
            for net, links in (s.get("соцсети") or {}).items():
                for u in links:
                    if re.search(SKIP, u, re.I):
                        continue
                    if net == "Telegram" and re.search(r"t\.me/[A-Za-z0-9_]{4,}", u):
                        jobs.append((name, tg, u))
                    elif net == "ВКонтакте" and re.search(r"vk\.(com|ru)/[A-Za-z0-9_.]{3,}", u):
                        jobs.append((name, vk, u))
    print(f"ссылок на проверку: {len(jobs)}", flush=True)
    with ThreadPoolExecutor(8) as pool:
        out = list(pool.map(lambda j: (j[0], j[1](j[2])), jobs))
    for v in res.values():
        v["соцсети: аудитория"] = []
    for name, r in out:
        if r["ссылка"] not in {x["ссылка"] for x in res[name]["соцсети: аудитория"]}:
            res[name]["соцсети: аудитория"].append(r)
    f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    ok = [r for _, r in out if r["подписчиков"] is not None]
    print(f"готово: {len(out)} ссылок, подписчики известны у {len(ok)}, последний пост у {sum(bool(r['последний пост']) for _, r in out)}")
    for name, r in sorted(out, key=lambda x: -(x[1]["подписчиков"] or 0))[:15]:
        print(f"  {name} | {r['сеть']} | {r['подписчиков']} | {r['последний пост']} | {r['ссылка']}")


if __name__ == "__main__":
    main()
