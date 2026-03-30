from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from pathlib import Path

import flet as ft

from app_state import AppState, Capabilities, compute_capabilities
from views.topbar import topbar_view


def question_view(
    page: ft.Page,
    state: AppState,
    rerender,
    broadcast_state,
    caps: Capabilities | None = None,
    play_sound=None,
    broadcast_sound=None,
    play_question_audio=None,
    broadcast_question_audio=None,
    set_question_audio_src=None,
    flet_audio_available: bool = False,
    flet_audio_works_ref=None,
    get_audio_duration_fn=None,
    get_audio_position_fn=None,
    set_audio_volume_fn=None,
) -> ft.Control:
    # Guard rails
    if state.board is None or state.selected is None:
        state.screen = "board"
        rerender()
        return ft.Text("Keine Frage ausgewählt.")

    state.ensure_players()
    role = (page.session.store.get("role") or "host").lower()
    if caps is None:
        caps = compute_capabilities(state, role)

    cat_i, tile_i = state.selected
    cat = state.board.categories[cat_i]
    tile = cat.tiles[tile_i]
    q = tile.question
    q_type = q.type  # "text" | "image" | "audio" | "estimate"

    def _play(name: str):
        if play_sound:
            play_sound(name)
        if broadcast_sound:
            broadcast_sound(name)

    # -------------------------------------------------------------------------
    # Shared UI refs
    # -------------------------------------------------------------------------
    answer_container = ft.Container()
    answerer_name_text = ft.Text("")
    buzzer_state_text = ft.Text("", opacity=0.8)
    correct_btn = ft.Button(content="✅ Richtig", on_click=lambda _: None)
    wrong_btn = ft.Button(content="❌ Falsch", on_click=lambda _: None)
    buzzer_holder = ft.Container()
    estimates_column = ft.Column(spacing=6, tight=True)  # host-only, estimate mode

    # -------------------------------------------------------------------------
    # Answer section
    # -------------------------------------------------------------------------
    def refresh_answer():
        if role == "host":
            if state.question_answer_revealed:
                badge = ft.Container(
                    padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                    border_radius=6,
                    bgcolor="tertiary_container",
                    content=ft.Text("✓ Für Spieler sichtbar", size=12, color="on_tertiary_container"),
                )
            else:
                badge = ft.Container(
                    padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                    border_radius=6,
                    bgcolor="surface_container_highest",
                    content=ft.Text("Noch nicht aufgedeckt", size=12, color="outline"),
                )
            answer_container.content = ft.Column(
                controls=[
                    ft.Text(
                        q.answer,
                        size=18,
                        selectable=True,
                        opacity=0.4 if not state.question_answer_revealed else 1.0,
                    ),
                    badge,
                ],
                tight=True,
                spacing=6,
            )
        else:
            answer_container.content = ft.Text(
                q.answer if state.question_answer_revealed else "",
                size=18,
                selectable=True,
            )

    # -------------------------------------------------------------------------
    # Status strip (not shown for estimate questions)
    # -------------------------------------------------------------------------
    def refresh_status():
        state.ensure_players()
        idx = max(0, min(state.question_answerer_index, len(state.players) - 1))
        state.question_answerer_index = idx
        a = state.players[idx]
        answerer_name_text.value = a.name
        buzzer_state_text.value = "• Buzzers offen" if state.buzzer_open else "• Nur Turn-Owner"
        if caps.can_award_points:
            correct_btn.content = f"✅ Richtig ({a.name})"
            wrong_btn.content = f"❌ Falsch ({a.name})"

    # -------------------------------------------------------------------------
    # Buzzer (not shown for estimate questions)
    # -------------------------------------------------------------------------
    def refresh_buzzer_controls():
        if q_type == "estimate":
            buzzer_holder.content = ft.Container()
            page.on_keyboard_event = None
            return

        if role != "player":
            buzzer_holder.content = ft.Container()
            return

        if not state.buzzer_open:
            page.on_keyboard_event = None
            buzzer_holder.content = ft.Container()
            return

        my_player_id = page.session.store.get("player_id") or ""
        my_index = next((i for i, p in enumerate(state.players) if p.player_id == my_player_id), -1)

        if my_index == state.question_answerer_index:
            page.on_keyboard_event = None
            buzzer_holder.content = ft.Container()
            return

        buzz_btn = ft.FilledButton("Buzz!  [Space]", width=200)

        def send_buzz(_=None):
            buzz_btn.disabled = True
            buzz_btn.update()
            lobby_id = page.session.store.get("lobby_id") or ""
            player_id = page.session.store.get("player_id") or ""
            msg = json.dumps({"type": "player_buzz", "lobby_id": lobby_id, "player_id": player_id})
            _play("buzz")
            page.pubsub.send_all(msg)
            page.on_keyboard_event = None

        buzz_btn.on_click = send_buzz

        def on_key(e: ft.KeyboardEvent):
            if e.key == " ":
                send_buzz()

        page.on_keyboard_event = on_key
        buzzer_holder.content = ft.Container(
            padding=16,
            alignment=ft.Alignment.CENTER,
            content=buzz_btn,
        )

    # -------------------------------------------------------------------------
    # Estimate: live input for player
    # -------------------------------------------------------------------------
    def _build_estimate_input() -> ft.Control:
        """Text field that sends on_change to host via PubSub."""
        my_player_id = page.session.store.get("player_id") or ""
        lobby_id = page.session.store.get("lobby_id") or ""
        existing = state.estimates.get(my_player_id, "")

        est_field = ft.TextField(
            label="Deine Schätzung",
            value=existing,
            expand=True,
            autofocus=True,
        )

        def on_estimate_change(e):
            msg = json.dumps({
                "type": "player_estimate",
                "lobby_id": lobby_id,
                "player_id": my_player_id,
                "answer": e.data,
            })
            page.pubsub.send_all(msg)

        est_field.on_change = on_estimate_change
        return ft.Column(
            controls=[
                ft.Text("Gib deine Schätzung ein:", size=15),
                ft.Row(controls=[est_field]),
            ],
            tight=True,
            spacing=8,
        )

    # -------------------------------------------------------------------------
    # Estimate: host sees live answers
    # -------------------------------------------------------------------------
    def refresh_estimates_display():
        rows = []
        for p in state.players:
            answer = state.estimates.get(p.player_id, "")
            rows.append(
                ft.Row(
                    controls=[
                        ft.Text(p.name, weight=ft.FontWeight.BOLD, width=140),
                        ft.Text(answer if answer else "—", italic=not answer, opacity=0.6 if not answer else 1.0),
                    ],
                )
            )
        estimates_column.controls = rows

    # -------------------------------------------------------------------------
    # Prompt / media area
    # -------------------------------------------------------------------------
    def _build_prompt_area() -> ft.Control:
        prompt_text = ft.Text(q.prompt, size=22)

        if q_type == "text":
            return prompt_text

        if q_type == "image":
            controls: list[ft.Control] = [prompt_text]
            if q.asset:
                try:
                    from board_loader import BOARDS_DIR
                    rel = Path(q.asset).relative_to(BOARDS_DIR)
                    src = f"/boards/{rel.as_posix()}"

                    def _open_zoom(_e, _src=src):
                        def _close(_):
                            dlg.open = False
                            page.update()
                        dlg = ft.AlertDialog(
                            content=ft.Image(src=_src, fit=ft.BoxFit.CONTAIN),
                            content_padding=ft.padding.all(0),
                            actions=[ft.TextButton("Schließen", on_click=_close)],
                            open=True,
                        )
                        page.overlay.append(dlg)
                        page.update()

                    controls.append(
                        ft.GestureDetector(
                            content=ft.Image(src=src, fit=ft.BoxFit.CONTAIN, height=300),
                            on_tap=_open_zoom,
                            mouse_cursor=ft.MouseCursor.ZOOM_IN,
                        )
                    )
                except Exception as _img_err:
                    print(f"[Image] Fehler beim Laden: {_img_err!r}  path={q.asset!r}")
                    controls.append(ft.Text(f"Bild nicht gefunden: {q.asset}", color="error", italic=True))
            return ft.Column(controls=controls, tight=True, spacing=8)

        if q_type == "audio":
            # Audio-URL aus absolutem Pfad berechnen
            audio_src = None
            if q.asset:
                try:
                    from board_loader import BOARDS_DIR
                    rel = Path(q.asset).relative_to(BOARDS_DIR)
                    audio_src = f"/boards/{rel.as_posix()}"
                except Exception:
                    pass

            if audio_src and set_question_audio_src:
                set_question_audio_src(audio_src)

            # Waveform-Balken: Höhen aus Dateinamen-Hash, Farbe = Fortschritt
            _seed = Path(q.asset).name if q.asset else "default"
            _h = hashlib.md5(_seed.encode()).digest()
            base_heights = [8 + (_h[i % len(_h)] % 44) for i in range(24)]
            is_playing = [False]

            bars: list[ft.Container] = [
                ft.Container(
                    width=5,
                    height=h,
                    bgcolor="outline",   # unplayed = dunkel
                    border_radius=2,
                    animate=ft.Animation(80, ft.AnimationCurve.EASE_IN_OUT),
                )
                for h in base_heights
            ]
            waveform_row = ft.Row(
                controls=bars,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=3,
            )
            waveform_box = ft.Container(
                height=68,
                border=ft.Border.all(1, color="outline"),
                border_radius=10,
                padding=ft.Padding(left=16, right=16, top=8, bottom=8),
                content=waveform_row,
                alignment=ft.Alignment(0, 0),
            )

            audio_status = ft.Text("", size=12, color="error", visible=False)

            def _audio_known_broken() -> bool:
                return bool(flet_audio_works_ref and flet_audio_works_ref() is False)

            def _fmt(ms: int) -> str:
                s = ms // 1000
                return f"{s // 60}:{s % 60:02d}"

            def _get_duration_ms() -> int | None:
                """Liest Duration frisch aus dem Cache (int ms, via on_duration_change)."""
                return get_audio_duration_fn() if get_audio_duration_fn else None

            # Zeitanzeige — Duration evtl. noch nicht da (Test läuft async)
            time_text = ft.Text(
                "0:00 / --:--",
                size=12,
                opacity=0.6,
                visible=flet_audio_available,
            )

            def _reset_bars():
                for bar in bars:
                    bar.bgcolor = "outline"
                dur_ms = _get_duration_ms()
                time_text.value = f"0:00 / {_fmt(dur_ms) if dur_ms else '--:--'}"
                try:
                    waveform_row.update()
                    time_text.update()
                except Exception:
                    pass

            async def _run_progress():
                # Duration frisch lesen; falls Test noch läuft kurz warten
                duration_ms = _get_duration_ms()
                print(f"[AUDIO] _run_progress start, duration_ms={duration_ms}")
                if duration_ms is None and get_audio_duration_fn:
                    for _ in range(15):  # bis zu 3s warten
                        await asyncio.sleep(0.2)
                        duration_ms = _get_duration_ms()
                        if duration_ms is not None:
                            break
                print(f"[AUDIO] _run_progress duration nach Warten: {duration_ms}")

                dur_str = _fmt(duration_ms) if duration_ms else "--:--"
                time_text.value = f"0:00 / {dur_str}"
                try:
                    time_text.update()
                except Exception:
                    pass

                play_start = time.monotonic()

                while is_playing[0]:
                    if _audio_known_broken():
                        print("[AUDIO] Loop: audio known broken, break")
                        break
                    pos_ms = None
                    if get_audio_position_fn and duration_ms:
                        pos_ms = get_audio_position_fn()  # interpoliert, int ms oder None

                    if pos_ms is not None and duration_ms:
                        fraction = min(1.0, pos_ms / duration_ms)
                        filled = int(fraction * len(bars))
                        for j, bar in enumerate(bars):
                            bar.bgcolor = "primary" if j < filled else "outline"
                        time_text.value = f"{_fmt(pos_ms)} / {dur_str}"
                        try:
                            waveform_row.update()
                            time_text.update()
                        except Exception:
                            break
                        if fraction >= 1.0:
                            break

                    # Sicherheits-Exit: länger als Duration + 3s aktiv → fertig
                    elapsed_s = time.monotonic() - play_start
                    if duration_ms and elapsed_s * 1000 > duration_ms + 3000:
                        break
                    if elapsed_s > 600:  # max. 10 Minuten
                        break

                    await asyncio.sleep(0.1)

                is_playing[0] = False
                await asyncio.sleep(1.0)
                _reset_bars()
                if _audio_known_broken():
                    try:
                        audio_status.value = "Audio nur im Static-Build verfügbar"
                        audio_status.visible = True
                        audio_status.update()
                    except Exception:
                        pass

            def _show_audio_unavailable():
                audio_status.value = "Audio nur im Static-Build verfügbar"
                audio_status.visible = True
                try:
                    audio_status.update()
                except Exception:
                    pass

            def trigger_play():
                if _audio_known_broken():
                    _show_audio_unavailable()
                    return
                _reset_bars()
                is_playing[0] = True
                page.run_task(_run_progress)
                if play_question_audio:
                    play_question_audio()

            # Für Spieler: Playback via PubSub auslösbar machen
            page.session.store.set("_trigger_question_audio", trigger_play)

            def on_play_click(_):
                if _audio_known_broken():
                    _show_audio_unavailable()
                    return
                _reset_bars()
                is_playing[0] = True
                page.run_task(_run_progress)
                if play_question_audio:
                    play_question_audio()
                if broadcast_question_audio:
                    broadcast_question_audio()

            # Lautstärkeregler — Wert wird in der Session gespeichert (fragenübergreifend)
            _saved_vol = page.session.store.get("_audio_volume")
            _current_vol = float(_saved_vol) if _saved_vol is not None else 1.0

            def on_volume_change(e):
                val = e.control.value
                print(f"[VOL] slider on_change_end: val={val!r} (type={type(val).__name__})")
                page.session.store.set("_audio_volume", val)
                if set_audio_volume_fn:
                    set_audio_volume_fn(val)

            volume_row = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.VOLUME_DOWN, size=18, opacity=0.6),
                    ft.Slider(
                        value=_current_vol, min=0.0, max=1.0,
                        expand=True,
                        on_change_end=on_volume_change,
                    ),
                    ft.Icon(ft.Icons.VOLUME_UP, size=18, opacity=0.6),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                visible=flet_audio_available,
            )

            audio_controls: list[ft.Control] = [
                prompt_text, waveform_box, time_text, audio_status, volume_row,
            ]

            if role == "host":
                play_btn = ft.IconButton(
                    icon=ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED,
                    icon_size=42,
                    on_click=on_play_click,
                )
                audio_controls.append(
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MUSIC_NOTE, size=16, opacity=0.5),
                            ft.Text(
                                Path(q.asset).name if q.asset else "—",
                                size=12,
                                italic=True,
                                opacity=0.5,
                                expand=True,
                            ),
                            play_btn,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    )
                )

            return ft.Column(controls=audio_controls, tight=True, spacing=8)

        if q_type == "estimate":
            controls_est: list[ft.Control] = [prompt_text]
            if role == "player":
                controls_est.append(ft.Container(height=8))
                controls_est.append(_build_estimate_input())
            return ft.Column(controls=controls_est, tight=True, spacing=8)

        return prompt_text  # fallback

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def reveal(_):
        state.question_answer_revealed = True
        refresh_answer()
        answer_container.update()
        broadcast_state()

    def back_without_use(_):
        page.on_keyboard_event = None
        state.selected = None
        state.end_question_round()
        state.screen = "board"
        rerender()
        broadcast_state()

    def finish_round_and_back():
        page.on_keyboard_event = None
        tile.used = True
        state.selected = None
        state.end_question_round()
        state.screen = "board"
        broadcast_state()

    def host_correct(_):
        if not caps.can_award_points:
            return
        correct_btn.disabled = True
        correct_btn.update()
        a = state.players[state.question_answerer_index]
        a.score += tile.value
        _play("correct_answer")
        state.advance_turn()
        finish_round_and_back()
        rerender()

    def host_wrong(_):
        if not caps.can_award_points:
            return
        wrong_btn.disabled = True
        wrong_btn.update()
        a = state.players[state.question_answerer_index]
        a.score -= tile.value
        _play("wrong_answer")
        state.open_buzzer()
        refresh_status()
        refresh_buzzer_controls()
        page.update()
        broadcast_state()

    correct_btn.on_click = host_correct
    wrong_btn.on_click = host_wrong

    # -------------------------------------------------------------------------
    # Host controls row
    # -------------------------------------------------------------------------
    if q_type == "estimate":
        # For estimate: no correct/wrong per-player; host reveals all, then picks winner
        def reveal_all(_):
            state.question_answer_revealed = True
            refresh_answer()
            answer_container.update()
            broadcast_state()

        host_action_row = ft.Row(
            controls=[
                ft.OutlinedButton("Antwort zeigen", on_click=reveal_all),
                ft.TextButton("Zurück (ohne verbrauchen)", on_click=back_without_use),
            ],
            wrap=True,
        )

        # Award-point buttons per player for estimate resolution
        def _make_award_btn(player_index: int) -> ft.Control:
            p = state.players[player_index]

            btn = ft.OutlinedButton(f"🏆 {p.name} gewinnt")

            def award(_b=btn, _pi=player_index):
                _b.disabled = True
                _b.update()
                state.players[_pi].score += tile.value
                state.question_answerer_index = _pi
                finish_round_and_back()
                rerender()

            btn.on_click = award
            return btn

        award_buttons = ft.Row(
            controls=[_make_award_btn(i) for i in range(len(state.players))],
            wrap=True,
        )

        host_controls = ft.Container(
            visible=caps.can_award_points,
            content=ft.Column(
                controls=[
                    ft.Text("Host-Steuerung", weight=ft.FontWeight.BOLD),
                    host_action_row,
                    ft.Container(height=4),
                    ft.Text("Schätzungen der Spieler:", size=13, weight=ft.FontWeight.BOLD),
                    estimates_column,
                    ft.Container(height=8),
                    ft.Text("Punkte vergeben:", size=13),
                    award_buttons,
                ],
                tight=True,
                spacing=6,
            ),
        )
    else:
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

    # -------------------------------------------------------------------------
    # Status strip (hidden for estimate)
    # -------------------------------------------------------------------------
    status_strip = ft.Container(
        visible=(q_type != "estimate"),
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

    topbar = topbar_view(title="Frage")

    card = ft.Container(
        padding=16,
        border=ft.Border.all(1, color="outline"),
        border_radius=12,
        bgcolor="surface_container",
        content=ft.Column(
            controls=[
                ft.Text(f"{cat.title} – {tile.value}", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                _build_prompt_area(),
                ft.Container(height=10),
                answer_container,
                ft.Container(height=10),
                host_controls,
            ],
            tight=True,
            spacing=8,
        ),
    )

    # Initial fill
    refresh_answer()
    if q_type != "estimate":
        refresh_status()
        refresh_buzzer_controls()
    else:
        refresh_estimates_display()

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
