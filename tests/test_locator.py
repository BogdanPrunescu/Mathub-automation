from __future__ import annotations

import json
from pathlib import Path

from mathub_extractor.locator import locate_lesson


def _line(line_id: str, text: str, y: float, height: float = 14.0) -> dict:
    return {
        "id": line_id,
        "bbox": [50.0, y, 500.0, y + height],
        "spans": [{"id": line_id + "-s001", "text": text, "bbox": [50.0, y, 500.0, y + height]}],
    }


def _write_page(
    root: Path,
    page_num: int,
    lines: list[tuple[str, float, float]],
    quality: str = "GOOD",
) -> None:
    page_id = f"p{page_num:04d}"
    block_lines = [
        _line(f"{page_id}-b0001-l{i+1:03d}", text, y, h)
        for i, (text, y, h) in enumerate(lines)
    ]
    page = {
        "schema_version": "0.2.0",
        "source_sha256": "a" * 64,
        "manual_id": "test-manual",
        "id": page_id,
        "pdf_page_index": page_num - 1,
        "pdf_page_number": page_num,
        "page_label": "",
        "width": 595.0,
        "height": 842.0,
        "rotation": 0,
        "text_layer": {
            "backend": "POPPLER_PDFTOTEXT",
            "backend_version": "test",
            "quality": {"status": quality},
            "blocks": [
                {
                    "id": f"{page_id}-b0001",
                    "type": "text",
                    "raw_order_index": 0,
                    "reading_order_index": 0,
                    "bbox": [50.0, 50.0, 500.0, 760.0],
                    "lines": block_lines,
                }
            ],
        },
        "images": [],
        "warnings": [],
    }
    (root / "pages" / f"{page_id}.json").write_text(
        json.dumps(page, ensure_ascii=False),
        encoding="utf-8",
    )


def test_locator_ignores_toc_and_uses_next_peer_heading(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()

    _write_page(
        tmp_path,
        1,
        [
            ("Cuprins", 60, 18),
            ("1.1. Legi de compoziţie ........ 3", 120, 12),
            ("1.2. Proprietăţi ale legilor de compoziţie ........ 5", 145, 12),
            ("1.3. Grupuri ........ 8", 170, 12),
            ("1.4. Alte noţiuni ........ 10", 195, 12),
            ("2.1. Inele ........ 12", 220, 12),
            ("2.2. Corpuri ........ 15", 245, 12),
            ("3.1. Polinoame ........ 20", 270, 12),
            ("4.1. Integrale ........ 25", 295, 12),
        ],
    )
    _write_page(
        tmp_path,
        2,
        [("Introducere", 80, 18), ("Text obişnuit de introducere.", 140, 12)],
    )
    _write_page(
        tmp_path,
        3,
        [
            ("1.1. Legi de compoziţie", 70, 22),
            ("Fie M o mulţime nevidă fixată.", 145, 12),
            ("Se numeşte lege de compoziţie...", 170, 12),
        ],
    )
    _write_page(
        tmp_path,
        4,
        [("Exemple", 80, 18), ("Un exemplu de operaţie.", 150, 12)],
    )
    _write_page(
        tmp_path,
        5,
        [
            ("1.2. Proprietăţi ale legilor de compoziţie", 75, 22),
            ("Text despre proprietăţi.", 145, 12),
        ],
    )

    manifest = {
        "schema_version": "0.2.0",
        "source": {
            "manual_id": "test-manual",
            "filename": "test.pdf",
            "sha256": "a" * 64,
            "page_count": 5,
        },
        "page_files": [f"pages/p{i:04d}.json" for i in range(1, 6)],
        "toc": [],
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    result = locate_lesson(tmp_path, lesson_title="Legi de compoziție")

    assert result["status"] == "FOUND_HIGH_CONFIDENCE"
    assert result["anchor"]["pdf_page_number"] == 3
    assert result["anchor"]["text"] == "1.1. Legi de compoziţie"
    assert result["boundary"]["pdf_page_number"] == 5
    assert result["boundary"]["text"].startswith("1.2.")
    assert result["target_region"]["start_pdf_page"] == 3
    assert result["target_region"]["end_pdf_page"] == 5
    assert "p0001" in result["toc_pages"]


def test_locator_returns_not_found_for_unrelated_title(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    _write_page(tmp_path, 1, [("1.1. Legi de compoziţie", 70, 22)])

    manifest = {
        "schema_version": "0.2.0",
        "source": {
            "manual_id": "test-manual",
            "filename": "test.pdf",
            "sha256": "b" * 64,
            "page_count": 1,
        },
        "page_files": ["pages/p0001.json"],
        "toc": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = locate_lesson(tmp_path, lesson_title="Integrale definite")
    assert result["status"] == "NOT_FOUND"
    assert result["anchor"] is None


def test_locator_rejects_numbered_noise_as_peer_heading(
    tmp_path: Path,
) -> None:
    """
    Regression test for the Carminis case.

    A line such as "3 ," must not be interpreted as the next section
    merely because it starts with a larger integer.
    """
    (tmp_path / "pages").mkdir()

    _write_page(
        tmp_path,
        1,
        [
            ("1 Legi de compoziţie pe o mulţime", 70, 22),
            ("Text introductiv despre legi de compoziţie.", 145, 12),
        ],
    )

    _write_page(
        tmp_path,
        2,
        [
            ("Exemple", 80, 18),
            ("3 ,", 300, 12),
            ("Continuarea lecţiei.", 340, 12),
        ],
    )

    _write_page(
        tmp_path,
        3,
        [
            ("2 Proprietăţi ale legilor de compoziţie", 75, 22),
            ("Text despre proprietăţi.", 145, 12),
        ],
    )

    manifest = {
        "schema_version": "0.2.0",
        "source": {
            "manual_id": "test-carminis",
            "filename": "test.pdf",
            "sha256": "c" * 64,
            "page_count": 3,
        },
        "page_files": [
            "pages/p0001.json",
            "pages/p0002.json",
            "pages/p0003.json",
        ],
        "toc": [],
    }

    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    result = locate_lesson(
        tmp_path,
        lesson_title="Legi de compoziție",
    )

    assert result["anchor"]["pdf_page_number"] == 1

    # Critical regression check:
    # "3 ," on page 2 must NOT become the boundary.
    assert result["boundary"]["pdf_page_number"] == 3
    assert result["boundary"]["text"].startswith("2 Proprietăţi")

def test_toc_peer_search_respects_current_position() -> None:
    from mathub_extractor.locator.toc import (
        TocEntry,
        find_next_peer_toc_entry,
    )

    def entry(
        section: tuple[int, ...],
        title: str,
        page: int,
    ) -> TocEntry:
        number = ".".join(str(x) for x in section)

        return TocEntry(
            page_id="p0100",
            pdf_page_number=100,
            line_id=f"line-{number}-{title}",
            raw_text=f"{number}. {title} .... {page}",
            section_number=section,
            title=title,
            normalized_title=title.casefold(),
            printed_page=page,
        )

    entries = [
        # Chapter I
        entry((1,), "Legi de compoziţie", 5),
        entry((1, 1), "Definiţii", 5),
        entry((1, 2), "Exemple", 6),
        entry((2,), "Proprietăţi", 14),

        # Another chapter resets numbering
        entry((1,), "Primitive", 140),
        entry((2,), "Integrala nedefinită", 150),
    ]

    current = entries[0]

    result = find_next_peer_toc_entry(
        current,
        entries,
    )

    assert result is entries[3]
    assert result.title == "Proprietăţi"
