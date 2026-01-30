import flet as ft


def topbar_view(
    title: str,
    on_back=None,
    right_control: ft.Control | None = None,
) -> ft.Control:
    """
    Topbar mit:
    - optionalem Zurück-Button links
    - zentriertem Titel (global zentriert)
    - optionalem rechten Control (Timer, Host-Info, ...)
    """

    left = (
        ft.OutlinedButton("Zur Lobby", on_click=on_back)
        if on_back
        else ft.Container(width=120)
    )

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
