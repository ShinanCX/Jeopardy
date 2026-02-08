import flet as ft

from app_state import AppState, Capabilities, compute_capabilities
from views.topbar import topbar_view


def question_view(page: ft.Page, state: AppState, rerender, broadcast_state, caps: Capabilities | None = None) -> (
        ft.Control):
    # Guard rails
    if state.board is None or state.selected is None:
        state.screen = "board"
        rerender()
        return ft.Text("Keine Frage ausgewählt.")

    state.ensure_players()
    if caps is None:
        role = page.session.store.get("role") or "host"
        caps = compute_capabilities(state, role)

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

    def refresh_answer():
        answer_text.value = f"{tile.question.answer}" if state.question_answer_revealed else ""

    def refresh_status():
        """Refresh answerer labels + host button captions."""
        state.ensure_players()
        idx = max(0, min(state.question_answerer_index, len(state.players) - 1))
        state.question_answerer_index = idx

        a = state.players[idx]
        answerer_name_text.value = a.name
        buzzer_state_text.value = "• Buzzers offen" if state.buzzer_open else "• Nur Turn-Owner"

        if caps.can_award_points:
            correct_btn.content = f"✅ Richtig ({a.name})"
            wrong_btn.content = f"❌ Falsch ({a.name})"

    def refresh_buzzer_controls():
        """Show/hide buzzer simulation controls depending on buzzer_open."""
        if not caps.can_simulate_buzzer:
            buzzer_holder.content = ft.Container()
            return

        def pick_answerer(i: int):
            if not state.buzzer_open and state.question_answerer_index is not None:
                return

            if state.buzzer_open:
                if i not in state.buzzed_queue:
                    state.buzzed_queue.append(i)
                state.set_answerer(state.buzzed_queue[0])
                state.buzzer_open = False

            refresh_status()
            refresh_buzzer_controls()
            page.update()
            broadcast_state()

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
        state.question_answer_revealed = True
        refresh_answer()
        page.update()
        broadcast_state()

    def back_without_use(_):
        state.selected = None
        state.end_question_round()
        state.screen = "board"
        rerender()
        broadcast_state()

    def finish_round_and_back():
        tile.used = True
        state.selected = None
        state.end_question_round()
        state.screen = "board"
        broadcast_state()

    def host_correct(_):
        if not caps.can_award_points:
            return
        a = state.players[state.question_answerer_index]
        a.score += tile.value

        # Turn rule (current default): next player after resolved question
        state.advance_turn()

        finish_round_and_back()
        rerender()

    def host_wrong(_):
        if not caps.can_award_points:
            return
        a = state.players[state.question_answerer_index]
        a.score -= tile.value

        # Open buzzers for remaining players (stay in question view)
        state.open_buzzer()

        refresh_status()
        refresh_buzzer_controls()
        page.update()

        broadcast_state()

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

    host_controls = ft.Container(
        visible=caps.can_award_points,
        content=ft.Column(
            controls=[
                ft.Text("Host-Steuerung", weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=[
                        ft.OutlinedButton("Antwort zeigen", on_click=reveal),
                        ft.TextButton("Zurück (ohne verbrauchen)", on_click=back_without_use),
                    ],
                    wrap=True,
                ),
                ft.Row(controls=[correct_btn, wrong_btn], wrap=True),
            ],
            tight=True,
            spacing=8,
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
                host_controls,
            ],
            tight=True,
            spacing=8,
        ),
    )

    # initial fill
    refresh_answer()
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
