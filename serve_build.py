"""
Reverse-Proxy-Server für den Flet Flutter-Build.

- HTTP  → serviert statische Dateien aus build/web/
- /ws   → proxied WebSocket-Verbindungen an den Flet-Python-Server (Port 8550)

Verwendung:
    Terminal 1: python main.py          (Flet-Python-Server, Port 8550)
    Terminal 2: python serve_build.py   (Proxy + Static, Port 8080)
    Browser:    http://localhost:8080
"""
import asyncio
import mimetypes
from pathlib import Path

import websockets
import websockets.asyncio.client as ws_client
from aiohttp import web

BUILD_DIR = Path(__file__).parent / "build" / "web"
BOARDS_DIR = Path(__file__).parent / "boards"
FLET_WS_URL = "ws://localhost:8550/ws"
PORT = 8080

mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")

MIME_OVERRIDES = {
    ".mjs": "application/javascript",
    ".wasm": "application/wasm",
    ".js": "application/javascript",
    ".html": "text/html",
    ".css": "text/css",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".mp3": "audio/mpeg",
    ".ttf": "font/ttf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


async def ws_proxy_handler(request: web.Request) -> web.WebSocketResponse:
    """Proxied eingehende WebSocket-Verbindung an den Flet-Python-Server."""
    ws_browser = web.WebSocketResponse()
    await ws_browser.prepare(request)

    try:
        async with ws_client.connect(FLET_WS_URL) as ws_flet:
            async def browser_to_flet():
                async for msg in ws_browser:
                    if ws_browser.closed:
                        break
                    if msg.type == web.WSMsgType.TEXT:
                        await ws_flet.send(msg.data)
                    elif msg.type == web.WSMsgType.BINARY:
                        await ws_flet.send(msg.data)

            async def flet_to_browser():
                async for msg in ws_flet:
                    if ws_browser.closed:
                        break
                    if isinstance(msg, str):
                        await ws_browser.send_str(msg)
                    else:
                        await ws_browser.send_bytes(msg)

            await asyncio.gather(browser_to_flet(), flet_to_browser())
    except Exception as e:
        print(f"[WS-Proxy] Verbindung beendet: {e}")

    return ws_browser


async def static_handler(request: web.Request) -> web.Response:
    """Serviert statische Dateien aus build/web/."""
    path = request.match_info.get("path", "")
    file_path = BUILD_DIR / path if path else BUILD_DIR / "index.html"

    if not file_path.exists() or file_path.is_dir():
        file_path = BUILD_DIR / "index.html"

    suffix = file_path.suffix.lower()
    content_type = MIME_OVERRIDES.get(suffix, "application/octet-stream")

    return web.Response(body=file_path.read_bytes(), content_type=content_type, charset="utf-8" if content_type in ("text/html", "text/css", "application/javascript", "application/json") else None)


async def boards_handler(request: web.Request) -> web.Response:
    """Serviert Board-Assets (Bilder etc.) aus dem boards/-Verzeichnis."""
    path = request.match_info.get("path", "")
    file_path = BOARDS_DIR / path
    if not file_path.exists() or file_path.is_dir():
        raise web.HTTPNotFound()
    suffix = file_path.suffix.lower()
    content_type = MIME_OVERRIDES.get(suffix, "application/octet-stream")
    return web.Response(body=file_path.read_bytes(), content_type=content_type)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/ws", ws_proxy_handler)
    app.router.add_get("/boards/{path:.*}", boards_handler)
    app.router.add_get("/{path:.*}", static_handler)
    return app


if __name__ == "__main__":
    print(f"Serving build/web + WebSocket-Proxy auf http://localhost:{PORT}")
    print(f"WebSocket wird weitergeleitet an {FLET_WS_URL}")
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
