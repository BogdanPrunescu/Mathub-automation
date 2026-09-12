from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..io import write_json, write_text
from .boundaries import (
    find_expected_toc_boundary,
    find_next_peer_heading,
    region_page_numbers,
)
from .load import load_lines, load_manifest
from .normalize import normalize_for_match, parse_section_number
from .scoring import make_candidates, title_match_score
from .toc import (
    detect_toc_pages,
    extract_toc_entries,
    find_matching_toc_entry,
    find_next_peer_toc_entry,
)


def _toc_support(query: str, toc_pages: set[str], by_page: dict) -> tuple[bool, list[dict]]:
    matches: list[dict] = []
    for page_id in toc_pages:
        for line in by_page.get(page_id, []):
            score, _ = title_match_score(query, line.text)
            if score >= 0.72:
                matches.append(
                    {
                        **line.source_ref(),
                        "match_score": round(score, 4),
                    }
                )
    return bool(matches), matches


def _status(candidates: list, top_score: float, margin: float) -> str:
    if not candidates or top_score < 0.50:
        return "NOT_FOUND"
    if top_score >= 0.82 and margin >= 0.10:
        return "FOUND_HIGH_CONFIDENCE"
    if top_score >= 0.68:
        if len(candidates) > 1 and margin < 0.08:
            return "MULTIPLE_CANDIDATES"
        return "FOUND_LOW_CONFIDENCE"
    return "FOUND_LOW_CONFIDENCE"


def _human_report(result: dict) -> str:
    lines = [
        "Mathub lesson localization report",
        "=" * 34,
        "",
        f"Manual ID: {result['manual_id']}",
        f"Requested lesson: {result['requested_lesson']['title']}",
        f"Status: {result['status']}",
        "",
    ]

    anchor = result.get("anchor")
    if anchor:
        lines.extend(
            [
                "Selected anchor:",
                f"  Page: {anchor['pdf_page_number']}",
                f"  Text: {anchor['text']}",
                f"  Score: {anchor['score']:.3f}",
                f"  Reasons: {', '.join(anchor['reasons']) or 'n/a'}",
                "",
            ]
        )

    boundary = result.get("boundary")
    if boundary:
        lines.extend(
            [
                "Detected end boundary:",
                f"  Type: {boundary['type']}",
                f"  Page: {boundary['pdf_page_number']}",
                f"  Text: {boundary['text']}",
                "",
            ]
        )
    elif anchor:
        lines.extend(
            [
                "Detected end boundary:",
                "  No peer heading found; conservative fallback page window used.",
                "",
            ]
        )

    region = result.get("target_region")
    if region:
        lines.extend(
            [
                "Target evidence region:",
                f"  Page range: {region['start_pdf_page']}–{region['end_pdf_page']}",
                f"  Start ref: {region['start_ref']['line_id']}",
                f"  End: {'before ' + region['end_exclusive_ref']['line_id'] if region.get('end_exclusive_ref') else 'fallback page window'}",
                "",
                f"Context before: {', '.join(region['context_before_pages']) or 'none'}",
                f"Context after: {', '.join(region['context_after_pages']) or 'none'}",
                "",
            ]
        )

    if result.get("toc_matches"):
        lines.append("TOC support:")
        for match in result["toc_matches"][:5]:
            lines.append(
                f"  Page {match['pdf_page_number']}: {match['text']} "
                f"(score {match['match_score']:.3f})"
            )
        lines.append("")

    lines.append("Top candidates:")
    for idx, cand in enumerate(result.get("candidates", [])[:5], start=1):
        line = cand["line"]
        lines.append(
            f"  {idx}. p.{line['pdf_page_number']} — {line['text']} "
            f"[{cand['final_score']:.3f}]"
        )

    lines.extend(
        [
            "",
            "Interpretation:",
            "  FOUND_HIGH_CONFIDENCE = cheap deterministic localization is sufficient.",
            "  FOUND_LOW_CONFIDENCE  = candidate exists but should be reviewed.",
            "  MULTIPLE_CANDIDATES   = cheap methods could not confidently choose one.",
            "  NOT_FOUND             = escalate localization; do not invent a region.",
            "",
            "The region is an evidence-capture proposal, not a final lesson-inclusion decision.",
            "",
        ]
    )
    return "\n".join(lines)


