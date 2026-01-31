import math
import flet as ft
from app_state import AppState
from views.components.player_card import PlayerCard


def player_view(page: ft.Page, state: AppState) -> ft.Container:
    state.ensure_players()

    MIN_PLAYER_W = 220
    PLAYER_GAP = 12

    players_content = ft.Column()

    host = ft.Container(
        expand=1,
        padding=8,
        border=ft.Border.all(1, color="outline"),
        border_radius=12,
        bgcolor="surface_container",
        content=ft.Row(
            controls=[players_content],
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    def build_players_row(card_width: int) -> ft.Row:
        cards = []

        for i, p in enumerate(state.players):
            def select_turn(i=i):
                state.set_turn(i)
                recompute()
                page.update()  # nur optisch; Screen bleibt gleich

            c = PlayerCard(
                name=p.name,
                score=p.score,
                is_active=p.is_turn,
                on_select=select_turn,
            )
            c.width = card_width
            c.expand = 1
            cards.append(c)

        return ft.Row(controls=cards, spacing=PLAYER_GAP, expand=1)

    def recompute():
        state.ensure_players()
        n = max(1, len(state.players))

        usable = page.width or 1200
        try:
            pad = page.padding or 0
        except RuntimeError:
            pad = 0
        usable -= 2 * pad
        usable -= 2 * 8  # host.padding
        usable -= 2 * 1 # host.border
        usable -= 2  # Sicherheitsmarge

        gaps = (n - 1) * PLAYER_GAP
        # verfügbare Breite für Karten
        available_for_cards = max(0, usable - gaps)

        # floor statt int() (int() ist auch floor, aber wir halten's explizit)
        card_w = math.floor(available_for_cards / n)

        # Mindestbreite erzwingen (dann darf gescrollt werden)
        card_w = max(MIN_PLAYER_W, card_w)
        players_content.controls = [build_players_row(card_w)]

    recompute()
    host.data = {"recompute": recompute}
    return host
