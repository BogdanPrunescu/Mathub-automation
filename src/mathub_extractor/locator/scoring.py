from __future__ import annotations

from difflib import SequenceMatcher
from statistics import median

from .model import Candidate, LineRecord
from .normalize import normalize_for_match, normalized_title_from_line, parse_section_number, tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def title_match_score(query: str, line_text: str) -> tuple[float, list[str]]:
    q = normalize_for_match(query)
    _number, candidate = normalized_title_from_line(line_text)
    reasons: list[str] = []
    if not q or not candidate:
        return 0.0, reasons

    if candidate == q:
        return 1.0, ["normalized_exact_title"]

    q_tokens = tokens(q)
    c_tokens = tokens(candidate)
    jac = _jaccard(q_tokens, c_tokens)
    seq = SequenceMatcher(None, q, candidate).ratio()

    containment = 0.0
    # Containment is meaningful for title phrases, not for one-token fragments
    # such as "i" that happen to occur inside a longer lesson title.
    shorter_tokens = q_tokens if len(q_tokens) <= len(c_tokens) else c_tokens
    if len(shorter_tokens) >= 2 and (q in candidate or candidate in q):
        shorter = min(len(q), len(candidate))
        longer = max(len(q), len(candidate))
        containment = 0.75 + 0.25 * (shorter / max(1, longer))
        reasons.append("normalized_containment")

    score = max(0.55 * jac + 0.45 * seq, containment)
    if jac >= 0.8:
        reasons.append("high_token_overlap")
    if seq >= 0.85:
        reasons.append("high_sequence_similarity")
    return min(1.0, score), reasons


def page_line_height_medians(by_page: dict[str, list[LineRecord]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for page_id, lines in by_page.items():
        heights = [line.height for line in lines if line.height > 0]
        out[page_id] = median(heights) if heights else 0.0
    return out


def heading_score(line: LineRecord, page_median_height: float) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    text = line.text.strip()
    section = parse_section_number(text)

    if section:
        score += 0.36
        reasons.append("numbered_heading_candidate")

    length = len(text)
    if length <= 80:
        score += 0.16
        reasons.append("short_line")
    elif length <= 140:
        score += 0.08

    if line.top_fraction <= 0.22:
        score += 0.14
        reasons.append("near_page_top")
    elif line.top_fraction <= 0.38:
        score += 0.07

    if page_median_height > 0 and line.height >= page_median_height * 1.15:
        score += 0.18
        reasons.append("larger_than_page_body")
    elif page_median_height > 0 and line.height >= page_median_height * 1.05:
        score += 0.08

    # A heading usually does not end like a prose sentence.
    if not text.endswith((".", ";", ",", ":")):
        score += 0.06

    return min(1.0, score), reasons


def make_candidates(
    query: str,
    lines: list[LineRecord],
    by_page: dict[str, list[LineRecord]],
    toc_pages: set[str],
    toc_title_present: bool,
) -> list[Candidate]:
    medians = page_line_height_medians(by_page)
    candidates: list[Candidate] = []

    for line in lines:
        title_score, title_reasons = title_match_score(query, line.text)
        if title_score < 0.42:
            continue

        h_score, heading_reasons = heading_score(line, medians.get(line.page_id, 0.0))
        toc_penalty = 0.58 if line.page_id in toc_pages else 0.0
        quality_penalty = 0.0
        if line.page_quality == "SUSPECT":
            quality_penalty = 0.06
        elif line.page_quality in {"EMPTY", "UNUSABLE"}:
            quality_penalty = 0.40
        if "\ufffd" in line.text:
            quality_penalty += 0.10

        toc_support = 0.07 if toc_title_present and line.page_id not in toc_pages else 0.0

        final = (
            0.74 * title_score
            + 0.26 * h_score
            + toc_support
            - toc_penalty
            - quality_penalty
        )
        final = max(0.0, min(1.0, final))

        reasons = title_reasons + heading_reasons
        if toc_support:
            reasons.append("toc_supported")
        if toc_penalty:
            reasons.append("toc_page_penalty")
        if quality_penalty:
            reasons.append("page_quality_penalty")

        candidates.append(
            Candidate(
                line=line,
                title_score=title_score,
                heading_score=h_score,
                toc_penalty=toc_penalty,
                quality_penalty=quality_penalty,
                toc_support=toc_support,
                final_score=final,
                match_reasons=reasons,
                section_number=parse_section_number(line.text),
            )
        )

    candidates.sort(
        key=lambda c: (
            c.final_score,
            c.title_score,
            c.heading_score,
            -c.line.pdf_page_number,
        ),
        reverse=True,
    )
    return candidates
