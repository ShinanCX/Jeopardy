import flet as ft
from app_state import AppState

from views.lobby import lobby_view
from views.board import board_view
from views.question import question_view


def build_view(page: ft.Page, state: AppState, rerender) -> ft.Control:
    if state.screen == "lobby":
        return lobby_view(page, state, rerender)
    if state.screen == "board":
        return board_view(page, state, rerender)
    if state.screen == "question":
        return question_view(page, state, rerender)

    return ft.Text(f"Unbekannter Screen: {state.screen}")
