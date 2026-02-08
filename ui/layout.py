from dataclasses import dataclass

@dataclass(frozen=True)
class Layout:
    page_padding: int = 16
    card_padding: int = 12
    grid_gap: int = 8
    section_gap: int = 24

LAYOUT = Layout()