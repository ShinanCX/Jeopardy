from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Callable

import flet as ft

from board_loader import BOARDS_DIR
from views.topbar import topbar_view

QUESTION_TYPES = ["text", "image", "audio", "estimate"]
QUESTION_TYPE_LABELS = {
    "text": "Text",
    "image": "Bild",
    "audio": "Audio",
    "estimate": "Schätzung",
}
DEFAULT_VALUES = [100, 200, 300, 400, 500]

MIN_CATS = 1
MAX_CATS = 10
MIN_Q = 1
MAX_Q = 10


# ---------------------------------------------------------------------------
# Interne Datenstrukturen
# ---------------------------------------------------------------------------

class _QData:
    def __init__(self, type_="text", value=100, prompt="", answer="", asset=""):
        self.type_ = type_
        self.value = value
        self.prompt = prompt
        self.answer = answer
        self.asset = asset


class _CatData:
    def __init__(self, title="", questions: list[_QData] | None = None):
        self.title = title
        self.questions: list[_QData] = questions or []


# ---------------------------------------------------------------------------
# Interne Helfer: Laden / Speichern / Skeleton
# ---------------------------------------------------------------------------

def _load_into_editor(board_id: str) -> tuple[str, list[_CatData], int, int]:
    """Lädt board.json in Editor-Strukturen. Gibt (title, cats, num_cats, num_q) zurück."""
    board_dir = BOARDS_DIR / board_id
    json_path = board_dir / "board.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    title = data.get("title", "")
    cats = []
    for c in data.get("categories", []):
        qs = []
        for t in c.get("tiles", []):
            q = t.get("question", {})
            qs.append(_QData(
                type_=q.get("type", "text"),
                value=int(t.get("value", 100)),
                prompt=q.get("prompt", ""),
                answer=q.get("answer", ""),
                asset=q.get("asset", "") or "",
            ))
        cats.append(_CatData(title=c.get("title", ""), questions=qs))

    # Ziel-Struktur aus Metadaten oder aus tatsächlichen Daten ableiten
    num_cats = int(data.get("num_categories", len(cats)))
    num_q = int(data.get("num_questions_per_cat",
                          max((len(c.questions) for c in cats), default=5)))
    return title, cats, num_cats, num_q


