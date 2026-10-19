# Собирает страницу vremya_na_proekt_frivent.html из itog.json
import json, html
from datetime import date
I = json.load(open(r"C:\Users\User\lead-engine\docs\vremya\itog.json", encoding="utf-8"))

CHTO = {  # что делали в этот день — по её сообщениям
 "2026-09-30": "Старт: схема воронки, оплата и подключение Apify и Bright Data, выбор сборщиков по отзывам, первый сбор (Яндекс Карты, 2ГИС, ЦИАН, ВК, YouTube), первая база",
 "2026-10-01": "Сбор продолжается: подключение 76 сборщиков, «всё в дашборд, таблицы не плодить», что осталось собрать",
 "2026-10-02": "Тендеры (площадки, регистрация), дизайн-бюро, тематические чаты Telegram, досье на застройщиков — «собрать ВСЁ, не только телефоны»",
 "2026-10-03": "Добор данных (юрлица, отзывы 2ГИС и Яндекса), коттеджные посёлки (Барвиха, Серебряный Бор, Ромашково), «Основа лендинга»: запрос → боль → решение, доли отзывов",
 "2026-10-04": "Правка таблицы «Основы лендинга», боли клиентов монтажников, проверка: ставят ли партнёры чужое; конкуренты — только европейские производители",
 "2026-10-05": "Начало сайта: разбор сайтов конкурентов, концепция «не винегрет», вёрстка, палитра, картинки (Gemini), шапка, каталоги по сегментам",
 "2026-10-06": "Сайт: прокрутка, отзывы-слайдер, логотип и курсив, фото объектов (Kol Gali и др.), памятка-подарок, сертификаты с frivent.ru",
 "2026-10-07": "Выжимка всех важных моментов из «Основы лендинга» и панели; чего нет у Frivent, а у рынка есть",
 "2026-10-09": "Сайт: отступы по всем страницам, внедрение приёмов из книг по маркетингу, прогоны по скиллам",
 "2026-10-10": "Сайт: скорость загрузки картинок, главная картинка, свои сгенерированные картинки, аудит «прыгающих» разделов",
 "2026-10-12": "Сайт: перенос на Cloudflare, как сдать сайт и не отдать доступы, картинки на главный слайдер, ссылка для партнёров",
 "2026-10-13": "Разговор о деньгах: как сказать заказчику о сроках и цене (вечером, после встречи с Пашей)",
 "2026-10-14": "Схема «что Frivent оказывает — полный цикл» по нашим скриптам и книгам",
 "2026-10-19": "Сравнение конкурентов в HTML для отправки",
}
NAP_CVET = {"Сайт": "#9b2335", "Сбор данных": "#2f6f8f", "Основа лендинга": "#b07a1c", "Панель": "#4f7a4a",
            "Конкуренты": "#6b5b95", "Деньги и договорённости": "#7a7a7a"}
NAP_OPIS = {"Сайт": "лендинг «Смарт Люкс» (был Frivent): вёрстка, картинки, правки, Cloudflare",
            "Сбор данных": "партнёры-монтажники, клиенты, посёлки, тендеры, досье, сборщики Apify",
            "Основа лендинга": "боли и запросы клиентов из отзывов: запрос → боль → решение",
            "Панель": "панель-дашборд лидогенерации",
            "Конкуренты": "европейские производители и сравнение сайтов",
            "Деньги и договорённости": "как говорить с заказчиком о цене и сроках"}


def ch(x):  # часы → «3 ч 05 мин»
    m = round(x * 60)
    return f"{m // 60} ч {m % 60:02d} мин" if m >= 60 else f"{m} мин"


vsego, v60, dni = I["vsego_chasov"], I["vsego_60"], I["dni"]
d0, d1 = date.fromisoformat(I["pervyy"][:10]), date.fromisoformat(I["posledniy"][:10])
kal = (d1 - d0).days + 1
osn_ch = sum(d["chasy"] for d in dni if d["den"] <= "2026-10-12")
mx = max(d["chasy"] for d in dni)

