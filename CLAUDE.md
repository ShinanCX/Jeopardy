# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python main.py
```

Opens at `http://localhost:8550`. Default role is Host.

**Multiplayer testing:**
1. Start the app in one terminal
2. Open `http://localhost:8550` in Browser A (Host)
3. Open the same URL in an incognito window (Player) — manually navigate to `/player/lobby`
4. Host clicks "Neues Spiel starten" → both clients sync automatically

Dev lobby ID is hardcoded as `"dev"` so Host and Player always share the same lobby.

## Architecture Overview

This is a host-authoritative multiplayer Jeopardy game built with **Python 3.12 + Flet 0.80.x** (web browser mode). All game state flows from Host → Players via PubSub broadcasts.

### State Flow

```
Host action → AppState mutation → broadcast_state()
    → lobby_store.update_lobby() + page.pubsub.send_all(snapshot_json)
    → Player._on_pubsub() → state.apply_snapshot() → UI rebuild / route change
```

### Key Modules

- **`app_state.py`** — `AppState` (serializable game state) and `Capabilities` (role-based permissions). Players only read state; Hosts mutate it.
- **`views/router.py`** — Route handler (`/{role}/{screen}`), PubSub subscription, and `broadcast_state()`. All routing goes through `page.push_route()` (async), never `page.go()`.
- **`lobby_store.py`** — Server-side `LOBBIES` dict that persists the last broadcast snapshot, allowing late joiners to sync.
- **`models/models.py`** — Dataclass models: `Question`, `Tile`, `Category`, `Board`. `build_dummy_board()` generates test data.
- **`ui/layout.py`** — Centralized spacing/padding constants used across all views.

### Capabilities Pattern

Views never check `if role == "host"`. They call `compute_capabilities(state, role)` which returns a `Capabilities` object with boolean flags like `can_pick_tile`, `can_award_points`, `can_simulate_buzzer`. Add new permission checks here, not inline in views.

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
- `role`: `"host"` or `"player"`
- `player_id`: UUID
- `lobby_id`: `"dev"` (hardcoded in dev mode)

### Flet Version Notes

This uses Flet 0.80.x. The API differs from newer Flet versions — always check the installed version before referencing docs. `ft.AppView.WEB_BROWSER` is the target view mode.
