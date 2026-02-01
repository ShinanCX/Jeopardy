import flet as ft
from app_state import AppState
from models.models import build_dummy_board


def lobby_view(page: ft.Page, state: AppState, rerender, *, broadcast_state=None) -> ft.Control:
    role = (page.session.store.get("role") or "host").lower()
    is_host = role == "host"

    def on_new_game(_):
        if not is_host:
            return

        state.board = build_dummy_board(cols=6, rows=5)
        state.ensure_players()
        state.screen = "board"
        rerender()

        if broadcast_state:
            broadcast_state()

    return ft.Column(
        controls=[
            ft.Text("Jeopardy Quiz", size=28, weight=ft.FontWeight.BOLD),
            ft.Text("Lobby – starte ein Spiel, um das Board zu sehen."),
            ft.Container(height=16),

            ft.FilledButton("Neues Spiel starten", on_click=on_new_game, visible=is_host),
            ft.Text("Warte auf den Host…", visible=not is_host),
        ],
        tight=True,
    )