stroki = ""
for d in dni:
    dt = date.fromisoformat(d["den"])
    bar = "".join(f'<i style="width:{v / mx * 100:.1f}%;background:{NAP_CVET[k]}" title="{k}: {ch(v)}"></i>'
                  for k, v in sorted(d["po_nap"].items(), key=lambda kv: -kv[1]))
    stroki += (f'<tr><td class="d">{dt:%d.%m}</td><td class="h">{ch(d["chasy"])}</td>'
               f'<td><div class="bar">{bar}</div><div>{html.escape(CHTO.get(d["den"], ""))}</div>'
               f'<div class="sm">когда работала: {", ".join(d["otrezki"])} · её сообщений: {d["soobshcheniy"]}'
               f' · сохранений в git: {d["kommitov"]}</div></td></tr>')

napr = ""
for k, v in sorted(I["po_nap"].items(), key=lambda kv: -kv[1]):
    napr += (f'<tr><td><span class="dot" style="background:{NAP_CVET[k]}"></span>{k}</td><td class="h">{ch(v)}</td>'
             f'<td class="h">{v / vsego * 100:.0f}%</td><td class="sm">{NAP_OPIS[k]}</td></tr>')

CSS = """
:root{--bg:#faf8f5;--card:#fff;--tx:#1d1b19;--mu:#6d665f;--ln:#e6e0d8;--ac:#9b2335}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161412;--card:#201d1a;--tx:#ece7e1;--mu:#a39b92;--ln:#35302b;--ac:#e0707f}}
:root[data-theme=dark]{--bg:#161412;--card:#201d1a;--tx:#ece7e1;--mu:#a39b92;--ln:#35302b;--ac:#e0707f}
body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:28px;margin:0 0 4px} h2{font-size:20px;margin:36px 0 10px}
.mu,.sm{color:var(--mu)} .sm{font-size:13px}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:22px 0}
.kpi div{background:var(--card);border:1px solid var(--ln);border-radius:12px;padding:14px 16px}
.kpi b{display:block;font-size:30px;color:var(--ac);font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--ln);border-radius:12px;overflow:hidden}
td,th{padding:10px 12px;border-bottom:1px solid var(--ln);vertical-align:top;text-align:left}
th{font-size:13px;color:var(--mu);font-weight:600}
.d{font-weight:600;white-space:nowrap} .h{white-space:nowrap;font-variant-numeric:tabular-nums}
.bar{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--ln);margin:4px 0 6px}
.bar i{display:block;height:100%}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}
.box{background:var(--card);border:1px solid var(--ln);border-left:4px solid var(--ac);border-radius:10px;padding:12px 16px;margin:12px 0}
ul{padding-left:20px} li{margin:4px 0}
@media (max-width:600px){td,th{padding:8px} .kpi b{font-size:24px}}
"""

page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Время на Frivent</title><style>{CSS}</style></head><body><main>
<h1>Сколько времени ушло на проект Frivent</h1>
<div class="mu">Сбор информации, партнёры, конкуренты, клиенты, панель, основа лендинга, сайт «Смарт Люкс». Посчитано 19.10.2026 по меткам времени переписок с Claude.</div>
<div class="kpi">
<div><b>≈ {round(vsego)} ч</b>активной работы с Claude<br><span class="sm">{ch(vsego)}; без встречи, звонков и работы вне Claude</span></div>
<div><b>{len(dni)} дней</b>в которые была работа<br><span class="sm">из {kal} календарных</span></div>
<div><b>{kal} дней</b>календарный срок<br><span class="sm">{d0:%d.%m} – {d1:%d.%m.%Y}; основная работа {d0:%d.%m} – 12.10 ({ch(osn_ch)})</span></div>
<div><b>{I["soobshcheniy"]}</b>её сообщений и заданий<br><span class="sm">{I["kommity_vsego"]} сохранений проекта в git</span></div>
</div>
<div class="box"><b>Как читать:</b> «≈ {round(vsego)} ч» — время, когда она реально сидела и работала: писала задания, проверяла, правила.
Если между её сообщениями прошло больше 30 минут — считаем, что она отошла, и перерыв не считаем.
Если перерывом считать только паузы больше часа — выходит ≈ {round(v60)} ч. Честный разброс: <b>{round(vsego)}–{round(v60)} ч</b>,
и это нижняя граница: что не вошло — ниже.</div>

