"""Личные ссылки менеджеров: у каждого своя, в Битриксе видно, по чьей ссылке клиент пришёл (её решение 29.10: адрес не собираем).
Менеджеров впиши в MANAGERS (ярлык латиницей: имя), BASE — адрес сайта. Запуск: python ssylki_menedzherov.py → ssylki_menedzherov.html"""
import html, sys
from pathlib import Path
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://smart-eng.frivent-dom.workers.dev/"  # сменить, когда будет свой домен
MANAGERS = {"manager-1": "Менеджер 1 (пример)", "manager-2": "Менеджер 2 (пример)", "manager-3": "Менеджер 3 (пример)"}

rows = []
for slug, name in MANAGERS.items():
    # utm_source — кто (менеджер), utm_medium — как (личная ссылка), utm_campaign — откуда (сайт); app.js кладёт их в скрытые поля заявки
    url = BASE + "?" + urlencode({"utm_source": slug, "utm_medium": "manager", "utm_campaign": "site"})
    rows.append(f"<tr><td>{html.escape(name)}</td><td><code>{html.escape(url)}</code></td></tr>")
out = Path(__file__).with_name("ssylki_menedzherov.html")
out.write_text('<!doctype html><meta charset="utf-8"><title>Ссылки менеджеров</title><body style="font:16px system-ui;max-width:900px;margin:24px auto">'
               "<h1>Личные ссылки менеджеров</h1><p>Дай менеджеру его ссылку. В Битриксе в заявке поле UTM_SOURCE покажет, по чьей ссылке пришёл клиент.</p>"
               '<table border="1" cellpadding="8" style="border-collapse:collapse">' + "".join(rows) + "</table></body>", encoding="utf-8")
print("готово:", out)
# Что делает скрипт целиком: берёт список менеджеров и для каждого собирает адрес сайта с его меткой UTM, складывает таблицей в html.
