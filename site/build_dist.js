// Чистая версия сайта для сдачи (её задача 12.10: «посетитель видит только сайт, код не украсть»):
// только готовые страницы/картинки/шрифты/PDF, без .py и служебных _*.html; HTML/CSS сжаты и без комментариев,
// app.js запутан (обфускация). Запуск: node build_dist.js <папка site> <папка dist> [--index]
// --index убирает noindex (только когда она скажет «запускаем»); по умолчанию сайт закрыт от поисковиков.
const fs = require("fs"), path = require("path");
const { minify } = require("html-minifier-terser");
const CleanCSS = require("clean-css");
const Obf = require("javascript-obfuscator");

const [SRC, DST] = process.argv.slice(2).map(p => path.resolve(p));
const INDEX = process.argv.includes("--index");
if (!SRC || !DST) { console.error("node build_dist.js <site> <dist>"); process.exit(1); }

fs.rmSync(DST, { recursive: true, force: true });
fs.mkdirSync(DST, { recursive: true });
const copyDir = (a, b) => {
  fs.mkdirSync(b, { recursive: true });
  for (const e of fs.readdirSync(a, { withFileTypes: true })) {
    if (e.name.startsWith("_")) continue;                       // _src, _old, _kandidaty — исходники не отдаём
    const s = path.join(a, e.name), d = path.join(b, e.name);
    if (e.isDirectory()) copyDir(s, d); else fs.copyFileSync(s, d);
  }
};
for (const d of ["img", "pdf"]) if (fs.existsSync(path.join(SRC, d))) copyDir(path.join(SRC, d), path.join(DST, d));
fs.mkdirSync(path.join(DST, "fonts"));
for (const f of fs.readdirSync(path.join(SRC, "fonts"))) if (f.endsWith(".woff2")) fs.copyFileSync(path.join(SRC, "fonts", f), path.join(DST, "fonts", f));
for (const f of ["robots.txt", "sitemap.xml", "favicon.ico", "favicon.svg"]) if (fs.existsSync(path.join(SRC, f))) fs.copyFileSync(path.join(SRC, f), path.join(DST, f));

// CSS: без комментариев, в одну строку
for (const f of fs.readdirSync(SRC).filter(f => f.endsWith(".css"))) {
  const out = new CleanCSS({ level: 1 }).minify(fs.readFileSync(path.join(SRC, f), "utf8"));
  if (out.errors.length) throw new Error(f + ": " + out.errors.join("; "));
  fs.writeFileSync(path.join(DST, f), out.styles);
}
// JS: запутать (без переименования глобальных имён — страницы на них не ссылаются, но так безопаснее)
for (const f of fs.readdirSync(SRC).filter(f => f.endsWith(".js") && !f.startsWith("_"))) {
  const code = Obf.obfuscate(fs.readFileSync(path.join(SRC, f), "utf8"), {
    compact: true, controlFlowFlattening: false, deadCodeInjection: false, stringArray: true,
    stringArrayEncoding: ["base64"], stringArrayThreshold: 0.75, renameGlobals: false, selfDefending: false,
    unicodeEscapeSequence: false, target: "browser",
  }).getObfuscatedCode();
  fs.writeFileSync(path.join(DST, f), code);
}
// HTML: без комментариев и лишних пробелов, встроенные стили/скрипты сжаты
(async () => {
  const pages = fs.readdirSync(SRC).filter(f => f.endsWith(".html") && !f.startsWith("_"));
  for (const f of pages) {
    let h = fs.readFileSync(path.join(SRC, f), "utf8");
    if (!INDEX && !/name="robots"/.test(h)) h = h.replace("<head>", '<head><meta name="robots" content="noindex, nofollow">');
    h = await minify(h, { removeComments: true, collapseWhitespace: true, conservativeCollapse: true, minifyCSS: true,
      minifyJS: true, removeRedundantAttributes: true, keepClosingSlash: true });
    fs.writeFileSync(path.join(DST, f), h);
  }
  // заголовки: запрет показа в чужих фреймах и подсказки браузеру
  // 14.10 (c/3493639787/800): + HSTS (только HTTPS) и CSP (грузить только своё). Всё на сайте своё; inline-стили в
  // атрибутах style= и правило speculationrules — разрешены точечно; mc.yandex.ru — заранее под Метрику (CONFIG.metrika).
  // Когда появится CONFIG.leadEndpoint на другом домене — дописать его в connect-src, иначе форма не отправится.
  const CSP = "default-src 'self'; script-src 'self' 'inline-speculation-rules' https://mc.yandex.ru; " +
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: https://mc.yandex.ru; font-src 'self'; " +
    "connect-src 'self' https://mc.yandex.ru; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'";
  fs.writeFileSync(path.join(DST, "_headers"), "/*\n  X-Frame-Options: DENY\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n" +
    "  Strict-Transport-Security: max-age=31536000\n  Content-Security-Policy: " + CSP + "\n" + (INDEX ? "" : "  X-Robots-Tag: noindex, nofollow\n"));
  console.log("готово:", pages.length, "страниц →", DST);
})();
