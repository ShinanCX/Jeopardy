import flet as ft
from typing import Callable
from board_loader import list_boards
from views.topbar import topbar_view

MIN_PLAYERS = 2
MAX_PLAYERS = 8


def host_setup_view(
    on_create: Callable[[dict], None],
    on_back: Callable,
) -> ft.Control:
    max_players_val = [4]

    count_label = ft.Text(str(max_players_val[0]), size=24, weight=ft.FontWeight.BOLD, width=40, text_align=ft.TextAlign.CENTER)
    error_text = ft.Text("", color="error", visible=False)

    boards = list_boards()  # [(board_id, title), ...]

    def update_count(delta: int):
        new_val = max_players_val[0] + delta
        if new_val < MIN_PLAYERS or new_val > MAX_PLAYERS:
            return
        max_players_val[0] = new_val
        count_label.value = str(new_val)
        count_label.update()

    def on_submit(_):
        board_id = board_control.value if isinstance(board_control, ft.Dropdown) else None
        if not board_id:
            error_text.value = "Bitte ein Board auswählen."
            error_text.visible = True
            error_text.update()
            return
        error_text.visible = False
        error_text.update()
        on_create({"max_players": max_players_val[0], "board_id": board_id})

    topbar = topbar_view(
        title="Lobby erstellen",
        on_back=on_back,
        back_label="Zum Menü",
    )

    if boards:
        board_control = ft.Dropdown(
            label="Board auswählen",
            width=280,
            options=[ft.dropdown.Option(key=bid, text=title) for bid, title in boards],
        )
    else:
        board_control = ft.Text(
            "Keine Boards gefunden. Lege ein Board unter boards/<name>/board.json an.",
            color="error",
            italic=True,
        )

    return ft.Column(
        controls=[
            topbar,
            ft.Container(height=40),
            ft.Column(
                controls=[
                    ft.Text("Board", size=15),
                    ft.Container(height=8),
                    board_control,
                    ft.Container(height=8),
                    error_text,
                    ft.Container(height=24),
                    ft.Text("Maximale Spieleranzahl", size=15),
                    ft.Container(height=8),
                    ft.Row(
                        controls=[
                            ft.IconButton(ft.Icons.REMOVE, on_click=lambda _: update_count(-1)),
                            count_label,
                            ft.IconButton(ft.Icons.ADD, on_click=lambda _: update_count(1)),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=32),
                    ft.FilledButton("Lobby erstellen", on_click=on_submit, width=240),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
        ],
        tight=True,
    )