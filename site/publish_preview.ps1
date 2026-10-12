# Публичное превью сайта без входа в Claude: https://viiiitaaaaa.github.io/frivent-preview/
# Копирует готовые страницы (без .py и служебных _*.html) в отдельный открытый репозиторий,
# ставит noindex (не индексируется поисковиками) и отправляет на GitHub Pages.
# Запуск после python site/build.py:  powershell -File site/publish_preview.ps1 [папка-клон]
param([string]$D = "$env:LOCALAPPDATA\frivent-preview")
$S = $PSScriptRoot
if (-not (Test-Path "$D\.git")) { git clone -q https://github.com/viiiitaaaaa/frivent-preview.git $D }
Get-ChildItem $D -Exclude .git | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force "$D\fonts" | Out-Null
Get-ChildItem $S -Filter *.html | Where-Object { $_.Name -notlike "_*" } | Copy-Item -Destination $D
Copy-Item "$S\*.css","$S\app.js" $D
Copy-Item "$S\img","$S\pdf" $D -Recurse -Force
Copy-Item "$S\fonts\*.woff2" "$D\fonts"
$utf8 = New-Object Text.UTF8Encoding $false
Get-ChildItem $D -Filter *.html | ForEach-Object {
  $t = [IO.File]::ReadAllText($_.FullName)
  if ($t -notmatch 'name="robots"') { [IO.File]::WriteAllText($_.FullName, $t.Replace('<head>','<head><meta name="robots" content="noindex, nofollow">'), $utf8) }
}
New-Item -ItemType File "$D\.nojekyll" -Force | Out-Null
git -C $D add -A
git -C $D commit -q -m "Обновление превью сайта"
git -C $D push -q
"Готово: https://viiiitaaaaa.github.io/frivent-preview/ (обновится через 1-2 минуты)"
