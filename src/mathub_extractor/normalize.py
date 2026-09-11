from __future__ import annotations

import unicodedata

# Old Romanian books were often produced with legacy 8-bit encodings where
# these visible characters represented Romanian letters.
_ROMANIAN_LEGACY_TRANSLATION = str.maketrans(
    {
        "ã": "ă",
        "Ã": "Ă",
        "þ": "ţ",
        "Þ": "Ţ",
        "º": "ş",
        "ª": "Ş",
    }
)


def _repair_cp1252_control(ch: str) -> str:
    code = ord(ch)
    if not 0x80 <= code <= 0x9F:
        return ch
    try:
        return bytes([code]).decode("cp1252")
    except UnicodeDecodeError:
        return ch


def normalize_poppler_text(text: str) -> str:
    """Repair deterministic legacy-encoding artefacts in Poppler output.

    This does not guess words or mathematics. It only converts known 8-bit
    encoding artefacts to their Unicode equivalents and normalizes to NFC.
    """
    repaired = "".join(_repair_cp1252_control(ch) for ch in text)
    repaired = repaired.translate(_ROMANIAN_LEGACY_TRANSLATION)
    return unicodedata.normalize("NFC", repaired)
