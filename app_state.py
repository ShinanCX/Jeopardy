from dataclasses import dataclass, field
from typing import Optional, Tuple, List

from models.models import Board  # bei dir: models/models.py


@dataclass
class Player:
    name: str
    score: int = 0
    is_turn: bool = False


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