#!/usr/bin/env python3
"""Small PIN-protected LAN bridge from an iPhone web remote to Android TV ADB."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, secrets, socket, subprocess, threading, time

HERE = Path(__file__).resolve().parent
ADB = Path(r"C:\Users\Maksim\Downloads\platform-tools-latest-windows\platform-tools\adb.exe")
TV = "192.168.1.167:5555"
PIN = f"{secrets.randbelow(1_000_000):06d}"
SESSIONS = set()
LOCK = threading.Lock()
KEYS = {"up": 19, "down": 20, "left": 21, "right": 22, "ok": 23,
        "back": 4, "home": 3, "volumeup": 24, "volumedown": 25,
        "mute": 164, "playpause": 85, "assistant": 219}
APPS = {"youtube": "com.yandex.tv.ytplayer", "vk": "com.vk.tv", "kinopoisk": "ru.kinopoisk.yandex.tv", "happ": "su.happ.proxyutility"}

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.1", 80)); return s.getsockname()[0]
    except OSError: return "<IP компьютера в Wi-Fi>"
    finally: s.close()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def reply(self, code, body, typ="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(data))); self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.reply(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/manifest.json":
            return self.reply(200, (HERE / "manifest.json").read_bytes(), "application/manifest+json")
        self.reply(404, "not found")
    def do_POST(self):
        try: obj = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except Exception: return self.reply(400, '{"error":"bad request"}')
        if self.path == "/pair":
            if not secrets.compare_digest(str(obj.get("pin", "")), PIN): return self.reply(403, '{"error":"Неверный PIN"}')
            token = secrets.token_urlsafe(32)
            with LOCK: SESSIONS.add(token)
            return self.reply(200, json.dumps({"token": token}))
        token = self.headers.get("X-Remote-Token", "")
        with LOCK: valid = token in SESSIONS
        if not valid: return self.reply(401, '{"error":"Сначала введите PIN"}')
        try:
            if self.path == "/key" and obj.get("key") in KEYS:
                cmd = [str(ADB), "-s", TV, "shell", "input", "keyevent", str(KEYS[obj["key"]])]
            elif self.path == "/app" and obj.get("app") in APPS:
                cmd = [str(ADB), "-s", TV, "shell", "monkey", "-p", APPS[obj["app"]], "1"]
            else: return self.reply(400, '{"error":"Неизвестная команда"}')
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if p.returncode: return self.reply(502, json.dumps({"error": (p.stderr or p.stdout or "ADB недоступен").strip()}))
            self.reply(200, '{"ok":true}')
        except (OSError, subprocess.TimeoutExpired) as e: self.reply(502, json.dumps({"error": str(e)}))

if __name__ == "__main__":
    if not ADB.exists(): raise SystemExit(f"Не найден adb.exe: {ADB}")
    print("iPhone TV remote — локальная сеть")
    print(f"Откройте на iPhone: http://{lan_ip()}:8765")
    print(f"PIN сопряжения: {PIN}")
    print("Окно сервера должно оставаться открытым. Для выхода нажмите Ctrl+C.")
    ThreadingHTTPServer(("0.0.0.0", 8765), Handler).serve_forever()
