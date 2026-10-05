"""РЎРєСЂРёРЅС‹ Рё СЃС‚СЂСѓРєС‚СѓСЂР° СЃР°Р№С‚РѕРІ РєРѕРЅРєСѓСЂРµРЅС‚РѕРІ РґР»СЏ СЂР°Р·Р±РѕСЂР° РїРµСЂРµРґ Р»РµРЅРґРёРЅРіРѕРј (05.10.2026).

Р”Р»СЏ РєР°Р¶РґРѕРіРѕ СЃР°Р№С‚Р°: РїРµСЂРІС‹Р№ СЌРєСЂР°РЅ (РџРљ 1440x900 Рё С‚РµР»РµС„РѕРЅ 390x844), СЃС‚СЂР°РЅРёС†Р° С†РµР»РёРєРѕРј (РґРѕ 7000 px),
РјРµРЅСЋ, H1/H2, РєРЅРѕРїРєРё, РїРѕР»СЏ С„РѕСЂРј, С‚РµР»РµС„РѕРЅС‹, РµСЃС‚СЊ Р»Рё С‡Р°С‚/РјРµСЃСЃРµРЅРґР¶РµСЂС‹.
РС‚РѕРі: data/raw/sayty_konkurentov/<slug>_*.jpg + sayty_konkurentov.json
Р—Р°РїСѓСЃРє: python parsers/sayty_konkurentov.py [slug ...]
"""
import asyncio, json, re, sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "sayty_konkurentov"
OUT.mkdir(parents=True, exist_ok=True)

