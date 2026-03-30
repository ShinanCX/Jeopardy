import asyncio
import json
import threading
import time
import uuid
from pathlib import Path
import flet as ft

from app_state import AppState, compute_capabilities
from lobby_store import get_lobby, update_lobby
from ui.layout import LAYOUT

from board_loader import list_boards
from views.menu import menu_view
from views.board_editor import board_editor_view, board_setup_view
from views.topbar import topbar_view
from views.host_setup import host_setup_view
from views.join import join_view
from views.lobby import lobby_view
from views.board import board_view
from views.question import question_view


_SCREEN_TO_ROUTE = {"lobby": "lobby", "board": "game", "question": "question"}
_ROUTE_TO_SCREEN = {"lobby": "lobby", "game": "board", "question": "question"}
_buzz_lock = threading.Lock()

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

    # Audio via flet_audio (funktioniert nur im flet build web, nicht im Dev-Server).
    _assets_dir = Path(__file__).parent.parent / "assets"
    _sound_files = {"buzz": "buzz.mp3", "correct_answer": "correct_answer.mp3", "wrong_answer": "wrong_answer.mp3"}
    _sounds = {}
    _q_audio = [None]              # aktiver FletAudio-Control für Frage-Audio
    _q_audio_duration = [None]    # gecachte Duration als int (ms) via on_duration_change
    _q_audio_position = [None]    # gecachte Position als (int ms, float monotonic_time) via on_position_change
    _pending_audio_src = [None]   # vorgemerkter Src, wird nach views.append() angewendet
    _flet_audio_available = [False]
    _flet_audio_works = [None]    # None=ungetestet, True=funktioniert, False=kein Flutter-Build
    _flet_audio_cls = None
    _release_mode_stop = None
    try:
        from flet_audio import Audio as _FA, ReleaseMode as _RM
        _flet_audio_cls = _FA
        _release_mode_stop = _RM.STOP
        _flet_audio_available[0] = True
        for name, filename in _sound_files.items():
            if (_assets_dir / filename).exists():
                audio = _flet_audio_cls(src=filename, autoplay=False, release_mode=_release_mode_stop)
                page.services.append(audio)
                _sounds[name] = audio
        if _sounds:
            page.update()
    except Exception:
        pass  # flet_audio nicht verfügbar (Dev-Modus)

    def play_sound(name: str):
        audio = _sounds.get(name)
        if audio:
            page.run_task(audio.play)

    def broadcast_sound(name: str):
        """Host sendet Sound-Event an alle Clients."""
        lobby_id = _get_lobby_id(page)
        if not lobby_id:
            return
        page.pubsub.send_all(json.dumps({
            "type": "play_sound",
            "lobby_id": lobby_id,
            "name": name,
        }))

    def set_question_audio_src(src: str):
        """Merkt Audio-Src vor; _apply_pending_audio() führt die eigentliche Arbeit durch."""
        _pending_audio_src[0] = src

    def _apply_pending_audio():
        """Muss nach page.views.append() aufgerufen werden, damit page.services erreichbar ist."""
        src = _pending_audio_src[0]
        _pending_audio_src[0] = None
        if not src or not _flet_audio_available[0]:
            return
        if _q_audio[0] and _q_audio[0] in page.services:
            page.services.remove(_q_audio[0])
        fa = _flet_audio_cls(src=src, autoplay=False, release_mode=_release_mode_stop)

        # Event-basierte Duration- und Positions-Aktualisierung (zuverlässiger als Polling)
        def _on_duration_change(e):
            try:
                ms = e.duration.in_milliseconds
                _q_audio_duration[0] = ms
                _flet_audio_works[0] = True
                print(f"[AUDIO] on_duration_change: {ms}ms")
            except Exception as ex:
                print(f"[AUDIO] on_duration_change error: {ex}")

        def _on_position_change(e):
            try:
                _q_audio_position[0] = (e.position, time.monotonic())
            except Exception:
                pass

        fa.on_duration_change = _on_duration_change
        fa.on_position_change = _on_position_change

        _q_audio_duration[0] = None
        _q_audio_position[0] = None
        page.services.append(fa)
        _q_audio[0] = fa
        _flet_audio_works[0] = None  # wird durch on_duration_change oder play()-Timeout gesetzt
        # Lautstärke wird in play_question_audio() direkt vor fa.play() angewendet,
        # wenn Flutter das Control bereits kennt (nach page.update()).

    def play_question_audio():
        """Spielt das geladene Frage-Audio ab. Timeout dient zur Dev-Modus-Erkennung."""
        if not _q_audio[0]:
            return
        # Position auf (0, jetzt) setzen → Interpolation startet sofort ab 0ms
        _q_audio_position[0] = (0, time.monotonic())
        fa = _q_audio[0]

        async def _do_play():
            # Lautstärke direkt vor play() setzen: Flutter kennt das Control bereits,
            # da page.update() bei der Fragenanzeige schon gelaufen ist.
            saved_vol = page.session.store.get("_audio_volume")
            print(f"[VOL] _do_play: saved_vol={saved_vol!r}")
            if saved_vol is not None:
                fa.volume = float(saved_vol)
                fa.update()
            try:
                await asyncio.wait_for(fa.play(), timeout=3.0)
                # _flet_audio_works wird via on_duration_change gesetzt; hier nur Fallback
                if _flet_audio_works[0] is None:
                    _flet_audio_works[0] = True
            except Exception:
                _flet_audio_works[0] = False

        page.run_task(_do_play)

    def broadcast_question_audio():
        """Sendet Play-Event für Frage-Audio an alle Clients."""
        lobby_id = _get_lobby_id(page)
        if not lobby_id:
            return
        page.pubsub.send_all(json.dumps({
            "type": "play_question_audio",
            "lobby_id": lobby_id,
        }))

    def get_audio_position():
        """Gibt die interpolierte Abspielposition zurück (int ms).
        Interpoliert zwischen on_position_change-Events; gecappt auf 900ms um
        Overshoot und Rücksprünge beim nächsten Event zu vermeiden."""
        data = _q_audio_position[0]
        if data is None:
            return None
        pos_ms, t = data
        # Cap: nie mehr als 900ms über den letzten Event-Wert hinaus interpolieren
        elapsed_ms = min(int((time.monotonic() - t) * 1000), 900)
        return pos_ms + elapsed_ms

    def set_audio_volume(value: float):
        """Setzt die lokale Lautstärke (0.0–1.0)."""
        clamped = max(0.0, min(1.0, value))
        print(f"[VOL] set_audio_volume({clamped:.2f}), fa exists={_q_audio[0] is not None}")
        if _q_audio[0]:
            _q_audio[0].volume = clamped
            _q_audio[0].update()

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
                play_sound=play_sound,
                broadcast_sound=broadcast_sound,
                play_question_audio=play_question_audio,
                broadcast_question_audio=broadcast_question_audio,
                set_question_audio_src=set_question_audio_src,
                flet_audio_available=_flet_audio_available[0],
                flet_audio_works_ref=lambda: _flet_audio_works[0],
                get_audio_duration_fn=lambda: _q_audio_duration[0],
                get_audio_position_fn=get_audio_position,
                set_audio_volume_fn=set_audio_volume,
            )

        return ft.Text(f"Unbekannter Screen: {state.screen}")

    def _build_menu_control() -> ft.Control:
        def on_host():
            push_route(page, "/host-setup")

        def on_join():
            push_route(page, "/join")

        def on_create():
            push_route(page, "/create")

        return menu_view(on_host=on_host, on_join=on_join, on_create=on_create)

    def _build_host_setup_control() -> ft.Control:
        def on_create(settings: dict):
            s = _store(page)
            s.set("role", "host")
            s.set("lobby_id", str(uuid.uuid4())[:8].upper())
            s.set("board_id", settings.get("board_id", ""))
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

    def _build_board_overview() -> ft.Control:
        boards = list_boards()  # [(board_id, title, wip), ...]

        def _edit_row(board_id: str, title: str, wip: bool) -> ft.Control:
            badge = ft.Container(
                padding=ft.Padding(left=6, right=6, top=2, bottom=2),
                border_radius=4,
                bgcolor="error_container",
                content=ft.Text("WIP", size=11, color="on_error_container"),
                visible=wip,
            )
            return ft.Row(
                controls=[
                    ft.Text(title, expand=True, size=16,
                            opacity=0.5 if wip else 1.0, italic=wip),
                    badge,
                    ft.OutlinedButton(
                        "Bearbeiten",
                        on_click=lambda _, bid=board_id: push_route(page, f"/create?board={bid}"),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        board_rows = [_edit_row(bid, title, wip) for bid, title, wip in boards] if boards else [
            ft.Text("Noch keine Boards vorhanden.", italic=True, opacity=0.6)
        ]

        return ft.Column(
            controls=[
                topbar_view(title="Boards", on_back=lambda: push_route(page, "/menu"), back_label="Zum Menü"),
                ft.Container(height=24),
                ft.Text("Vorhandene Boards", size=15, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                ft.Column(controls=board_rows, spacing=8, tight=True),
                ft.Container(height=24),
                ft.FilledButton(
                    "Neues Board erstellen",
                    on_click=lambda _: push_route(page, "/create?new=1"),
                    width=240,
                ),
            ],
            tight=True,
        )

    def route_change(_):
        route = page.route or "/"

        if route == "/":
            push_route(page, "/menu")
            return

        # Query-String vom Pfad trennen, bevor wir splitten
        path = route.split("?")[0]
        parts = [p for p in path.split("/") if p]

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

        if len(parts) == 1 and parts[0] == "create":
            qd = page.query.to_dict if page.query else {}
            board_id = qd.get("board") or ""
            is_new = bool(qd.get("new"))
            if board_id:
                # Schritt 2: bestehendes Board bearbeiten
                ctrl = board_editor_view(page, board_id=board_id, on_back=lambda: push_route(page, "/create"))
            elif is_new:
                # Schritt 1: neues Board anlegen
                ctrl = board_setup_view(
                    page,
                    on_back=lambda: push_route(page, "/create"),
                    on_created=lambda bid: push_route(page, f"/create?board={bid}"),
                )
            else:
                # Übersichtsseite
                ctrl = _build_board_overview()
            page.views.clear()
            page.views.append(
                ft.View(
                    route=route,
                    controls=[ctrl],
                    padding=LAYOUT.page_padding,
                    scroll=ft.ScrollMode.AUTO,
                )
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
        _apply_pending_audio()
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

        if msg_type == "play_sound":
            play_sound(msg.get("name", ""))
            return

        if msg_type == "play_question_audio":
            play_question_audio()
            fn = page.session.store.get("_trigger_question_audio")
            if callable(fn):
                fn()
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
                _apply_pending_audio()
                page.update()

            if page.session and page.session.connection:
                page.run_task(_refresh_lobby)
            return

        if msg_type == "player_buzz" and _get_role(page) == "host":
            with _buzz_lock:
                if state.buzzer_open:
                    player_id = msg.get("player_id", "")
                    idx = next((i for i, p in enumerate(state.players) if p.player_id == player_id), -1)
                    if idx >= 0 and idx not in state.buzzed_queue:
                        state.buzzed_queue.append(idx)
                    if state.buzzed_queue:
                        state.set_answerer(state.buzzed_queue[0])
                        state.buzzer_open = False
                    broadcast_state()

                async def _refresh_question():
                    play_sound("buzz")
                    page.views.clear()
                    page.views.append(
                        ft.View(route=page.route, controls=[_build_screen_control()], padding=LAYOUT.page_padding)
                    )
                    _apply_pending_audio()
                    page.update()

                if page.session and page.session.connection:
                    page.run_task(_refresh_question)
            return

        if msg_type == "player_estimate" and _get_role(page) == "host":
            player_id = msg.get("player_id", "")
            answer = msg.get("answer", "")
            state.estimates[player_id] = answer

            async def _refresh_estimates():
                page.views.clear()
                page.views.append(
                    ft.View(route=page.route, controls=[_build_screen_control()], padding=LAYOUT.page_padding)
                )
                _apply_pending_audio()
                page.update()

            if page.session and page.session.connection:
                page.run_task(_refresh_estimates)
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
            _apply_pending_audio()
            page.update()

        if page.session and page.session.connection:
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
