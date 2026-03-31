import json
import os
from pathlib import Path

from models.models import Board, Category, Tile, Question

BOARDS_DIR = Path(os.environ.get("JEOPARDY_BOARDS_DIR", Path(__file__).parent / "boards"))


def list_boards() -> list[tuple[str, str, bool]]:
    """Gibt eine sortierte Liste von (board_id, title, wip) aller gültigen Boards zurück."""
    result = []
    if not BOARDS_DIR.exists():
        return result
    for entry in sorted(BOARDS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        json_path = entry / "board.json"
        if not json_path.exists():
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            title = data.get("title", entry.name)
            wip = bool(data.get("wip", False))
            result.append((entry.name, title, wip))
        except Exception:
            pass
    return result


def load_board(board_id: str) -> Board:
    """Lädt ein Board anhand seiner ID aus dem boards-Verzeichnis.
    Wirft ValueError wenn das Board nicht gefunden oder ungültig ist."""
    board_dir = BOARDS_DIR / board_id
    if not board_dir.is_dir():
        raise ValueError(f"Board-Verzeichnis nicht gefunden: {board_id!r}")
    json_path = board_dir / "board.json"
    if not json_path.exists():
        raise ValueError(f"board.json fehlt für Board: {board_id!r}")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Ungültiges JSON in board.json ({board_id!r}): {e}") from e

    categories = []
    for cat_data in data.get("categories", []):
        tiles = []
        for tile_data in cat_data.get("tiles", []):
            q = tile_data.get("question", {})
            # Backward compat: support both "assets" (list) and legacy "asset" (single)
            raw_assets = q.get("assets")
            if raw_assets is None:
                old = q.get("asset")
                raw_assets = [old] if old else []
            resolved_assets = []
            for asset in raw_assets:
                if asset:
                    resolved = (board_dir / asset).resolve()
                    if resolved.is_relative_to(BOARDS_DIR.resolve()):
                        resolved_assets.append(str(resolved))
            tiles.append(Tile(
                value=int(tile_data.get("value", 0)),
                question=Question(
                    type=str(q.get("type", "text")),
                    prompt=str(q.get("prompt", "")),
                    answer=str(q.get("answer", "")),
                    assets=resolved_assets,
                ),
            ))
        categories.append(Category(
            title=str(cat_data.get("title", "")),
            tiles=tiles,
        ))
    return Board(categories=categories, title=data.get("title", ""))
