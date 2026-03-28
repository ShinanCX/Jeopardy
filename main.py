import mimetypes
import uuid
import flet as ft

from app_state import AppState
from ui.layout import LAYOUT
from views.router import setup_router, push_route

# Fix für Flutter Web ES-Modules (.mjs)
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")


def main(page: ft.Page):
    page.title = "Jeopardy (Flet)"
    page.padding = LAYOUT.page_padding
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
    if store.get("player_id") is None:
        store.set("player_id", str(uuid.uuid4()))

    # Router
    setup_router(page, state)

    # Beim direkten Aufruf einer spezifischen Route (z.B. /player/lobby) diese verwenden,
    # sonst ins Menü.
    target = page.route if (page.route and page.route != "/") else "/menu"
    push_route(page, target)

if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550)
