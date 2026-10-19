# Считает её время на проект Frivent по меткам времени её сообщений Claude
import json, re, sys, subprocess, collections
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding="utf-8")

PAUZA = timedelta(minutes=30)   # перерыв больше 30 мин = она отошла, новый отрезок
HVOST = timedelta(minutes=5)    # после последнего сообщения отрезка — 5 мин прочитать ответ

# Переписки целиком про Frivent (отобраны вручную по её сообщениям) и направление по умолчанию
CELIKOM = {
    "53c78804": "Сбор данных", "4c684b90": "Панель", "9611721f": "Сбор данных", "fef7417a": "Сбор данных",
    "1b3f7154": "Основа лендинга", "75c00256": "Основа лендинга", "77c7e40f": "Основа лендинга",
    "3e592021": "Сайт", "2c8bbef8": "Сайт", "af0a0ace": "Сайт", "67bafba2": "Сайт", "424c8d32": "Основа лендинга",
    "ad8e349f": "Сайт", "015cec07": "Сайт", "8c514d1b": "Сайт", "36ca2aed": "Сайт", "5101c8f1": "Конкуренты",
}
# Смешанные переписки — берём только отрезок про Frivent
KUSKI = [("612252cb", "10-14T00:50", "10-14T01:10", "Сайт"),
         ("63b5e136", "10-13T21:44", "10-13T22:00", "Деньги и договорённости"),
         ("abdaa5c4", "10-19T14:10", "10-19T14:30", "Конкуренты")]
# Слова в сообщении уточняют направление
SLOVA = [("Конкуренты", r"конкурент|systemair|york|menerga|swegon"),
         ("Основа лендинга", r"основ\w* лендинг|бол[ьие]|запрос|спрос"),
         ("Панель", r"панел|дашборд"),
         ("Сбор данных", r"apify|апифа|монтажн|партн[её]р|досье|клиент|сбор|скрапер|чат"),
         ("Сайт", r"сайт|картин|страниц|лендинг|фото|шрифт|курсив|cloudflare")]
NE_ONA = re.compile(r"^(<task-notification>|This session is being continued|Пульт перезапускался)")

m = json.load(open(sys.argv[1], encoding="utf-8"))
moi = []
for x in m:
    if NE_ONA.match(x["text"]):
        continue                                   # это не её сообщение, а служебное
    mmdd = x["t"][5:16]
    nap = CELIKOM.get(x["sess"])
    for s, a, b, n in KUSKI:
        if x["sess"] == s and a <= mmdd <= b:
            nap = n
    if not nap:
        continue
    for n, rx in SLOVA:
        if re.search(rx, x["text"], re.I):
            nap = n
            break
    moi.append((datetime.fromisoformat(x["t"]), nap, x["text"]))
moi.sort()

# Склеиваем в отрезки: все вкладки на одной ленте, чтобы параллельная работа не считалась дважды
otrezki = []
for t, nap, txt in moi:
    if otrezki and t - otrezki[-1]["konec"] <= PAUZA:
        o = otrezki[-1]
        o["po_nap"][o["nap"]] += t - o["konec"]   # время до этого сообщения — на направление прошлого
        o["konec"], o["nap"] = t, nap
        o["n"] += 1
    else:
        otrezki.append({"nachalo": t, "konec": t, "nap": nap, "n": 1,
                        "po_nap": collections.defaultdict(timedelta), "teksty": []})
    otrezki[-1]["teksty"].append(txt)
for o in otrezki:
    o["po_nap"][o["nap"]] += HVOST

dni = collections.OrderedDict()
for o in otrezki:
    d = dni.setdefault(o["nachalo"].date().isoformat(), {"otrezki": [], "po_nap": collections.defaultdict(timedelta), "n": 0})
    d["otrezki"].append(o); d["n"] += o["n"]
    for k, v in o["po_nap"].items():
        d["po_nap"][k] += v

kommity = collections.Counter(subprocess.run(["git", "-C", r"C:\Users\User\lead-engine", "log", "--format=%ad", "--date=short"],
                              capture_output=True, text=True).stdout.split())
itog = {"soobshcheniy": len(moi), "otrezkov": len(otrezki), "pervyy": moi[0][0].isoformat(), "posledniy": moi[-1][0].isoformat(),
        "dni": [], "po_nap": collections.defaultdict(float)}
for den, d in dni.items():
    chasy = sum(d["po_nap"].values(), timedelta()).total_seconds() / 3600
    itog["dni"].append({"den": den, "chasy": round(chasy, 2), "soobshcheniy": d["n"], "kommitov": kommity.get(den, 0),
                        "otrezki": [f'{o["nachalo"]:%H:%M}–{(o["konec"] + HVOST):%H:%M}' for o in d["otrezki"]],
                        "po_nap": {k: round(v.total_seconds() / 3600, 2) for k, v in d["po_nap"].items()}})
    for k, v in d["po_nap"].items():
        itog["po_nap"][k] += v.total_seconds() / 3600
itog["vsego_chasov"] = round(sum(x["chasy"] for x in itog["dni"]), 2)
itog["kommity_vsego"] = sum(kommity.values())
json.dump(itog, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Всего часов:", itog["vsego_chasov"], "| дней:", len(itog["dni"]), "| сообщений:", len(moi))
for x in itog["dni"]:
    print(x["den"], x["chasy"], x["soobshcheniy"], x["kommitov"], " ".join(x["otrezki"]), x["po_nap"])
print({k: round(v, 1) for k, v in itog["po_nap"].items()})
