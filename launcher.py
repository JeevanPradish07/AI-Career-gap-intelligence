"""
launcher.py
───────────────────────────────────────────────────────────────
Unified control server for the AI Career Platform.
Starts BOTH the FastAPI backend and the Vite frontend.
Runs on http://localhost:8888 (control only — not the app)

Endpoints:
  GET  /status  → { backend: "running"|"stopped", frontend: "running"|"stopped" }
  POST /start   → starts both servers
  POST /stop    → stops both servers
  GET  /logs    → SSE stream of live log lines from both servers

Usage:
  python launcher.py   (or double-click START_PLATFORM.bat)
  Browser opens launcher.html → click START → app opens at http://localhost:5173
"""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR     = Path(__file__).parent
BACKEND_DIR  = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
LAUNCHER_HTML = ROOT_DIR / "launcher.html"

BACKEND_CMD  = [sys.executable, "-m", "uvicorn", "main:app",
                "--host", "0.0.0.0", "--port", "8000", "--reload"]
FRONTEND_CMD = ["npm", "run", "dev"]

# ── State ─────────────────────────────────────────────────────────────────────
_backend:  subprocess.Popen | None = None
_frontend: subprocess.Popen | None = None
_log_queue: queue.Queue = queue.Queue(maxsize=1000)
_lock = threading.Lock()


def _log(msg: str):
    _log_queue.put(msg)


def _stream(proc: subprocess.Popen, prefix: str):
    """Stream stdout/stderr from a process into the log queue."""
    try:
        for line in proc.stdout:
            text = line.rstrip()
            if text:
                _log(f"[{prefix}] {text}")
    except Exception:
        pass


def _start_process(cmd, cwd, prefix) -> subprocess.Popen | None:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # Use shell=True on Windows for npm
    use_shell = (sys.platform == "win32" and cmd[0] == "npm")
    try:
        proc = subprocess.Popen(
            cmd if not use_shell else " ".join(cmd),
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            shell=use_shell,
        )
        t = threading.Thread(target=_stream, args=(proc, prefix), daemon=True)
        t.start()
        return proc
    except Exception as e:
        _log(f"[{prefix}] ❌ Failed to start: {e}")
        return None


def _is_running(proc: subprocess.Popen | None) -> bool:
    return proc is not None and proc.poll() is None


def _kill(proc: subprocess.Popen | None):
    if not proc or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception:
        try: proc.kill()
        except Exception: pass


# ── Actions ───────────────────────────────────────────────────────────────────
def start_all():
    global _backend, _frontend
    with _lock:
        results = {}

        if _is_running(_backend):
            results["backend"] = "already running"
        else:
            _log("▸ Starting FastAPI backend on :8000 ...")
            _backend = _start_process(BACKEND_CMD, BACKEND_DIR, "API")
            results["backend"] = "started" if _backend else "failed"
            if _backend:
                _log(f"✅ Backend started (PID {_backend.pid})")

        if _is_running(_frontend):
            results["frontend"] = "already running"
        else:
            _log("▸ Starting Vite frontend on :5173 ...")
            _frontend = _start_process(FRONTEND_CMD, FRONTEND_DIR, "UI")
            results["frontend"] = "started" if _frontend else "failed"
            if _frontend:
                _log(f"✅ Frontend started (PID {_frontend.pid})")

        # Always open web application directly in browser
        threading.Timer(2.5, webbrowser.open, args=("http://localhost:5173",)).start()
        _log("🌐 Directing browser to http://localhost:5173 ...")

        return results


def stop_all():
    global _backend, _frontend
    with _lock:
        _log("🛑 Stopping all servers...")
        _kill(_backend);  _backend  = None; _log("✅ Backend stopped.")
        _kill(_frontend); _frontend = None; _log("✅ Frontend stopped.")
        return {"ok": True}


def get_status():
    with _lock:
        return {
            "backend":  {"status": "running" if _is_running(_backend)  else "stopped",
                         "pid":    _backend.pid  if _is_running(_backend)  else None},
            "frontend": {"status": "running" if _is_running(_frontend) else "stopped",
                         "pid":    _frontend.pid if _is_running(_frontend) else None},
        }


# ── HTTP Handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # silence access log

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors(); self.end_headers(); self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self._json(get_status())
        elif self.path == "/logs":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control",  "no-cache")
            self.send_header("Connection",      "keep-alive")
            self._cors(); self.end_headers()
            try:
                while True:
                    try:
                        line = _log_queue.get(timeout=1)
                        msg = f"data: {json.dumps(line)}\n\n"
                        self.wfile.write(msg.encode()); self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n"); self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if   self.path == "/start": self._json(start_all())
        elif self.path == "/stop":  self._json(stop_all())
        else: self._json({"error": "not found"}, 404)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = HTTPServer(("localhost", 8888), Handler)
    print("🚀 Starting AI Career Platform...")
    print("   Backend  → http://localhost:8000")
    print("   Frontend → http://localhost:5173")
    print()
    # Automatically start backend & frontend servers and open web app directly
    start_all()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_all()
        print("\n👋 Platform stopped.")

