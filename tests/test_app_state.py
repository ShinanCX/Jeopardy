"""Tests für AppState — Kernlogik Spieler, Turn, Snapshot, Capabilities."""
import pytest
from models.models import build_dummy_board
from app_state import AppState, compute_capabilities


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state():
    s = AppState()
    s.board = build_dummy_board()
    s.ensure_players()
    return s


# ---------------------------------------------------------------------------
# Spieler: Join / Reconnect / Leave
# ---------------------------------------------------------------------------

class TestPlayerManagement:
    def test_add_new_player(self):
        s = AppState()
        s.add_player("id-1", "Alice")
        assert len(s.players) == 1
        assert s.players[0].name == "Alice"
        assert s.players[0].player_id == "id-1"

    def test_add_duplicate_player_id_updates_name(self):
        s = AppState()
        s.add_player("id-1", "Alice")
        s.add_player("id-1", "Alice Neu")
        assert len(s.players) == 1
        assert s.players[0].name == "Alice Neu"

    def test_reconnect_by_name_updates_player_id(self):
        """Spieler schließt Tab und joinet mit gleichem Namen neu."""
        s = AppState()
        s.add_player("old-id", "Bob")
        reconnected = s.add_player("new-id", "Bob")
        assert reconnected is True
        assert len(s.players) == 1
        assert s.players[0].player_id == "new-id"

    def test_different_name_adds_new_player(self):
        s = AppState()
        s.add_player("id-1", "Alice")
        s.add_player("id-2", "Bob")
        assert len(s.players) == 2

    def test_remove_player(self):
        s = AppState()
        s.add_player("id-1", "Alice")
        s.add_player("id-2", "Bob")
        s.remove_player("id-1")
        assert len(s.players) == 1
        assert s.players[0].name == "Bob"

    def test_remove_nonexistent_player_is_safe(self):
        s = AppState()
        s.add_player("id-1", "Alice")
        s.remove_player("id-999")
        assert len(s.players) == 1


# ---------------------------------------------------------------------------
# Turn-Logik
# ---------------------------------------------------------------------------

class TestTurnLogic:
    def test_set_turn_marks_correct_player(self, state):
        state.set_turn(1)
        assert state.players[1].is_turn is True
        assert all(not p.is_turn for i, p in enumerate(state.players) if i != 1)

    def test_set_turn_clamps_to_valid_range(self, state):
        state.set_turn(999)
        assert state.active_player_index == len(state.players) - 1

    def test_advance_turn_wraps_around(self, state):
        last = len(state.players) - 1
        state.set_turn(last)
        state.advance_turn()
        assert state.active_player_index == 0

    def test_ensure_players_fills_to_max(self):
        s = AppState()
        s.max_players = 3
        s.ensure_players()
        assert len(s.players) == 3

    def test_ensure_players_trims_to_max(self):
        s = AppState()
        s.max_players = 2
        for i in range(5):
            s.add_player(f"id-{i}", f"Spieler {i}")
        s.ensure_players()
        assert len(s.players) == 2


# ---------------------------------------------------------------------------
# Punkte
# ---------------------------------------------------------------------------

class TestScoring:
    def test_correct_answer_increases_score(self, state):
        state.set_turn(0)
        state.players[0].score += 200
        assert state.players[0].score == 200

    def test_wrong_answer_decreases_score(self, state):
        state.players[0].score = 300
        state.players[0].score -= 100
        assert state.players[0].score == 200


# ---------------------------------------------------------------------------
# Snapshot / apply_snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_with_board(self, state):
        snap = state.snapshot(include_board=True)
        assert "board" in snap
        assert snap["board"] is not None

    def test_snapshot_without_board(self, state):
        snap = state.snapshot(include_board=False)
        assert "board" not in snap

    def test_apply_snapshot_restores_state(self, state):
        state.players[0].score = 500
        state.screen = "question"
        state.selected = (2, 3)
        snap = state.snapshot(include_board=True)

        fresh = AppState()
        fresh.apply_snapshot(snap)

        assert fresh.screen == "question"
        assert tuple(fresh.selected) == (2, 3)
        assert fresh.players[0].score == 500

    def test_apply_snapshot_without_board_keeps_existing_board(self, state):
        """Delta-Snapshot ohne Board darf das vorhandene Board nicht löschen."""
        original_board = state.board
        snap = state.snapshot(include_board=False)

        state.apply_snapshot(snap)
        assert state.board is original_board

    def test_snapshot_roundtrip_players(self, state):
        state.players[1].score = 300
        state.players[1].name = "Geändert"
        snap = state.snapshot()
        fresh = AppState()
        fresh.apply_snapshot(snap)
        assert fresh.players[1].score == 300
        assert fresh.players[1].name == "Geändert"

    def test_snapshot_buzzer_state(self, state):
        state.start_question_round()
        state.open_buzzer()
        state.buzzed_queue = [1, 2]
        snap = state.snapshot()
        fresh = AppState()
        fresh.apply_snapshot(snap)
        assert fresh.buzzer_open is True
        assert fresh.buzzed_queue == [1, 2]


# ---------------------------------------------------------------------------
# Fragen-Runde
# ---------------------------------------------------------------------------

class TestQuestionRound:
    def test_start_question_round_resets_buzzer(self, state):
        state.buzzer_open = True
        state.buzzed_queue = [0, 1]
        state.start_question_round()
        assert state.buzzer_open is False
        assert state.buzzed_queue == []

    def test_end_question_round_resets_state(self, state):
        state.start_question_round()
        state.open_buzzer()
        state.question_answer_revealed = True
        state.end_question_round()
        assert state.buzzer_open is False
        assert state.question_answer_revealed is False


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class TestCapabilities:
    def test_host_on_board_can_pick_tile(self, state):
        state.screen = "board"
        caps = compute_capabilities(state, "host")
        assert caps.can_pick_tile is True

    def test_player_cannot_pick_tile(self, state):
        state.screen = "board"
        caps = compute_capabilities(state, "player")
        assert caps.can_pick_tile is False

    def test_host_on_question_can_award_points(self, state):
        state.screen = "question"
        caps = compute_capabilities(state, "host")
        assert caps.can_award_points is True

    def test_player_cannot_award_points(self, state):
        state.screen = "question"
        caps = compute_capabilities(state, "player")
        assert caps.can_award_points is False

    def test_host_can_go_to_lobby(self, state):
        caps = compute_capabilities(state, "host")
        assert caps.can_go_to_lobby is True

    def test_player_cannot_go_to_lobby(self, state):
        caps = compute_capabilities(state, "player")
        assert caps.can_go_to_lobby is False
