from __future__ import annotations

from dataclasses import asdict, dataclass

from ..locator.model import LineRecord
from ..locator.normalize import repair_legacy_for_search


@dataclass(frozen=True)
class RetrievalChunk:
    chunk_id: str
    manual_id: str
    page_id: str
    pdf_page_number: int
    start_line_id: str
    end_line_id: str
    text: str
    embedding_text: str
    word_count: int
    is_toc_page: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "RetrievalChunk":
        return cls(**payload)


def _page_tokens(lines: list[LineRecord]) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for line in lines:
        for word in line.text.split():
            tokens.append((word, line.line_id))
    return tokens


def build_retrieval_chunks(
    *,
    manual_id: str,
    by_page: dict[str, list[LineRecord]],
    toc_pages: set[str],
    chunk_words: int = 220,
    overlap_words: int = 60,
    min_words: int = 30,
) -> list[RetrievalChunk]:
    """Build page-local sliding windows for semantic retrieval.

    Retrieval chunks are search artifacts, not SEUs. They never cross a PDF
    page, keep exact line provenance, and preserve the canonical extracted text
    alongside a search-repaired copy used for embedding.
    """
    if chunk_words <= 0:
        raise ValueError("chunk_words must be > 0")
    if overlap_words < 0:
        raise ValueError("overlap_words must be >= 0")
    if overlap_words >= chunk_words:
        raise ValueError("overlap_words must be smaller than chunk_words")
    if min_words <= 0:
        raise ValueError("min_words must be > 0")

    step = chunk_words - overlap_words
    chunks: list[RetrievalChunk] = []

    ordered_pages = sorted(
        by_page.items(),
        key=lambda item: item[1][0].page_index if item[1] else 10**9,
    )

    for page_id, lines in ordered_pages:
        if not lines:
            continue

        tokens = _page_tokens(lines)
        if not tokens:
            continue

        starts = list(range(0, len(tokens), step))
        page_chunk_index = 0

        for start in starts:
            end = min(len(tokens), start + chunk_words)

            # If the final window would be tiny, shift it backward so the tail
            # remains represented without creating a near-empty chunk.
            if end == len(tokens) and (end - start) < min_words and start > 0:
                start = max(0, len(tokens) - chunk_words)
                if chunks and chunks[-1].page_id == page_id:
                    previous = chunks[-1]
                    if previous.start_line_id == tokens[start][1] and previous.end_line_id == tokens[end - 1][1]:
                        break

            window = tokens[start:end]
            if not window:
                continue

            raw_text = " ".join(word for word, _line_id in window)
            embedding_text = repair_legacy_for_search(raw_text)
            page_chunk_index += 1

            chunks.append(
                RetrievalChunk(
                    chunk_id=f"{manual_id}-{page_id}-c{page_chunk_index:03d}",
                    manual_id=manual_id,
                    page_id=page_id,
                    pdf_page_number=lines[0].pdf_page_number,
                    start_line_id=window[0][1],
                    end_line_id=window[-1][1],
                    text=raw_text,
                    embedding_text=embedding_text,
                    word_count=len(window),
                    is_toc_page=page_id in toc_pages,
                )
            )

            if end == len(tokens):
                break

    return chunks
