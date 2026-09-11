from __future__ import annotations

import json
from pathlib import Path

import pymupdf

from mathub_extractor.extractor import extract_pdf


def _make_test_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 90), "Legi de compozitie", fontsize=18)
    page.insert_text((72, 130), "Definitie de test.", fontsize=11)
    doc.set_toc([[1, "Legi de compozitie", 1]])
    doc.save(path)
    doc.close()


def test_native_pdf_creates_page_based_output(tmp_path: Path) -> None:
    pdf_path = tmp_path / "manual.pdf"
    output_dir = tmp_path / "out"
    _make_test_pdf(pdf_path)

    manifest = extract_pdf(
        pdf_path,
        manual_id="test-manual",
        output_dir=output_dir,
        force_backend="native",
    )

    assert manifest["schema_version"] == "0.2.0"
    assert manifest["source"]["page_count"] == 1
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "report.txt").exists()
    assert (output_dir / "pages" / "p0001.json").exists()

    page = json.loads((output_dir / "pages" / "p0001.json").read_text("utf-8"))
    assert page["text_layer"]["backend"] == "PYMUPDF_NATIVE"
    assert page["text_layer"]["quality"]["status"] == "GOOD"
    spans = page["text_layer"]["blocks"][0]["lines"][0]["spans"]
    assert spans[0]["text"]
