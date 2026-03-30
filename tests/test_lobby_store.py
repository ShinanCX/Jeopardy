"""Tests für lobby_store — Lobby-Verwaltung und Cleanup."""
import time
import pytest
from lobby_store import LOBBIES, get_lobby, update_lobby, _cleanup_old_lobbies


@pytest.fixture(autouse=True)
def clear_lobbies():
    """Leert den globalen LOBBIES-Dict vor jedem Test."""
    LOBBIES.clear()
    yield
    LOBBIES.clear()


class TestGetLobby:
    def test_creates_new_lobby_on_first_access(self):
        lobby = get_lobby("ABC123")
        assert lobby.lobby_id == "ABC123"
        assert lobby.version == 0
        assert lobby.data == {}

    def test_returns_existing_lobby(self):
        first = get_lobby("XYZ")
        second = get_lobby("XYZ")
        assert first is second

    def test_different_ids_are_independent(self):
        a = get_lobby("AAA")
        b = get_lobby("BBB")
        assert a is not b


class TestUpdateLobby:
    def test_increments_version(self):
        update_lobby("L1", {"screen": "lobby"})
        lobby = update_lobby("L1", {"screen": "board"})
        assert lobby.version == 2

    def test_merges_data(self):
        update_lobby("L1", {"screen": "lobby", "players": []})
        lobby = update_lobby("L1", {"screen": "board"})
        assert lobby.data["screen"] == "board"
        assert "players" in lobby.data

    def test_updates_updated_at(self):
        before = time.time()
        lobby = update_lobby("L1", {})
        assert lobby.updated_at >= before


class TestCleanup:
    def test_removes_old_lobbies(self):
        lobby = get_lobby("OLD")
        lobby.updated_at = time.time() - (5 * 3600)  # 5h > _LOBBY_MAX_AGE_S (4h)
        _cleanup_old_lobbies()
        assert "OLD" not in LOBBIES

    def test_keeps_recent_lobbies(self):
        get_lobby("NEW")
        _cleanup_old_lobbies()
        assert "NEW" in LOBBIES

    def test_only_removes_stale(self):
        get_lobby("FRESH")
        stale = get_lobby("STALE")
        stale.updated_at = time.time() - (5 * 3600)  # 5h > _LOBBY_MAX_AGE_S (4h)
        _cleanup_old_lobbies()
        assert "FRESH" in LOBBIES
        assert "STALE" not in LOBBIES
