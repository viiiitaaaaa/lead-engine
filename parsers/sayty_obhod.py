"""Обход сайтов партнёров, всех монтажников и конкурентов (её задача 04.10): одна загрузка — три пользы.
С каждого сайта: главная + до 20 внутренних страниц (о компании, услуги, каталог, бренды, проекты, контакты, реквизиты,
политика конфиденциальности/оферта — там часто ИНН). Сохраняет: заголовки (title, h1–h3), meta description/keywords,
текст (до 80 тыс. знаков), телефоны, почты, ИНН.
→ проверка «ставит чужое» (partnery_proverka.py) и ключевые слова (klyuchevye_slova.py).

python parsers/sayty_obhod.py
Итог: data/raw/sayty_obhod.json = {сайт: {группа, пункт, страниц, заголовки, мета, текст, телефоны, почты, ИНН}}
"""
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from build_base import domain
from list_dossier import get
from yandex_maps_bd import ROOT

OUT = ROOT / "data/raw/sayty_obhod.json"
PAGES = (r"о-компании|o-kompanii|about|o-nas|о-нас|company|kompani|rekvizit|реквизит|contact|kontakt|контакт|uslug|услуг|service|"
         r"katalog|catalog|каталог|brand|бренд|proizvod|оборудован|oborudovan|product|produkc|project|proekt|проект|portfolio|"
         r"objects|obekt|работы|raboty|politik|privacy|konfiden|oferta|оферт|montazh|монтаж|ventil|вентил|bassein|бассейн|klimat|климат")
PHONE = r"(?:\+7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"
MAIL = r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.(?:ru|com|рф|su|net|org|moscow|pro|info|biz)"
MAIL_JUNK = r"example|domain|sentry|wixpress|\.png|\.jpg|\.webp|ivanov|test@|email@|mail@mail|your|name@"


def text(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>|<[^>]+>", " ", h, flags=re.S | re.I))).strip()


def heads(h: str) -> list:
    out = [text(x) for x in re.findall(r"<(?:title|h1|h2|h3)[^>]*>(.*?)</(?:title|h1|h2|h3)>", h, re.S | re.I)]
    return [x for x in out if 3 <= len(x) <= 160]


def one(site: str) -> dict:
    root = (re.match(r"https?://[^/]+", site if "://" in site else "https://" + site) or [None])[0]
    if not root:
        return {"ответ": "нет сайта"}
    first = get(root) or get(root.replace("https://", "http://"))
    if not first:
        return {"ответ": "недоступен"}
    links = {urljoin(root, x) for x in re.findall(r'href="([^"#]+)"', first)}
    inner = sorted(u for u in links if domain(u) == domain(root) and re.search(PAGES, u, re.I)
                   and not re.search(r"\.(jpe?g|png|pdf|webp|svg|docx?|xlsx?)$|\?|tel:|mailto:", u, re.I))[:20]
    hs = [first] + [get(u) for u in inner]
    hs = [h for h in hs if h]
    raw = " ".join(hs)
    t = " ".join(text(h) for h in hs)
    meta = " ".join(html.unescape(m) for m in re.findall(r'<meta[^>]+name="(?:description|keywords)"[^>]+content="([^"]*)"', raw, re.I))
    phones = sorted({re.sub(r"\D", "", p)[-10:] for p in re.findall(PHONE, t + " " + " ".join(re.findall(r'href="tel:([^"]+)"', raw)))})
    mails = sorted({m.lower() for m in re.findall(MAIL, raw) if not re.search(MAIL_JUNK, m, re.I)})
    inns = sorted(set(re.findall(r"ИНН[\s:/№]*(?:/\s*КПП)?[\s:]*(\d{10}|\d{12})(?!\d)", t)))
    return {"ответ": "ок", "страниц": len(hs), "заголовки": sorted({x for h in hs for x in heads(h)})[:200], "мета": meta[:3000],
            "текст": t[:80000], "телефоны": ["+7" + p for p in phones if len(p) == 10][:8], "почты": mails[:8], "ИНН": inns[:5]}


def main():
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    jobs = {}
    for grp, f in (("монтажники", "dossier_montazhniki.json"), ("конкуренты", "dossier_konkurenty.json")):
        for n, v in json.loads((ROOT / "data/raw" / f).read_text(encoding="utf-8")).items():
            s = next((x.get("сайт") for x in v["сайты"] if x.get("сайт")), "")
            if s:
                jobs[s] = {"группа": grp, "пункт": n, "партнёр?": bool(v.get("партнёр?"))}
    jobs.setdefault("https://frivent.ru", {"группа": "мы", "пункт": "Frivent", "партнёр?": False})
    # с 04.10 конкуренты — только европейские марки (data/lists/konkurenty.tsv) и их русские сайты представителей;
    # старые 26 (бризеры, дилеры, магазины) — «игроки рынка», в «у конкурентов» не считаются
    for s, v in res.items():
        if s in jobs:
            v.update(jobs[s])
        elif v.get("группа") == "конкуренты":
            v["группа"] = "игроки рынка"
    todo = [s for s in jobs if s not in res]
    print(f"сайтов {len(jobs)}, осталось {len(todo)}", flush=True)
    with ThreadPoolExecutor(8) as pool:
        futs = {pool.submit(one, s): s for s in todo}
        for n, fu in enumerate(as_completed(futs), 1):
            s = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                r = {"ответ": f"ошибка {e}"}
            res[s] = {**jobs[s], **r}
            if n % 10 == 0 or n == len(todo):
                OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                print(f"сделано {n} из {len(todo)}", flush=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
