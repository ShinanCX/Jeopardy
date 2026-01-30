# Jeopardy Quiz – PROJECT_CONTEXT

## Projektziel
Ein webbasiertes Jeopardy-Quiz, umgesetzt mit **Python + Flet**, erreichbar über den Browser.
Später sollen **Host- und Spieleransichten**, **Lobby**, **Buzzer-Logik** und **Multiplayer** möglich sein.
Aktuell Fokus auf **UI + Spiellogik-Grundlagen** (kein echtes Networking).

---

## Tech-Stack
- Python
- Flet (aktueller Stand, docs.flet.dev)
- Web-Target (`flet run --web`)
- Material 3 Theme
- Keine deprecated APIs (z. B. `ft.Border.all`, keine `ft.colors`, keine `ft.border.all`, etc.)

---

## Projektstruktur (relevant)

- Jeopardy\
  - models\
    - models.py → Board, Category, Tile, Question, build_dummy_board()
  - views\
    - components\
      - player_card.py
    - \_\_init__.py
    - board.py
    - board_grid.py
    - lobby.py
    - player_view.py
    - question.py
    - router.py
    - topbar.py
  - main.py
  - app_state.py
  

---

## Globaler State (`AppState`)
Wichtige Felder:
- `screen`: `"lobby" | "board" | "question"`
- `board`: Board-Objekt
- `selected`: `(cat_index, tile_index)` oder None

### Player & Turn
- `players`: List[Player(name, score, is_turn)]
- `active_player_index`: wer aktuell **Turn-Owner** ist (wählt Fragen)

### Question / Buzzer Vorbereitung
- `question_turn_owner_index`: Spieler, der die Frage gewählt hat
- `question_answerer_index`: Spieler, der gerade antwortet (kann wechseln)
- `buzzer_open`: bool
- `buzzed_queue`: vorbereitet für spätere WebSocket-Buzzer

Wichtige Methoden:
- `ensure_players()`
- `set_turn(index)`
- `advance_turn()`
- `start_question_round()`
- `open_buzzer()`
- `set_answerer(index)`
- `end_question_round()`

---

## UI / Layout
- **Theme** wird zentral in `main.py` gesetzt (Material 3)
- Wichtige Theme-Rollen:
  - `"surface"` → App-Hintergrund
  - `"surface_container"` → Cards / Panels
  - `"outline"` → Rahmen
  - `"primary"` → Highlights (aktiver Spieler)
- Halbtransparente Badges via Hex (`#26ffffff`)

### Topbar
- Eigene Datei `views/topbar.py`
- Zentrierter Titel (Stack-basiert)
- Zurück-Button links

### Board
- `board.py` setzt Layout zusammen
- `board_grid.py` rendert Kategorien + Tiles
- Board hat fixe Höhe, horizontal scrollfähig
- Spaltenbreiten werden bei Resize neu berechnet (`recompute()`)

### PlayerView
- Eigene Datei `player_view.py`
- Enthält PlayerCards
- Horizontal gleichmäßig verteilt, scrollt bei zu wenig Platz
- Vertikal expandierend
- Klick auf PlayerCard setzt Turn (Host-Workflow)

### PlayerCard
- Eigene Klasse `PlayerCard`
- Aufbau:
  - Name oben (Badge)
  - Score groß zentriert
  - Punkte unten (Badge)
- Aktiver Spieler: dicker Border in `"primary"`
- Klickbar (Host kann Turn setzen)

---

## QuestionView (aktueller Stand)
- Eigene Datei `question.py`
- Zeigt:
  - Kategorie + Wert
  - Frage
  - Antwort (Reveal)
  - Status: wer antwortet + Buzzer-Status
  - Host-Steuerung

### Host-Buttons
- ✅ Richtig (für aktuellen Answerer)
- ❌ Falsch (öffnet Buzzer)

### Verhalten
- Tile-Auswahl:
  - `start_question_round()`
  - initialer Answerer = Turn-Owner
- Richtig:
  - Punkte +value
  - Tile.used = True
  - `advance_turn()`
  - zurück zum Board
- Falsch:
  - Punkte -value
  - `open_buzzer()`
  - bleibt in QuestionView

### Buzzer (Simulation)
- Nur sichtbar, wenn `buzzer_open == True`
- Buttons „Spieler X buzzert“
- Klick setzt `question_answerer_index`
- Später durch echte Buzzer-Events ersetzbar

### Wichtiges UI-Pattern
- Platzhalter-Container (`buzzer_holder`)
- `refresh_status()` / `refresh_buzzer_controls()`
- Kein vollständiges Rerendern nötig, gezielte Updates

---

## Resize / Rendering
- Jede größere View stellt `recompute()` in `control.data`
- `board.py` ruft bei `page.on_resize` alle `recompute()` auf
- Scrollbars werden durch konservative Breitenrechnung vermieden (1–2px Safety)

---

## Bekannte Designentscheidungen
- Funktionen statt Klassen für Views (außer wiederverwendbare Komponenten)
- UI zuerst fertigstellen, dann Logik verfeinern
- Buzzer-Logik **vorbereitet**, aber noch kein Networking
- Kein Hot-Reload → Prozess-Neustart bei Codeänderungen (optional mit Watcher)

---

## Nächste sinnvolle Schritte
- Buzzer-Logik weiter verfeinern (Eligibility, Queue)
- Turn-Regeln variabel machen (bleibt Spieler bei richtiger Antwort?)
- Lobby-Optionen (Spieleranzahl, Host)
- Board aus JSON laden
- Host vs. Player View trennen
- Später: echtes Multiplayer (WebSockets)