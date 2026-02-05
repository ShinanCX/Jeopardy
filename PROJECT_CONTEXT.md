# Jeopardy Quiz – PROJECT_CONTEXT

## Projektziel
Ein webbasiertes **Jeopardy-Quiz** mit **Python + Flet (>=0.80.x)**, das im Browser läuft.

Das Projekt unterstützt:
- **Host- und Player-Rollen**
- **gemeinsame Spiel-Lobby**
- **echtes Multiplayer-Verhalten** (Host steuert, Player folgen)
- saubere **Trennung von UI, Logik und Berechtigungen**
- spätere Erweiterungen wie **Ready-Status, Buzzer, Punktevergabe**

Der aktuelle Fokus liegt auf:
- stabiler Architektur
- synchronisiertem Game-State
- Host-autoritativer Steuerung


---

## Tech-Stack
- **Python 3.12**
- **Flet 0.80.x**
- Web-Target (`ft.run(..., view=WEB_BROWSER)`)
- Routing über `page.push_route()` (async, 0.80-konform)
- PubSub für Multiplayer-Sync
- Material-3-Theme


---

## Architektur – Überblick

### 1. AppState (lokaler View-State)
`AppState` hält den aktuellen Spielzustand **pro Client**, u. a.:

- `screen` (`lobby | board | question`)
- `board`
- `players`
- `selected` (aktuelles Tile `(cat_i, tile_i)`)
- Question-Round-Status (Answerer, Buzzer etc.)

Zusätzlich:
- `snapshot()` → minimal serialisierbarer Shared-State
- `apply_snapshot()` → wendet Shared-State an (Player-Clients)


---

### 2. Shared State / Multiplayer
Multiplayer wird über **serverseitigen Shared-State + PubSub** umgesetzt.

#### `lobby_store.py`
- globale Registry: `LOBBIES[lobby_id]`
- jeder Lobby-State enthält:
  - `data` (letzter Snapshot)
  - `version`
- **Host ist authoritative source of truth**

#### Ablauf
1. Host ändert State (z. B. Spiel starten, Tile wählen)
2. Host ruft `broadcast_state()`
3. Snapshot wird gespeichert + via `page.pubsub.send_all()` gesendet
4. Player empfangen Snapshot → `apply_snapshot()` → Route-Sync


---

### 3. Routing (Flet 0.80.x-konform)

- Routing erfolgt **ausschließlich** über:
  - `page.push_route()` (async)
  - `page.on_route_change`
  - `page.views` (View-Stack)

⚠️ Wichtig:
- `push_route()` **immer async**
- In PubSub-Callbacks **niemals `asyncio.create_task`**
- Stattdessen: `page.run_task(async_fn)`

Beispiel:
```python
async def _sync():
    await page.push_route("/player/game")

page.run_task(_sync)
```


---

### 4. Capabilities-Pattern (Berechtigungen)

Views fragen **nicht**:
> „Bin ich Host?“

Sondern:
> „Darf ich das?“

#### `Capabilities`
Beispiele:
- `can_pick_tile`
- `can_select_turn`
- `can_award_points`
- `can_simulate_buzzer`

#### `compute_capabilities(state, role)`
- zentrale Logik
- abhängig von `role` + `state.screen`
- Views bleiben komplett rollen-agnostisch


---

### 5. Views

#### Lobby (`views/lobby.py`)
- **nur Host** sieht „Spiel starten“
- Host:
  - baut Board
  - setzt `state.screen="board"`
  - `broadcast_state()`
- Player:
  - sehen „Warte auf Host…“
  - folgen automatisch nach Broadcast

#### Board (`views/board.py`)
- Host:
  - Tiles klickbar
  - Spielerwechsel erlaubt
- Player:
  - Board read-only
- Tile-Pick:
```python
state.selected = (cat_i, tile_i)
state.start_question_round()
state.screen = "question"
rerender()
broadcast_state()
```

#### Question (`views/question.py`)
- Host:
  - Richtig/Falsch
  - Buzzer-Simulation
- Player:
  - reine Anzeige
- Aktionen des Hosts werden gebroadcastet


---

## Session & Identität

- Nutzung von `page.session.store`
- Wichtige Keys:
  - `role` → `"host" | "player"`
  - `player_id` → UUID
  - `lobby_id`

⚠️ **Dev-Modus aktuell:**
```python
lobby_id = "dev"
```
→ Host & Player landen garantiert in derselben Lobby

Später: echter Lobby-Join per Code


---

## Bekannte Stolpersteine (bereits gelöst)

- ❌ `page.go()` → deprecated  
  ✅ `page.push_route()`

