import json
import uuid
import flet as ft

from app_state import AppState, compute_capabilities
from lobby_store import get_lobby, update_lobby
from ui.layout import LAYOUT

from views.lobby import lobby_view
from views.board import board_view
from views.question import question_view


_SCREEN_TO_ROUTE = {"lobby": "lobby", "board": "game", "question": "question"}
_ROUTE_TO_SCREEN = {"lobby": "lobby", "game": "board", "question": "question"}

def push_route(page: ft.Page, route: str):
    async def _do():
        await page.push_route(route)

    page.run_task(_do)

def _store(page: ft.Page):
    return page.session.store


def _ensure_defaults(page: ft.Page):
    s = _store(page)
    if s.get("role") is None:
        s.set("role", "host")
    if s.get("player_id") is None:
        s.set("player_id", str(uuid.uuid4()))
    if s.get("lobby_id") is None:
        # DEV: Host & Player müssen dieselbe Lobby teilen, sonst kein Sync
        s.set("lobby_id", "dev")


def _get_role(page: ft.Page) -> str:
    role = (_store(page).get("role") or "host").lower()
    return role if role in {"host", "player"} else "host"


def _get_lobby_id(page: ft.Page) -> str:
    return _store(page).get("lobby_id")


def _route_for_screen(page: ft.Page, screen: str) -> str:
    role = _get_role(page)
    tail = _SCREEN_TO_ROUTE.get(screen, "lobby")
    return f"/{role}/{tail}"


def setup_router(page: ft.Page, state: AppState):
    _ensure_defaults(page)

    def broadcast_state():
        role = _get_role(page)
        if role != "host":
            return

        lobby_id = _get_lobby_id(page)
        snap = state.snapshot()
        lobby = update_lobby(lobby_id, snap)

        msg = {
            "type": "lobby_state",
            "lobby_id": lobby_id,
            "version": lobby.version,
            "data": lobby.data,
        }
        page.pubsub.send_all(json.dumps(msg))

    def rerender():
        push_route(page, _route_for_screen(page, state.screen))

    def _build_screen_control() -> ft.Control:
        role = _get_role(page)
        caps = compute_capabilities(state, role)

        if state.screen == "lobby":
            return lobby_view(page, state, rerender, broadcast_state=broadcast_state)

        if state.screen == "board":
            return board_view(
                page, state, rerender,
                caps=caps,
                broadcast_state=broadcast_state,
            )

        if state.screen == "question":
            return question_view(
                page, state, rerender,
                caps=caps,
                broadcast_state=broadcast_state,
            )

        return ft.Text(f"Unbekannter Screen: {state.screen}")

    def route_change(_):
        route = page.route or "/"
        if route == "/":
            push_route(page, _route_for_screen(page, "lobby"))
            return

        parts = [p for p in route.split("/") if p]
        role = parts[0].lower() if len(parts) >= 1 else _get_role(page)
        tail = parts[1].lower() if len(parts) >= 2 else "lobby"

        if role not in {"host", "player"}:
            role = "host"
        _store(page).set("role", role)

        state.screen = _ROUTE_TO_SCREEN.get(tail, "lobby")

        # Optional Guard: wenn /game ohne Board -> zurück in Lobby
        if state.screen == "board" and getattr(state, "board", None) is None:
            state.screen = "lobby"
            push_route(page, _route_for_screen(page, "lobby"))
            return

        page.views.clear()
        page.views.append(
            ft.View(route=route, controls=[_build_screen_control()], padding=LAYOUT.page_padding)
        )
        page.update()

    def view_pop(e: ft.ViewPopEvent):
        if page.views:
            page.views.pop()
        if page.views:
            push_route(page, page.views[-1].route)
        else:
            push_route(page, _route_for_screen(page, "lobby"))

    def _on_pubsub(message: str):
        try:
            msg = json.loads(message)
        except Exception:
            return

        if msg.get("type") != "lobby_state":
            return

        if msg.get("lobby_id") != _get_lobby_id(page):
            return

        if _get_role(page) == "host":
            return

        data = msg.get("data") or {}
        state.apply_snapshot(data)

        async def _apply_and_refresh():
            target = _route_for_screen(page, state.screen)

            # Wenn Screen/Route gewechselt hat: normal navigieren (triggert route_change -> rebuild)
            if page.route != target:
                await page.push_route(target)
                return

            # Route ist gleich -> trotzdem UI neu bauen, sonst sieht der Client nichts
            page.views.clear()
            page.views.append(
                ft.View(route=page.route, controls=[_build_screen_control()], padding=LAYOUT.page_padding)
            )
            page.update()

        page.run_task(_apply_and_refresh)

    page.pubsub.subscribe(_on_pubsub)
    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Optional: beim Join direkt aktuellen Lobby-State ziehen
    try:
        lobby = get_lobby(_get_lobby_id(page))
        if lobby.data:
            state.apply_snapshot(lobby.data)
            push_route(page, _route_for_screen(page, state.screen))
    except Exception:
        pass
