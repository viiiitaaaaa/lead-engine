"""Значок вкладки и картинка превью ссылки (находки 12.10: <head> 2026 — SVG-фавиконка и Open Graph).

Запуск: python site/make_icons.py — один раз или после смены слайда 1 / цветов.
  img/favicon.svg          — значок вкладки: буква F цвета шампанского на глубоком синем (цвета из :root styles.css)
  img/favicon-32.png       — тот же значок для старых браузеров
  img/apple-touch-icon.png — 180×180, значок на экране телефона
  img/og.jpg               — 1200×630, превью ссылки в Telegram/WhatsApp (кадр слайда 1, без надписей)
Буква нарисована прямоугольниками (без шрифта), поэтому SVG и PNG одинаковые.
"""
from pathlib import Path
from PIL import Image, ImageDraw

SITE = Path(__file__).resolve().parent
DEEP, CHAMP = "#222947", "#e3d6bd"  # --deep и --on-dark-accent
# буква F в квадрате 64×64: стойка + верхняя и средняя перекладины
BARS = [(20, 14, 27, 50), (20, 14, 46, 20), (20, 30, 41, 36)]

svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
       f'<rect width="64" height="64" rx="12" fill="{DEEP}"/>'
       + "".join(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="{CHAMP}"/>' for x0, y0, x1, y1 in BARS)
       + "</svg>\n")
(SITE / "img" / "favicon.svg").write_text(svg, "utf-8")


def png(size, name, radius=True):
    k = 8  # рисуем крупно и уменьшаем — края ровные
    S = size * k
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=(12 * S // 64) if radius else 0, fill=DEEP)
    for x0, y0, x1, y1 in BARS:
        d.rectangle((x0 * S // 64, y0 * S // 64, x1 * S // 64 - 1, y1 * S // 64 - 1), fill=CHAMP)
    im = im.resize((size, size), Image.LANCZOS)
    if not radius:
        im = im.convert("RGB")
    im.save(SITE / "img" / name)


png(32, "favicon-32.png")
png(180, "apple-touch-icon.png", radius=False)  # iOS сам скругляет углы

# превью ссылки: кадр слайда 1 (фасад усадьбы), обрезка по центру до 1200×630
src = Image.open(SITE / "img" / "slides" / "s1.jpg").convert("RGB")
W, H = 1200, 630
# чуть крупнее и левее центра: в правом нижнем углу исходника — след значка генератора, в превью он не попадает
r = max(W / src.width, H / src.height) * 1.1
im = src.resize((round(src.width * r), round(src.height * r)), Image.LANCZOS)
left, top = (im.width - W) // 2 - 50, (im.height - H) // 2 - 25
im.crop((left, top, left + W, top + H)).save(SITE / "img" / "og.jpg", "JPEG", quality=82, optimize=True, progressive=True)
print("значки и og.jpg готовы")
