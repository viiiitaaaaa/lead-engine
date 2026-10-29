"""Проверка сайта по правилам Vercel Web Interface Guidelines (наш список, без установки чужого скилла).
Читает собранные страницы (*.html без _*) и styles.css, ничего не меняет. Запуск: python check_vercel.py
Итог: что нарушено по каждому правилу и на скольких страницах."""
import re, sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).parent
pages = sorted(p for p in ROOT.glob("*.html") if not p.name.startswith("_"))
css = (ROOT / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "app.js").read_text(encoding="utf-8")
found = defaultdict(list)  # правило -> [страница: пример]

def add(rule, where, sample=""):
    found[rule].append(f"{where}: {sample}"[:110])

for p in pages:
    h = p.read_text(encoding="utf-8")
    body = re.sub(r"<(script|style)\b.*?</\1>", "", h, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", body)
    n = p.name
    # Доступность
    if "<main" not in h: add("A. нет <main>", n)
    if not re.search(r'class="[^"]*skip', h) and 'href="#main' not in h: add("A. нет ссылки «к содержимому» (skip link)", n)
    if len(re.findall(r"<h1\b", h)) != 1: add("A. h1 не ровно один", n, str(len(re.findall(r"<h1\b", h))))
    lv = [int(x) for x in re.findall(r"<h([1-6])\b", h)]
    for a, b in zip(lv, lv[1:]):
        if b > a + 1: add("A. заголовки перескакивают уровень", n, f"h{a}→h{b}"); break
    for m in re.finditer(r"<img\b[^>]*>", h):
        t = m.group(0)
        if "alt=" not in t: add("A. img без alt", n, t[:60])
        if not ("width=" in t and "height=" in t): add("И. img без width/height (прыжки вёрстки)", n, t[:60])
    for m in re.finditer(r"<(div|span)\b[^>]*onclick", h): add("A. div/span с onclick вместо button", n)
    for m in re.finditer(r"<button\b[^>]*>\s*(<svg|<i\b|[×✕✖☰≡‹›‹›←→])[^<]{0,3}</button>", h):
        if "aria-label" not in m.group(0): add("A. кнопка-значок без aria-label", n, m.group(0)[:60])
    # Формы
    for m in re.finditer(r"<input\b[^>]*>", h):
        t = m.group(0)
        if re.search(r'type="(hidden|checkbox|submit)"', t) or 'class="hp"' in t: continue
        if "autocomplete" not in t: add("Ф. поле без autocomplete", n, t[:70])
        if "name=" not in t: add("Ф. поле без name", n, t[:70])
        if 'type="tel"' in t and "inputmode" not in t: add("Ф. tel без inputmode", n)
        ph = re.search(r'placeholder="([^"]*)"', t)
        if ph and ph.group(1) and not ph.group(1).rstrip().endswith("…"): add("Ф. placeholder не кончается на «…»", n, ph.group(1))
    if "onpaste" in h.lower(): add("Ф. запрет вставки (onpaste)", n)
    # Типографика
    if re.search(r"\w\.\.\.(?!\.)", text): add("Т. три точки вместо «…»", n)
    if re.search(r'(?<![=\w])"[А-Яа-яA-Za-z]', text): add("Т. прямые кавычки в тексте", n)
    # Голова страницы
    if 'name="viewport"' not in h and n != "index.html": add("Г. нет viewport", n)
    if 'name="theme-color"' not in h: add("Г. нет theme-color", n)
    imgs = re.findall(r"<img\b[^>]*>", h)
    if imgs and not any('loading="lazy"' in t for t in imgs[1:]) and len(imgs) > 3: add("И. нет loading=lazy у картинок ниже экрана", n)

# CSS
for m in re.finditer(r"transition:\s*all\b", css): add("Ан. transition: all", "styles.css", css[m.start():m.start()+40])
for m in re.finditer(r"outline:\s*(none|0)\b", css):
    ctx = css[max(0, m.start()-200):m.start()+250]
    if "focus-visible" not in ctx and "box-shadow" not in ctx[200:]:
        add("Ф. outline:none без замены фокуса", "styles.css", css[max(0, m.start()-60):m.start()+20].replace("\n", " "))
if "prefers-reduced-motion" not in css: add("Ан. нет prefers-reduced-motion", "styles.css")
if "touch-action" not in css: add("Т. нет touch-action: manipulation", "styles.css")
if "overscroll-behavior" not in css: add("Т. нет overscroll-behavior в окнах", "styles.css")
if "scroll-margin-top" not in css and "scroll-padding-top" not in css: add("A. нет scroll-margin-top для якорей под шапкой", "styles.css")
if "text-wrap" not in css: add("Ти. нет text-wrap: balance у заголовков", "styles.css")
if "tabular-nums" not in css: add("Ти. нет tabular-nums у цифр", "styles.css")
if "font-display" not in css: add("П. шрифты без font-display", "styles.css")
if "safe-area" not in css: add("Э. нет env(safe-area-inset-*)", "styles.css")
if "color-scheme" not in css: add("Т. нет color-scheme", "styles.css")
if "aria-live" not in (js + "".join(p.read_text(encoding='utf-8') for p in pages[:1])): add("A. статус формы без aria-live", "app.js / index.html")
if "preload" not in (ROOT / "index.html").read_text(encoding="utf-8"): add("П. нет preload критичных шрифтов", "index.html")

if not found:
    print("Нарушений не найдено")
for rule in sorted(found):
    items = found[rule]
    pgs = sorted({i.split(":")[0] for i in items})
    print(f"\n● {rule} — {len(items)} шт., файлов: {len(pgs)}")
    print("   пример:", items[0])
print(f"\nИтого правил с замечаниями: {len(found)}; страниц проверено: {len(pages)}")
# Что делает скрипт целиком: читает готовые страницы и styles.css, сверяет с правилами Vercel и печатает, что нарушено; файлы не меняет.
