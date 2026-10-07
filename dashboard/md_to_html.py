"""Простой .md → .html для чтения в браузере (у неё нет Word). python dashboard/md_to_html.py docs/файл.md"""
import re, html, sys
from pathlib import Path

src_path = Path(sys.argv[1])
src = src_path.read_text(encoding="utf-8").splitlines()
title = next((l[2:] for l in src if l.startswith("# ")), src_path.stem)


def inl(t):
    t = html.escape(t.replace("`", ""))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


out, lst = [], None


def close():
    global lst
    if lst:
        out.append(f"</{lst}>")
        lst = None


for line in src:
    if not line.strip():
        close(); continue
    m = re.match(r"(#{1,3}) (.*)", line)
    if m:
        close(); out.append(f"<h{len(m[1])}>{inl(m[2])}</h{len(m[1])}>"); continue
    for tag, rx in (("ul", r"- (.*)"), ("ol", r"\d+\. (.*)")):
        m = re.match(rx, line)
        if m:
            if lst != tag:
                close(); out.append(f"<{tag}>"); lst = tag
            out.append(f"<li>{inl(m[1])}</li>")
            break
    else:
        close(); out.append(f"<p>{inl(line)}</p>")
close()
page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
body{{margin:0;background:#f4f1ec;color:#222;font:17px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:820px;margin:0 auto;padding:32px 20px 64px}}
h1{{font-size:28px;color:#222947;margin:0 0 8px}}h2{{font-size:21px;color:#6b1a24;margin:34px 0 10px;padding-top:14px;border-top:1px solid #d9d2c7}}
li{{margin:5px 0}}b{{color:#111}}p{{margin:8px 0}}
</style></head><body><main>""" + "\n".join(out) + "</main></body></html>"
src_path.with_suffix(".html").write_text(page, encoding="utf-8")
print("ok", src_path.with_suffix(".html"))
