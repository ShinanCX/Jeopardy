import flet as ft
from typing import Callable, Optional

from ui.layout import LAYOUT


class PlayerCard(ft.Container):
    def __init__(
        self,
        name: str,
        score: int,
        is_active: bool = False,
        on_select: Optional[Callable[[], None]] = None,
        body_content: ft.Control | None = None,
        footer_controls: list[ft.Control] | None = None,
        highlight_color: str | None = None,
    ):
        super().__init__()

        self.name = name
        self.score = score
        self.is_active = is_active
        self.body_content = body_content
        self.footer_controls = footer_controls
        self.highlight_color = highlight_color

        border_color = highlight_color if highlight_color else ("primary" if is_active else "outline")
        border_width = 2 if (is_active or highlight_color) else 1
        self.border = ft.Border.all(border_width, color=border_color)
        self.border_radius = 16
        self.padding = LAYOUT.card_padding
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
        middle = ft.Container(
            expand=1,
            alignment=ft.Alignment.CENTER,
            content=self.body_content,
        )

        score_badge = self._badge(f"Punkte: {self.score}")
        if self.footer_controls:
            bottom = ft.Column(
                controls=[
                    ft.Container(alignment=ft.Alignment.CENTER, content=score_badge),
                    ft.Row(
                        controls=self.footer_controls,
                        alignment=ft.MainAxisAlignment.CENTER,
                        wrap=True,
                        spacing=4,
                    ),
                ],
                tight=True,
                spacing=4,
            )
        else:
            bottom = ft.Container(alignment=ft.Alignment.CENTER, content=score_badge)

        return ft.Column(
            controls=[
                ft.Container(alignment=ft.Alignment.CENTER, content=self._badge(self.name)),
                middle,
                bottom,
            ],
            spacing=8,
        )
