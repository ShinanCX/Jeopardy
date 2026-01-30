import mimetypes

# Fix für Flutter Web ES-Modules (.mjs) → verhindert "Expected JavaScript... MIME text/plain"
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".mjs")  # optional
mimetypes.add_type("application/wasm", ".wasm")  # optional

import flet as ft

from app_state import AppState
from views import build_view



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

    def rerender():
        page.controls.clear()
        page.add(build_view(page, state, rerender))
        page.update()

    rerender()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550)
