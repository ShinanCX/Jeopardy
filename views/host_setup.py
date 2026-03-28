import flet as ft
from typing import Callable
from views.topbar import topbar_view

MIN_PLAYERS = 2
MAX_PLAYERS = 8


def host_setup_view(
    on_create: Callable[[dict], None],
    on_back: Callable,
) -> ft.Control:
    max_players_val = [4]  # mutable container

    count_label = ft.Text(str(max_players_val[0]), size=24, weight=ft.FontWeight.BOLD, width=40, text_align=ft.TextAlign.CENTER)

    def update_count(delta: int):
        new_val = max_players_val[0] + delta
        if new_val < MIN_PLAYERS or new_val > MAX_PLAYERS:
            return
        max_players_val[0] = new_val
        count_label.value = str(new_val)
        count_label.update()

    def on_submit(_):
        on_create({"max_players": max_players_val[0]})

    topbar = topbar_view(
        title="Lobby erstellen",
        on_back=on_back,
        back_label="Zum Menü",
    )

    return ft.Column(
        controls=[
            topbar,
            ft.Container(height=40),
            ft.Column(
                controls=[
                    ft.Text("Maximale Spieleranzahl", size=15),
                    ft.Container(height=8),
                    ft.Row(
                        controls=[
                            ft.IconButton(ft.Icons.REMOVE, on_click=lambda _: update_count(-1)),
                            count_label,
                            ft.IconButton(ft.Icons.ADD, on_click=lambda _: update_count(1)),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=32),
                    ft.FilledButton("Lobby erstellen", on_click=on_submit, width=240),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
        ],
        tight=True,
    )