<h2>По направлениям</h2>
<table><tr><th>Направление</th><th>Время</th><th>Доля</th><th>Что входит</th></tr>{napr}</table>

<h2>По дням</h2>
<table><tr><th>Дата</th><th>Часы</th><th>Что делали</th></tr>{stroki}</table>
<div class="sm" style="margin-top:6px">Если работа шла за полночь, отрезок записан на день, когда начался.</div>

<h2>Что НЕ вошло — добавить, когда она назовёт</h2>
<ul>
<li><b>Встреча с Пашей 13.10</b> — запись разговора 17 мин (docs\\встреча_паша_2026-10-13.md). Сколько заняла вся встреча с дорогой — <b>спросить её</b>.</li>
<li><b>Звонки и переписка с Пашей и Андреем</b> в Telegram — в переписках Claude их нет. Неизвестно.</li>
<li><b>Работа без Claude:</b> генерация картинок в Gemini, поиск фото, показ руководителю, чтение документов, голосовые в бот. Неизвестно.</li>
<li><b>Переписки в Claude Desktop и на claude.ai</b> — на диске их нет, не считались.</li>
<li><b>Ожидание, пока агенты собирали данные</b> (часто часами, ночью) — не считали, это не её личное время. Но сбор шёл на её подписке Claude.</li>
<li><b>Её деньги на сервисы</b> (Apify, Bright Data, подписка Claude) — здесь не суммировались; цифры — по её чекам.</li>
</ul>

<h2>Как считали и что неточно</h2>
<ul>
<li>Взяты все переписки Claude Code на этом ПК (папки .claude\\projects): 3 064 её сообщения с 14.09. Из них про Frivent — {I["soobshcheniy"]}:
17 переписок целиком и куски из 3 смешанных (13.10 вечер — разговор о деньгах, 14.10 ночь — схема полного цикла, 19.10 — сравнение конкурентов).</li>
<li>Не взяты: сентябрьская работа с Apify (это был AliExpress, не Frivent), питч инвестору ВБ, резюме, поставщики — другие проекты, хотя слово «Frivent» там мелькает.</li>
<li>Служебные сообщения (уведомления агентов, «сессия продолжена») — не её, выкинуты.</li>
<li>Все вкладки сложены на одну ленту времени: если она вела две вкладки сразу, время не посчитано дважды.</li>
<li>К каждому отрезку добавлено 5 минут — прочитать последний ответ.</li>
<li>Направление определено по словам в её сообщениях («сайт», «конкурент», «основа лендинга»…) — это примерно, ±1–2 часа между направлениями.</li>
<li>Первое сообщение по проекту — {I["pervyy"][:16].replace("T", " ")}, первое сохранение в git — 30.09 19:29: совпадает.</li>
</ul>
<div class="box"><b>Для разговора о деньгах:</b> ≈ {round(vsego)}–{round(v60)} ч её личного времени за {len(dni)} рабочих дней
(+ встреча, звонки и работа вне Claude) — и всё это до первой оплаты. Как применить в разговоре — скилл dogovorennosti.</div>
<div class="sm" style="margin-top:20px">Скрипты: docs\\vremya\\sobrat_soobshcheniya.py → poschitat_vremya.py → sobrat_html.py</div>
</main></body></html>"""
open(r"C:\Users\User\lead-engine\docs\vremya_na_proekt_frivent.html", "w", encoding="utf-8").write(page)
print("ok")
