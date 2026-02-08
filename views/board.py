import flet as ft

from app_state import AppState, Capabilities, compute_capabilities

from views.player_view import player_view
from views.board_grid import board_grid_view
from views.topbar import topbar_view


def board_view(page: ft.Page, state: AppState, rerender, broadcast_state, caps: Capabilities | None = None) -> (
        ft.Control):
    if state.board is None:
        state.screen = "lobby"
        rerender()
        return ft.Text("Kein Board geladen – zurück zur Lobby.")

    state.ensure_players()

    if caps is None:
        role = (page.session.store.get("role") or "host")
        caps = compute_capabilities(state, role)

    def go_lobby(_):
        state.screen = "lobby"
        rerender()

    topbar = topbar_view(
        title="Testboard",
        on_back=go_lobby,
    )

    def on_pick_tile(cat_i: int, tile_i: int):
        if not caps.can_pick_tile:
            return
        state.selected = (cat_i, tile_i)
        state.start_question_round()
        state.screen = "question"
        rerender()
        broadcast_state()

    board_host = board_grid_view(
        page,
        state,
        on_pick_tile=on_pick_tile,
        can_pick_tile=caps.can_pick_tile,
    )
    player_host = player_view(page, state, broadcast_state, can_select_turn=caps.can_select_turn)

    def recompute_all():
        # Board recompute
        bd = getattr(board_host, "data", None) or {}
        fn = bd.get("recompute")
        if callable(fn):
            fn()

        # Player recompute
        pd = getattr(player_host, "data", None) or {}
        fn = pd.get("recompute")
        if callable(fn):
            fn()

    def on_resize(_):
        recompute_all()
        page.update()

    page.on_resize = on_resize
    recompute_all()

    return ft.Column(
        controls=[
            topbar,
            ft.Container(height=10),
            board_host,              # fix height -> kein vertikales expand
            ft.Container(height=10),
            player_host,             # expand=1 -> nimmt Resthöhe
        ],
        expand=True,
        spacing=0,
    )
