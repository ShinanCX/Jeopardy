"""
Startet alle drei Dienste gleichzeitig:
  - python main.py          (Flet-Python-Server, Port 8550)
  - python serve_build.py   (Flutter-Build + WebSocket-Proxy, Port 8080)
  - cloudflared tunnel      (öffentliche URL auf Port 8080)

Beenden mit Strg+C.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent


def stream_output(proc: subprocess.Popen, prefix: str, filter_fn=None):
    """Gibt die Ausgabe eines Prozesses mit Präfix aus."""
    for line in iter(proc.stdout.readline, b""):
        decoded = line.decode(errors="replace").rstrip()
        if filter_fn is None or filter_fn(decoded):
            print(f"[{prefix}] {decoded}")


def _tunnel_filter(line: str) -> bool:
    """Zeigt nur die Tunnel-URL und Fehler an."""
    return "trycloudflare.com" in line or "ERR" in line


def main():
    procs = []

    try:
        p_main = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        procs.append(p_main)
        threading.Thread(target=stream_output, args=(p_main, "server"), daemon=True).start()
        print("[start] Flet-Server gestartet (Port 8550)")

        # Kurz warten damit der Server hochfährt bevor der Proxy startet
        time.sleep(2)

        p_serve = subprocess.Popen(
            [sys.executable, "serve_build.py"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        procs.append(p_serve)
        threading.Thread(target=stream_output, args=(p_serve, "proxy "), daemon=True).start()
        print("[start] Flutter-Proxy gestartet (Port 8080)")

        time.sleep(1)

        p_cf = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:8080"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        procs.append(p_cf)
        threading.Thread(target=stream_output, args=(p_cf, "tunnel", _tunnel_filter), daemon=True).start()
        print("[start] Cloudflare-Tunnel gestartet — URL erscheint gleich oben")

        # Alle Prozesse laufen lassen bis Strg+C
        while all(p.poll() is None for p in procs):
            time.sleep(1)

        print("[start] Ein Prozess hat sich unerwartet beendet.")

    except KeyboardInterrupt:
        print("\n[start] Beende alle Prozesse...")

    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("[start] Alle Prozesse beendet.")


if __name__ == "__main__":
    main()
