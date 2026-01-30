from dataclasses import dataclass
from typing import List


@dataclass
class Question:
    prompt: str
    answer: str


@dataclass
class Tile:
    value: int
    question: Question
    used: bool = False


@dataclass
class Category:
    title: str
    tiles: List[Tile]


@dataclass
class Board:
    categories: List[Category]


def build_dummy_board(cols: int = 6, rows: int = 5) -> Board:
    values = [100, 200, 300, 400, 500][:rows]
    categories: List[Category] = []

    for c in range(cols):
        tiles: List[Tile] = []
        for r in range(rows):
            v = values[r]
            tiles.append(
                Tile(
                    value=v,
                    question=Question(
                        prompt=f"Frage {v} in Kategorie {c+1}",
                        answer=f"Antwort zu {v} (Kategorie {c+1})",
                    ),
                )
            )
        categories.append(Category(title=f"Kategorie {c+1}", tiles=tiles))

    return Board(categories=categories)
