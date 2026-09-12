from __future__ import annotations

from mathub_extractor.locator.model import LineRecord
from mathub_extractor.semantic.chunks import build_retrieval_chunks
from mathub_extractor.semantic.index import DEFAULT_MODEL_NAME, SEMANTIC_INDEX_VERSION


def _line(page: int, line_index: int, text: str) -> LineRecord:
    page_id = f"p{page:04d}"
    return LineRecord(
        page_id=page_id,
        pdf_page_number=page,
        page_index=page - 1,
        block_id=f"{page_id}-b0001",
        line_id=f"{page_id}-b0001-l{line_index:03d}",
        block_index=0,
        line_index=line_index - 1,
        text=text,
        bbox=[50.0, 50.0 + line_index * 15, 500.0, 62.0 + line_index * 15],
        page_width=595.0,
        page_height=842.0,
        page_quality="GOOD",
        backend="test",
    )


def test_semantic_defaults_are_declared_without_loading_model() -> None:
    assert DEFAULT_MODEL_NAME == "intfloat/multilingual-e5-small"
    assert SEMANTIC_INDEX_VERSION == "0.1.0"


def test_chunks_are_page_local_and_keep_line_provenance() -> None:
    page1 = [
        _line(1, 1, " ".join(f"a{i}" for i in range(90))),
        _line(1, 2, " ".join(f"b{i}" for i in range(90))),
    ]
    page2 = [
        _line(2, 1, " ".join(f"c{i}" for i in range(80))),
    ]

    chunks = build_retrieval_chunks(
        manual_id="manual-test",
        by_page={"p0001": page1, "p0002": page2},
        toc_pages={"p0002"},
        chunk_words=100,
        overlap_words=20,
        min_words=10,
    )

    assert chunks
    assert {chunk.page_id for chunk in chunks} == {"p0001", "p0002"}
    assert all(chunk.pdf_page_number in {1, 2} for chunk in chunks)
    assert all(chunk.start_line_id.startswith(chunk.page_id) for chunk in chunks)
    assert all(chunk.end_line_id.startswith(chunk.page_id) for chunk in chunks)
    assert all(chunk.word_count <= 100 for chunk in chunks)
    assert all(chunk.is_toc_page for chunk in chunks if chunk.page_id == "p0002")
    assert all(not chunk.is_toc_page for chunk in chunks if chunk.page_id == "p0001")


def test_embedding_text_repairs_legacy_romanian_without_rewriting_source() -> None:
    source = "Legi de compoziþie. O lege de compoziÆie."
    line = _line(1, 1, source)

    chunks = build_retrieval_chunks(
        manual_id="manual-test",
        by_page={"p0001": [line]},
        toc_pages=set(),
        chunk_words=100,
        overlap_words=20,
        min_words=1,
    )

    assert len(chunks) == 1
    assert "compoziþie" in chunks[0].text
    assert "compoziÆie" in chunks[0].text
    assert "compoziţie" in chunks[0].embedding_text
    assert "compoziŢie" in chunks[0].embedding_text
