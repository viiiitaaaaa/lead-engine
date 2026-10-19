# Собирает её сообщения из всех переписок Claude: время, папка, текст (без служебных вставок)
import json, glob, re, os, sys
from datetime import datetime, timezone, timedelta

MSK = timezone(timedelta(hours=3))
papki = glob.glob(r"C:\Users\User\.claude\projects\C--Users-User*")
out = []
for papka in papki:
    for f in glob.glob(os.path.join(papka, "*.jsonl")):
        for line in open(f, encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain"):
                continue
            c = d.get("message", {}).get("content")
            if isinstance(c, list):
                if any(x.get("type") == "tool_result" for x in c if isinstance(x, dict)):
                    continue
                c = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
            if not isinstance(c, str):
                continue
            c = re.sub(r"<system-reminder>.*?</system-reminder>", "", c, flags=re.S).strip()
            if not c or c.startswith("<local-command") or c.startswith("<command-") or c.startswith("Caveat:"):
                continue
            t = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).astimezone(MSK)
            out.append({"t": t.isoformat(), "papka": os.path.basename(papka), "sess": os.path.basename(f)[:8],
                        "cwd": d.get("cwd", ""), "text": c[:400]})
out.sort(key=lambda x: x["t"])
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(out), "сообщений;", out[0]["t"], "—", out[-1]["t"])
