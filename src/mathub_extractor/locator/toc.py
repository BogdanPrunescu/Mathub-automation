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
    entries: list[TocEntry] = []

    for page_id in toc_pages:
        for line in by_page.get(page_id, []):
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
    current_number = current.section_number
    if not current_number:
        return None

    expected = (
        current_number[:-1]
        + (current_number[-1] + 1,)
    )

    # Prefer exact successor: 1 -> 2, 1.1 -> 1.2.
    for entry in entries:
        if entry.section_number == expected:
            return entry

    # Fallback: later same-level entry with same parent.
    possible = []

    for entry in entries:
        number = entry.section_number
        if not number:
            continue

        if len(number) != len(current_number):
            continue

        if len(number) > 1 and number[:-1] != current_number[:-1]:
            continue

        if number[-1] > current_number[-1]:
            possible.append(entry)

    if not possible:
        return None

    possible.sort(key=lambda entry: entry.section_number)
    return possible[0]