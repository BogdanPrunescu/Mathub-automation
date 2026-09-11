from __future__ import annotations

from dataclasses import asdict, dataclass
import unicodedata


@dataclass(frozen=True)
class TextQuality:
    status: str
    character_count: int
    non_whitespace_count: int
    control_count: int
    replacement_count: int
    alphabetic_count: int
    control_ratio: float
    replacement_ratio: float
    alphabetic_ratio: float

    def to_dict(self) -> dict:
        return asdict(self)


def _is_bad_control(ch: str) -> bool:
    return unicodedata.category(ch) == "Cc" and ch not in "\t\n\r"


def assess_text(text: str) -> TextQuality:
    character_count = len(text)
    non_whitespace_count = sum(not ch.isspace() for ch in text)
    denominator = max(non_whitespace_count, 1)

    control_count = sum(_is_bad_control(ch) for ch in text)
    replacement_count = text.count("\ufffd")
    alphabetic_count = sum(ch.isalpha() for ch in text)

    control_ratio = control_count / denominator
    replacement_ratio = replacement_count / denominator
    alphabetic_ratio = alphabetic_count / denominator

    if non_whitespace_count == 0:
        status = "EMPTY"
    elif control_ratio > 0.20 or replacement_ratio > 0.20:
        status = "UNUSABLE"
    elif control_ratio > 0.005 or replacement_ratio > 0.005:
        status = "SUSPECT"
    else:
        status = "GOOD"

    return TextQuality(
        status=status,
        character_count=character_count,
        non_whitespace_count=non_whitespace_count,
        control_count=control_count,
        replacement_count=replacement_count,
        alphabetic_count=alphabetic_count,
        control_ratio=round(control_ratio, 6),
        replacement_ratio=round(replacement_ratio, 6),
        alphabetic_ratio=round(alphabetic_ratio, 6),
    )


def status_rank(status: str) -> int:
    return {
        "GOOD": 4,
        "SUSPECT": 3,
        "EMPTY": 2,
        "UNUSABLE": 1,
    }.get(status, 0)
