from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..io import write_json, write_text
from ..locator.load import load_lines, load_manifest
from ..locator.normalize import repair_legacy_for_search
from ..locator.toc import detect_toc_pages
from .chunks import RetrievalChunk, build_retrieval_chunks


SEMANTIC_INDEX_VERSION = "0.1.0"
DEFAULT_MODEL_NAME = "intfloat/multilingual-e5-small"
DEFAULT_CHUNK_WORDS = 220
DEFAULT_OVERLAP_WORDS = 60


def _require_semantic_dependencies():
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            'Semantic retrieval dependencies are missing. Install them with: '
            'python -m pip install -e ".[semantic]"'
        ) from exc
    return np, SentenceTransformer


def _index_dir(manual_dir: Path) -> Path:
    return manual_dir / "semantic_index"


def _index_paths(manual_dir: Path) -> tuple[Path, Path, Path]:
    root = _index_dir(manual_dir)
    return root / "meta.json", root / "chunks.json", root / "vectors.npy"


def _expected_meta(
    *,
    manifest: dict,
    model_name: str,
    chunk_words: int,
    overlap_words: int,
) -> dict[str, Any]:
    return {
        "semantic_index_version": SEMANTIC_INDEX_VERSION,
        "manual_id": manifest["source"]["manual_id"],
        "source_sha256": manifest["source"]["sha256"],
        "model_name": model_name,
        "chunk_words": chunk_words,
        "overlap_words": overlap_words,
    }


def _cache_matches(meta_path: Path, expected: dict[str, Any]) -> bool:
    if not meta_path.exists():
        return False
    try:
        actual = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return all(actual.get(key) == value for key, value in expected.items())


def _build_index(
    manual_dir: Path,
    *,
    manifest: dict,
    model,
    model_name: str,
    chunk_words: int,
    overlap_words: int,
    batch_size: int,
) -> dict[str, Any]:
    np, _SentenceTransformer = _require_semantic_dependencies()
    lines, by_page = load_lines(manual_dir, manifest)
    toc_pages, _toc_scores = detect_toc_pages(by_page)
    chunks = build_retrieval_chunks(
        manual_id=manifest["source"]["manual_id"],
        by_page=by_page,
        toc_pages=toc_pages,
        chunk_words=chunk_words,
        overlap_words=overlap_words,
    )
    if not chunks:
        raise RuntimeError(f"No text chunks could be created from {manual_dir}")

    passages = [f"passage: {chunk.embedding_text}" for chunk in chunks]
    vectors = model.encode(
        passages,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    vectors = np.asarray(vectors, dtype=np.float32)

    meta_path, chunks_path, vectors_path = _index_paths(manual_dir)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(vectors_path, vectors)
    chunks_path.write_text(
        json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta = {
        **_expected_meta(
            manifest=manifest,
            model_name=model_name,
            chunk_words=chunk_words,
            overlap_words=overlap_words,
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "chunk_count": len(chunks),
        "embedding_dimension": int(vectors.shape[1]),
        "toc_page_count": len(toc_pages),
    }
    write_json(meta, meta_path)
    return meta


def ensure_index(
    manual_dir: Path,
    *,
    model,
    model_name: str = DEFAULT_MODEL_NAME,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
    batch_size: int = 32,
    rebuild: bool = False,
) -> dict[str, Any]:
    manual_dir = manual_dir.resolve()
    manifest = load_manifest(manual_dir)
    expected = _expected_meta(
        manifest=manifest,
        model_name=model_name,
        chunk_words=chunk_words,
        overlap_words=overlap_words,
    )
    meta_path, chunks_path, vectors_path = _index_paths(manual_dir)

    if (
        not rebuild
        and chunks_path.exists()
        and vectors_path.exists()
        and _cache_matches(meta_path, expected)
    ):
        return json.loads(meta_path.read_text(encoding="utf-8"))

    return _build_index(
        manual_dir,
        manifest=manifest,
        model=model,
        model_name=model_name,
        chunk_words=chunk_words,
        overlap_words=overlap_words,
        batch_size=batch_size,
    )


def _load_chunks(path: Path) -> list[RetrievalChunk]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [RetrievalChunk.from_dict(item) for item in payload]


def _snippet(text: str, limit: int = 420) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def _human_report(result: dict) -> str:
    lines = [
        "Mathub semantic retrieval report",
        "=" * 32,
        "",
        f"Manual ID: {result['manual_id']}",
        f"Query: {result['query']}",
        f"Model: {result['model_name']}",
        f"Chunks indexed: {result['index']['chunk_count']}",
        "",
        "Top semantic matches:",
    ]
    for match in result["matches"]:
        toc = " [TOC]" if match["is_toc_page"] else ""
        lines.extend(
            [
                f"  {match['rank']}. score={match['score']:.4f}  p.{match['pdf_page_number']}{toc}",
                f"     chunk: {match['chunk_id']}",
                f"     lines: {match['start_line_id']} -> {match['end_line_id']}",
                f"     {_snippet(match['text'])}",
                "",
            ]
        )
    lines.extend(
        [
            "Interpretation:",
            "  This is retrieval only. Scores are model-relative and are not approval thresholds.",
            "  Retrieval chunks are search artifacts, not final Source Evidence Units.",
            "  Inspect whether the top results point to the actual lesson content and whether relevant hits cluster on neighboring pages.",
            "",
        ]
    )
    return "\n".join(lines)


def search_manual(
    manual_dir: Path,
    *,
    query: str,
    output_path: Path | None = None,
    top_k: int = 15,
    model_name: str = DEFAULT_MODEL_NAME,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
    batch_size: int = 32,
    rebuild: bool = False,
) -> dict[str, Any]:
    if top_k <= 0:
        raise ValueError("top_k must be > 0")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    np, SentenceTransformer = _require_semantic_dependencies()
    manual_dir = manual_dir.resolve()
    manifest = load_manifest(manual_dir)

    model = SentenceTransformer(model_name)
    meta = ensure_index(
        manual_dir,
        model=model,
        model_name=model_name,
        chunk_words=chunk_words,
        overlap_words=overlap_words,
        batch_size=batch_size,
        rebuild=rebuild,
    )

    _meta_path, chunks_path, vectors_path = _index_paths(manual_dir)
    chunks = _load_chunks(chunks_path)
    vectors = np.load(vectors_path)
    if len(chunks) != len(vectors):
        raise RuntimeError("Semantic index is inconsistent: chunk/vector counts differ")

    repaired_query = repair_legacy_for_search(query)
    query_vector = model.encode(
        [f"query: {repaired_query}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    scores = vectors @ np.asarray(query_vector, dtype=np.float32)
    ranked_indices = np.argsort(scores)[::-1][: min(top_k, len(chunks))]

    matches = []
    for rank, index in enumerate(ranked_indices, start=1):
        chunk = chunks[int(index)]
        matches.append(
            {
                "rank": rank,
                "score": round(float(scores[int(index)]), 6),
                **chunk.to_dict(),
            }
        )

    result = {
        "semantic_retrieval_version": SEMANTIC_INDEX_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manual_id": manifest["source"]["manual_id"],
        "source_sha256": manifest["source"]["sha256"],
        "query": query,
        "model_name": model_name,
        "index": meta,
        "matches": matches,
    }

    if output_path is not None:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(result, output_path)
        write_text(_human_report(result), output_path.with_suffix(".txt"))

    return result
