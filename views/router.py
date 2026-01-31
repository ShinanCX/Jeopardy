import flet as ft
import asyncio
from app_state import AppState

from views.lobby import lobby_view
from views.board import board_view
from views.question import question_view


# AppState-Screens bleiben wie gehabt, URLs werden semantischer
_SCREEN_TO_ROUTE = {
    "lobby": "lobby",
    "board": "game",
    "question": "question",
}

_ROUTE_TO_SCREEN = {
    "lobby": "lobby",
    "game": "board",
    "question": "question",
}


def _get_role(page: ft.Page) -> str:
    role = (page.session.store.get("role") or "host").lower()
    return role if role in {"host", "player"} else "host"


def _route_for_screen(page: ft.Page, screen: str) -> str:
    role = _get_role(page)
    tail = _SCREEN_TO_ROUTE.get(screen, "lobby")
    return f"/{role}/{tail}"


def _build_screen_control(page: ft.Page, state: AppState, rerender) -> ft.Control:
    # Bestehende state-driven Views werden weiter genutzt.
    if state.screen == "lobby":
        return lobby_view(page, state, rerender)
    if state.screen == "board":
        return board_view(page, state, rerender)
    if state.screen == "question":
        return question_view(page, state, rerender)
    return ft.Text(f"Unbekannter Screen: {state.screen}")


def setup_router(page: ft.Page, state: AppState):
    """
    Step 2: Flet Routing (Views stack) wird mit dem bestehenden AppState verbunden.

    Wichtig:
    - Views können weiter state.screen setzen und rerender() aufrufen.
    - rerender() macht daraus page.go(...) auf die passende Route.
    """

    def rerender():
        # Übersetzt "state.screen changed" => Route change
        asyncio.create_task(page.push_route(_route_for_screen(page, state.screen)))

    def route_change(_):
        # Unterstützte Routen:
        #   /host/lobby, /host/game, /host/question
        #   /player/lobby, /player/game, /player/question
        route = page.route or "/"

        if route == "/":
            asyncio.create_task(page.push_route(_route_for_screen(page, "lobby")))
            return

        parts = [p for p in route.split("/") if p]
        role = parts[0].lower() if len(parts) >= 1 else _get_role(page)
        tail = parts[1].lower() if len(parts) >= 2 else "lobby"

        # Normalize role into session (single source of truth)
        if role not in {"host", "player"}:
            role = _get_role(page)
        page.session.store.set("role", role)

        # Route => State screen
        state.screen = _ROUTE_TO_SCREEN.get(tail, "lobby")

        # Single view stack for now (später kann man hier stacking erweitern)
        page.views.clear()
        page.views.append(
            ft.View(
                route=route,
                controls=[_build_screen_control(page, state, rerender)],
                padding=16,
            )
        )
        page.update()

    def view_pop(e: ft.ViewPopEvent):
        # Standard-Flet Pattern
        page.views.pop()
        top = page.views[-1]
        asyncio.create_task(page.push_route(top.route))

    page.on_route_change = route_change
    page.on_view_pop = view_pop
