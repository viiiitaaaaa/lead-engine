"""Приёмник данных из вкладки Chrome: страница шлёт POST JSON на http://127.0.0.1:8768/<имя> → data/raw/<имя>_<время>.json.
Нужен, когда сбор идёт в браузере под её входом (Fabrikant, Тендерплан), а вкладка отдаёт мне данные только кусками.

python parsers/browser_receiver.py   # слушает 127.0.0.1:8768, только локально
"""
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from yandex_maps_bd import ROOT


class H(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_POST(self):
        name = "".join(c for c in self.path.strip("/") if c.isalnum() or c in "_-") or "browser"
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        data = json.loads(body.decode("utf-8"))
        out = ROOT / "data" / "raw" / f"{name}_{datetime.now():%Y-%m-%d_%H-%M-%S}.json"
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"принято {len(data) if isinstance(data, list) else 1} → {out}", flush=True)
        self.send_response(200)
        self.cors()
        self.end_headers()
        self.wfile.write(b"ok")


if __name__ == "__main__":
    print("приёмник слушает 127.0.0.1:8768", flush=True)
    HTTPServer(("127.0.0.1", 8768), H).serve_forever()
