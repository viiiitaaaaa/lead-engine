"""Полное досье по её списку (компании и посёлки): «надо собрать ВСЁ — отзывы, статьи, вопросы, клиенты, информация».

По каждому пункту:
  1) сайт (до 15 страниц: о компании, реквизиты, контакты, проекты/портфолио/объекты, отзывы): ИНН, описание, соцсети и
     мессенджеры, проекты/клиенты (упоминания посёлков и «КП …»), число проектов в портфолио;
  2) ЕГРЮЛ (egrul.nalog.ru, бесплатно): юрлицо, ИНН, ОГРН, руководитель, дата регистрации, статус — по ИНН с сайта,
     иначе по названию (тогда «проверить»: бывают тёзки);
  3) поиск Яндекса (Bright Data): отзывы на других площадках, статьи и новости, вопросы и обсуждения (форумы, FORUMHOUSE),
     клиенты/кейсы, выручка по ИНН (сниппеты справочников);
  4) уже собранное: все контакты (spisok_kontakty.tsv), отзывы Яндекс Карт и жалобы, дизайн-разбор, подрядчики в посёлках,
     Instagram, сводка посёлков.
python parsers/list_dossier.py           # всё (продолжает с места: data/raw/dossier_partial.json)
python parsers/list_dossier.py --group developers --no-search   # без поиска Яндекса (нет денег на Bright Data): сайт + ЕГРЮЛ
python parsers/list_dossier.py --research --group developers     # потом добрать поиск у пунктов, где он пустой
Итог: data/raw/dossier.json; панель — блок «Ваш список — досье».
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import pandas as pd

from build_base import DRIVE, domain
from design_bureaus import PLACES
from list_contacts import BROKERS, items as list_items
from yandex_maps_bd import ROOT, env
from yandex_search_bd import REGISTRY, serp

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36", "Accept-Language": "ru"}
PAGES = r"о-компании|o-kompanii|about|о-нас|company|rekvizit|реквизит|contact|kontakt|контакт|project|proekt|проект|portfolio|портфолио|objects|объект|works|raboty|работы|кейс|cases|клиент|client|отзыв|otzyv|review"
SOC = {"ВКонтакте": r"https?://(?:m\.)?vk\.(?:com|ru)/[A-Za-z0-9_.]+", "Telegram": r"https?://t\.me/[A-Za-z0-9_+]{4,}",
       "WhatsApp": r"https?://(?:wa\.me|api\.whatsapp\.com/send|chat\.whatsapp\.com)/[^\s\"'<>]+", "Instagram": r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+",
       "YouTube": r"https?://(?:www\.)?youtube\.com/(?:@|channel/|c/|user/)[A-Za-z0-9_\-.]+", "Дзен": r"https?://dzen\.ru/[A-Za-z0-9_\-.]+",
       "Одноклассники": r"https?://ok\.ru/[A-Za-z0-9_\-./]+", "Rutube": r"https?://rutube\.ru/channel/\d+"}
REVIEW_SITES = r"otzovik|irecommend|zoon|yell|flamp|2gis|google\.\w+/maps|profi\.ru|forumhouse|otzyvy|otziv|pravda-sotrudnikov|dreamjob|spr\.ru|orgpage|vashe-mnenie|houzz|otzovik"
FORUMS = r"forumhouse|forum|otvet\.mail|yandex\.ru/q/|pikabu|vc\.ru|dzen\.ru|reddit|banki\.ru|ask|vopros|thread|topic"
MEDIA_NOT = REGISTRY + r"|yandex\.|avito|cian|domclick|hh\.ru|zoon|yell|2gis|otzovik|flamp|youtube|vk\.com|t\.me|instagram"


def get(u: str, timeout=20) -> str:
    try:
        return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout).read().decode("utf-8", "ignore")
    except Exception:
        return ""


def text(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>|<[^>]+>", " ", h, flags=re.S | re.I))).strip()


PREMIUM = r"премиум|premium|элитн|резиденц|особняк|усадьб|вилл[аыу]|загородн\w* дом|коттедж|бассейн|спа-зон|(?:от|более)\s*\d{3,4}\s*(?:м2|м²|кв\.?\s*м)"
MASS = r"квартир|бризер|бытов\w* кондиционер|сплит-систем\w* от \d|недорог|дешев|эконом"


SOC_JUNK = r"vk\.(com|ru)/(js|rtrg|video_ext\.php|video|share\.php|group|privacy|widget\w*|app\d+_?|away|wall|photo|feed)\b|t\.me/(share|joinchat|\+)|dzen\.ru/(id|embed|a)/?$|vk\.(com|ru)/?$"


def site_info(site: str) -> dict:
    root = (re.match(r"https?://[^/]+", site if "://" in site else "https://" + site) or [None])[0]
    if not root:
        return {}
    first = get(root) or get(root.replace("https://", "http://"))
    if not first:
        return {"сайт": root, "ответ": "недоступен"}
    links = {urljoin(root, h) for h in re.findall(r'href="([^"#]+)"', first)}
    inner = [u for u in links if domain(u) == domain(root) and re.search(PAGES, u, re.I) and not re.search(r"\.(jpe?g|png|pdf|webp)$", u, re.I)]
    hs = [first] + [get(u) for u in sorted(inner)[:14]]
    raw = " ".join(hs)
    t = " ".join(text(h) for h in hs)
    desc = html.unescape((re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', first, re.I) or [None, ""])[1])
    title = text((re.search(r"<title[^>]*>(.*?)</title>", first, re.S | re.I) or [None, ""])[1])
    inns = re.findall(r"ИНН[\s:/№]*(?:/\s*КПП)?[\s:]*(\d{10}|\d{12})(?!\d)", t)
    places = sorted(set(m.lower() for m in re.findall(PLACES, t, re.I)))
    kp = sorted(set(re.findall(r"(?:КП|коттеджн\w* пос[её]лк\w*)\s*[«\"]([^»\"]{3,40})[»\"]", t)))[:25]
    proj = len({u for u in links if re.search(r"project|proekt|portfolio|objects|works|cases|кейс", u, re.I)})
    # служебные ссылки (счётчики, виджеты, «поделиться») — не соцсети компании (проверка 03.10)
    soc = {k: sorted(set(m.rstrip("/.,") for m in re.findall(p, raw) if not re.search(SOC_JUNK, m, re.I)))[:3] for k, p in SOC.items()}
    return {"сайт": root, "ответ": "ок", "заголовок": title[:150], "описание": desc[:300], "ИНН с сайта": sorted(set(inns))[:3],
            "упоминает наши места": places, "КП в тексте": kp, "страниц проектов": proj,
            "соцсети": {k: v for k, v in soc.items() if v}, "страниц прочитано": len(hs),
            "премиум-слова": len(re.findall(PREMIUM, t, re.I)), "масс-слова": len(re.findall(MASS, t, re.I)),
            "премиум примеры": sorted(set(m.lower() for m in re.findall(PREMIUM, t, re.I)))[:10]}


def egrul(query: str) -> list:
    """ЕГРЮЛ ФНС: до 5 записей по ИНН или названию (Москва и область)"""
    def req(u, data=None):
        r = urllib.request.Request(u, data=urllib.parse.urlencode(data).encode() if data else None, headers={**H, "X-Requested-With": "XMLHttpRequest"})
        return json.loads(urllib.request.urlopen(r, timeout=40).read().decode("utf-8"))
    for n in range(3):
        try:
            t = req("https://egrul.nalog.ru/", {"query": query, "region": "" if query.isdigit() else "77,50", "PreventChromeAutocomplete": ""})
            time.sleep(1.5)
            rows = req(f"https://egrul.nalog.ru/search-result/{t['t']}").get("rows", [])
            return [{"юрлицо": r.get("n", ""), "ИНН": r.get("i", ""), "ОГРН": r.get("o", ""), "руководитель": r.get("g", ""),
                     "регистрация": r.get("r", ""), "ликвидировано": r.get("e") or "", "адрес": r.get("a") or ""} for r in rows[:5]]
        except Exception:
            time.sleep(5 * (n + 1))
    return []


def found(items: list, kind: str) -> list:
    return [{"заголовок": i["title"][:140], "ссылка": i["url"], "сниппет": i["snippet"][:260], "вид": kind} for i in items]


def brand_keys(name: str, si: list, legal: dict) -> set:
    """как ещё называют этот пункт: название из списка, бренд из заголовка сайта, домен, юрлицо — для отсева тёзок"""
    from villages_merge import key
    ks = {key(name)}
    for s in si:
        if s.get("сайт"):
            ks.add(re.sub(r"[^a-z0-9]", "", domain(s["сайт"]).split(".")[0]))
        if s.get("заголовок"):
            ks.add(key(re.split(r"\s[-–—|]\s|:", s["заголовок"])[0]))
    if legal.get("юрлицо"):
        ks.add(key(re.sub(r"ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ|АКЦИОНЕРНОЕ ОБЩЕСТВО|ООО|АО", "", legal["юрлицо"])))
    return {k for k in ks if len(k) >= 4}


def search(name: str, vid: str, inn: str, token: str, keys: set, alt: str = "") -> dict:
    from villages_merge import key
    tag = "коттеджный поселок" if vid == "посёлок" else ""
    q0 = f'"{name}"' + (f' OR "{alt}"' if alt and alt.lower() != name.lower() else "")
    qs = {"отзывы": f"{q0} {tag} отзывы", "статьи": f"{q0} {tag} статья новости интервью",
          "вопросы": f"{q0} {tag} форум вопрос forumhouse", "клиенты": f"{q0} {tag} проект построили клиент кейс"}
    if inn:
        qs["выручка"] = f"ИНН {inn} выручка сотрудники"
    with ThreadPoolExecutor(len(qs)) as pool:  # запросы одного пункта — параллельно
        got = dict(zip(qs, pool.map(lambda q: serp(q, token) or [], qs.values())))
    out = {}
    for k, raw in got.items():
        items = [i for i in raw if "yabs.yandex" not in i["url"] and "yandex.ru/an/" not in i["url"]]
        if k != "выручка":  # отсев тёзок: в результате должен быть бренд/домен/юрлицо именно этого пункта
            items = [i for i in items if any(kk in key(i["title"] + " " + i["snippet"]) or kk in re.sub(r"[^a-z0-9]", "", i["url"].lower())
                                             for kk in keys)]
        if k == "отзывы":
            items = [i for i in items if re.search(REVIEW_SITES, i["url"], re.I) or re.search(r"отзыв", i["title"], re.I)]
        elif k == "статьи":
            items = [i for i in items if not re.search(MEDIA_NOT, i["url"], re.I)]
        elif k == "вопросы":
            items = [i for i in items if re.search(FORUMS, i["url"], re.I)]
        elif k == "выручка":
            items = [i for i in items if re.search(r"выручк|оборот|сотрудник|прибыл", i["snippet"], re.I)]
        out[k] = found(items[:8], k)
    rev = " ".join(i["сниппет"] for i in out.get("выручка", []))
    m = re.search(r"[Вв]ыручка[^.]{0,60}?(\d[\d\s,.]*\s*(?:млрд|млн|тыс)\.?\s*(?:руб|₽)?)", rev)
    out["выручка кратко"] = m.group(1).strip() if m else ""
    m = re.search(r"(\d+)\s*сотрудник", rev)
    out["сотрудников"] = m.group(1) if m else ""
    return out


def one(it: dict, token: str) -> dict:
    sites = [s for s in it["сайты"] if not re.search(BROKERS, s, re.I)][:3]
    si = [site_info(s) for s in sites]
    inn = next((i for s in si for i in s.get("ИНН с сайта", [])), "")
    # --no-egrul: сначала только сайты (налоговая тормозит при 8 потоках, 04.10), ЕГРЮЛ потом добирает --egrul у нужных
    eg = [] if "--no-egrul" in sys.argv else (egrul(inn) if inn else (egrul(re.sub(r"^группа компаний\s+", "", it["пункт"], flags=re.I)) if it["вид"] == "компания" else []))
    eg_active = [e for e in eg if not e["ликвидировано"]]
    # юрлицо — только по ИНН с сайта; одно совпадение по названию часто тёзка (АО «Конти» кондитер, ГСК №54 — проверка 03.10) → кандидат
    legal = eg_active[0] if inn and eg_active else {}
    cand = eg_active[0] if not inn and len(eg_active) == 1 else {}
    note = "по ИНН с сайта" if legal else ("по названию нашлось одно юрлицо — НЕ подтверждено (часто тёзка), нужен ИНН с сайта или договора" if cand
                                          else (f"тёзки: {len(eg_active)} действующих" if eg_active else ""))
    alt = next((re.split(r"\s[-–—|]\s|:", x["заголовок"])[0].strip() for x in si if x.get("заголовок")), "")
    # --no-search: без поиска Яндекса (Bright Data без денег) — сайт, ЕГРЮЛ; поиск потом добирает --research
    s = {} if "--no-search" in sys.argv else search(it["пункт"], it["вид"], legal.get("ИНН", "") or inn, token,
                                                   brand_keys(it["пункт"], si, legal), alt[:40])
    extra = {k: it[k] for k in ("рубрики", "адреса", "отзывов 2ГИС") if k in it}
    return {**extra, "пункт": it["пункт"], "вид": it["вид"], "посёлки": it["посёлки"], "сайты": si, "юрлицо": legal, "юрлицо-кандидат": cand, "юрлицо: как найдено": note,
            "тёзки ЕГРЮЛ": eg_active[:5] if not legal else [], **s}


def research() -> None:
    """повторить только поиск Яндекса у пунктов, где он пришёл пустым (Bright Data сбоил), медленнее; сайт и юрлицо не трогаем"""
    grp = sys.argv[sys.argv.index("--group") + 1] if "--group" in sys.argv else ""
    f = ROOT / f"data/raw/dossier{'_' + grp if grp else ''}.json"
    res = json.loads(f.read_text(encoding="utf-8"))
    token = env("BRIGHTDATA_API_TOKEN")
    empty = [v for v in res.values() if not any(v.get(k) for k in ("отзывы", "статьи", "вопросы", "клиенты"))]
    print(f"пустой поиск у {len(empty)} из {len(res)}", flush=True)

    def redo(v):
        si, legal = v["сайты"], v["юрлицо"]
        alt = next((re.split(r"\s[-–—|]\s|:", x["заголовок"])[0].strip() for x in si if x.get("заголовок")), "")
        return v["пункт"], search(v["пункт"], v["вид"], legal.get("ИНН", ""), token, brand_keys(v["пункт"], si, legal), alt[:40])
    with ThreadPoolExecutor(2) as pool:
        for n, (name, s) in enumerate(pool.map(redo, empty), 1):
            res[name].update(s)
            f.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            print(f"повтор: сделано {n} из {len(empty)}", flush=True)


def group_items(g: str) -> list:
    """важные группы базы: premium — 61 бюро «загородный премиум», contractors — подрядчики в посёлках, developers — застройщики посёлков"""
    L = ROOT / "data/lists"
    if g == "premium":
        d = pd.read_csv(L / "dizain_byuro.tsv", sep="\t", dtype=str).fillna("")
        d = d[d["группа"].str.startswith("1.")]
        return [{"пункт": r["бюро"][:80], "вид": "компания", "посёлки": r["наши места"], "сайты": [r["сайт"]], "known": []} for _, r in d.iterrows()]
    if g == "contractors":
        d = pd.read_csv(L / "podryadchiki_poselkov.tsv", sep="\t", dtype=str).fillna("")
        d = d[d["сомнительно"] != "True"]
        return [{"пункт": r["сайт"], "вид": "компания", "посёлки": r["посёлки"][:200], "сайты": [r["сайт"]], "known": []} for _, r in d.iterrows()]
    if g == "developers":
        d = pd.read_csv(L / "cian_poselki.tsv", sep="\t", dtype=str).fillna("")
        d = d[d["застройщик"].str.strip() != ""]
        out = {}
        for _, r in d.iterrows():
            e = out.setdefault(r["застройщик"].strip(), {"пункт": r["застройщик"].strip(), "вид": "компания", "посёлки": [], "сайты": [], "known": []})
            e["посёлки"].append(r["посёлок"])
            if r["сайт"] and r["сайт"] not in e["сайты"]:
                e["сайты"].append(r["сайт"])
        return [{**e, "посёлки": ", ".join(e["посёлки"])[:200]} for e in out.values()]
    if g == "montazhniki":  # монтажники вентиляции, климата, отопления, воды и бассейнов (2ГИС) — кандидаты в партнёры
        from klimat_boli import ENG_RUB, NOT_NAME, NOT_RUB
        d = json.loads((ROOT / "data/raw/klimat_montazhniki.json").read_text(encoding="utf-8"))
        out = {}
        for c in d.values():
            if not c.get("сайт") or not re.search(ENG_RUB, c["рубрики"]) or re.search(NOT_RUB, c["рубрики"]) or re.search(NOT_NAME, c["название"], re.I):
                continue
            e = out.setdefault(domain(c["сайт"]), {"пункт": re.split(r",\s", c["название"])[0][:80], "вид": "компания", "посёлки": "",
                                                    "сайты": [c["сайт"]], "known": [], "рубрики": c["рубрики"][:200], "адреса": [], "отзывов 2ГИС": 0})
            e["адреса"].append(c["адрес"])
            e["отзывов 2ГИС"] += c["отзывов"]
        return list(out.values())
    if g == "konkurenty":  # конкуренты Frivent (её задача 04.10 «конкурентов тоже собирай»): data/lists/konkurenty.tsv
        d = pd.read_csv(L / "konkurenty.tsv", sep="	", dtype=str).fillna("")
        return [{"пункт": r["конкурент"], "вид": "компания", "посёлки": "", "сайты": [r["сайт"]], "known": [], "рубрики": f"{r['тип']} · {r['страна бренда']}"}
                for _, r in d.iterrows()]
    raise SystemExit("группа: premium | contractors | developers | montazhniki | konkurenty")


def main():
    if "--research" in sys.argv:
        return research()
    grp = sys.argv[sys.argv.index("--group") + 1] if "--group" in sys.argv else ""
    its = group_items(grp) if grp else list_items()
    token = env("BRIGHTDATA_API_TOKEN")
    part = ROOT / f"data/raw/dossier{'_' + grp if grp else ''}_partial.json"
    res = json.loads(part.read_text(encoding="utf-8")) if part.exists() else {}
    todo = [i for i in its if i["пункт"] not in res]
    print(f"пунктов {len(its)}, осталось {len(todo)}", flush=True)
    t0 = time.time()
    th = int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else (8 if "--no-search" in sys.argv else 3)
    with ThreadPoolExecutor(th) as pool:  # 3 пункта × до 5 запросов = ≤15 одновременно к Bright Data
        futs = [pool.submit(one, i, token) for i in todo]  # по готовности: медленный сайт не держит остальных (04.10)
        for n, fu in enumerate(as_completed(futs), 1):
            r = fu.result()
            res[r["пункт"]] = r
            part.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            if n % 5 == 0 or n == len(todo):
                print(f"сделано {n} из {len(todo)}, осталось ≈{(time.time() - t0) / n * (len(todo) - n) / 60:.0f} мин", flush=True)
    out = ROOT / f"data/raw/dossier{'_' + grp if grp else ''}.json"
    out.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    part.unlink(missing_ok=True)
    v = list(res.values())
    print(f"готово {len(v)}: юрлицо {sum(bool(x['юрлицо']) for x in v)}, отзывы-ссылки {sum(len(x.get('отзывы', [])) for x in v)}, "
          f"статьи {sum(len(x.get('статьи', [])) for x in v)}, вопросы {sum(len(x.get('вопросы', [])) for x in v)}, "
          f"клиенты {sum(len(x.get('клиенты', [])) for x in v)}, соцсети у {sum(any(s.get('соцсети') for s in x['сайты']) for x in v)}")


if __name__ == "__main__":
    main()
