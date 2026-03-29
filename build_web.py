"""
Build-Script: flet build web + index.html patchen für lokales Hosting.

Verwendung:
    python build_web.py

Danach:
    Terminal 1: python main.py          (Python-Server auf Port 8550)
    Terminal 2: python serve_build.py   (Flutter-Build auf Port 8080)
"""
import re
import subprocess
import sys
from pathlib import Path

INDEX_HTML = Path(__file__).parent / "build" / "web" / "index.html"

WEBSOCKET_PATCH = """\
  <script>
    // Leite WebSocket-Verbindungen an den Flet-Python-Server auf Port 8550 um
    const _OrigWS = window.WebSocket;
    window.WebSocket = function(url, ...args) {
      if (typeof url === "string") {
        url = url.replace(/^ws:\\/\\/[^/]+\\/ws/, "ws://localhost:8550/ws");
      }
      return new _OrigWS(url, ...args);
    };
    window.WebSocket.prototype = _OrigWS.prototype;
    window.WebSocket.CONNECTING = _OrigWS.CONNECTING;
    window.WebSocket.OPEN = _OrigWS.OPEN;
    window.WebSocket.CLOSING = _OrigWS.CLOSING;
    window.WebSocket.CLOSED = _OrigWS.CLOSED;
  </script>"""


def patch_index_html():
    html = INDEX_HTML.read_text(encoding="utf-8")

    # pyodide: true -> false
    html = html.replace("pyodide: true,", "pyodide: false,", 1)

    # WebSocket-Patch vor python.js einfügen (nur wenn noch nicht vorhanden)
    if "_OrigWS" not in html:
        html = html.replace('  <script src="python.js"></script>',
                            f'{WEBSOCKET_PATCH}\n  <script src="python.js"></script>', 1)

    INDEX_HTML.write_text(html, encoding="utf-8")
    print("✓ index.html gepatcht (pyodide: false + WebSocket-Redirect)")


def main():
    print("=== flet build web ===")
    result = subprocess.run(
        [sys.executable, "-m", "flet", "build", "web"],
        cwd=Path(__file__).parent,
    )
    if result.returncode != 0:
        print("✗ Build fehlgeschlagen.")
        sys.exit(result.returncode)

    print("\n=== index.html patchen ===")
    patch_index_html()

    print("\n✓ Fertig! Starten mit:")
    print("  Terminal 1: python main.py")
    print("  Terminal 2: python serve_build.py")
    print("  Browser:    http://localhost:8080")


if __name__ == "__main__":
    main()