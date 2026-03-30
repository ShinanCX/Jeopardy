from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any
import time


@dataclass
class LobbyState:
    lobby_id: str
    version: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


LOBBIES: Dict[str, LobbyState] = {}

_LOBBY_MAX_AGE_S = 4 * 3600  # 4 Stunden


def get_lobby(lobby_id: str) -> LobbyState:
    _cleanup_old_lobbies()
    l = LOBBIES.get(lobby_id)
    if l is None:
        l = LobbyState(lobby_id=lobby_id)
        LOBBIES[lobby_id] = l
    return l


def update_lobby(lobby_id: str, patch: Dict[str, Any]) -> LobbyState:
    l = get_lobby(lobby_id)
    l.version += 1
    l.updated_at = time.time()
    l.data.update(patch)
    return l


def _cleanup_old_lobbies() -> None:
    """Entfernt Lobbies, die seit mehr als _LOBBY_MAX_AGE_S nicht aktualisiert wurden."""
    cutoff = time.time() - _LOBBY_MAX_AGE_S
    stale = [lid for lid, l in LOBBIES.items() if l.updated_at < cutoff]
    for lid in stale:
        del LOBBIES[lid]
