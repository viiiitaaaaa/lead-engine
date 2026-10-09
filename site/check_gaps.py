"""Проверка вертикальных отступов между блоками на всех страницах (её правило 09.10: везде одинаково).
Запуск: python site/check_gaps.py site — норма (её таблица 09.10): 186 между блоками одного фона и через смену фона, 151 = 79+72 перед тёмным, 144 = 51+93 после тёмного, 93 от фото первого экрана.
"""
import sys, glob, os, json
from playwright.sync_api import sync_playwright
JS = r"""
() => {
  const main = document.querySelector('main'); if (!main) return [];
  // top-level blocks: children of main, plus children of <article> wrapper
  let blocks = [];
  for (const c of main.children) { if (c.tagName==='ARTICLE' || c.tagName==='DIV' && !c.className) blocks.push(...c.children); else blocks.push(c); }
  blocks = blocks.filter(b => b.getBoundingClientRect().height > 0 && b.tagName!=='SCRIPT');
  const contentBox = el => {
    let top=Infinity, bot=-Infinity;
    const walk = n => { for (const k of n.children) {
        const cs=getComputedStyle(k); if (cs.display==='none'||cs.visibility==='hidden') continue;
        const r=k.getBoundingClientRect(); if (r.height===0) continue;
        const boxy = (cs.backgroundColor!=='rgba(0, 0, 0, 0)' && cs.backgroundColor!==getComputedStyle(el).backgroundColor) || parseFloat(cs.borderTopWidth)>0 || parseFloat(cs.borderBottomWidth)>0;
        if (boxy || k.children.length===0 || ['P','H1','H2','H3','IMG','PICTURE','A','BUTTON','LI','SPAN','INPUT','TEXTAREA','SELECT','LABEL','FIGURE','B','DT','DD','SUMMARY'].includes(k.tagName)) {
          top=Math.min(top,r.top+scrollY); bot=Math.max(bot,r.bottom+scrollY);
        } else walk(k);
      } };
    walk(el); return [top,bot];
  };
  return blocks.map(b => { const r=b.getBoundingClientRect(); const [t,bo]=contentBox(b);
    return {id: b.id || b.className.split(' ').slice(0,2).join('.'), tag:b.tagName, top:r.top+scrollY, bottom:r.bottom+scrollY, ct:t, cb:bo, bg:getComputedStyle(b).backgroundColor, pt:getComputedStyle(b).paddingTop, pb:getComputedStyle(b).paddingBottom}; });
}
"""
site = sys.argv[1]
pages = sorted(os.path.basename(p) for p in glob.glob(site + "/*.html") if not os.path.basename(p).startswith("_"))
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 900})
    for name in pages:
        pg.goto("file:///" + site.replace("\\", "/") + "/" + name); pg.wait_for_timeout(300)
        bl = pg.evaluate(JS); gaps = []
        for a, c in zip(bl, bl[1:]):
            gaps.append((a["id"], c["id"], round(c["ct"] - a["cb"]), a["bg"] == c["bg"]))
        out[name] = gaps
    b.close()
for n, g in out.items():
    print("==", n)
    for a, c, gap, same in g: print(f"   {gap:5d}  {a} -> {c}{'' if same else '  [смена фона]'}")

