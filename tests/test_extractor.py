from __future__ import annotations

from pathlib import Path

import pymupdf

from mathub_extractor.extractor import extract_pdf


def _make_test_pdf(path: Path) -> None:
    doc = pymupdf.open()

    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((72, 90), "Legi de compozitie", fontsize=18)
    page1.insert_text((72, 130), "Definitie de test.", fontsize=11)

    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((72, 90), "Exemplu", fontsize=16)
    page2.insert_text((72, 130), "x * y = x + y", fontsize=11)

    doc.set_toc(
        [
            [1, "Legi de compozitie", 1],
            [2, "Exemplu", 2],
        ]
    )
    doc.save(path)
    doc.close()


def test_extract_pdf_preserves_structure(tmp_path: Path) -> None:
    pdf_path = tmp_path / "manual.pdf"
    output_dir = tmp_path / "out"
    _make_test_pdf(pdf_path)

    result = extract_pdf(
        pdf_path,
        manual_id="test-manual",
        output_dir=output_dir,
    )

    assert result["schema_version"] == "0.1.0"
    assert result["source"]["manual_id"] == "test-manual"
    assert result["source"]["page_count"] == 2
    assert len(result["source"]["sha256"]) == 64

    first_page = result["pages"][0]
    assert first_page["pdf_page_number"] == 1
    assert "Legi de compozitie" in first_page["plain_text_reading_order"]
    assert any(block["type"] == "text" for block in first_page["blocks"])

    first_text_block = next(
        block for block in first_page["blocks"] if block["type"] == "text"
    )
    assert first_text_block["bbox"] is not None
    assert first_text_block["lines"]
    assert first_text_block["lines"][0]["spans"]

    assert result["toc"][0]["title"] == "Legi de compozitie"
