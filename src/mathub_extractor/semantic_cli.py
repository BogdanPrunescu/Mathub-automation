from __future__ import annotations

import argparse
from pathlib import Path
import re
import unicodedata

from .semantic.index import (
    DEFAULT_CHUNK_WORDS,
    DEFAULT_MODEL_NAME,
    DEFAULT_OVERLAP_WORDS,
    search_manual,
)


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "query"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mathub-semantic",
        description=(
            "Run local multilingual embedding retrieval over an already extracted Mathub manual. "
            "The first run builds and caches a semantic index; later queries reuse it."
        ),
    )
    parser.add_argument(
        "manual_dir",
        type=Path,
        help="Manual extraction directory containing manifest.json and pages/.",
    )
    parser.add_argument(
        "--lesson",
        required=True,
        help='Semantic query, e.g. "Legi de compoziție".',
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=15,
        help="Number of highest-scoring retrieval chunks to report (default: 15).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        help=f"SentenceTransformers model name (default: {DEFAULT_MODEL_NAME}).",
    )
    parser.add_argument(
        "--chunk-words",
        type=int,
        default=DEFAULT_CHUNK_WORDS,
        help=f"Approximate words per page-local retrieval chunk (default: {DEFAULT_CHUNK_WORDS}).",
    )
    parser.add_argument(
        "--overlap-words",
        type=int,
        default=DEFAULT_OVERLAP_WORDS,
        help=f"Word overlap between neighboring chunks (default: {DEFAULT_OVERLAP_WORDS}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Embedding batch size (default: 32; reduce if memory is tight).",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuilding the cached semantic index.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional result JSON path. Defaults to "
            "<manual_dir>/semantic_search/<lesson-slug>.json."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not (args.manual_dir / "manifest.json").exists():
        raise SystemExit(f"Not a Mathub extracted manual directory: {args.manual_dir}")
    if args.top_k <= 0:
        raise SystemExit("--top-k must be > 0")
    if args.chunk_words <= 0:
        raise SystemExit("--chunk-words must be > 0")
    if args.overlap_words < 0 or args.overlap_words >= args.chunk_words:
        raise SystemExit("--overlap-words must be >= 0 and smaller than --chunk-words")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")

    output = args.output
    if output is None:
        output = args.manual_dir / "semantic_search" / f"{_slug(args.lesson)}.json"

    try:
        result = search_manual(
            args.manual_dir,
            query=args.lesson,
            output_path=output,
            top_k=args.top_k,
            model_name=args.model,
            chunk_words=args.chunk_words,
            overlap_words=args.overlap_words,
            batch_size=args.batch_size,
            rebuild=args.rebuild,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    print()
    print("Mathub semantic retrieval")
    print("=" * 25)
    print(f"Manual: {result['manual_id']}")
    print(f"Query:  {args.lesson}")
    print(f"Model:  {result['model_name']}")
    print(f"Chunks: {result['index']['chunk_count']}")
    print()
    for match in result["matches"][: min(5, len(result["matches"]))]:
        toc = " [TOC]" if match["is_toc_page"] else ""
        print(
            f"#{match['rank']:>2}  {match['score']:.4f}  "
            f"p.{match['pdf_page_number']}{toc}  {match['chunk_id']}"
        )
    print()
    print(f"JSON:   {output}")
    print(f"Report: {output.with_suffix('.txt')}")


if __name__ == "__main__":
    main()
