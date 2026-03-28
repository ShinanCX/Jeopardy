import flet as ft
from app_state import AppState
from models.models import build_dummy_board
from views.topbar import topbar_view


def lobby_view(page: ft.Page, state: AppState, rerender, *, broadcast_state=None) -> ft.Control:
    role = (page.session.store.get("role") or "host").lower()
    is_host = role == "host"
    lobby_id = page.session.store.get("lobby_id") or "—"

    def on_new_game(_):
        if not is_host:
            return

        state.board = build_dummy_board(cols=6, rows=5)
        state.ensure_players()
        state.screen = "board"
        rerender()

        if broadcast_state:
            broadcast_state()

    def go_menu(_):
        import json
        from views.router import push_route
        if is_host:
            state.screen = "menu"
            if broadcast_state:
                broadcast_state()
        else:
            player_id = page.session.store.get("player_id")
            msg = json.dumps({
                "type": "player_leave",
                "lobby_id": lobby_id,
                "player_id": player_id,
            })
            page.pubsub.send_all(msg)
        push_route(page, "/menu")

    copy_btn = ft.IconButton(
        icon=ft.Icons.COPY,
        tooltip="Lobby-Code kopieren",
        on_click=lambda _: page.run_task(page.clipboard.set, lobby_id),
    )

    topbar = topbar_view(
        title=f"Lobby · {lobby_id}",
        on_back=go_menu,
        back_label="Zum Menü",
        right_control=copy_btn,
    )

    real_players = [p for p in state.players if p.player_id]

    def filled_slot(name: str) -> ft.Control:
        return ft.Container(
            padding=ft.Padding(left=16, right=16, top=10, bottom=10),
            border_radius=10,
            bgcolor="surface_container",
            content=ft.Text(name, size=15),
        )

    def empty_slot(index: int) -> ft.Control:
        return ft.Container(
            padding=ft.Padding(left=16, right=16, top=10, bottom=10),
            border_radius=10,
            border=ft.Border.all(1, color="outline"),
            content=ft.Text(f"Slot {index} – wartet…", size=15, italic=True, color="outline"),
        )

    if is_host:
        slots = []
        for i in range(state.max_players):
            if i < len(real_players):
                slots.append(filled_slot(real_players[i].name))
            else:
                slots.append(empty_slot(i + 1))
        player_list = ft.Column(controls=slots, spacing=8)
    else:
        player_list = ft.Column(
            controls=[filled_slot(p.name) for p in real_players] if real_players else [
                ft.Text("Noch keine Spieler beigetreten…", italic=True, color="outline"),
            ],
            spacing=8,
        )

    return ft.Column(
        controls=[
            topbar,
            ft.Container(height=16),
            ft.Text("Spieler", size=16, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            player_list,
            ft.Container(height=24),
            ft.FilledButton("Spiel starten", on_click=on_new_game, visible=is_host),
            ft.Text("Warte auf den Host…", visible=not is_host),
        ],
        tight=True,
    )
