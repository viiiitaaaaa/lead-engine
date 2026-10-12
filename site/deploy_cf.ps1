# Выкладка сайта на Cloudflare (её аккаунт, адрес без её имени): https://frivent-site.frivent-dom.workers.dev
# 1) собрать страницы, 2) чистая версия без комментариев/исходников, JS запутан, 3) выложить.
# Запуск: powershell -File site/deploy_cf.ps1      (добавить -Index, когда она скажет «запускаем» — уберёт noindex)
param([switch]$Index)
$S = $PSScriptRoot
$T = "C:\Users\User\tools\site-dist"   # там node_modules (wrangler, obfuscator) и wrangler.jsonc (имя frivent-site, папка dist)
python "$S\build.py" | Out-Null
$a = @("$T\build_dist.js", $S, "$T\dist"); if ($Index) { $a += "--index" }
Copy-Item "$S\build_dist.js" "$T\build_dist.js" -Force
node @a
Push-Location $T; & "$T\node_modules\.bin\wrangler.cmd" deploy; Pop-Location
