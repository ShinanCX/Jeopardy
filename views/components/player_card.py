import flet as ft
from typing import Callable, Optional


class PlayerCard(ft.Container):
    def __init__(
        self,
        name: str,
        score: int,
        is_active: bool = False,
        on_select: Optional[Callable[[], None]] = None,
    ):
        super().__init__()

        self.name = name
        self.score = score
        self.is_active = is_active

        self.border = ft.Border.all(2 if is_active else 1, color="primary" if is_active else "outline")
        self.border_radius = 16
        self.padding = 12
        self.expand = 1
        self.bgcolor = "surface_container"

        # klickbar (Host kann Turn setzen)
        if on_select is not None:
            self.on_click = lambda _: on_select()

        self.content = self._build()

    def _badge(self, text: str) -> ft.Container:
        return ft.Container(
            padding=ft.Padding(left=12, right=12, top=6, bottom=6),
            border_radius=12,
            alignment=ft.Alignment.CENTER,
            bgcolor="#26ffffff",
            content=ft.Text(text, weight=ft.FontWeight.BOLD),
        )

    def _build(self) -> ft.Control:
        return ft.Column(
            controls=[
                ft.Container(alignment=ft.Alignment.CENTER, content=self._badge(self.name)),
                ft.Container(
                    expand=1,
                    alignment=ft.Alignment.CENTER,
                    content=None,
                ),
                ft.Container(alignment=ft.Alignment.CENTER, content=self._badge(f"Punkte: {self.score}")),
            ],
            spacing=8,
        )
