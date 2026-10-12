"""Проверка битых ссылок по всем страницам (находки 12.10, CodeGuard Python/1026: requests + BeautifulSoup).

Запуск: python site/check_links.py [адрес-сайта]   (по умолчанию — превью https://viiiitaaaaa.github.io/frivent-preview/)
Проверяет на каждой странице из site/*.html (кроме служебных _*.html):
  - ссылки <a href> на свои страницы и файлы (PDF, картинки) — отвечает ли сервер 200;
  - якоря #id — есть ли такой id на странице, куда ведёт ссылка;
  - картинки, srcset, стили, скрипты, значки;
  - внешние ссылки (если появятся) — отвечают ли вообще; на сайте их быть не должно (её решение 10.10: без контактов и ссылок наружу),
    поэтому каждая внешняя ссылка печатается отдельно — для проверки глазами.
Итог: список «страница → что сломано». Код выхода 1, если есть битые.
"""
import sys
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://viiiitaaaaa.github.io/frivent-preview/").rstrip("/") + "/"
SITE = Path(__file__).resolve().parent
pages = sorted(p.name for p in SITE.glob("*.html") if not p.name.startswith("_"))
S = requests.Session()
S.headers["User-Agent"] = "frivent-link-check/1.0"
status, ids = {}, {}


def fetch(url):
    if url not in status:
        try:
            r = S.get(url, timeout=20, allow_redirects=True)
            status[url] = r.status_code
            if r.ok and "html" in r.headers.get("content-type", ""):
                ids[url] = {t.get("id") for t in BeautifulSoup(r.text, "html.parser").find_all(id=True)}
        except requests.RequestException as e:
            status[url] = f"нет ответа ({type(e).__name__})"
    return status[url]


broken, external = {}, set()
for name in pages:
    page = urljoin(BASE, name)
    if fetch(page) != 200:
        broken.setdefault(name, []).append(f"сама страница: {status[page]}")
        continue
    html = S.get(page, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")
    refs = [("a", a["href"]) for a in soup.find_all("a", href=True)]
    refs += [("img", t["src"]) for t in soup.find_all(["img", "script"], src=True)]
    refs += [("link", t["href"]) for t in soup.find_all("link", href=True) if "canonical" not in (t.get("rel") or [])]
    for t in soup.find_all("source", srcset=True):
        refs += [("srcset", part.strip().split(" ")[0]) for part in t["srcset"].split(",") if part.strip()]
    for kind, ref in refs:
        if ref.startswith(("mailto:", "tel:", "javascript:", "data:")):
            if ref.startswith(("mailto:", "tel:")):
                broken.setdefault(name, []).append(f"{kind}: {ref} — контакт на сайте (её решение 10.10: только через заявку)")
            continue
        url, frag = urldefrag(urljoin(page, ref))
        if not url.startswith(BASE):
            external.add(url)
            code = fetch(url)
            if code != 200:
                broken.setdefault(name, []).append(f"{kind} наружу: {ref} → {code}")
            continue
        code = fetch(url)
        if code != 200:
            broken.setdefault(name, []).append(f"{kind}: {ref} → {code}")
        elif frag and kind == "a" and url in ids and frag not in ids[url]:
            broken.setdefault(name, []).append(f"якорь: {ref} — на странице нет id «{frag}»")

print(f"проверено страниц: {len(pages)}, адресов: {len(status)}")
for u in sorted(external):
    print("ссылка наружу:", u)
for name, errs in broken.items():
    print(name)
    for e in sorted(set(errs)):
        print("   ", e)
print("битых нет" if not broken else f"страниц с битыми: {len(broken)}")
sys.exit(1 if broken else 0)