def _create_board_skeleton(board_id: str, title: str, num_cats: int, num_q: int) -> None:
    """Legt ein leeres Board-Gerüst auf dem Dateisystem an."""
    board_dir = BOARDS_DIR / board_id
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "images").mkdir(exist_ok=True)
    data = {
        "title": title,
        "wip": True,
        "num_categories": num_cats,
        "num_questions_per_cat": num_q,
        "categories": [
            {
                "title": "",
                "tiles": [
                    {
                        "value": DEFAULT_VALUES[q_i] if q_i < len(DEFAULT_VALUES) else (q_i + 1) * 100,
                        "question": {"type": "text", "prompt": "", "answer": "", "asset": None},
                    }
                    for q_i in range(num_q)
                ],
            }
            for _ in range(num_cats)
        ],
    }
    (board_dir / "board.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_board(board_id: str, title: str, cats: list[_CatData], num_cats_target: int, num_q_target: int) -> bool:
    """Speichert board.json mit wip-Flag. Gibt True zurück wenn vollständig (wip=False)."""
    complete = (
        len(cats) == num_cats_target
        and all(len(c.questions) == num_q_target for c in cats)
        and all(c.title.strip() for c in cats)
        and all(q.prompt.strip() and q.answer.strip() for c in cats for q in c.questions)
    )
    board_dir = BOARDS_DIR / board_id
    board_dir.mkdir(parents=True, exist_ok=True)
    (board_dir / "images").mkdir(exist_ok=True)
    data = {
        "title": title,
        "wip": not complete,
        "num_categories": num_cats_target,
        "num_questions_per_cat": num_q_target,
        "categories": [
            {
                "title": c.title,
                "tiles": [
                    {
                        "value": q.value,
                        "question": {
                            "type": q.type_,
                            "prompt": q.prompt,
                            "answer": q.answer,
                            "asset": q.asset or None,
                        },
                    }
                    for q in c.questions
                ],
            }
            for c in cats
        ],
    }
    (board_dir / "board.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return complete


# ---------------------------------------------------------------------------
# Schritt 1: Board-Basis festlegen
# ---------------------------------------------------------------------------

def board_setup_view(
    page: ft.Page,
    on_back: Callable,
    on_created: Callable[[str], None],
) -> ft.Control:
    """Schritt 1: Board-Titel, Anzahl Kategorien und Fragen festlegen."""
    num_cats_val = [6]
    num_q_val = [5]

    title_field = ft.TextField(label="Board-Titel", width=320, autofocus=True)
    cats_label = ft.Text(str(num_cats_val[0]), size=24, weight=ft.FontWeight.BOLD,
                         width=40, text_align=ft.TextAlign.CENTER)
    q_label = ft.Text(str(num_q_val[0]), size=24, weight=ft.FontWeight.BOLD,
                      width=40, text_align=ft.TextAlign.CENTER)
    error_text = ft.Text("", color="error", visible=False)

    def update_cats(delta: int):
        new = num_cats_val[0] + delta
        if MIN_CATS <= new <= MAX_CATS:
            num_cats_val[0] = new
            cats_label.value = str(new)
            cats_label.update()

    def update_q(delta: int):
        new = num_q_val[0] + delta
        if MIN_Q <= new <= MAX_Q:
            num_q_val[0] = new
            q_label.value = str(new)
            q_label.update()

    def on_submit(_):
        title = title_field.value.strip()
        if not title:
            error_text.value = "Bitte einen Board-Titel eingeben."
            error_text.visible = True
            error_text.update()
            return
        error_text.visible = False
        error_text.update()
        board_id = str(uuid.uuid4())
        _create_board_skeleton(board_id, title, num_cats_val[0], num_q_val[0])
        on_created(board_id)

    def _stepper(label: str, ctrl: ft.Control, on_dec, on_inc) -> ft.Control:
        return ft.Column(
            controls=[
                ft.Text(label, size=15),
                ft.Container(height=6),
                ft.Row(
                    controls=[
                        ft.IconButton(ft.Icons.REMOVE, on_click=lambda _: on_dec()),
                        ctrl,
                        ft.IconButton(ft.Icons.ADD, on_click=lambda _: on_inc()),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

    return ft.Column(
        controls=[
            topbar_view(title="Neues Board", on_back=on_back, back_label="Zur Übersicht"),
            ft.Container(height=32),
            ft.Column(
                controls=[
                    ft.Text("Board-Titel", size=15),
                    ft.Container(height=6),
                    title_field,
                    error_text,
                    ft.Container(height=24),
                    _stepper("Anzahl Kategorien", cats_label,
                              lambda: update_cats(-1), lambda: update_cats(1)),
                    ft.Container(height=16),
                    _stepper("Fragen pro Kategorie", q_label,
                              lambda: update_q(-1), lambda: update_q(1)),
                    ft.Container(height=32),
                    ft.FilledButton("Weiter →", on_click=on_submit, width=240),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
        ],
        tight=True,
    )


# ---------------------------------------------------------------------------
# Schritt 2: Kategorien und Fragen befüllen
# ---------------------------------------------------------------------------

def board_editor_view(
    page: ft.Page,
    board_id: str,
    on_back: Callable,
) -> ft.Control:
    """Schritt 2: Feste Struktur befüllen (kein Hinzufügen/Entfernen von Kategorien/Fragen)."""
    loaded_title, cats, num_cats_target, num_q_target = _load_into_editor(board_id)

    # Struktur auf Zielgröße bringen (Padding / Trimming)
    while len(cats) < num_cats_target:
        q_i_start = len(cats[0].questions) if cats else 0
        cats.append(_CatData(questions=[
            _QData(value=DEFAULT_VALUES[q_i] if q_i < len(DEFAULT_VALUES) else (q_i + 1) * 100)
            for q_i in range(num_q_target)
        ]))
    cats = cats[:num_cats_target]
    for c in cats:
        while len(c.questions) < num_q_target:
            q_i = len(c.questions)
            c.questions.append(_QData(
                value=DEFAULT_VALUES[q_i] if q_i < len(DEFAULT_VALUES) else (q_i + 1) * 100
            ))
        c.questions = c.questions[:num_q_target]

    title_field = ft.TextField(label="Board-Titel", value=loaded_title, width=400)
    status_text = ft.Text("", color="tertiary")
    cats_column = ft.Column(spacing=16, tight=True)
    _mounted = [False]
    # Dropdown-Referenzen für zuverlässiges Auslesen beim Speichern
    _type_dropdowns: dict[tuple[int, int], ft.Dropdown] = {}
    _asset_tfs: dict[tuple[int, int], ft.TextField] = {}

    board_dir = BOARDS_DIR / board_id
    _file_picker = ft.FilePicker()
    page.services.append(_file_picker)
    page.update()

    def rebuild():
        _type_dropdowns.clear()
        _asset_tfs.clear()
        cats_column.controls = [_cat_card(i) for i in range(len(cats))]
        if _mounted[0]:
            cats_column.update()

    def _question_card(cat_i: int, q_i: int) -> ft.Control:
        q = cats[cat_i].questions[q_i]

        type_dd = ft.Dropdown(
            label="Typ",
            value=q.type_,
            width=130,
            options=[ft.dropdown.Option(key=t, text=QUESTION_TYPE_LABELS[t]) for t in QUESTION_TYPES],
        )
        _type_dropdowns[(cat_i, q_i)] = type_dd

        def on_type_change(e):
            val = type_dd.value or "text"
            asset_row.visible = val in ("image", "audio")
            asset_row.update()

        type_dd.on_select = on_type_change

        value_tf = ft.TextField(
            label="Punkte",
            value=str(q.value),
            width=90,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda e: setattr(q, "value", int(e.data) if e.data.isdigit() else q.value),
        )
        prompt_tf = ft.TextField(
            label="Frage",
            value=q.prompt,
            expand=True,
            multiline=True,
            min_lines=2,
            on_change=lambda e: setattr(q, "prompt", e.data),
        )
        answer_tf = ft.TextField(
            label="Antwort",
            value=q.answer,
            expand=True,
            on_change=lambda e: setattr(q, "answer", e.data),
        )
        asset_tf = ft.TextField(
            label="Asset-Pfad (z. B. images/bild.png)",
            value=q.asset,
            expand=True,
            hint_text="Relativ zum Board-Verzeichnis",
        )
        _asset_tfs[(cat_i, q_i)] = asset_tf

        def pick_asset(_q=q, _tf=asset_tf):
            async def _do():
                try:
                    files = await _file_picker.pick_files(allow_multiple=False, with_data=True)
                    if not files:
                        return
                    picked = files[0]
                    dest_dir = board_dir / "images"
                    dest_dir.mkdir(exist_ok=True)
                    dest = dest_dir / picked.name
                    if picked.bytes:
                        dest.write_bytes(picked.bytes)
                    elif picked.path:
                        shutil.copy2(picked.path, dest)
                    else:
                        return
                    rel_path = f"images/{picked.name}"
                    _tf.value = rel_path
                    _tf.update()
                except Exception as ex:
                    print(f"[FilePicker] Fehler: {ex}")
            page.run_task(_do)

        asset_row = ft.Row(
            controls=[
                asset_tf,
                ft.IconButton(
                    ft.Icons.FOLDER_OPEN_OUTLINED,
                    tooltip="Datei auswählen & kopieren",
                    on_click=pick_asset,
                ),
            ],
            visible=q.type_ in ("image", "audio"),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            padding=10,
            border=ft.Border.all(1, color="outline_variant"),
            border_radius=10,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[type_dd, value_tf],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(controls=[prompt_tf]),
                    ft.Row(controls=[answer_tf]),
                    asset_row,
                ],
                tight=True,
                spacing=6,
            ),
        )

    def _cat_card(cat_i: int) -> ft.Control:
        cat = cats[cat_i]
        title_tf = ft.TextField(
            label=f"Kategorie {cat_i + 1}",
            value=cat.title,
            expand=True,
            on_change=lambda e, c=cat: setattr(c, "title", e.data),
        )
        return ft.Container(
            padding=12,
            border=ft.Border.all(1, color="outline"),
            border_radius=12,
            bgcolor="surface_container",
            content=ft.Column(
                controls=[
                    title_tf,
                    ft.Column(
                        controls=[_question_card(cat_i, q_i) for q_i in range(num_q_target)],
                        spacing=8,
                        tight=True,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        )

    def save(_):
        # Werte zuverlässig aus den Controls lesen (on_change/e.data in Flet 0.83 unzuverlässig)
        for (ci, qi), dd in _type_dropdowns.items():
            cats[ci].questions[qi].type_ = dd.value or "text"
        for (ci, qi), tf in _asset_tfs.items():
            cats[ci].questions[qi].asset = tf.value or ""

        title = title_field.value.strip()
        if not title:
            status_text.value = "Bitte einen Board-Titel eingeben."
            status_text.color = "error"
            status_text.update()
            return
        is_complete = _save_board(board_id, title, cats, num_cats_target, num_q_target)
        if is_complete:
            status_text.value = "✓ Gespeichert – Board ist vollständig und spielbereit."
            status_text.color = "tertiary"
        else:
            status_text.value = "⚠ Gespeichert – noch unvollständig (WIP). Alle Titel, Fragen und Antworten ausfüllen um freizugeben."
            status_text.color = "secondary"
        status_text.update()

    rebuild()
    _mounted[0] = True

    return ft.Column(
        controls=[
            topbar_view(
                title=f"Board bearbeiten ({num_cats_target}×{num_q_target})",
                on_back=on_back,
                back_label="Zur Übersicht",
            ),
            ft.Container(height=16),
            ft.Row(
                controls=[
                    title_field,
                    ft.FilledButton("Speichern", on_click=save),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            status_text,
            ft.Container(height=16),
            cats_column,
            ft.Container(height=32),
        ],
        tight=True,
    )