- ❌ `asyncio.create_task()` in PubSub  
  ✅ `page.run_task()`

- ❌ `page.padding` während `route_change()`  
  ✅ try/except-Guard

- ❌ getrennte Lobbies durch zufällige `lobby_id`  
  ✅ fixierte Dev-Lobby


---

## Test-Setup (empfohlen)

1. Server starten
2. Browser A:
   ```
   /host/lobby
   ```
3. Inkognito / anderer Browser:
   ```
   /player/lobby
   ```
4. Host startet Spiel
5. Player folgt automatisch
6. Host pickt Tile → Player springt mit


---

## Aktueller Stand (Kurzfassung)

✅ Host/Player-Routing  
✅ Capabilities-Pattern  
✅ Shared-State + PubSub  
✅ Host-autoritative Steuerung  
✅ Player folgen automatisch  
🚧 Lobby-Ready / Buzzer / Punkte-Sync folgen als nächste Schritte


---

## Wichtige Arbeitsprinzipien & Leitlinien für dieses Projekt

Dieses Kapitel beschreibt grundlegende Annahmen, Arbeitsweisen und Vorgaben,
die im bisherigen Projektverlauf mehrfach explizit festgelegt wurden
und bei zukünftigen Entscheidungen **immer als gegeben gelten sollen**.

### 1. Flet-Version & Dokumentation
- Zielplattform ist **Flet 0.80.x**
- Entscheidungen müssen **immer** mit der offiziellen Dokumentation abgeglichen werden:
  - https://docs.flet.dev
- Veraltete APIs (z.B. `page.go()`) dürfen **nicht** weiterverwendet werden
- Asynchrone APIs (`push_route`, PubSub, etc.) müssen versionskonform eingesetzt werden

### 2. Routing & Navigation (verbindlich)
- Routing erfolgt ausschließlich über:
  - `page.push_route()`
  - `page.on_route_change`
  - `page.views` (View-Stack)
- `page.go()` ist deprecated und darf nicht mehr verwendet werden
- `push_route()` ist **immer async**
- In Thread-/PubSub-Kontexten:
  - **niemals** `asyncio.create_task(...)`
  - **immer** `page.run_task(async_fn)`

### 3. State-Architektur
- **Host ist authoritative source of truth**
- Player ändern niemals direkt den Game-State
- Synchronisation erfolgt über:
  - `snapshot()` (serialisierbarer Minimal-State)
  - `apply_snapshot()` (Client-Seite)
  - PubSub (`page.pubsub.send_all / subscribe`)
- Shared-State liegt serverseitig (z.B. `lobby_store.py`)
- `AppState` ist pro Client lokal, wird aber über Snapshots synchronisiert

### 4. Capabilities-Pattern (zentrale Designentscheidung)
- Views fragen **nicht** nach Rollen (`host` / `player`)
- Views fragen ausschließlich nach **Capabilities** (z.B. `can_pick_tile`, `can_award_points`, `can_select_turn`)
- Capabilities werden zentral berechnet:
  ```python
  compute_capabilities(state, role)
  ```
- Keine UI-Logik mit `if role == "host"` in Views

### 5. Multiplayer-Testmodus (Dev-Modus)
- Für Entwicklung & Debugging:
  ```python
  lobby_id = "dev"
  ```
- Host und Player müssen **immer** dieselbe Lobby teilen
- Mehrere Browser / Inkognito-Fenster sind das empfohlene Testsetup
- Später wird dies durch echten Lobby-Code / Join-Flow ersetzt

### 6. Defensive UI-Logik
- UI darf **niemals** implizit annehmen, dass State existiert
- Guards sind erlaubt und erwünscht:
  - gegen leere Views
  - gegen nicht initialisierte Boards
  - gegen fehlende Fragen
- Besonders kritisch:
  - `page.padding` während `route_change()` → immer absichern

### 7. Arbeitsweise & Erwartungshaltung
- Änderungen sollen **inkrementell**, **minimal-invasiv** und **architektonisch sauber** erfolgen
- Lieber ein sauberer Zwischenschritt als eine große, fragile Änderung
- Refactoring ist erlaubt, wenn es spätere Erweiterungen vereinfacht
- Ziel ist ein **langfristig wartbares Multiplayer-Projekt**, kein Quick Hack

### 8. Zielrichtung des Projekts
- Fokus auf:
  - saubere Trennung von UI / Logik / State
  - Erweiterbarkeit (Ready-System, Buzzer, Reconnect, Spectator)
- UX-Verbesserungen sind willkommen, aber **nicht vor Architektur**
- Stabilität & Nachvollziehbarkeit haben Vorrang vor Feature-Menge
