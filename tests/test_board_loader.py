"""Tests für board_loader — Laden, Fehlerbehandlung, Path-Traversal-Schutz."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def boards_dir(tmp_path):
    """Temporäres boards/-Verzeichnis mit einem gültigen Beispiel-Board."""
    board_dir = tmp_path / "testboard"
    board_dir.mkdir()
    images_dir = board_dir / "images"
    images_dir.mkdir()

    data = {
        "title": "Testboard",
        "wip": False,
        "categories": [
            {
                "title": "Geografie",
                "tiles": [
                    {
                        "value": 100,
                        "question": {
                            "type": "text",
                            "prompt": "Hauptstadt von Deutschland?",
                            "answer": "Berlin",
                            "asset": None,
                        },
                    },
                    {
                        "value": 200,
                        "question": {
                            "type": "image",
                            "prompt": "Was ist das?",
                            "answer": "Berlin",
                            "asset": "images/test.png",
                        },
                    },
                ],
            }
        ],
    }
    (board_dir / "board.json").write_text(json.dumps(data), encoding="utf-8")
    (images_dir / "test.png").write_bytes(b"fakepng")
    return tmp_path


@pytest.fixture
def loader(boards_dir):
    """board_loader mit gepatchtem BOARDS_DIR."""
    import board_loader
    with patch.object(board_loader, "BOARDS_DIR", boards_dir):
        yield board_loader


class TestLoadBoard:
    def test_loads_valid_board(self, loader):
        board = loader.load_board("testboard")
        assert board.title == "Testboard"
        assert len(board.categories) == 1
        assert board.categories[0].title == "Geografie"

    def test_loads_tiles_correctly(self, loader):
        board = loader.load_board("testboard")
        tiles = board.categories[0].tiles
        assert len(tiles) == 2
        assert tiles[0].value == 100
        assert tiles[0].question.prompt == "Hauptstadt von Deutschland?"
        assert tiles[0].question.answer == "Berlin"

    def test_resolves_asset_to_absolute_path(self, loader, boards_dir):
        board = loader.load_board("testboard")
        assets = board.categories[0].tiles[1].question.assets
        assert len(assets) == 1
        assert Path(assets[0]).is_absolute()
        assert Path(assets[0]).exists()

    def test_null_asset_stays_empty_list(self, loader):
        board = loader.load_board("testboard")
        assert board.categories[0].tiles[0].question.assets == []

    def test_raises_for_missing_directory(self, loader):
        with pytest.raises(ValueError, match="nicht gefunden"):
            loader.load_board("gibts-nicht")

    def test_raises_for_missing_board_json(self, loader, boards_dir):
        empty_dir = boards_dir / "leer"
        empty_dir.mkdir()
        with pytest.raises(ValueError, match="board.json fehlt"):
            loader.load_board("leer")

    def test_raises_for_invalid_json(self, loader, boards_dir):
        (boards_dir / "testboard" / "board.json").write_text("{ kaputt", encoding="utf-8")
        with pytest.raises(ValueError, match="Ungültiges JSON"):
            loader.load_board("testboard")

    def test_blocks_path_traversal_in_asset(self, loader, boards_dir):
        """Asset-Pfad mit ../ darf nicht außerhalb von BOARDS_DIR aufgelöst werden."""
        data = {
            "title": "Hack",
            "wip": False,
            "categories": [
                {
                    "title": "Evil",
                    "tiles": [
                        {
                            "value": 100,
                            "question": {
                                "type": "image",
                                "prompt": "?",
                                "answer": "!",
                                "asset": "../../secret.txt",
                            },
                        }
                    ],
                }
            ],
        }
        hack_dir = boards_dir / "hackboard"
        hack_dir.mkdir()
        (hack_dir / "board.json").write_text(json.dumps(data), encoding="utf-8")

        board = loader.load_board("hackboard")
        # Asset muss gefiltert werden, da es außerhalb von BOARDS_DIR liegt
        assert board.categories[0].tiles[0].question.assets == []


class TestListBoards:
    def test_lists_available_boards(self, loader):
        boards = loader.list_boards()
        ids = [b[0] for b in boards]
        assert "testboard" in ids

    def test_returns_title_and_wip(self, loader):
        boards = loader.list_boards()
        board = next(b for b in boards if b[0] == "testboard")
        assert board[1] == "Testboard"
        assert board[2] is False

    def test_ignores_directories_without_board_json(self, loader, boards_dir):
        (boards_dir / "kein-board").mkdir()
        boards = loader.list_boards()
        ids = [b[0] for b in boards]
        assert "kein-board" not in ids
