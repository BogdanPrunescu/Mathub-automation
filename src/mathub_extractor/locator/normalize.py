from __future__ import annotations

import re
import unicodedata

_SECTION_PREFIX_RE = re.compile(
    r"^\s*(?:(?:capitol(?:ul)?|chapter)\s+)?"
    r"(?P<number>\d+(?:\.\d+){0,4})[\.\)]?\s+",
    flags=re.IGNORECASE,
)
_TRAILING_PAGE_RE = re.compile(r"(?:\.{2,}\s*)?\b\d{1,4}\s*$")
_PUNCT_RE = re.compile(r"[^\w\s]+", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def fold_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", nfc(text))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_for_match(text: str) -> str:
    text = fold_diacritics(text).casefold()
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def strip_section_prefix(text: str) -> tuple[str | None, str]:
    match = _SECTION_PREFIX_RE.match(nfc(text))
    if not match:
        return None, nfc(text).strip()
    return match.group("number"), nfc(text)[match.end():].strip()


def strip_trailing_page_number(text: str) -> str:
    return _TRAILING_PAGE_RE.sub("", nfc(text)).strip()


def normalized_title_from_line(text: str) -> tuple[str | None, str]:
    number, body = strip_section_prefix(text)
    body = strip_trailing_page_number(body)
    return number, normalize_for_match(body)


def tokens(text: str) -> set[str]:
    return {t for t in normalize_for_match(text).split() if t}


def parse_section_number(text: str) -> tuple[int, ...] | None:
    number, _ = strip_section_prefix(text)
    if not number:
        return None
    try:
        return tuple(int(part) for part in number.split("."))
    except ValueError:
        return None


def same_level_next(candidate: tuple[int, ...], start: tuple[int, ...]) -> bool:
    if len(candidate) != len(start):
        return False
    if len(start) == 1:
        return candidate[0] > start[0]
    return candidate[:-1] == start[:-1] and candidate[-1] > start[-1]


def is_descendant(candidate: tuple[int, ...], start: tuple[int, ...]) -> bool:
    return len(candidate) > len(start) and candidate[: len(start)] == start