def locate_lesson(
    manual_dir: Path,
    *,
    lesson_title: str,
    output_path: Path | None = None,
    context_pages: int = 1,
    max_candidates: int = 10,
) -> dict:
    manual_dir = manual_dir.resolve()
    manifest = load_manifest(manual_dir)
    lines, by_page = load_lines(manual_dir, manifest)
    toc_pages, toc_page_scores = detect_toc_pages(by_page)
    toc_present, toc_matches = _toc_support(lesson_title, toc_pages, by_page)
    toc_entries = extract_toc_entries(toc_pages, by_page)

    candidates = make_candidates(
        lesson_title,
        lines,
        by_page,
        toc_pages,
        toc_title_present=toc_present,
    )

    top = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None
    margin = (top.final_score - second.final_score) if top and second else (top.final_score if top else 0.0)
    status = _status(candidates, top.final_score if top else 0.0, margin)

    anchor = None
    boundary = None
    target_region = None

    if top and status != "NOT_FOUND":
        anchor_line = top.line

        end_heading = None
        boundary_source = None

        # Preferred path:
        # use the textbook's own TOC structure.
        current_toc_entry = find_matching_toc_entry(
            top.section_number,
            lesson_title,
            toc_entries,
        )

        next_toc_entry = None

        if current_toc_entry is not None:
            next_toc_entry = find_next_peer_toc_entry(
                current_toc_entry,
                toc_entries,
            )

        if (
            current_toc_entry is not None
            and next_toc_entry is not None
        ):
            end_heading = find_expected_toc_boundary(
                anchor=anchor_line,
                current_toc_entry=current_toc_entry,
                next_toc_entry=next_toc_entry,
                lines=lines,
            )

            if end_heading is not None:
                boundary_source = "TOC_CONFIRMED"

        # Fallback only if TOC cannot establish the boundary.
        if end_heading is None:
            end_heading = find_next_peer_heading(
                anchor_line,
                top.section_number,
                lines,
            )

            if end_heading is not None:
                boundary_source = "BODY_HEADING_INFERENCE"

        end_heading = find_next_peer_heading(anchor_line, top.section_number, lines)
        total_pages = int(manifest["source"]["page_count"])
        start_page, end_page = region_page_numbers(anchor_line, end_heading, total_pages)

        anchor = {
            **anchor_line.source_ref(),
            "score": round(top.final_score, 4),
            "reasons": top.match_reasons,
            "section_number": (
                ".".join(str(x) for x in top.section_number)
                if top.section_number
                else None
            ),
        }

        if end_heading:
            boundary = {
                "type": "NEXT_PEER_HEADING",
                "source": boundary_source,
                **end_heading.source_ref(),
                "section_number": (
                    ".".join(str(x) for x in (parse_section_number(end_heading.text) or ()))
                    or None
                ),
            }
            if next_toc_entry is not None:
                boundary["expected_toc_title"] = (
                    next_toc_entry.title
                )
                boundary["expected_printed_page"] = (
                    next_toc_entry.printed_page
                )

        before = [
            f"p{p:04d}"
            for p in range(max(1, start_page - context_pages), start_page)
        ]
        after_start = end_heading.pdf_page_number if end_heading else end_page
        after = [
            f"p{p:04d}"
            for p in range(
                after_start,
                min(total_pages, after_start + context_pages - 1) + 1,
            )
            if p >= 1
        ]

        target_region = {
            "start_pdf_page": start_page,
            "end_pdf_page": end_page,
            "start_ref": anchor_line.source_ref(),
            "end_exclusive_ref": end_heading.source_ref() if end_heading else None,
            "context_before_pages": before,
            "context_after_pages": after,
            "boundary_policy": (
                "exclusive_next_peer_heading"
                if end_heading
                else "fallback_fixed_page_window"
            ),
        }

    result = {
        "locator_version": "0.3.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manual_id": manifest["source"]["manual_id"],
        "source_sha256": manifest["source"]["sha256"],
        "requested_lesson": {
            "title": lesson_title,
            "normalized_title": normalize_for_match(lesson_title),
        },
        "status": status,
        "score_margin": round(margin, 4),
        "anchor": anchor,
        "boundary": boundary,
        "target_region": target_region,
        "toc_pages": sorted(toc_pages),
        "toc_page_scores": {
            page_id: round(score, 4)
            for page_id, score in toc_page_scores.items()
            if score >= 0.30
        },
        "toc_matches": toc_matches[:10],
        "candidates": [candidate.to_dict() for candidate in candidates[:max_candidates]],
    }

    if output_path is not None:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(result, output_path)
        write_text(_human_report(result), output_path.with_suffix(".txt"))

    return result
