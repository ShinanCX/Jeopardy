import mimetypes
import asyncio
import uuid
import flet as ft

from app_state import AppState
from views.router import setup_router

# Fix für Flutter Web ES-Modules (.mjs)
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")


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

    # --- session.store defaults ---
    store = page.session.store
    if store.get("role") is None:
        store.set("role", "host")

    if store.get("player_id") is None:
        store.set("player_id", str(uuid.uuid4()))

    # WICHTIG: lobby_id NICHT randomisieren, sonst sind Host/Player nie in derselben Lobby.
    # Für Dev-Test fix:
    if store.get("lobby_id") is None:
        store.set("lobby_id", "dev")

    # Router
    setup_router(page, state)

    # WICHTIG: route_change muss initial getriggert werden, egal ob route schon gesetzt ist.
    # Wenn jemand direkt /player/lobby öffnet, ist page.route != "/" und sonst bleibt views leer.
    target = page.route if page.route else "/"
    if target == "/":
        role = store.get("role") or "host"
        target = f"/{role}/lobby"

    asyncio.create_task(page.push_route(target))


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550)
