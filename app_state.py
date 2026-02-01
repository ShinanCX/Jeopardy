from dataclasses import dataclass, field
from typing import Optional, Tuple, List

from models.models import Board  # bei dir: models/models.py


@dataclass
class Player:
    name: str
    score: int = 0
    is_turn: bool = False

class Capabilities:
    """UI/Action permissions derived from role + current game state."""
    can_pick_tile: bool = False  # Board tiles clickable (host only)
    can_select_turn: bool = False # aktiven Spieler wechseln
    can_award_points: bool = False # Richtig/Falsch, Punkte
    can_simulate_buzzer: bool = False # Buzzer-Sim Buttons / Answerer pick


def compute_capabilities(state: "AppState", role: str) -> Capabilities:
    role = (role or "host").lower()
    caps = Capabilities()

    # Host-only interactions for now
    if role == "host":
        caps.can_pick_tile = state.screen == "board"
        caps.can_select_turn = state.screen == "board"

        caps.can_award_points = state.screen == "question"
        caps.can_simulate_buzzer = state.screen == "question"
    return caps


@dataclass
class AppState:
    screen: str = "lobby"
    board: Optional[Board] = None
    selected: Optional[Tuple[int, int]] = None

    max_players: int = 4
    players: List[Player] = field(default_factory=list)
    active_player_index: int = 0  # <-- neu
    question_turn_owner_index: int = 0  # wer hat die Frage ausgewählt (Turn)
    question_answerer_index: int = 0  # wer darf gerade antworten (kann wechseln)
    buzzer_open: bool = False  # sind Buzzers offen?
    buzzed_queue: list[int] = field(default_factory=list)  # später live; jetzt vorbereitet

    def ensure_players(self):
        if not self.players:
            self.players = [Player(name=f"Spieler {i+1}") for i in range(self.max_players)]
            self.set_turn(0)
            return

        if len(self.players) < self.max_players:
            start = len(self.players)
            for i in range(start, self.max_players):
                self.players.append(Player(name=f"Spieler {i+1}"))
        elif len(self.players) > self.max_players:
            self.players = self.players[: self.max_players]

        # active index absichern
        if self.players:
            self.active_player_index = max(0, min(self.active_player_index, len(self.players) - 1))
            # sicherstellen, dass genau einer "dran" ist
            self.set_turn(self.active_player_index)

    def set_turn(self, index: int):
        """Setzt den aktiven Spieler."""
        if not self.players:
            return
        index = max(0, min(index, len(self.players) - 1))
        self.active_player_index = index
        for i, p in enumerate(self.players):
            p.is_turn = (i == index)

    def advance_turn(self, step: int = 1):
        """Wechselt zum nächsten Spieler (ringförmig)."""
        if not self.players:
            return
        nxt = (self.active_player_index + step) % len(self.players)
        self.set_turn(nxt)

    def active_player(self) -> Optional[Player]:
        if not self.players:
            return None
        return self.players[self.active_player_index]

    def start_question_round(self):
        """
        Wird aufgerufen, wenn ein Tile gewählt wird.
        Turn-Owner ist der aktuelle active_player_index.
        Dieser ist initial auch Answerer.
        """
        self.ensure_players()
        self.question_turn_owner_index = self.active_player_index
        self.question_answerer_index = self.active_player_index
        self.buzzer_open = False
        self.buzzed_queue = []

    def open_buzzer(self):
        """Host öffnet Buzzers für alle außer dem aktuellen Answerer."""
        self.buzzer_open = True
        self.buzzed_queue = []

    def set_answerer(self, index: int):
        """Setzt den aktuell antwortenden Spieler (temporär)."""
        if not self.players:
            return
        index = max(0, min(index, len(self.players) - 1))
        self.question_answerer_index = index

    def end_question_round(self):
        """Runde beenden und Substate zurücksetzen."""
        self.buzzer_open = False
        self.buzzed_queue = []

        # --- Shared-state sync helpers (server -> clients) ---

    @staticmethod
    def _board_to_dict(board: Optional[Board]) -> Optional[dict]:
        if board is None:
            return None
        return {
            "categories": [
                {
                    "title": c.title,
                    "tiles": [
                        {
                            "value": t.value,
                            "used": t.used,
                            "question": {
                                "prompt": t.question.prompt,
                                "answer": t.question.answer,
                            },
                        }
                        for t in c.tiles
                    ],
                }
                for c in board.categories
            ]
        }

    @staticmethod
    def _board_from_dict(data: Optional[dict]) -> Optional[Board]:
        if not data:
            return None
        from models.models import Board, Category, Tile, Question

        categories = []
        for c in data.get("categories", []):
            tiles = []
            for t in c.get("tiles", []):
                q = t.get("question") or {}
                tiles.append(
                    Tile(
                        value=int(t.get("value", 0)),
                        used=bool(t.get("used", False)),
                        question=Question(
                            prompt=str(q.get("prompt", "")),
                            answer=str(q.get("answer", "")),
                        ),
                    )
                )
            categories.append(Category(title=str(c.get("title", "")), tiles=tiles))
        return Board(categories=categories)

    @staticmethod
    def _players_to_list(players: List[Player]) -> list[dict]:
        return [{"name": p.name, "score": p.score, "is_turn": p.is_turn} for p in players]

    @staticmethod
    def _players_from_list(data: Optional[list]) -> List[Player]:
        if not data:
            return []
        out: List[Player] = []
        for p in data:
            out.append(
                Player(
                    name=str(p.get("name", "")),
                    score=int(p.get("score", 0)),
                    is_turn=bool(p.get("is_turn", False)),
                )
            )
        return out

    def snapshot(self) -> dict:
        """Minimaler, serialisierbarer Zustand für Multiplayer-Sync."""
        return {
            "screen": self.screen,
            "board": self._board_to_dict(self.board),
            "selected": self.selected,
            "max_players": self.max_players,
            "players": self._players_to_list(self.players),
            "active_player_index": self.active_player_index,
            "question_turn_owner_index": self.question_turn_owner_index,
            "question_answerer_index": self.question_answerer_index,
            "buzzer_open": self.buzzer_open,
            "buzzed_queue": list(self.buzzed_queue),
        }

    def apply_snapshot(self, snap: dict) -> None:
        """Übernimmt einen Snapshot (vom Host) in den lokalen State."""
        if "screen" in snap:
            self.screen = snap["screen"]

        if "board" in snap:
            self.board = self._board_from_dict(snap.get("board"))

        if "selected" in snap:
            self.selected = snap.get("selected")

        if "max_players" in snap and snap["max_players"] is not None:
            try:
                self.max_players = int(snap["max_players"])
            except Exception:
                pass

        if "players" in snap:
            self.players = self._players_from_list(snap.get("players"))

        if "active_player_index" in snap and snap["active_player_index"] is not None:
            try:
                self.active_player_index = int(snap["active_player_index"])
            except Exception:
                self.active_player_index = 0
            # is_turn flags konsistent setzen
            self.ensure_players()

        if "question_turn_owner_index" in snap and snap["question_turn_owner_index"] is not None:
            try:
                self.question_turn_owner_index = int(snap["question_turn_owner_index"])
            except Exception:
                pass

        if "question_answerer_index" in snap and snap["question_answerer_index"] is not None:
            try:
                self.question_answerer_index = int(snap["question_answerer_index"])
            except Exception:
                pass

        if "buzzer_open" in snap:
            self.buzzer_open = bool(snap["buzzer_open"])

        if "buzzed_queue" in snap and snap["buzzed_queue"] is not None:
            try:
                self.buzzed_queue = [int(x) for x in snap["buzzed_queue"]]
            except Exception:
                self.buzzed_queue = []