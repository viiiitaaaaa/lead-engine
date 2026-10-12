"""Проверка сайта по фазам агента design-review: все страницы × 3 ширины.
Ищет: ошибки консоли, битые запросы (4xx/5xx), битые картинки, горизонтальную прокрутку,
вылезающие элементы, мелкий текст на телефоне, мелкие кнопки, картинки без alt, поля без подписи,
битые внутренние ссылки и якоря. Скрины телефона — в shots/."""
import json, re, sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://viiiitaaaaa.github.io/frivent-preview/"
SITE = Path(sys.argv[2]) if len(sys.argv) > 2 else None
OUT = Path(__file__).parent
(OUT / "shots").mkdir(exist_ok=True)
VIEWS = {"desktop": (1440, 900), "tablet": (768, 1024), "mobile": (375, 812)}

pages = sorted(p.name for p in SITE.glob("*.html")) if SITE else ["index.html"]

JS = r"""
() => {
  const W = document.documentElement.clientWidth;
  const r = {scrollW: document.documentElement.scrollWidth, W, overflow: [], small_text: [], small_tap: [],
             no_alt: [], broken_img: [], no_label: [], anchors: []};
  const vis = el => { const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
  const name = el => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
     (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0,2).join('.') : '') +
     ' «' + (el.innerText || el.alt || el.value || '').trim().slice(0, 40).replace(/\s+/g,' ') + '»');
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el)) continue;
    const b = el.getBoundingClientRect();
    // вылезает вправо, и не внутри прокручиваемого/обрезающего контейнера
    if (b.right > W + 2) {
      let p = el.parentElement, clipped = false;
      while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o !== 'visible') { clipped = true; break; } p = p.parentElement; }
      if (!clipped) r.overflow.push(name(el) + ' right=' + Math.round(b.right));
    }
    const s = getComputedStyle(el);
    if (W < 500 && el.childNodes.length && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 2)
        && parseFloat(s.fontSize) < 12) r.small_text.push(name(el) + ' ' + s.fontSize);
    if (W < 500 && el.matches('a,button,input,select,textarea,[role=button]') && (b.height < 32 || b.width < 32))
      r.small_tap.push(name(el) + ' ' + Math.round(b.width) + '×' + Math.round(b.height));
  }
  for (const im of document.images) {
    if (!im.hasAttribute('alt')) r.no_alt.push(im.getAttribute('src'));
    if (im.complete && im.naturalWidth === 0 && im.getAttribute('src') && !im.loading) r.broken_img.push(im.getAttribute('src'));
  }
  for (const f of document.querySelectorAll('input:not([type=hidden]):not([type=submit]),select,textarea')) {
    const ok = (f.id && document.querySelector('label[for="' + f.id + '"]')) || f.closest('label') || f.getAttribute('aria-label') || f.getAttribute('aria-labelledby');
    if (!ok) r.no_label.push(name(f) + ' placeholder=' + (f.placeholder || ''));
  }
  for (const a of document.querySelectorAll('a[href^="#"]')) {
    const id = a.getAttribute('href').slice(1); if (id && !document.getElementById(id)) r.anchors.push('#' + id);
  }
  r.links = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
  r.title = document.title;
  return r;
}
"""

report = {}
with sync_playwright() as pw:
    br = pw.chromium.launch()
    for vname, (w, h) in VIEWS.items():
        ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                             is_mobile=(vname == "mobile"), has_touch=(vname != "desktop"))
        for name in pages:
            pg = ctx.new_page()
            cons, bad = [], []
            pg.on("console", lambda m: cons.append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
            pg.on("pageerror", lambda e: cons.append(f"pageerror: {str(e)[:200]}"))
            pg.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
            pg.on("requestfailed", lambda r: bad.append(f"FAILED {r.url} {r.failure}"))
            pg.goto(urljoin(BASE, name), wait_until="networkidle", timeout=60000)
            # прокрутить до конца, чтобы подгрузились ленивые картинки
            pg.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); } window.scrollTo(0, 0); }")
            pg.wait_for_timeout(800)
            res = pg.evaluate(JS)
            res["console"], res["bad_requests"] = cons, sorted(set(bad))
            if vname == "mobile":
                pg.screenshot(path=str(OUT / "shots" / f"m_{name}.png"), full_page=True)
            if vname == "desktop" and name == "index.html":
                pg.screenshot(path=str(OUT / "shots" / f"d_{name}.png"), full_page=True)
            report.setdefault(name, {})[vname] = res
            pg.close()
        ctx.close()
    br.close()

# битые внутренние ссылки на страницы
names = set(pages)
for name, v in report.items():
    miss = set()
    for href in v["desktop"]["links"]:
        u = urlparse(href)
        if u.scheme or href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        f = u.path.split("/")[-1]
        if f.endswith(".html") and f not in names:
            miss.add(href)
        elif u.path and not f.endswith(".html") and SITE and not (SITE / u.path).exists():
            miss.add(href)
    v["missing_links"] = sorted(miss)
    for vv in ("desktop", "tablet", "mobile"):
        v[vv].pop("links", None)

(OUT / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
# краткая сводка
for name, v in report.items():
    line = []
    for vn in VIEWS:
        r = v[vn]
        if r["scrollW"] > r["W"] + 1: line.append(f"{vn}: гориз.прокрутка {r['scrollW']}>{r['W']}")
        for k in ("overflow", "broken_img", "console", "bad_requests", "anchors", "no_label"):
            if r[k]: line.append(f"{vn}:{k}={len(r[k])}")
        if vn == "mobile":
            for k in ("small_text", "small_tap"):
                if r[k]: line.append(f"mobile:{k}={len(r[k])}")
    if v["missing_links"]: line.append(f"битых ссылок={len(v['missing_links'])}")
    print(name, "|", "; ".join(line) or "ок")
