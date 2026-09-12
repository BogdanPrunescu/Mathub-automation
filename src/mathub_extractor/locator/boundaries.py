from __future__ import annotations
from difflib import SequenceMatcher

from .normalize import normalize_for_match
from .toc import TocEntry

from .model import LineRecord
from .normalize import (
    normalize_for_match,
    parse_section_number,
    same_level_next,
    strip_section_prefix,
)


def _position_key(line: LineRecord) -> tuple[int, int, int]:
    return (line.page_index, line.block_index, line.line_index)


def _is_immediate_peer(
    candidate: tuple[int, ...],
    start: tuple[int, ...],
) -> bool:
    """
    Examples:
        1   -> 2     True
        1   -> 3     False
        1.1 -> 1.2   True
        1.1 -> 1.3   False
        1.1 -> 2.1   False
    """
    if len(candidate) != len(start):
        return False

    if len(start) > 1 and candidate[:-1] != start[:-1]:
        return False

    return candidate[-1] == start[-1] + 1


def _has_meaningful_heading_text(line: LineRecord) -> bool:
    """
    Reject things that merely start with a number but are not real headings.

    For example:
        "3 ,"          -> reject
        "2 )"          -> reject
        "4 x + y = 2"  -> reject
        "2 Proprietăţi ale legilor..." -> accept
    """
    _number, body = strip_section_prefix(line.text)
    normalized_body = normalize_for_match(body)

    if not normalized_body:
        return False

    alphabetic_count = sum(
        1 for char in normalized_body if char.isalpha()
    )

    # A section title should contain at least a small amount of actual language.
    if alphabetic_count < 3:
        return False

    return True


def _looks_like_peer_heading(
    line: LineRecord,
    anchor: LineRecord,
) -> bool:
    """
    Apply cheap structural checks in addition to section numbering.

    A real peer heading should:
      - contain meaningful title text;
      - be reasonably short;
      - and either resemble the anchor's line height or occur near
        the upper part of a page.

    This prevents numbered examples / formulas from becoming boundaries.
    """
    text = line.text.strip()

    if not _has_meaningful_heading_text(line):
        return False

    if len(text) > 180:
        return False

    # If geometry is unavailable, textual checks are all we have.
    if line.height <= 0 or anchor.height <= 0:
        return True

    similar_heading_height = line.height >= anchor.height * 0.80
    near_page_top = line.top_fraction <= 0.35

    return similar_heading_height or near_page_top


def find_next_peer_heading(
    anchor: LineRecord,
    anchor_section: tuple[int, ...] | None,
    lines: list[LineRecord],
) -> LineRecord | None:
    if not anchor_section:
        return None

    anchor_pos = _position_key(anchor)

    later_lines = [
        line
        for line in lines
        if _position_key(line) > anchor_pos
    ]

    # First pass:
    # strongly prefer the immediately expected peer:
    # 1 -> 2, 1.1 -> 1.2, 2.3 -> 2.4, etc.
    for line in later_lines:
        section = parse_section_number(line.text)

        if (
            section
            and _is_immediate_peer(section, anchor_section)
            and _looks_like_peer_heading(line, anchor)
        ):
            return line

    # Second pass:
    # textbooks can theoretically skip a section number, so allow a later
    # same-level peer only if the expected immediate peer was not found.
    for line in later_lines:
        section = parse_section_number(line.text)

        if (
            section
            and same_level_next(section, anchor_section)
            and _looks_like_peer_heading(line, anchor)
        ):
            return line

    return None


def region_page_numbers(
    anchor: LineRecord,
    end_heading: LineRecord | None,
    total_pages: int,
) -> tuple[int, int]:
    start = anchor.pdf_page_number

    if end_heading is None:
        return start, min(total_pages, start + 4)

    # The boundary heading itself is excluded from target evidence.
    # Its page can still contain target material above that heading,
    # therefore that page remains part of the coarse page range.
    end = end_heading.pdf_page_number

    return start, end

def find_expected_toc_boundary(
    *,
    anchor: LineRecord,
    current_toc_entry: TocEntry,
    next_toc_entry: TocEntry,
    lines: list[LineRecord],
    search_radius_pages: int = 2,
) -> LineRecord | None:
    """
    Use TOC information to predict where the next peer section should
    appear in the PDF, then confirm it using the expected title.

    Example:
        TOC says current section starts printed page 5.
        Actual anchor is PDF page 6.
        Therefore offset = +1.

        Next TOC section says printed page 14.
        Expected PDF page = 15.
    """
    if (
        current_toc_entry.printed_page is None
        or next_toc_entry.printed_page is None
    ):
        return None

    page_offset = (
        anchor.pdf_page_number
        - current_toc_entry.printed_page
    )

    expected_pdf_page = (
        next_toc_entry.printed_page
        + page_offset
    )

    expected_title = normalize_for_match(
        next_toc_entry.title
    )

    best_line: LineRecord | None = None
    best_score = 0.0

    for line in lines:
        if abs(
            line.pdf_page_number - expected_pdf_page
        ) > search_radius_pages:
            continue

        # Must be near the expected page.
        candidate_text = normalize_for_match(
            line.text
        )

        if not candidate_text:
            continue

        # Compare expected TOC title against body heading.
        if expected_title in candidate_text:
            score = 1.0
        else:
            score = SequenceMatcher(
                None,
                expected_title,
                candidate_text,
            ).ratio()

        # Give preference to lines near the top of the page.
        if line.top_fraction <= 0.35:
            score += 0.08

        # Give preference to relatively short heading-like text.
        if len(line.text.strip()) <= 180:
            score += 0.04

        if score > best_score:
            best_score = score
            best_line = line

    # Do not invent a boundary from a weak match.
    if best_score < 0.68:
        return None

    return best_line