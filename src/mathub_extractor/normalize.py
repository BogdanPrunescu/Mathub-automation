from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def make_search_text(text: str) -> str:
    # Search-oriented representation only; canonical extracted text is never modified.
    normalized = unicodedata.normalize("NFC", text)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized.casefold()
