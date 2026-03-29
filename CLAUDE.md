# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python main.py
```

Opens at `http://localhost:8550` and lands on the main menu.

**Multiplayer testing:**
1. Start the app in one terminal
2. Open `http://localhost:8550` in Browser A → "Host" → configure settings → "Lobby erstellen" → copy lobby code
3. Open the same URL in an incognito window → "Lobby beitreten" → enter name + lobby code → join
4. Host clicks "Spiel starten" → both clients sync automatically

## Architecture Overview

This is a host-authoritative multiplayer Jeopardy game built with **Python 3.12 + Flet 0.83.0** (web browser mode). All game state flows from Host → Players via PubSub broadcasts.

### State Flow

```
Host action → AppState mutation → broadcast_state()
    → lobby_store.update_lobby() + page.pubsub.send_all(snapshot_json)
    → Player._on_pubsub() → state.apply_snapshot() → UI rebuild / route change
```

### Key Modules

- **`app_state.py`** — `AppState` (serializable game state) and `Capabilities` (role-based permissions). Players only read state; Hosts mutate it.
- **`views/router.py`** — Route handler, PubSub subscription, and `broadcast_state()`. All routing goes through `page.push_route()` (async), never `page.go()`.
- **`lobby_store.py`** — Server-side `LOBBIES` dict that persists the last broadcast snapshot, allowing late joiners to sync.
- **`board_loader.py`** — `load_board(board_id)` loads a board from `boards/<id>/board.json`. `list_boards()` returns `(id, title, wip)` tuples. Asset paths are resolved to absolute paths.
- **`views/board_editor.py`** — Two-step board creation: `board_setup_view` (Step 1: title + dimensions) and `board_editor_view` (Step 2: fill in content). Boards get a `wip` flag (True = incomplete).
- **`models/models.py`** — Dataclass models: `Question`, `Tile`, `Category`, `Board`.
- **`ui/layout.py`** — Centralized spacing/padding constants used across all views.

### Routing

Flat pre-session routes (no role prefix):
- `/menu` — main menu (Host / Join / Create)
- `/host-setup` — host configures lobby settings before creating
- `/join` — player enters name + lobby code
- `/create` — board overview; `?new=1` → Step 1 (new board); `?board=<id>` → Step 2 (edit board)

Role-prefixed in-session routes:
- `/{role}/lobby` — lobby waiting room
- `/{role}/game` — game board
- `/{role}/question` — active question screen

### PubSub Message Types

Beyond `lobby_state` (host → all players), the app uses:
- `player_join` — player → all; host picks it up, adds player to state, rebroadcasts
- `player_leave` — player → all; host picks it up, removes player from state, rebroadcasts
- `player_buzz` — player → all; host picks it up, sets answerer, closes buzzer, rebroadcasts
- `player_estimate` — player → all; host picks it up, stores answer in `state.estimates`, rebuilds locally (no broadcast)

Host ignores `lobby_state` messages. Players ignore `player_join`/`player_leave`/`player_buzz`/`player_estimate` messages.

### Capabilities Pattern

Views never check `if role == "host"`. They call `compute_capabilities(state, role)` which returns a `Capabilities` object with boolean flags like `can_pick_tile`, `can_award_points`, `can_go_to_lobby`. Add new permission checks here, not inline in views.

### Async Rules

- **Never use `asyncio.create_task()`** inside PubSub callbacks — always use `page.run_task()`.
- Route pushes inside callbacks must be wrapped:
  ```python
  async def _do():
      await page.push_route(route)
  page.run_task(_do)
  ```

### Session Identity

Per-client values stored in `page.session.store`:
- `role`: `"host"` or `"player"` — set when leaving the menu
- `player_id`: UUID — set on first load
- `lobby_id`: random 8-char uppercase string — set when host creates or player joins a lobby
- `player_name`: display name — set by player in join view

### Flet Version Notes

This uses **Flet 0.83.0**. Key API differences from older versions:

- `ft.Image(src=bytes_or_str)` — pass raw `bytes` directly, no `src_base64`. Use `ft.BoxFit` (not `ft.ImageFit`).
- `ft.Dropdown` uses `on_select` (not `on_change`) for selection events.
- `ft.FilePicker` is a **Service** — add via `page.services.append(picker)`, not `page.overlay`. `pick_files()` is async, returns `list[FilePickerFile]` directly. Use `with_data=True` in web mode for file bytes.
- `page.query.to_dict` (property) — safe dict for query params. Do NOT call `.get()` on the `QueryString` object directly (raises KeyError).
- `ft.AppView.WEB_BROWSER` is the target view mode.

Clipboard API: `await page.clipboard.set(value)` — async, use via `page.run_task(page.clipboard.set, value)`.

### Board Format

Boards live in `boards/<id>/board.json`. Required fields:
```json
{
  "title": "...",
  "wip": false,
  "num_categories": 6,
  "num_questions_per_cat": 5,
  "categories": [{ "title": "...", "tiles": [{ "value": 100, "question": { "type": "text", "prompt": "...", "answer": "...", "asset": null } }] }]
}
```
`wip: true` = incomplete (hidden from host-setup board picker). Question types: `text`, `image`, `audio`, `estimate`. Assets are relative paths from the board directory (e.g. `images/foo.jpg`).