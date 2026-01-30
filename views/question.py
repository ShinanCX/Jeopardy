import flet as ft

from app_state import AppState
from views.topbar import topbar_view


def question_view(page: ft.Page, state: AppState, rerender) -> ft.Control:
    # Guard rails
    if state.board is None or state.selected is None:
        state.screen = "board"
        rerender()
        return ft.Text("Keine Frage ausgewählt.")

    state.ensure_players()

    cat_i, tile_i = state.selected
    cat = state.board.categories[cat_i]
    tile = cat.tiles[tile_i]

    # --- UI controls we want to update without rebuilding the whole view ---
    answer_text = ft.Text("", size=18, selectable=True)

    answerer_name_text = ft.Text("")
    buzzer_state_text = ft.Text("", opacity=0.8)

    correct_btn = ft.Button(content="✅ Richtig", on_click=lambda _: None)
    wrong_btn = ft.Button(content="❌ Falsch", on_click=lambda _: None)

    buzzer_holder = ft.Container()  # will receive content dynamically

    def refresh_status():
        """Refresh answerer labels + host button captions."""
        state.ensure_players()
        idx = max(0, min(state.question_answerer_index, len(state.players) - 1))
        state.question_answerer_index = idx

        a = state.players[idx]
        answerer_name_text.value = a.name
        buzzer_state_text.value = "• Buzzers offen" if state.buzzer_open else "• Nur Turn-Owner"

        correct_btn.content = f"✅ Richtig ({a.name})"
        wrong_btn.content = f"❌ Falsch ({a.name})"

    def refresh_buzzer_controls():
        """Show/hide buzzer simulation controls depending on buzzer_open."""
        if not state.buzzer_open:
            buzzer_holder.content = ft.Container()
            return

        def pick_answerer(i: int):
            state.set_answerer(i)
            refresh_status()
            refresh_buzzer_controls()
            page.update()

        buzzer_holder.content = ft.Container(
            padding=12,
            border=ft.Border.all(1, color="outline"),
            border_radius=12,
            bgcolor="surface_container",
            content=ft.Column(
                controls=[
                    ft.Text("Buzzer (Simulation)", weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Später ersetzen wir das durch echte Buzz-Events (WebSocket).",
                        size=12,
                        opacity=0.7,
                    ),
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                content=f"{p.name} buzzert",
                                on_click=lambda e, i=i: pick_answerer(i),
                                disabled=(i == state.question_answerer_index),
                            )
                            for i, p in enumerate(state.players)
                        ],
                        wrap=True,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        )

    # --- actions ---
    def reveal(_):
        answer_text.value = f"Antwort: {tile.question.answer}"
        page.update()

    def back_without_use(_):
        state.selected = None
        state.end_question_round()
        state.screen = "board"
        rerender()

    def finish_round_and_back():
        tile.used = True
        state.selected = None
        state.end_question_round()
        state.screen = "board"

    def host_correct(_):
        a = state.players[state.question_answerer_index]
        a.score += tile.value

        # Turn rule (current default): next player after resolved question
        state.advance_turn()

        finish_round_and_back()
        rerender()

    def host_wrong(_):
        a = state.players[state.question_answerer_index]
        a.score -= tile.value

        # Open buzzers for remaining players (stay in question view)
        state.open_buzzer()

        refresh_status()
        refresh_buzzer_controls()
        page.update()

    # wire host button handlers (now that functions exist)
    correct_btn.on_click = host_correct
    wrong_btn.on_click = host_wrong

    # --- topbar ---
    topbar = topbar_view(title="Frage", on_back=back_without_use)

    # --- status strip ---
    status_strip = ft.Container(
        padding=10,
        border=ft.Border.all(1, color="outline"),
        border_radius=12,
        bgcolor="surface_container",
        content=ft.Row(
            controls=[
                ft.Text("Antwortet:", weight=ft.FontWeight.BOLD),
                answerer_name_text,
                buzzer_state_text,
            ],
            wrap=True,
        ),
    )

    # --- question card ---
    card = ft.Container(
        padding=16,
        border=ft.Border.all(1, color="outline"),
        border_radius=12,
        bgcolor="surface_container",
        content=ft.Column(
            controls=[
                ft.Text(f"{cat.title} – {tile.value}", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Text(tile.question.prompt, size=22),
                ft.Container(height=10),
                answer_text,
                ft.Container(height=10),
                ft.Row(
                    controls=[
                        ft.OutlinedButton("Antwort zeigen", on_click=reveal),
                        ft.TextButton("Zurück (ohne verbrauchen)", on_click=back_without_use),
                    ],
                    wrap=True,
                ),
                ft.Container(height=8),
                ft.Text("Host-Steuerung", weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=[
                        correct_btn,
                        wrong_btn,
                    ],
                    wrap=True,
                ),
            ],
            tight=True,
            spacing=8,
        ),
    )

    # initial fill
    refresh_status()
    refresh_buzzer_controls()

    return ft.Column(
        controls=[
            topbar,
            ft.Container(height=10),
            status_strip,
            ft.Container(height=10),
            card,
            ft.Container(height=10),
            buzzer_holder,
        ],
        expand=True,
    )
