from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from pathlib import Path

import flet as ft

from app_state import AppState, Capabilities, compute_capabilities
from ui.layout import LAYOUT
from views.components.player_card import PlayerCard
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
    rebuild_view=None,
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
    # Answer section
    # -------------------------------------------------------------------------
    answer_container = ft.Container()

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
    # Action handlers
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
        broadcast_state(include_board=True)

    correct_btn = ft.FilledButton("✅ Richtig", on_click=lambda _: None)
    wrong_btn = ft.OutlinedButton("❌ Falsch", on_click=lambda _: None)

    def host_correct(_):
        if not caps.can_award_points:
            return
        a = state.players[state.question_answerer_index]
        a.score += tile.value
        _play("correct_answer")
        state.advance_turn()
        finish_round_and_back()
        rerender()

    def host_wrong(_):
        if not caps.can_award_points:
            return
        a = state.players[state.question_answerer_index]
        a.score -= tile.value
        _play("wrong_answer")
        state.open_buzzer()
        broadcast_state()
        if rebuild_view:
            rebuild_view()

    correct_btn.on_click = host_correct
    wrong_btn.on_click = host_wrong

    # -------------------------------------------------------------------------
    # Estimate actions
    # -------------------------------------------------------------------------
    def reveal_all_estimates(_):
        for p in state.players:
            if p.player_id in state.estimates_locked and p.player_id not in state.estimates_revealed:
                state.estimates_revealed.append(p.player_id)
        broadcast_state()
        if rebuild_view:
            rebuild_view()

    # -------------------------------------------------------------------------
    # Estimate: input with lock-in for player
    # -------------------------------------------------------------------------
    def _build_estimate_input() -> ft.Control:
        my_player_id = page.session.store.get("player_id") or ""
        lobby_id = page.session.store.get("lobby_id") or ""
        is_locked = my_player_id in state.estimates_locked
        existing = state.estimates.get(my_player_id, "")

        est_field = ft.TextField(
            label="Deine Schätzung",
            value=existing,
            expand=True,
            autofocus=not is_locked,
            read_only=is_locked,
        )

        def on_estimate_change(e):
            if is_locked:
                return
            page.pubsub.send_all(json.dumps({
                "type": "player_estimate",
                "lobby_id": lobby_id,
                "player_id": my_player_id,
                "answer": e.data,
            }))

        est_field.on_change = on_estimate_change

        def lock_in(_):
            answer = est_field.value.strip()
            if not answer:
                return
            page.pubsub.send_all(json.dumps({
                "type": "player_estimate_lock",
                "lobby_id": lobby_id,
                "player_id": my_player_id,
                "answer": answer,
            }))

        controls = [ft.Row(controls=[est_field])]
        if is_locked:
            controls.append(ft.Row(controls=[
                ft.Icon(ft.Icons.LOCK, size=14, color="tertiary"),
                ft.Text("Eingeloggt", size=12, color="tertiary"),
            ]))
        else:
            controls.append(ft.Row(controls=[
                ft.FilledButton("Einloggen", icon=ft.Icons.LOCK_OUTLINED, on_click=lock_in),
            ]))
        return ft.Column(controls=controls, tight=True, spacing=6)

    # -------------------------------------------------------------------------
    # Asset navigation (shared between topbar and prompt area)
    # -------------------------------------------------------------------------
    def _asset_nav_compact() -> ft.Control | None:
        if not q.assets or len(q.assets) <= 1:
            return None
        n_assets = len(q.assets)
        asset_idx = max(0, min(state.question_asset_index, n_assets - 1))

        def _nav_prev(_):
            if state.question_asset_index > 0:
                state.question_asset_index -= 1
                broadcast_state()
                if rebuild_view:
                    rebuild_view()

        def _nav_next(_):
            if state.question_asset_index < n_assets - 1:
                state.question_asset_index += 1
                broadcast_state()
                if rebuild_view:
                    rebuild_view()

        return ft.Row(
            controls=[
                ft.IconButton(ft.Icons.ARROW_BACK_IOS_ROUNDED, on_click=_nav_prev,
                              disabled=asset_idx == 0, icon_size=18),
                ft.Text(f"{asset_idx + 1}/{n_assets}", size=12, opacity=0.7),
                ft.IconButton(ft.Icons.ARROW_FORWARD_IOS_ROUNDED, on_click=_nav_next,
                              disabled=asset_idx == n_assets - 1, icon_size=18),
            ],
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

    # -------------------------------------------------------------------------
    # Media content (ohne Prompt-Text; der kommt als Card-Header)
    # -------------------------------------------------------------------------
    def _build_media_content() -> ft.Control | None:
        asset_idx = max(0, min(state.question_asset_index, len(q.assets) - 1)) if q.assets else 0
        current_asset = q.assets[asset_idx] if q.assets else None

        if q_type == "text":
            return None

        if q_type == "image":
            if not current_asset:
                return None
            try:
                from board_loader import BOARDS_DIR
                rel = Path(current_asset).relative_to(BOARDS_DIR)
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

                return ft.GestureDetector(
                    content=ft.Image(src=src, fit=ft.BoxFit.CONTAIN, height=300),
                    on_tap=_open_zoom,
                    mouse_cursor=ft.MouseCursor.ZOOM_IN,
                )
            except Exception as _img_err:
                print(f"[Image] Fehler beim Laden: {_img_err!r}  path={current_asset!r}")
                return ft.Text(f"Bild nicht gefunden: {current_asset}", color="error", italic=True)

        if q_type == "audio":
            audio_src = None
            if current_asset:
                try:
                    from board_loader import BOARDS_DIR
                    rel = Path(current_asset).relative_to(BOARDS_DIR)
                    audio_src = f"/boards/{rel.as_posix()}"
                except Exception:
                    pass

            if audio_src and set_question_audio_src:
                set_question_audio_src(audio_src)

            _seed = Path(current_asset).name if current_asset else "default"
            _h = hashlib.md5(_seed.encode()).digest()
            base_heights = [8 + (_h[i % len(_h)] % 44) for i in range(24)]
            is_playing = [False]

            bars: list[ft.Container] = [
                ft.Container(
                    width=5,
                    height=h,
                    bgcolor="outline",
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
                return get_audio_duration_fn() if get_audio_duration_fn else None

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
                duration_ms = _get_duration_ms()
                if duration_ms is None and get_audio_duration_fn:
                    for _ in range(15):
                        await asyncio.sleep(0.2)
                        duration_ms = _get_duration_ms()
                        if duration_ms is not None:
                            break

                dur_str = _fmt(duration_ms) if duration_ms else "--:--"
                time_text.value = f"0:00 / {dur_str}"
                try:
                    time_text.update()
                except Exception:
                    pass

                play_start = time.monotonic()

                while is_playing[0]:
                    if _audio_known_broken():
                        break
                    pos_ms = None
                    if get_audio_position_fn and duration_ms:
                        pos_ms = get_audio_position_fn()

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

                    elapsed_s = time.monotonic() - play_start
                    if duration_ms and elapsed_s * 1000 > duration_ms + 3000:
                        break
                    if elapsed_s > 600:
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

            _saved_vol = page.session.store.get("_audio_volume")
            try:
                _current_vol = max(0.0, min(1.0, float(_saved_vol))) if _saved_vol is not None else 1.0
            except (TypeError, ValueError):
                _current_vol = 1.0

            def on_volume_change(e):
                val = e.control.value
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
                waveform_box, time_text, audio_status, volume_row,
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
                                Path(current_asset).name if current_asset else "—",
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

            return ft.Column(controls=audio_controls, tight=True, spacing=8,
                             horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        if q_type == "estimate":
            return None

        return None

    # -------------------------------------------------------------------------
    # Topbar
    # -------------------------------------------------------------------------
    def _build_topbar() -> ft.Control:
        title_str = f"{cat.title} – {tile.value}"

        if role == "player":
            return topbar_view(title=title_str)

        reveal_btn = ft.OutlinedButton("Antwort zeigen", on_click=reveal)

        if q_type == "estimate":
            reveal_all_btn = ft.FilledTonalButton(
                "Alle aufdecken",
                icon=ft.Icons.VISIBILITY,
                on_click=reveal_all_estimates,
                visible=caps.can_award_points,
            )
            return topbar_view(
                title=title_str,
                on_back=back_without_use,
                back_label="← Zurück",
                left_extra=reveal_btn,
                right_control=reveal_all_btn,
            )

        # Non-estimate host
        answerer_idx = max(0, min(state.question_answerer_index, len(state.players) - 1))
        a = state.players[answerer_idx]
        correct_btn.text = f"✅ Richtig ({a.name})"
        wrong_btn.text = f"❌ Falsch ({a.name})"

        right_controls: list[ft.Control] = []
        if caps.can_award_points:
            right_controls.extend([correct_btn, wrong_btn])
        nav = _asset_nav_compact()
        if nav:
            right_controls.append(nav)

        right = ft.Row(
            controls=right_controls,
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ) if right_controls else None

        return topbar_view(
            title=title_str,
            on_back=back_without_use,
            back_label="← Zurück",
            left_extra=reveal_btn,
            right_control=right,
        )

    # -------------------------------------------------------------------------
    # Player cards row (replaces status strip + buzzer holder)
    # -------------------------------------------------------------------------
    def _build_player_cards_row() -> ft.Container:
        MIN_PLAYER_W = 180
        PLAYER_GAP = 8
        my_player_id = page.session.store.get("player_id") or ""
        answerer_idx = max(0, min(state.question_answerer_index, len(state.players) - 1))

        players_content = ft.Column()

        outer = ft.Container(
            padding=8,
            border=ft.Border.all(1, color="outline"),
            border_radius=12,
            bgcolor="surface_container",
            content=ft.Row(
                controls=[players_content],
                scroll=ft.ScrollMode.AUTO,
            ),
        )

        def build_cards_row(card_width: int) -> ft.Row:
            cards = []
            for i, p in enumerate(state.players):
                body = None
                footer = None
                highlight = None

                if q_type == "estimate":
                    if role == "player":
                        if p.player_id == my_player_id:
                            body = _build_estimate_input()
                        else:
                            # Andere Karten: aufgedeckte Antwort zeigen falls vorhanden
                            if p.player_id in state.estimates_revealed:
                                answer = state.estimates.get(p.player_id, "—")
                                body = ft.Container(
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Text(answer, size=13, text_align=ft.TextAlign.CENTER),
                                    padding=ft.padding.symmetric(horizontal=4),
                                )
                    elif role == "host":
                        answer = state.estimates.get(p.player_id, "")
                        is_locked = p.player_id in state.estimates_locked
                        is_revealed = p.player_id in state.estimates_revealed

                        lock_icon = ft.Icon(
                            ft.Icons.LOCK if is_locked else ft.Icons.LOCK_OPEN,
                            size=14,
                            color="tertiary" if is_locked else "outline",
                        )
                        display = answer if answer else "—"
                        body = ft.Row(
                            controls=[
                                lock_icon,
                                ft.Text(display, size=12, expand=True,
                                        italic=not is_locked, text_align=ft.TextAlign.CENTER),
                            ],
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        )

                        def make_reveal_btn(pid, locked, revealed):
                            def reveal_one(_):
                                if pid not in state.estimates_revealed:
                                    state.estimates_revealed.append(pid)
                                broadcast_state()
                                if rebuild_view:
                                    rebuild_view()
                            return ft.TextButton(
                                "Aufdecken",
                                on_click=reveal_one,
                                disabled=not locked or revealed,
                                style=ft.ButtonStyle(padding=ft.padding.all(2)),
                            )

                        def make_unlock_btn(pid, locked):
                            def unlock(_):
                                if pid in state.estimates_locked:
                                    state.estimates_locked.remove(pid)
                                if pid in state.estimates_revealed:
                                    state.estimates_revealed.remove(pid)
                                if pid in state.estimates:
                                    del state.estimates[pid]
                                broadcast_state()
                                if rebuild_view:
                                    rebuild_view()
                            return ft.IconButton(
                                ft.Icons.LOCK_OPEN,
                                tooltip="Entsperren",
                                on_click=unlock,
                                icon_size=14,
                                visible=locked,
                            )

                        def make_award_btn(_pi=i):
                            def award(_):
                                state.players[_pi].score += tile.value
                                state.question_answerer_index = _pi
                                _play("correct_answer")
                                finish_round_and_back()
                                rerender()
                            return ft.TextButton(
                                "🏆 gewinnt",
                                on_click=award,
                                style=ft.ButtonStyle(padding=ft.padding.all(2)),
                            )

                        footer = [
                            make_reveal_btn(p.player_id, is_locked, is_revealed),
                            make_unlock_btn(p.player_id, is_locked),
                            make_award_btn(),
                        ]
                else:
                    # Non-estimate: Buzz-Button für eigene Karte des Spielers
                    if role == "player" and p.player_id == my_player_id:
                        my_idx = next(
                            (j for j, pl in enumerate(state.players) if pl.player_id == my_player_id), -1
                        )
                        if state.buzzer_open and my_idx != answerer_idx:
                            buzz_btn = ft.FilledButton("Buzz!  [Space]", width=160)

                            def send_buzz(_=None, _btn=buzz_btn):
                                _btn.disabled = True
                                try:
                                    _btn.update()
                                except Exception:
                                    pass
                                lobby_id = page.session.store.get("lobby_id") or ""
                                pid = page.session.store.get("player_id") or ""
                                msg = json.dumps({
                                    "type": "player_buzz",
                                    "lobby_id": lobby_id,
                                    "player_id": pid,
                                })
                                _play("buzz")
                                page.pubsub.send_all(msg)
                                page.on_keyboard_event = None

                            buzz_btn.on_click = send_buzz

                            def on_key(e: ft.KeyboardEvent):
                                if e.key == " ":
                                    send_buzz()

                            page.on_keyboard_event = on_key
                            body = ft.Container(
                                alignment=ft.Alignment.CENTER,
                                content=buzz_btn,
                                padding=ft.padding.symmetric(vertical=8),
                            )
                        else:
                            page.on_keyboard_event = None

                    # Aktiver Antworter: blauer Rahmen
                    if i == answerer_idx:
                        highlight = "primary"

                card = PlayerCard(
                    name=p.name,
                    score=p.score,
                    is_active=(i == answerer_idx) if q_type != "estimate" else p.is_turn,
                    body_content=body,
                    footer_controls=footer,
                    highlight_color=highlight,
                )
                card.width = card_width
                card.height = round(card_width * 9 / 16)
                cards.append(card)

            return ft.Row(controls=cards, spacing=PLAYER_GAP, expand=1)

        def recompute(viewport_w: int, pad: int):
            state.ensure_players()
            n = max(1, len(state.players))
            usable = viewport_w - 2 * pad - 2 * 8 - 2 - 2
            gaps = (n - 1) * PLAYER_GAP
            card_w = max(MIN_PLAYER_W, math.floor((usable - gaps) / n))
            players_content.controls = [build_cards_row(card_w)]

        recompute(page.width or 1200, LAYOUT.page_padding)
        outer.data = {"recompute": recompute}
        return outer

    # -------------------------------------------------------------------------
    # Assembly
    # -------------------------------------------------------------------------
    refresh_answer()

    _media = _build_media_content()
    _card_controls: list[ft.Control] = [
        ft.Container(
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(bottom=2),
            content=ft.Text(q.prompt, size=22, text_align=ft.TextAlign.CENTER),
        ),
        ft.Divider(height=1, color="outline", thickness=1),
    ]
    if _media is not None:
        _card_controls.append(
            ft.Container(alignment=ft.Alignment.CENTER, content=_media, expand=True)
        )
    _card_controls.append(ft.Container(height=6))
    _card_controls.append(answer_container)

    card = ft.Container(
        padding=16,
        border=ft.Border.all(1, color="outline"),
        border_radius=12,
        bgcolor="surface_container",
        content=ft.Column(
            controls=_card_controls,
            tight=True,
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        expand=True,
    )

    player_row = _build_player_cards_row()

    def on_resize(_):
        fn = (player_row.data or {}).get("recompute")
        if callable(fn):
            fn(page.width or 1200, LAYOUT.page_padding)
        page.update()

    page.on_resize = on_resize

    return ft.Column(
        controls=[
            _build_topbar(),
            ft.Container(height=8),
            card,
            ft.Container(height=8),
            player_row,
        ],
        expand=True,
        spacing=0,
    )
