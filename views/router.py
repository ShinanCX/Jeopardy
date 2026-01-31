import asyncio
import json
import uuid
import flet as ft

from app_state import AppState, compute_capabilities
from lobby_store import get_lobby, update_lobby

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


def _store(page: ft.Page):
    # Flet 0.80.x: session.store ist der KV-Store
    return page.session.store


def _ensure_defaults(page: ft.Page):
    s = _store(page)
    if s.get("role") is None:
        s.set("role", "host")
    if s.get("player_id") is None:
        s.set("player_id", str(uuid.uuid4()))
    if s.get("lobby_id") is None:
        # Später ersetzt durch echten Lobby-Code-Join
        # s.set("lobby_id", str(uuid.uuid4()))
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
    """
    Router verbindet Flet 0.80.x routing (push_route + views stack)
    mit dem bestehenden AppState.

    Zusätzlich:
    - shared state sync via PubSub: Host broadcastet snapshots, Player applied.
    """

    _ensure_defaults(page)

    def broadcast_state():
        """
        Host broadcastet den aktuellen minimalen Snapshot an alle Clients.
        """
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
        # PubSub payload am besten als JSON-string senden
        page.pubsub.send_all(json.dumps(msg))

    def rerender():
        # Übersetzt "state.screen changed" => Route change
        asyncio.create_task(page.push_route(_route_for_screen(page, state.screen)))

    def _build_screen_control() -> ft.Control:
        role = _get_role(page)
        caps = compute_capabilities(state, role)

        if state.screen == "lobby":
            return lobby_view(page, state, rerender)

        if state.screen == "board":
            return board_view(
                page,
                state,
                rerender,
                caps=caps,
                broadcast_state=broadcast_state,
            )

        if state.screen == "question":
            return question_view(
                page,
                state,
                rerender,
                caps=caps,
                broadcast_state=broadcast_state,
            )

        return ft.Text(f"Unbekannter Screen: {state.screen}")

    def route_change(_):
        route = page.route or "/"

        if route == "/":
            asyncio.create_task(page.push_route(_route_for_screen(page, "lobby")))
            return

        parts = [p for p in route.split("/") if p]
        role = parts[0].lower() if len(parts) >= 1 else _get_role(page)
        tail = parts[1].lower() if len(parts) >= 2 else "lobby"

        if role not in {"host", "player"}:
            role = "host"

        # Rolle in store normalisieren
        _store(page).set("role", role)

        # Route => Screen
        state.screen = _ROUTE_TO_SCREEN.get(tail, "lobby")

        page.views.clear()
        page.views.append(
            ft.View(
                route=route,
                controls=[_build_screen_control()],
                padding=16,
            )
        )
        page.update()

    def view_pop(e: ft.ViewPopEvent):
        # Standard pattern: view stack + route sync
        if page.views:
            page.views.pop()

        if page.views:
            top = page.views[-1]
            asyncio.create_task(page.push_route(top.route))
        else:
            asyncio.create_task(page.push_route(_route_for_screen(page, "lobby")))

    def _on_pubsub(message: str):
        """
        Player empfängt snapshots und zieht UI nach.
        Host ignoriert (Host ist source of truth).
        """
        try:
            msg = json.loads(message)
        except Exception:
            return

        if msg.get("type") != "lobby_state":
            return

        lobby_id = _get_lobby_id(page)
        if msg.get("lobby_id") != lobby_id:
            return

        role = _get_role(page)
        if role == "host":
            return

        data = msg.get("data") or {}
        state.apply_snapshot(data)

        # Route an Screen anpassen
        asyncio.create_task(page.push_route(_route_for_screen(page, state.screen)))

    # Subscribe nur einmal
    page.pubsub.subscribe(_on_pubsub)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Optional: Client beim Connect direkt auf shared lobby-state "ziehen"
    # (hilft bei Reload / späterem Join)
    try:
        lobby = get_lobby(_get_lobby_id(page))
        if lobby.data:
            state.apply_snapshot(lobby.data)
            asyncio.create_task(page.push_route(_route_for_screen(page, state.screen)))
    except Exception:
        pass
