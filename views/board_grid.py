import flet as ft
from app_state import AppState


def board_grid_view(
    page: ft.Page,
    state: AppState,
    on_pick_tile,
) -> ft.Control:
    """
    Rendert das Jeopardy-Board (Header + Tiles) in einem eigenen Host-Container:
    - Spaltenbreite verteilt sich gleichmäßig über die Containerbreite
    - Mindestbreite pro Spalte; wenn überschritten -> horizontaler Scroll
    - Host hat fixe Höhe (Board expandet nicht vertikal)
    - host.data["recompute"] = Funktion zum Rebuild bei Resize
    """
    if state.board is None:
        return ft.Text("Kein Board geladen.")

    # ---- Board sizing ----
    MIN_COL_W = 220
    CELL_H = 76
    GAP = 12

    rows = len(state.board.categories[0].tiles)
    cols = len(state.board.categories)

    tile_btn_style = ft.ButtonStyle(
        alignment=ft.Alignment.CENTER,
        shape=ft.RoundedRectangleBorder(radius=10),
    )

    def build_board_grid(col_w: int) -> ft.Control:
        header = ft.Row(
            controls=[
                ft.Container(
                    width=col_w,
                    height=CELL_H,
                    alignment=ft.Alignment.CENTER,
                    padding=10,
                    border=ft.Border.all(1, color="outline"),
                    bgcolor="surface_container",
                    border_radius=10,
                    content=ft.Text(cat.title, weight=ft.FontWeight.BOLD),
                )
                for cat in state.board.categories
            ],
            spacing=GAP,
        )

        def tile_cell(cat_i: int, tile_i: int) -> ft.Control:
            tile = state.board.categories[cat_i].tiles[tile_i]

            def _pick(_):
                if tile.used:
                    return
                on_pick_tile(cat_i, tile_i)

            return ft.Container(
                width=col_w,
                height=CELL_H,
                alignment=ft.Alignment.CENTER,
                content=ft.Button(
                    content=str(tile.value),
                    on_click=_pick,
                    disabled=tile.used,
                    style=tile_btn_style,
                    width=col_w,
                    height=CELL_H,
                ),
            )

        grid_rows = [header]
        for r in range(rows):
            grid_rows.append(
                ft.Row(
                    controls=[tile_cell(c, r) for c in range(cols)],
                    spacing=GAP,
                )
            )

        return ft.Column(controls=grid_rows, spacing=GAP)

    board_content = ft.Column()

    # Fixe Höhe: Header + rows
    board_height = (CELL_H + GAP) * (rows + 1) + GAP

    host = ft.Container(
        height=board_height,
        padding=8,
        border=ft.Border.all(1, color="outline"),
        bgcolor="surface_container",
        border_radius=12,
        content=ft.Row(
            controls=[board_content],
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    def recompute():
        usable = (page.width or 1200)
        try:
            pad = page.padding or 0
        except RuntimeError:
            pad = 0
        usable -= 2 * pad
        usable -= 2 * 8  # host.padding

        col_w = int(max(MIN_COL_W, (usable - (cols - 1) * GAP) / cols))
        board_content.controls = [build_board_grid(col_w)]

    # Initial befüllen (kein update() auf board_content!)
    recompute()

    host.data = {"recompute": recompute}
    return host
