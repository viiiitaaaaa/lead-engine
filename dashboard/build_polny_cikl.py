"""Вставляет приёмы из docs/полный_цикл_приёмы.txt в docs/полный_цикл_frivent.html
между метками <!--PRIEMY--> ... <!--/PRIEMY-->.  Запуск: python dashboard/build_polny_cikl.py"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "полный_цикл_приёмы.txt"
PAGE = ROOT / "docs" / "полный_цикл_frivent.html"

ST = {"ok": ("готово", "ok"), "wait": ("ждёт данных", "pause"),
      "new": ("делаем", "todo"), "no": ("не делаем", "no")}


def parse():
    branches, cur = [], None
    for line in SRC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("## "):
            bid, grp, name, why = [p.strip() for p in line[3:].split("|")]
            cur = {"id": bid, "grp": grp, "name": name, "why": why, "items": []}
            branches.append(cur)
        elif line.startswith("- ") and cur:
            st, what, how, src = [p.strip() for p in line[2:].split("|")]
            cur["items"].append((st, what, how, src))
    return branches


def render(branches):
    e = html.escape
    total = sum(len(b["items"]) for b in branches)
    cnt = {k: sum(1 for b in branches for i in b["items"] if i[0] == k) for k in ST}
    out = [f'<p class="muted">В схему вошли {total} приёмов: готово {cnt["ok"]}, делаем {cnt["new"]}, '
           f'ждут данных или решения {cnt["wait"]}, не делаем по вашим решениям {cnt["no"]}. '
           'Нажмите на ветку, чтобы раскрыть её.</p>',
           '<div class="filt" role="group" aria-label="Фильтр по статусу">'
           '<button type="button" class="on" data-f="all">Все</button>'
           + "".join(f'<button type="button" data-f="{k}">{v[0]}</button>' for k, v in ST.items())
           + '<button type="button" id="openall">Раскрыть всё</button></div>']
    grp = None
    for b in branches:
        if b["grp"] != grp:
            grp = b["grp"]
            out.append(f'<h3 class="grp">{e(grp)}</h3>')
        n = {k: sum(1 for i in b["items"] if i[0] == k) for k in ST}
        chips = "".join(f'<span class="pill {ST[k][1]}">{ST[k][0]} {n[k]}</span>' for k in ST if n[k])
        out.append(f'<details class="br" id="{b["id"]}"><summary><span class="bn">{e(b["name"])}</span>'
                   f'<span class="bw">{e(b["why"])}</span><span class="chips">{chips}</span></summary><ul class="pr">')
        for st, what, how, src in b["items"]:
            lab, cls = ST[st]
            how_html = f' — {e(how)}' if how else ""
            out.append(f'<li data-s="{st}"><span class="pill {cls}">{lab}</span>'
                       f'<div><b>{e(what)}</b>{how_html}<small>{e(src)}</small></div></li>')
        out.append("</ul></details>")
    return "\n".join(out), total


def main():
    body, total = render(parse())
    page = PAGE.read_text(encoding="utf-8")
    page, k = re.subn(r"<!--PRIEMY-->.*?<!--/PRIEMY-->", lambda m: f"<!--PRIEMY-->\n{body}\n<!--/PRIEMY-->",
                      page, flags=re.S)
    if not k:
        raise SystemExit("нет меток <!--PRIEMY--> в странице")
    PAGE.write_text(page, encoding="utf-8")
    print(f"приёмов: {total} -> {PAGE.name}")


if __name__ == "__main__":
    main()
