import flet as ft
from typing import Callable
from views.topbar import topbar_view


def join_view(
    on_join: Callable[[str, str], None],
    on_back: Callable,
) -> ft.Control:
    lobby_code = ft.TextField(
        label="Lobby-Code",
        hint_text="z. B. A1B2C3D4",
        text_align=ft.TextAlign.CENTER,
        width=280,
        capitalization=ft.TextCapitalization.CHARACTERS,
    )
    player_name = ft.TextField(
        label="Dein Name",
        hint_text="z. B. Max",
        width=280,
    )
    error_text = ft.Text("", color="error", visible=False)

    def on_submit(_):
        code = lobby_code.value.strip().upper()
        name = player_name.value.strip()

        if not code:
            error_text.value = "Bitte einen Lobby-Code eingeben."
            error_text.visible = True
            lobby_code.update()
            error_text.update()
            return

        if not name:
            error_text.value = "Bitte einen Namen eingeben."
            error_text.visible = True
            player_name.update()
            error_text.update()
            return

        error_text.visible = False
        error_text.update()
        on_join(code, name)

    topbar = topbar_view(
        title="Lobby beitreten",
        on_back=on_back,
        back_label="Zum Menü",
    )

    return ft.Column(
        controls=[
            topbar,
            ft.Container(height=40),
            ft.Column(
                controls=[
                    player_name,
                    ft.Container(height=8),
                    lobby_code,
                    ft.Container(height=8),
                    error_text,
                    ft.Container(height=16),
                    ft.FilledButton("Beitreten", on_click=on_submit, width=280),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
        ],
        tight=True,
    )
