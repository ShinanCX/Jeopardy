"""Serviert build/web mit korrekten MIME-Types für Flutter."""
import http.server
import mimetypes
from pathlib import Path

mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent / "build" / "web"), **kwargs)

    def guess_type(self, path):
        if str(path).endswith(".mjs"):
            return "application/javascript"
        if str(path).endswith(".wasm"):
            return "application/wasm"
        return super().guess_type(path)

if __name__ == "__main__":
    with http.server.HTTPServer(("", 8080), Handler) as httpd:
        print("Serving build/web on http://localhost:8080")
        httpd.serve_forever()