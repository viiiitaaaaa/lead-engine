"""Основа лендинга отдельной страницей для показа руководителю: docs/лендинг_основа.md → dashboard/лендинг_основа.html (+ копия на Диске).
python dashboard/build_landing_doc.py [--no-open]
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parsers"))
from yandex_maps_bd import DRIVE  # noqa: E402

SRC = ROOT / "docs" / "лендинг_основа.md"
OUT = ROOT / "dashboard" / "лендинг_основа.html"

CSS = """
:root{--bg:#f6f4ef;--paper:#fff;--ink:#1d1d1b;--muted:#6b6862;--line:#e4e0d6;--accent:#8a5a2b;--soft:#f3ece2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:32px auto;background:var(--paper);padding:48px 56px;border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
h1{font-size:30px;line-height:1.2;margin:0 0 6px}
.sub{color:var(--muted);font-size:14px;margin:0 0 28px;padding-bottom:20px;border-bottom:1px solid var(--line)}
h2{font-size:21px;margin:40px 0 14px;padding-top:6px;color:var(--accent)}
p,li{max-width:76ch}
ul,ol{padding-left:22px}li{margin:6px 0}
strong{font-weight:650}
.lead{background:var(--soft);border-left:4px solid var(--accent);padding:16px 20px;border-radius:8px;font-size:18px;margin:14px 0}
.lead p{margin:0}
table{width:100%;border-collapse:collapse;margin:12px 0 4px;font-size:14.5px}
th{text-align:left;font-weight:600;color:var(--muted);font-size:12.5px;text-transform:uppercase;letter-spacing:.03em;border-bottom:2px solid var(--line);padding:8px 10px}
td{border-bottom:1px solid var(--line);padding:9px 10px;vertical-align:top}
tr:hover td{background:#fbf9f5}
td:first-child{font-weight:600}
.src{font-size:13px;color:var(--muted)}
.bar{display:inline-block;height:8px;width:var(--w);background:var(--accent);border-radius:4px;margin-right:6px;vertical-align:middle}
td:has(.bar){white-space:nowrap}
@media (max-width:720px){main{margin:0;border-radius:0;padding:24px 16px}table{display:block;overflow-x:auto}h1{font-size:24px}}
@media print{body{background:#fff}main{box-shadow:none;margin:0;padding:0;max-width:none}h2{break-after:avoid}tr{break-inside:avoid}tr:hover td{background:none}}
"""


def main():
    md = SRC.read_text(encoding="utf-8")
    title, body = md.split("\n", 1)
    title = title.lstrip("# ").strip()
    m = re.match(r"(.*?)\s*\((\d{2}\.\d{2}\.\d{4})\)", title)
    name, date = (m.group(1), m.group(2)) if m else (title, "")
    html = markdown.markdown(body.strip(), extensions=["tables"])
    # первый абзац — источник данных, мельче; основной запрос — выделенной плашкой
    html = html.replace("<p>Источник:", '<p class="src">Источник:', 1)
    html = re.sub(r"(<h2>2\. [^<]*</h2>\s*)<p>(.*?)</p>", r'\1<div class="lead"><p>\2</p></div>', html, count=1, flags=re.S)
    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Основа лендинга</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><main><h1>{name}</h1><p class="sub">{date} · поставщик технического оборудования для премиальных загородных домов и коттеджей · Новая Рига, Рублёвка, Ильинское ш.</p>
{html}</main></body></html>"""
    OUT.write_text(page, encoding="utf-8")
    drive_copy = DRIVE.parent / OUT.name
    shutil.copy(OUT, drive_copy)
    print(f"страница: {OUT}; копия: {drive_copy}")
    if "--no-open" not in sys.argv:
        subprocess.Popen(["cmd", "/c", "start", "chrome", str(OUT)])


if __name__ == "__main__":
    main()
