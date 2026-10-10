"""Картинки карточек каталога.

python site/make_katalog_img.py            — готовые картинки из img/katalog/_src/<ключ>.* → img/katalog/<ключ>.jpg/.webp (1200 px)
python site/make_katalog_img.py --prompts  — страница docs/промты_каталога.html: промт на каждую позицию + кнопка «Копировать»
Промты — site/catalog_prompts.py. После картинок — `python site/build.py`.
"""
import sys
from html import escape
from pathlib import Path

from catalog_data import ITEMS, CATALOGS
from catalog_prompts import PROMPTS, HOME

SITE = Path(__file__).parent
SRC, OUT = SITE / "img" / "katalog" / "_src", SITE / "img" / "katalog"
WHO = {"sobstvennik": "Владельцу", "pomoshchnik": "Ассистенту", "dizayner": "Дизайнеру", "montazh": "Монтажной компании",
       "zastroyshchik": "Застройщику", "kommerciya": "Коммерция"}


def convert():
    from PIL import Image
    SRC.mkdir(parents=True, exist_ok=True)
    done = 0
    for f in sorted(SRC.iterdir()):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".jfif") or f.stem not in ITEMS:
            continue
        im = Image.open(f).convert("RGB")
        w, h = im.size  # обрезка по центру до 4:3, как карточка
        if w / h > 4 / 3:
            nw = round(h * 4 / 3); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = round(w * 3 / 4); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        im = im.resize((1200, 900), Image.LANCZOS)
        im.save(OUT / f"{f.stem}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
        im.save(OUT / f"{f.stem}.webp", "WEBP", quality=80)
        done += 1
    print(f"картинок готово: {done}; ждут: {len([k for k in PROMPTS if not (OUT / f'{k}.jpg').exists()])} из {len(PROMPTS)}")


def prompts_page():
    order = []  # порядок: по каталогам клиентов, без повторов
    for who, cats in CATALOGS.items():
        for cat, keys in cats:
            for k in keys:
                if k not in [o[0] for o in order]:
                    order.append((k, who, cat))
    miss = [k for k, _, _ in order if k not in PROMPTS]
    if miss:
        sys.exit(f"нет промта для: {', '.join(miss)}")
    where = {k: sorted({f"{WHO[w]} · {c}" for w, cs in CATALOGS.items() for c, ks in cs for kk in ks if kk == k}) for k in PROMPTS}
    cards, last = [], None
    for k, who, _ in order:
        if who != last:
            cards.append(f'<h2>{WHO[who]}</h2>'); last = who
        base, scene = PROMPTS[k]
        full = f"{base}\n\n{scene}"
        ready = "✅ на сайте" if (OUT / f"{k}.jpg").exists() else "ждёт картинку"
        att = "приложить слайд 1 (site/img/slides/s1.jpg)" if base is HOME else "без вложения"
        cards.append(f'''<article class="c"><div class="top"><b>{escape(ITEMS[k][1])}</b><span class="st">{ready}</span></div>
<p class="m">Где: {escape("; ".join(where[k]))}<br>Сохранить как: <code>site/img/katalog/_src/{k}.png</code> · {att}</p>
<pre>{escape(full)}</pre><button type="button">Копировать</button></article>''')
    html = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Промты каталога</title><style>
:root{{--paper:#efebe6;--sand:#ddd5cb;--ink:#1d1b19;--wine:#6b1a24;--deep:#222947}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,sans-serif;padding:24px 16px}}
main{{max-width:980px;margin:auto}} h1{{font-size:30px;margin:0 0 8px}} h2{{margin:36px 0 12px;color:var(--deep)}}
.c{{background:#f7f4f0;border:1px solid var(--sand);border-radius:14px;padding:16px 18px;margin:12px 0}}
.top{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}} .st{{font-size:13px;color:var(--wine)}}
.m{{font-size:13px;color:#5d5650;margin:6px 0}} code{{background:var(--sand);padding:1px 5px;border-radius:4px}}
pre{{white-space:pre-wrap;font:13px/1.45 ui-monospace,Consolas,monospace;background:var(--paper);padding:12px;border-radius:8px;max-height:180px;overflow:auto}}
button{{background:var(--wine);color:#fff;border:0;border-radius:99px;padding:8px 18px;font:inherit;cursor:pointer}}
</style></head><body><main>
<h1>Промты картинок каталога — {len(order)} позиций</h1>
<p>Одна позиция = одна картинка: она встанет во все каталоги, где эта позиция есть. Где делать: Gemini (лучше держит «тот же дом» по вложению), Recraft, ChatGPT.
Формат 4:3. Цвета — как на сайте: беж, грейж, известняк, мрамор, латунь, акценты бордовый и тёмно-синий, без зелёного.<br>
Готовую картинку — в <code>site/img/katalog/_src/</code> под указанным именем, дальше скажите мне «вставь картинки каталога».</p>
{chr(10).join(cards)}
</main><script>
document.querySelectorAll('.c button').forEach(b=>b.onclick=()=>{{navigator.clipboard.writeText(b.previousElementSibling.textContent);b.textContent='Скопировано';setTimeout(()=>b.textContent='Копировать',1500)}});
</script></body></html>'''
    out = SITE.parent / "docs" / "промты_каталога.html"
    out.write_text(html, encoding="utf-8")
    print(f"промтов: {len(order)} -> {out}")


if __name__ == "__main__":
    prompts_page() if "--prompts" in sys.argv else convert()
