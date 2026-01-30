import flet as ft
from app_state import AppState
from models.models import build_dummy_board


def lobby_view(page: ft.Page, state: AppState, rerender) -> ft.Control:
    def on_new_game(_):
        state.board = build_dummy_board(cols=6, rows=5)
        state.ensure_players()
        state.screen = "board"
        rerender()

    return ft.Column(
        controls=[
            ft.Text("Jeopardy Quiz", size=28, weight=ft.FontWeight.BOLD),
            ft.Text("Lobby – starte ein Spiel, um das Board zu sehen."),
            ft.Container(height=16),
            ft.FilledButton("Neues Spiel starten", on_click=on_new_game),
        ],
        tight=True,
    )