SITES = [
    # (РіСЂСѓРїРїР°, slug, РЅР°Р·РІР°РЅРёРµ, url)
    ("РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊ", "frivent", "Frivent (РјС‹)", "https://frivent.ru"),
    ("РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊ", "systemair", "Systemair", "https://www.systemair.com/ru-ru"),
    ("РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊ", "swegon", "Swegon", "https://www.swegon.com"),
    ("РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊ", "menerga", "Menerga", "https://menerga.com/en"),
    ("РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊ", "euroclima", "Euroclima", "https://www.euroclima.com"),
    ("РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊ", "prime", "PRIME", "https://prime-t.com"),
    ("РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊ", "york", "York", "https://www.york.com"),
    ("РёРЅР¶РµРЅРµСЂРёСЏ", "avgis", "РђР’Р“ РёРЅР¶РµРЅРµСЂРЅС‹Р№ СЃРµСЂРІРёСЃ", "https://avgis.ru"),
    ("РёРЅР¶РµРЅРµСЂРёСЏ", "teploservis", "РўРµРїР»РѕСЃРµСЂРІРёСЃ (Viessmann)", "https://viessmann-profi.ru"),
    ("РёРЅР¶РµРЅРµСЂРёСЏ", "superspa", "Superspa", "https://superspa.ru"),
    ("РёРЅР¶РµРЅРµСЂРёСЏ", "aquarai", "РђРєРІР°СЂР°Р№", "https://aquarai.ru"),
    ("РёРЅР¶РµРЅРµСЂРёСЏ", "prioritet", "РџСЂРёРѕСЂРёС‚РµС‚ Luxury", "https://prioritet-luxury.ru"),
    ("РёРЅР¶РµРЅРµСЂРёСЏ", "hotwell", "Hotwell", "https://www.hotwell.com"),
    ("РёРЅР¶РµРЅРµСЂРёСЏ", "monolithome", "Monolithome", "https://monolithome.ru"),
    ("Р±СЋСЂРѕ", "fedorova", "Fedorova Architects", "https://fedorova.ru"),
    ("Р±СЋСЂРѕ", "reznikov", "Reznikov Studio", "https://reznikov-studio.ru"),
    ("Р±СЋСЂРѕ", "usov", "Р‘СЋСЂРѕ РњРёС…Р°РёР»Р° РЈСЃРѕРІР°", "https://usov.archi"),
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

EXTRACT = r"""() => {
  const t = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const uniq = a => [...new Set(a.filter(Boolean))];
  const nav = uniq([...document.querySelectorAll('header a, nav a')].filter(vis).map(t)).filter(s => s.length < 40).slice(0, 25);
  const h1 = uniq([...document.querySelectorAll('h1')].map(t)).slice(0, 3);
  const h2 = uniq([...document.querySelectorAll('h2')].map(t)).filter(s => s.length < 140).slice(0, 30);
  const btn = uniq([...document.querySelectorAll('button, a[class*=btn], a[class*=button], input[type=submit]')]
     .filter(vis).map(e => t(e) || e.value)).filter(s => s && s.length < 50).slice(0, 25);
  const forms = [...document.querySelectorAll('form')].map(f => [...f.querySelectorAll('input:not([type=hidden]), textarea, select')]
     .map(i => i.placeholder || i.name || i.type)).filter(a => a.length).slice(0, 6);
  const html = document.documentElement.innerHTML;
  const body = document.body ? document.body.innerText : '';
  return {title: document.title, nav, h1, h2, btn, forms,
    phones: uniq((body.match(/(\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}/g) || [])).slice(0, 4),
    messengers: ['wa.me','whatsapp','t.me/','telegram','jivo','bitrix24','carrotquest','vk.com'].filter(k => html.includes(k)),
    height: document.documentElement.scrollHeight, words: body.split(/\s+/).length};
}"""

# закрыть плашки cookie: нажать «принять», а что не нажалось — спрятать
HIDE_COOKIES = r"""() => {
  const ok = /^(принять( все)?|я согласен|согласен|ок|ok|закрыть|разрешить все.*|allow all|accept( all)?|agree)$/i;
  for (const b of document.querySelectorAll('button, a, div[role=button]')) {
    const s = (b.innerText || '').trim();
    if (s.length < 40 && ok.test(s)) { try { b.click(); } catch (e) {} }
  }
  for (const el of document.querySelectorAll('[id*=cookie i], [class*=cookie i], [id*=Cookiebot], [class*=consent i]')) {
    const st = getComputedStyle(el);
    if (st.position === 'fixed' || st.position === 'sticky') el.style.display = 'none';
  }
}"""


async def shoot(browser, group, slug, name, url):
    rec = {"РіСЂСѓРїРїР°": group, "slug": slug, "РЅР°Р·РІР°РЅРёРµ": name, "url": url}
    try:
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, user_agent=UA, locale="ru-RU")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(4000)
        # РїСЂРѕРєСЂСѓС‚РєР° РІРЅРёР·-РІРІРµСЂС…, С‡С‚РѕР±С‹ РїРѕРґРіСЂСѓР·РёР»РёСЃСЊ Р»РµРЅРёРІС‹Рµ РєР°СЂС‚РёРЅРєРё
        for y in range(0, 7000, 900):
            await page.evaluate(f"window.scrollTo(0,{y})"); await page.wait_for_timeout(250)
        await page.evaluate("window.scrollTo(0,0)"); await page.wait_for_timeout(1200)
        rec["final_url"] = page.url
        rec.update(await page.evaluate(EXTRACT))
        await page.evaluate(HIDE_COOKIES); await page.wait_for_timeout(800)
        await page.screenshot(path=OUT / f"{slug}_pc.jpg", type="jpeg", quality=80)
        # высоту окна не растягиваем: первый экран в 100vh раздувается на всю страницу
        h = min(rec.get("height", 900), 7000)
        await page.screenshot(path=OUT / f"{slug}_full.jpg", type="jpeg", quality=60, full_page=True,
                              clip={"x": 0, "y": 0, "width": 1440, "height": h})
        await ctx.close()
        m = await browser.new_context(viewport={"width": 390, "height": 844}, user_agent=UA.replace(
            "Windows NT 10.0; Win64; x64", "iPhone; CPU iPhone OS 17_0 like Mac OS X") + " Mobile", locale="ru-RU",
            is_mobile=True, has_touch=True, device_scale_factor=2)
        mp = await m.new_page()
        await mp.goto(url, wait_until="domcontentloaded", timeout=90000); await mp.wait_for_timeout(4000)
        await mp.evaluate(HIDE_COOKIES); await mp.wait_for_timeout(800)
        await mp.screenshot(path=OUT / f"{slug}_mob.jpg", type="jpeg", quality=75)
        await m.close()
        rec["ok"] = True
    except Exception as e:
        rec["ok"] = False; rec["error"] = str(e)[:300]
    print(("OK  " if rec["ok"] else "ERR ") + slug, rec.get("error", ""), flush=True)
    return rec


async def main(only):
    sites = [s for s in SITES if not only or s[1] in only]
    res_path = OUT / "sayty_konkurentov.json"
    old = {r["slug"]: r for r in json.loads(res_path.read_text("utf-8"))} if res_path.exists() else {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        sem = asyncio.Semaphore(5)
        async def run(s):
            async with sem:
                return await shoot(browser, *s)
        for r in await asyncio.gather(*(run(s) for s in sites)):
            old[r["slug"]] = r
        await browser.close()
    order = [s[1] for s in SITES]
    res_path.write_text(json.dumps(sorted(old.values(), key=lambda r: order.index(r["slug"])),
                                   ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    asyncio.run(main(set(sys.argv[1:])))



