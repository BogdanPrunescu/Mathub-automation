from __future__ import annotations

import re
from dataclasses import dataclass

from .model import LineRecord
from .normalize import normalize_for_match, parse_section_number


_DOTS_PAGE_RE = re.compile(r"\.{2,}\s*\d{1,4}\s*$")
_NUMBERED_ENTRY_RE = re.compile(r"^\s*\d+(?:\.\d+){0,4}\.?\s+\S+")
_TRAILING_PAGE_RE = re.compile(r"(?:\.{2,}\s*)?(\d{1,4})\s*$")


@dataclass(frozen=True)
class TocEntry:
    page_id: str
    pdf_page_number: int
    line_id: str
    raw_text: str
    section_number: tuple[int, ...] | None
    title: str
    normalized_title: str
    printed_page: int | None


def _parse_toc_line(line: LineRecord) -> TocEntry | None:
    text = line.text.strip()

    section_number = parse_section_number(text)
    if not section_number:
        return None

    page_match = _TRAILING_PAGE_RE.search(text)
    if not page_match:
        return None

    printed_page = int(page_match.group(1))

    # Remove final dotted leader + page number.
    body = text[: page_match.start()].rstrip(". ").strip()

    # Remove numbering prefix from title.
    number_match = re.match(
        r"^\s*\d+(?:\.\d+){0,4}\.?\s+",
        body,
    )

    if number_match:
        title = body[number_match.end():].strip()
    else:
        title = body

    if not title:
        return None

    return TocEntry(
        page_id=line.page_id,
        pdf_page_number=line.pdf_page_number,
        line_id=line.line_id,
        raw_text=text,
        section_number=section_number,
        title=title,
        normalized_title=normalize_for_match(title),
        printed_page=printed_page,
    )


def detect_toc_pages(
    by_page: dict[str, list[LineRecord]],
) -> tuple[set[str], dict[str, float]]:
    toc_pages: set[str] = set()
    scores: dict[str, float] = {}

    for page_id, lines in by_page.items():
        if not lines:
            scores[page_id] = 0.0
            continue

        normalized = [normalize_for_match(line.text) for line in lines]

        has_cuprins = any(
            text == "cuprins" or text.startswith("cuprins ")
            for text in normalized
        )

        dot_entries = sum(
            bool(_DOTS_PAGE_RE.search(line.text))
            for line in lines
        )

        numbered_entries = sum(
            bool(_NUMBERED_ENTRY_RE.match(line.text))
            for line in lines
        )

        short_lines = sum(
            1
            for line in lines
            if 3 <= len(line.text.strip()) <= 120
        )

        density = short_lines / max(1, len(lines))

        score = (
            (0.65 if has_cuprins else 0.0)
            + min(0.25, dot_entries * 0.04)
            + min(0.25, numbered_entries * 0.025)
            + (0.10 if density > 0.75 and len(lines) >= 8 else 0.0)
        )

        score = min(1.0, score)
        scores[page_id] = score

        if score >= 0.55:
            toc_pages.add(page_id)

    return toc_pages, scores


def extract_toc_entries(
    toc_pages: set[str],
    by_page: dict[str, list[LineRecord]],
) -> list[TocEntry]:
    """
    Extract TOC entries in actual document order.

    TOC section numbers may restart in later chapters, so preserving
    sequence is essential.
    """
    ordered_lines: list[LineRecord] = []

    for page_id in toc_pages:
        ordered_lines.extend(by_page.get(page_id, []))

    ordered_lines.sort(
        key=lambda line: (
            line.page_index,
            line.y0,
            line.block_index,
            line.line_index,
        )
    )

    entries: list[TocEntry] = []

    for line in ordered_lines:
        entry = _parse_toc_line(line)

        if entry is not None:
            entries.append(entry)

    return entries


def find_matching_toc_entry(
    anchor_section: tuple[int, ...] | None,
    lesson_title: str,
    entries: list[TocEntry],
) -> TocEntry | None:
    if not anchor_section:
        return None

    requested = normalize_for_match(lesson_title)

    candidates = [
        entry
        for entry in entries
        if entry.section_number == anchor_section
    ]

    if not candidates:
        return None

    # Prefer the candidate whose title contains the requested lesson title.
    for entry in candidates:
        if (
            requested in entry.normalized_title
            or entry.normalized_title in requested
        ):
            return entry

    # If numbering is unique, it is still strong evidence.
    if len(candidates) == 1:
        return candidates[0]

    return None


def find_next_peer_toc_entry(
    current: TocEntry,
    entries: list[TocEntry],
) -> TocEntry | None:
    """
    Find the next structural TOC boundary *after this exact entry*.

    Important:
    section numbers can restart in every chapter, so we must never
    search globally for another entry merely because it is numbered
    2, 3, etc.

    Examples:

        1
            1.1
            1.2
            1.3
        2

    For current=1, return 2.

        1.1
        1.2
        1.3

    For current=1.1, return 1.2.

    If the current subsection is the last child, a shallower entry
    also represents a valid boundary:

        1.5
        2

    For current=1.5, return 2.
    """
    current_number = current.section_number

    if not current_number:
        return None

    try:
        current_index = entries.index(current)
    except ValueError:
        return None

    current_depth = len(current_number)
    current_parent = current_number[:-1]

    # Only inspect entries that physically occur AFTER the matched
    # TOC entry.
    for entry in entries[current_index + 1:]:
        number = entry.section_number

        if not number:
            continue

        depth = len(number)

        # Deeper entries are children of the current section.
        #
        # Example:
        #
        #   current: 1
        #       1.1
        #       1.2
        #
        # They belong inside the current evidence region, so skip them.
        if depth > current_depth:
            continue

        # A shallower entry means we have left the current hierarchy.
        #
        # Example:
        #
        #   current: 1.5
        #   next:    2
        #
        # This is a valid boundary.
        if depth < current_depth:
            return entry

        # Same hierarchy depth.
        if current_depth == 1:
            # At top level, the first later numbered section is the
            # structural boundary.
            #
            # If numbering has restarted (e.g. new chapter starts at 1),
            # that still marks the end of the current region.
            return entry

        # For nested sections, remain inside the same parent.
        #
        # Example:
        #   1.2 -> 1.3
        if number[:-1] == current_parent:
            return entry

        # Parent changed, so we have left the current hierarchy.
        # That entry itself marks the boundary.
        return entry

    return None