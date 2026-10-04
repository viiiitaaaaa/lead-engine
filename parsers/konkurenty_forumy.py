"""Отзывы о конкурентах с форумов — плюсы и минусы (её задача 04.10, «ЭТО ОЧЕНЬ ВАЖНО»).
Темы и страницы отзывов найдены поиском Яндекса в Chrome (kf_search.json в Загрузках): ForumHouse, Мастерград, АВОК,
Отзовик, iRecommend и др. Мастерград, АВОК (lofiversion), Отзовик и прочие читаются отсюда; ForumHouse отдаёт страницы
только браузеру — его сообщения приходят файлом fh_konk.json (собираются в Chrome).
Из сообщений берутся фразы, где назван бренд (или фраза рядом с ним в том же сообщении), и раскладываются:
плюс / минус / смешанное, по темам. Цитаты чужих сообщений вырезаются, имена авторов не сохраняются.

python parsers/konkurenty_forumy.py fetch kf_search.json      # загрузить страницы (кроме ForumHouse)
python parsers/konkurenty_forumy.py fh fh_konk.json           # добавить ForumHouse из Chrome
python parsers/konkurenty_forumy.py analyze                   # плюсы/минусы → data/raw/konkurenty_forumy_svod.json
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from bs4 import BeautifulSoup

from list_dossier import get
from yandex_maps_bd import ROOT

RAW = ROOT / "data/raw/konkurenty_forumy.json"
SVOD = ROOT / "data/raw/konkurenty_forumy_svod.json"
DL = Path.home() / "Downloads"
ALIAS = {
    "Turkov": r"turkov|турков", "Breezart": r"breezart|бризарт|бризарт", "Ventmachine": r"ventmachine|вентмашин|венмашин", "Minibox": r"minibox|минибокс",
    "Shuft": r"shuft|шуфт", "ВЕЗА": r"(?<![а-яё])веза(?![а-яё])|veza", "Арктос": r"арктос|arktos", "Clever-Air": r"clever.?air|клевер.?эйр",
    "Ровен": r"(?<![а-яё])ровен(?![а-яё])|rowen", "Тион": r"(?<![а-яё])тион|(?<![a-z])tion(?![a-z])", "Vakio": r"vakio|вакио", "Royal Clima": r"royal.?clima|роял.?клима",
    "Komfovent": r"komfovent|комфовент", "Zehnder": r"zehnder|цендер", "Systemair": r"systemair|системэйр|систем эйр", "Salda": r"(?<![a-z])salda|салда",
    "Calorex (дилер iClim)": r"calorex|калорекс", "Dantherm": r"dantherm|дантерм|датерм", "Джилекс": r"джилекс|jeelex|джумбо", "BWT": r"(?<![a-z])bwt(?![a-z])",
    "Провент": r"provent|провент", "Аласка": r"alasca|аласка", "Frivent": r"frivent|фривент|aquavent|klimabox", "Naveka": r"naveka|навека",
    "Мир климата": r"мир климата|mircli", "Климат Маркет": r"klimat\.market|климат маркет", "Панорама Вент": r"панорама вент|panoramavent", "Fresh Air": r"fresh-air|fresh air",  # «свежий воздух» — не бренд (проверено 04.10)
}
OK_HOST = r"forumhouse|mastergrad|abok|otzovik|irecommend|otzyv|otziv|forum|dom\.ria|stroimdom|pikabu|dzen\.ru|vc\.ru|yandex\.ru/q|otvet\.mail|market\.yandex|reviews\.yandex|2gis|zoon|ozon\.ru/.*review|vseinstrumenti.*otzyv|mircli.*otzyv|bigam.*otzyv|gdeotziv"
PLUS = (r"доволен|довольн|нравится|понравил|отличн|хорош(о|ий|ая|ее|ие)\b|надежн|надёжн|(?<![а-яё])тих(о|ая|ий|ие)\b|бесшумн|не слышно|рекомендую|советую(?! не)|качествен|"
        r"работает (без|отлично|хорошо|исправно|уже \d|нормально|стабильно)|без проблем|ни разу не|супер|(?<![а-яё])лучш|грамотн|оперативн|быстро (ответ|приех|поменял|решил)|"
        r"экономи|окупил|адекватн|приятн|удобн|продуман")
MINUS = (r"шум(?!о)|гудит|(?<![а-яё])гул(?!яр|ир|ят)|свист|вибрац|сломал|полом|вышел из строя|вышла из строя|обмерза|замерза|(?<![а-яё])л[её]д(?:[ауе]|ом|ян\w*)?(?![а-яё])|теч[её]т|протек|конденсат|брак|"
         r"не работает|перестал|проблем|глюч|зависа|ошибк|плат[аы] (сгорел|полетел|вылет)|сгорел|дорог|переплат|минус|жалею|разочаров|ужас|кошмар|"
         r"сервис\w* (ужас|плох|нет|не )|не отвечают|долго (ждал|чинил|везли)|запчаст\w* (нет|ждать|ждали)|не советую|не рекомендую|не берите|хлипк|слаб(ый|ая|о)|"
         r"дует|сквозн|холодн\w* (воздух|приток)|не справляет|не тянет|воняет|запах")
ADS = r"нашей компании|наша компания|мы предлагаем|представил[аи]? |купить|цена от|артикул|\d{3}-\d{3}-\d{2}|скидк|акци[яи] |в наличии|доставк"
NEGATED = (r"без (лишнего )?(шум\w*|проблем\w*|нарекани\w*|сбо\w*|поломок)|не (шумит|гудит|свистит|обмерза\w*|замерза\w*|теч[её]т|ломал\w*|сломал\w*)|"
           r"нет (никаких )?(проблем|нареканий|шума)|(решил\w*|решен\w*|решает) проблем\w*|проблем\w* (нет|не было|не возникал\w*|никогда не)")
THEME_MINUS = {"шум и вибрация": r"шум(?!о)|гудит|(?<![а-яё])гул(?!яр|ир|ят)|свист|вибрац", "зима: обмерзание, холодный приток": r"обмерза|замерза|(?<![а-яё])л[её]д(?:[ауе]|ом|ян\w*)?(?![а-яё])|холодн\w* (воздух|приток)|(?<![а-яё])дует",
               "конденсат и течи": r"конденсат|теч[её]т|протек|капа", "поломки и электроника": r"сломал|полом|вышел из строя|вышла из строя|плат|сгорел|ошибк|глюч|зависа|перестал",
               "сервис и запчасти": r"сервис|не отвечают|запчаст|гаранти|долго (ждал|чинил)", "цена": r"дорог|переплат|цен", "качество сборки": r"брак|хлипк|качеств|сборк",
               "не справляется с задачей": r"не справляет|не тянет|слаб|мощност"}
THEME_PLUS = {"тихая работа": r"тих|бесшумн|не слышно", "надёжность": r"надежн|надёжн|ни разу не|без проблем|работает (уже|без|стабильно)",
              "сервис и поддержка": r"сервис|поддерж|грамотн|оперативн|быстро", "цена и окупаемость": r"цен|экономи|окупил|адекватн",
              "качество и продуманность": r"качествен|продуман|удобн|сборк", "свежий воздух, комфорт": r"свеж|дышится|комфорт|влажност"}


def get2(u: str) -> str:
    """как list_dossier.get, но с кодировкой страницы (iXBT и старые форумы — windows-1251, проверено 04.10)"""
    import urllib.request
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128 Safari/537.36",
                                                                         "Accept-Language": "ru"}), timeout=25)
        b = r.read()
        m = re.search(rb"charset=[\"']?([\w-]+)", b[:3000])
        cs = r.headers.get_content_charset() or (m.group(1).decode() if m else "utf-8")
        return b.decode(cs if cs.lower() not in ("utf8",) else "utf-8", "ignore")
    except Exception:
        return ""


def fallback(h: str, alias: str) -> list:
    """страница без известной вёрстки: абзацы и блоки, где назван бренд (отзывы магазинов, iXBT, блоги)"""
    s = BeautifulSoup(h or "", "html.parser")
    for x in s(["script", "style", "nav", "header", "footer", "noscript"]):
        x.decompose()
    out = []
    for d in s.find_all(["p", "li", "td", "div"]):
        if d.find(["p", "li", "td", "div"]):
            continue
        t = re.sub(r"\s+", " ", d.get_text(" ", strip=True))
        if 60 <= len(t) <= 4000 and re.search(alias, t, re.I):
            out.append(t)
    return list(dict.fromkeys(out))[:60]


def thread_url(u: str) -> str:
    if "abok" in u:
        m = re.search(r"showtopic=(\d+)|/t(\d+)\.html", u)
        return f"https://forum.abok.ru/lofiversion/index.php/t{m.group(1) or m.group(2)}.html" if m else ""
    return re.sub(r"#.*", "", u)


def posts(u: str, h: str) -> list:
    s = BeautifulSoup(h or "", "html.parser")
    if "abok" in u:
        sel, q = "div.postcontent", "div.quotetop, div.quotemain"
    elif "mastergrad" in u:
        sel, q = "div.pagetext", "blockquote, .bbcode_quote, .quote"
    elif "otzovik" in u:
        sel, q = "div.review-body, div.review-plus, div.review-minus, .review-teaser, [itemprop=description]", ""
    elif "irecommend" in u:
        sel, q = "div.reviewText, .description, .smTeaser", ""
    else:
        sel, q = "article, .post, .message, .comment, .review, p", ""
    out = []
    for d in s.select(sel):
        if q:
            for x in d.select(q):
                x.decompose()
        t = re.sub(r"\s+", " ", d.get_text(" ", strip=True))
        if 40 <= len(t):
            out.append(t[:4000])
    return out


def fetch(fn: str):
    res = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    got = json.loads((DL / fn).read_text(encoding="utf-8"))
    jobs = {}
    for r in got:
        for i in r["items"]:
            u = thread_url(i["url"])
            if u and re.search(OK_HOST, u, re.I):
                jobs.setdefault(u, {"бренды": set(), "заголовок": i["title"], "сниппет": i["snippet"]})["бренды"].add(r["пункт"])
    todo = [u for u in jobs if (u not in res or not res[u]["посты"]) and "forumhouse" not in u]
    print(f"страниц {len(jobs)} (ForumHouse {sum('forumhouse' in u for u in jobs)}), загрузить {len(todo)}", flush=True)
    for u, v in jobs.items():  # ForumHouse — заготовка, сообщения придут из Chrome
        if "forumhouse" in u and u not in res:
            res[u] = {"бренды": sorted(v["бренды"]), "заголовок": v["заголовок"], "сниппет": v["сниппет"], "посты": []}

    def one(u):
        time.sleep(0.5)
        h = get2(u)
        p = posts(u, h)
        if not p:  # своя вёрстка у сайта — абзацы с брендом
            alias = "|".join(ALIAS.get(b, re.escape(b)) for b in jobs[u]["бренды"])
            p = fallback(h, alias)
        return u, p
    with ThreadPoolExecutor(6) as pool:
        for n, fu in enumerate(as_completed([pool.submit(one, u) for u in todo]), 1):
            u, p = fu.result()
            res[u] = {"бренды": sorted(jobs[u]["бренды"]), "заголовок": jobs[u]["заголовок"], "сниппет": jobs[u]["сниппет"], "посты": p}
            if n % 20 == 0 or n == len(todo):
                RAW.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"  {n} из {len(todo)}, сообщений {sum(len(x['посты']) for x in res.values())}", flush=True)
    RAW.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    fh = sorted(u for u in res if "forumhouse" in u)
    (ROOT / "data/raw/fh_konk_urls.json").write_text(json.dumps([u.replace("https://www.forumhouse.ru", "") for u in fh]), encoding="utf-8")
    print("ForumHouse-страниц для Chrome:", len(fh))


def add_fh(fn: str):
    res = json.loads(RAW.read_text(encoding="utf-8"))
    fh = json.loads((DL / fn).read_text(encoding="utf-8"))
    for u, p in fh.items():
        u = u if u.startswith("http") else "https://www.forumhouse.ru" + u
        if u in res:
            res[u]["посты"] = p
    RAW.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print("ForumHouse сообщений:", sum(len(p) for p in fh.values()))


def sentences(t: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", t) if 25 <= len(s.strip()) <= 350]


def analyze():
    import pandas as pd
    res = json.loads(RAW.read_text(encoding="utf-8"))
    svod, allrows = {}, []
    for brand, rx in ALIAS.items():
        seen, plus, minus, mixed, srcs, n_posts = set(), [], [], [], {}, 0
        for u, v in res.items():
            # страница не прочиталась (Отзовик — проверка «Вы робот?», её не обходим) — берём отрывок из выдачи Яндекса
            for p in (v["посты"] or [re.sub(r"^.*?›", "", v.get("сниппет", ""))]):
                if not re.search(rx, p, re.I):
                    continue
                n_posts += 1
                host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
                ss = sentences(p)
                idx = [k for k, s in enumerate(ss) if re.search(rx, s, re.I)]
                near = {k2 for k in idx for k2 in (k - 1, k, k + 1) if 0 <= k2 < len(ss)}  # фраза с брендом и соседние
                for k in sorted(near):
                    s = ss[k]
                    if s in seen:
                        continue
                    if s.rstrip().endswith("?") or re.search(ADS, s, re.I):  # вопрос и реклама продавца — не мнение (проверено глазами 04.10)
                        continue
                    neg = re.sub(NEGATED, " ", s, flags=re.I)  # «без шума», «не гудит», «нет проблем», «решил проблему» — это не минус
                    pl = bool(re.search(PLUS, s, re.I)) or neg != s
                    mn = bool(re.search(MINUS, neg, re.I))
                    if not (pl or mn):
                        continue
                    seen.add(s)
                    srcs[host] = srcs.get(host, 0) + 1
                    item = {"фраза": s, "где": host, "ссылка": u}
                    (mixed if pl and mn else plus if pl else minus).append(item)
        for kind, items in (("плюс", plus), ("минус", minus), ("и плюс, и минус", mixed)):
            for i in items:
                T = THEME_PLUS if kind == "плюс" else THEME_MINUS
                allrows.append({"конкурент": brand, "оценка": kind, "тема": ", ".join(t for t, r in T.items() if re.search(r, i["фраза"], re.I)),
                                "фраза": i["фраза"], "где": i["где"], "ссылка": i["ссылка"]})
        th = lambda items, T: {t: [i for i in items if re.search(r, i["фраза"], re.I)] for t, r in T.items()}
        tm, tp = th(minus + mixed, THEME_MINUS), th(plus + mixed, THEME_PLUS)
        pick = lambda xs: [x["фраза"][:260] for x in sorted(xs, key=lambda x: (not re.search(rx, x["фраза"], re.I), len(x["фраза"])))[:3]]
        svod[brand] = {"сообщений с брендом": n_posts, "плюсов": len(plus), "минусов": len(minus), "смешанных": len(mixed), "площадки": dict(sorted(srcs.items(), key=lambda kv: -kv[1])[:6]),
                       "минусы по темам": {t: {"сколько": len(v), "цитаты": pick(v)} for t, v in sorted(tm.items(), key=lambda kv: -len(kv[1])) if v},
                       "плюсы по темам": {t: {"сколько": len(v), "цитаты": pick(v)} for t, v in sorted(tp.items(), key=lambda kv: -len(kv[1])) if v},
                       "минусы цитаты": pick(minus), "плюсы цитаты": pick(plus)}
        print(f"{brand:22} сообщений {n_posts:4} | плюсов {len(plus):3} минусов {len(minus):3} смеш {len(mixed):3} | "
              + ", ".join(f"{t} {len(v)}" for t, v in sorted(tm.items(), key=lambda kv: -len(kv[1]))[:3] if v), flush=True)
    SVOD.write_text(json.dumps(svod, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(allrows).to_csv(ROOT / "data/lists/konkurenty_otzyvy_forumy.tsv", sep="	", index=False)
    print("всего высказываний с оценкой:", len(allrows))


if __name__ == "__main__":
    {"fetch": lambda: fetch(sys.argv[2]), "fh": lambda: add_fh(sys.argv[2]), "analyze": analyze}[sys.argv[1]]()
