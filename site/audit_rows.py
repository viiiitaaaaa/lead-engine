# Аудит «прыгающих» рядов: в каждой сетке карточек сравниваем, на одной ли высоте у соседей в ряду
# начинается текст после заголовка (и линия под заголовком). Печатает страницу, ширину, сетку и разброс в px.
import subprocess,time,glob,os,sys,json
from playwright.sync_api import sync_playwright
SITE=r"C:\Users\User\lead-engine\site"
pages=sorted(os.path.basename(f) for f in glob.glob(SITE+r"\*.html") if not os.path.basename(f).startswith("_"))
JS=r"""
() => {
 const out=[];
 const grids=[...document.querySelectorAll('main *')].filter(el=>{
   const d=getComputedStyle(el).display; return (d==='grid'||d==='flex') && el.children.length>=2 && el.querySelector(':scope > * h3, :scope > h3');
 });
 for(const g of grids){
   const kids=[...g.children].filter(c=>c.querySelector('h3')&&c.offsetHeight>0);
   const rows={};
   for(const c of kids){const t=Math.round(c.getBoundingClientRect().top);(rows[t]=rows[t]||[]).push(c)}
   for(const [t,cs] of Object.entries(rows)){
     if(cs.length<2) continue;
     const ys=cs.map(c=>{const h=c.querySelector('h3');let n=h.nextElementSibling;while(n&&n.offsetHeight===0)n=n.nextElementSibling;
        return n? Math.round(n.getBoundingClientRect().top - c.getBoundingClientRect().top):null}).filter(v=>v!==null);
     if(ys.length<2) continue;
     const spread=Math.max(...ys)-Math.min(...ys);
     if(spread>3) out.push({grid:(g.className||g.tagName)+'', sec:(g.closest('section')||{}).id||'', n:cs.length, spread});
   }
 }
 return out;
}"""
srv=subprocess.Popen([sys.executable,"-m","http.server","8767"],cwd=SITE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(1.5)
res={}
with sync_playwright() as p:
  b=p.chromium.launch()
  for w in (1440,1280,1024,768):
    pg=b.new_page(viewport={"width":w,"height":900})
    for f in pages:
      pg.goto(f"http://localhost:8767/{f}");pg.wait_for_timeout(250)
      for r in pg.evaluate(JS):
        key=r['grid']; res.setdefault(key,[]).append(f"{f}@{w}#{r['sec']} ({r['spread']}px)")
  b.close()
srv.kill()
tot=0
for k,v in sorted(res.items(),key=lambda x:-len(x[1])):
  tot+=len(v); print(f"[{len(v)}] {k}: "+"; ".join(v[:4])+(" …" if len(v)>4 else ""))
print("ВСЕГО прыгающих рядов:",tot)
