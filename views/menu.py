import flet as ft
from typing import Callable


def menu_view(
    on_host: Callable,
    on_join: Callable,
    on_create: Callable,
) -> ft.Control:
    return ft.Column(
        controls=[
            ft.Text("Jeopardy", size=40, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            ft.Text("Was möchtest du tun?", size=16),
            ft.Container(height=40),
            ft.FilledButton("Host", on_click=lambda _: on_host(), width=240),
            ft.Container(height=12),
            ft.OutlinedButton("Lobby beitreten", on_click=lambda _: on_join(), width=240),
            ft.Container(height=12),
            ft.OutlinedButton("Board erstellen", on_click=lambda _: on_create(), width=240),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
