import json
import uuid
import flet as ft

from app_state import AppState, compute_capabilities
from lobby_store import get_lobby, update_lobby
from ui.layout import LAYOUT

from views.menu import menu_view
from views.host_setup import host_setup_view
from views.join import join_view
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
    # lobby_id wird erst beim Menü-Eintrag gesetzt


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

    def _build_menu_control() -> ft.Control:
        def on_host():
            push_route(page, "/host-setup")

        def on_join():
            push_route(page, "/join")

        def on_create():
            pass  # TODO: Create-Flow

        return menu_view(on_host=on_host, on_join=on_join, on_create=on_create)

    def _build_host_setup_control() -> ft.Control:
        def on_create(settings: dict):
            s = _store(page)
            s.set("role", "host")
            s.set("lobby_id", str(uuid.uuid4())[:8].upper())
            state.players.clear()
            state.board = None
            state.screen = "lobby"
            state.max_players = settings.get("max_players", 4)
            push_route(page, "/host/lobby")

        def on_back():
            push_route(page, "/menu")

        return host_setup_view(on_create=on_create, on_back=on_back)

    def _build_join_control() -> ft.Control:
        def on_join(code: str, name: str):
            s = _store(page)
            s.set("role", "player")
            s.set("lobby_id", code)
            s.set("player_name", name)

            # Aktuellen Lobby-State laden, damit Player sofort synced ist
            try:
                lobby = get_lobby(code)
                if lobby.data:
                    state.apply_snapshot(lobby.data)
            except Exception:
                pass

            # Host über Beitritt informieren
            msg = json.dumps({
                "type": "player_join",
                "lobby_id": code,
                "player_id": s.get("player_id"),
                "name": name,
            })
            page.pubsub.send_all(msg)

            push_route(page, "/player/lobby")

        def on_back():
            push_route(page, "/menu")

        return join_view(on_join=on_join, on_back=on_back)

    def route_change(_):
        route = page.route or "/"

        if route == "/":
            push_route(page, "/menu")
            return

        parts = [p for p in route.split("/") if p]

        # Flat routes ohne Rollen-Präfix
        if len(parts) == 1 and parts[0] == "menu":
            page.views.clear()
            page.views.append(
                ft.View(route=route, controls=[_build_menu_control()], padding=LAYOUT.page_padding)
            )
            page.update()
            return

        if len(parts) == 1 and parts[0] == "host-setup":
            page.views.clear()
            page.views.append(
                ft.View(route=route, controls=[_build_host_setup_control()], padding=LAYOUT.page_padding)
            )
            page.update()
            return

        if len(parts) == 1 and parts[0] == "join":
            page.views.clear()
            page.views.append(
                ft.View(route=route, controls=[_build_join_control()], padding=LAYOUT.page_padding)
            )
            page.update()
            return

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

        msg_type = msg.get("type")
        my_lobby = _get_lobby_id(page)

        if msg.get("lobby_id") != my_lobby:
            return

        if msg_type in ("player_join", "player_leave") and _get_role(page) == "host":
            if msg_type == "player_join":
                state.add_player(msg.get("player_id", ""), msg.get("name", "Spieler"))
            else:
                state.remove_player(msg.get("player_id", ""))
            broadcast_state()

            async def _refresh_lobby():
                page.views.clear()
                page.views.append(
                    ft.View(route=page.route, controls=[_build_screen_control()], padding=LAYOUT.page_padding)
                )
                page.update()

            page.run_task(_refresh_lobby)
            return

        if msg_type != "lobby_state":
            return

        if _get_role(page) == "host":
            return

        data = msg.get("data") or {}
        state.apply_snapshot(data)

        async def _apply_and_refresh():
            # Host hat die Lobby geschlossen → Player ins Menü
            if state.screen == "menu":
                await page.push_route("/menu")
                return

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

    # Beim Join direkt aktuellen Lobby-State ziehen (nur wenn lobby_id bereits gesetzt)
    lobby_id = _get_lobby_id(page)
    if lobby_id:
        try:
            lobby = get_lobby(lobby_id)
            if lobby.data:
                state.apply_snapshot(lobby.data)
                push_route(page, _route_for_screen(page, state.screen))
        except Exception:
            pass
