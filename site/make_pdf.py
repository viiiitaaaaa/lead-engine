# Собирает PDF-памятки (gift_content.py) в site/pdf/ — через Chromium (Playwright), шрифт Vela Sans и палитра сайта.
# Запуск: python site/make_pdf.py
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gift_content import GIFT  # noqa: E402

OUT = HERE / "pdf"
OUT.mkdir(exist_ok=True)
F = (HERE / "fonts").as_uri()

CSS = f"""
@font-face{{font-family:"Vela Sans";src:url({F}/vela-regular.woff2) format("woff2");font-weight:400}}
@font-face{{font-family:"Vela Sans";src:url({F}/vela-medium.woff2) format("woff2");font-weight:500}}
@font-face{{font-family:"Vela Sans";src:url({F}/vela-semibold.woff2) format("woff2");font-weight:600}}
@font-face{{font-family:"Vela Sans";src:url({F}/vela-light.woff2) format("woff2");font-weight:300}}
@page{{size:A4;margin:18mm 18mm 20mm}}
*{{box-sizing:border-box}}
body{{margin:0;font:11pt/1.5 "Vela Sans",Arial,sans-serif;color:#1d1b19;background:#fff}}
.head{{border-bottom:2px solid #6b1a24;padding-bottom:10pt;margin-bottom:14pt;display:flex;justify-content:space-between;align-items:flex-end;gap:20pt}}
.head img{{height:34pt}}
.head .tag{{font-size:8.5pt;letter-spacing:.12em;text-transform:uppercase;color:#394172}}
h1{{font:500 22pt/1.15 "Vela Sans";letter-spacing:-.02em;margin:0 0 6pt}}
.sub{{font-size:12pt;color:#5a5651;margin:0 0 14pt}}
.intro{{font-size:11pt;margin:0 0 16pt;padding:10pt 12pt;background:#efebe6;border-left:3px solid #6b1a24}}
.item{{break-inside:avoid;display:grid;grid-template-columns:28pt 1fr;gap:8pt;padding:9pt 0;border-top:1px solid #ddd5cb}}
.item .n{{font:600 10pt/1 "Vela Sans";color:#6b1a24;padding-top:3pt}}
.item h2{{font:500 12pt/1.3 "Vela Sans";margin:0 0 3pt;color:#1d1b19}}
.item p{{margin:0;color:#3a3733}}
.close{{margin-top:16pt;padding:12pt 14pt;background:#222947;color:#efebe6;border-radius:2pt}}
.close b{{display:block;font-weight:500;margin-bottom:3pt}}
.close span{{color:#e3d6bd}}
.foot{{margin-top:10pt;font-size:8.5pt;color:#7a756e;display:flex;justify-content:space-between}}
"""


def html(g, phone, site):
    e = lambda t: escape(t, quote=False)
    items = "\n".join(
        f'<div class="item"><div class="n">{i:02d}</div><div><h2>{e(a)}</h2><p>{e(b)}</p></div></div>'
        for i, (a, b) in enumerate(g["items"], 1))
    logo = (HERE / "img" / "logo-frivent.png").as_uri()
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{e(g["title"])}</title><style>{CSS}</style></head>
<body>
<div class="head"><img src="{logo}" alt="Frivent"><span class="tag">Памятка · Frivent</span></div>
<h1>{e(g["title"])}</h1>
<p class="sub">{e(g["subtitle"])}</p>
<p class="intro">{e(g["intro"])}</p>
{items}
<div class="close"><b>{e(g["closing"])}</b><span>{e(phone)} · {e(site)}</span></div>
<div class="foot"><span>Frivent — загородный дом под ключ. Новая Рига, Рублёвка, Ильинское шоссе</span><span>Москва · с 1997 года</span></div>
</body></html>"""


def main():
    import build  # PHONE и домен — из сборщика сайта
    phone = getattr(build, "PHONE", "")
    site = "frivent.ru"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        for who, g in GIFT.items():
            tmp = OUT / (g["file"] + ".html")
            tmp.write_text(html(g, phone, site), "utf-8")
            pg.goto(tmp.as_uri())
            pg.wait_for_timeout(300)
            pg.pdf(path=str(OUT / g["file"]), format="A4", print_background=True, prefer_css_page_size=True)
            tmp.unlink()
            print("pdf:", g["file"], (OUT / g["file"]).stat().st_size // 1024, "KB")
        b.close()


if __name__ == "__main__":
    main()
