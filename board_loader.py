import json
import os
from pathlib import Path

from models.models import Board, Category, Tile, Question

BOARDS_DIR = Path(os.environ.get("JEOPARDY_BOARDS_DIR", Path(__file__).parent / "boards"))


def list_boards() -> list[tuple[str, str]]:
    """Gibt eine sortierte Liste von (board_id, title) aller gültigen Boards zurück."""
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
            result.append((entry.name, title))
        except Exception:
            pass
    return result


def load_board(board_id: str) -> Board:
    """Lädt ein Board anhand seiner ID aus dem boards-Verzeichnis."""
    board_dir = BOARDS_DIR / board_id
    json_path = board_dir / "board.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))

    categories = []
    for cat_data in data.get("categories", []):
        tiles = []
        for tile_data in cat_data.get("tiles", []):
            q = tile_data.get("question", {})
            asset = q.get("asset")
            if asset:
                asset = str(board_dir / asset)
            tiles.append(Tile(
                value=int(tile_data.get("value", 0)),
                question=Question(
                    type=str(q.get("type", "text")),
                    prompt=str(q.get("prompt", "")),
                    answer=str(q.get("answer", "")),
                    asset=asset,
                ),
            ))
        categories.append(Category(
            title=str(cat_data.get("title", "")),
            tiles=tiles,
        ))
    return Board(categories=categories)