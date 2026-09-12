from __future__ import annotations

import json
from pathlib import Path

from mathub_extractor.locator import locate_lesson
from mathub_extractor.locator.normalize import normalize_for_match
from mathub_extractor.locator.scoring import title_match_score


def test_sigma_fragment_does_not_get_containment_credit() -> None:
    score, reasons = title_match_score("Legi de compoziție", "e c")
    assert "normalized_token_containment" not in reasons
    assert score < 0.42


def test_legacy_romanian_search_normalization() -> None:
    expected = normalize_for_match("Legi de compoziție")
    assert normalize_for_match("Legi de compoziþie") == expected
    assert normalize_for_match("Legi de compoziÆie") == expected


def _write_single_page_manual(root: Path, text: str) -> None:
    (root / "pages").mkdir()
    page = {
        "schema_version": "0.2.0",
        "source_sha256": "d" * 64,
        "manual_id": "uncertain-manual",
        "id": "p0001",
        "pdf_page_index": 0,
        "pdf_page_number": 1,
        "page_label": "",
        "width": 595.0,
        "height": 842.0,
        "rotation": 0,
        "text_layer": {
            "backend": "PYMUPDF_NATIVE",
            "backend_version": "test",
            "quality": {"status": "GOOD"},
            "blocks": [
                {
                    "id": "p0001-b0001",
                    "type": "text",
                    "raw_order_index": 0,
                    "reading_order_index": 0,
                    "bbox": [50.0, 100.0, 500.0, 130.0],
                    "lines": [
                        {
                            "id": "p0001-b0001-l001",
                            "bbox": [50.0, 100.0, 500.0, 114.0],
                            "spans": [
                                {
                                    "id": "p0001-b0001-l001-s001",
                                    "text": text,
                                    "bbox": [50.0, 100.0, 500.0, 114.0],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        "images": [],
        "warnings": [],
    }
    (root / "pages" / "p0001.json").write_text(
        json.dumps(page, ensure_ascii=False), encoding="utf-8"
    )
    manifest = {
        "schema_version": "0.2.0",
        "source": {
            "manual_id": "uncertain-manual",
            "filename": "test.pdf",
            "sha256": "d" * 64,
            "page_count": 1,
        },
        "page_files": ["pages/p0001.json"],
        "toc": [],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_uncertain_localization_does_not_create_target_region(tmp_path: Path) -> None:
    _write_single_page_manual(tmp_path, "de compoziţie")
    result = locate_lesson(tmp_path, lesson_title="Legi de compoziție")

    assert result["status"] == "NEEDS_SEMANTIC_LOCALIZATION"
    assert result["deterministic_status"] != "FOUND_HIGH_CONFIDENCE"
    assert result["anchor"] is None
    assert result["boundary"] is None
    assert result["target_region"] is None
