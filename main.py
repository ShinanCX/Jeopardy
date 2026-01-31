import mimetypes
import asyncio

# Fix für Flutter Web ES-Modules (.mjs) → verhindert "Expected JavaScript... MIME text/plain"
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".mjs")  # optional
mimetypes.add_type("application/wasm", ".wasm")  # optional

import flet as ft
import uuid

from app_state import AppState
from views.router import setup_router


def main(page: ft.Page):
    page.title = "Jeopardy (Flet)"
    page.padding = 16
    page.theme_mode = ft.ThemeMode.DARK

    page.theme = ft.Theme(
        use_material3=True,
        color_scheme=ft.ColorScheme(
            primary="#1e88e5",
            secondary="#fbc02d",
            surface="#0f141a",
            surface_container="#161b22",
            surface_container_high="#1d2430",
            outline="#2a2f36",
            on_primary="#ffffff",
            on_secondary="#000000",
            on_surface="#ffffff",
        ),
    )
    page.bg_color = "surface"
    state = AppState()

    # --- Session fundamentals (Step 1) ---
    store = page.session.store
    if store.get("role") is None:
        store.set("role", "host")

    if store.get("player_id") is None:
        store.set("player_id", str(uuid.uuid4()))

    if store.get("lobby_id") is None:
        store.set("lobby_id", str(uuid.uuid4()))

    # --- Routing / Views (Step 2) ---
    setup_router(page, state)

    # Initial navigation
    if not page.route or page.route == "/":
        role = store.get("role") or "host"
        asyncio.create_task(page.push_route(f"/{role}/lobby"))


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550)

