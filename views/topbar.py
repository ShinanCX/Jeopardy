import flet as ft


def topbar_view(
    title: str,
    on_back=None,
    back_label: str = "Zur Lobby",
    right_control: ft.Control | None = None,
    left_extra: ft.Control | None = None,
) -> ft.Control:
    """
    Topbar mit:
    - optionalem Zurück-Button links (+ optionalem left_extra daneben)
    - zentriertem Titel (global zentriert)
    - optionalem rechten Control (Timer, Host-Info, ...)
    """

    if on_back:
        back_btn = ft.OutlinedButton(back_label, on_click=on_back)
        if left_extra is not None:
            left = ft.Row(
                controls=[back_btn, left_extra],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            )
        else:
            left = back_btn
    else:
        left = left_extra if left_extra is not None else ft.Container(width=120)

    center = ft.Container(
        alignment=ft.Alignment.CENTER,
        content=ft.Text(title, size=22, weight=ft.FontWeight.BOLD),
        expand=1,
    )

    right = right_control if right_control else ft.Container(width=120)

    return ft.Container(
        padding=ft.Padding(left=0, top=8, right=0, bottom=8),
        content=ft.Row(
            controls=[
                left,
                center,
                right,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
