from __future__ import annotations

import argparse
from pathlib import Path

from .extractor import extract_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mathub-extract",
        description=(
            "Create a quality-gated deterministic source representation of a PDF manual."
        ),
    )
    parser.add_argument("pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "--manual-id",
        required=True,
        help="Stable logical manual identifier, e.g. manual-all.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory.",
    )
    parser.add_argument(
        "--pdftotext",
        type=Path,
        default=None,
        help="Optional explicit path to Poppler's pdftotext executable.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "native", "poppler"],
        default="auto",
        help=(
            "Text backend policy. 'auto' uses PyMuPDF first and Poppler only when "
            "the native quality gate fails."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF does not exist: {args.pdf}")
    if args.pdf.suffix.lower() != ".pdf":
        raise SystemExit(f"Expected a PDF file: {args.pdf}")

    manifest = extract_pdf(
        args.pdf,
        manual_id=args.manual_id,
        output_dir=args.output,
        pdftotext_path=args.pdftotext,
        force_backend=args.backend,
    )

    summary = manifest["extraction_summary"]
    print()
    print("Mathub extraction complete")
    print("=" * 26)
    print(f"Manual:  {manifest['source']['filename']}")
    print(f"Pages:   {manifest['source']['page_count']}")
    print(f"Status:  {summary['overall_status']}")
    print()
    print("Backends:")
    for backend, count in summary["backend_page_counts"].items():
        print(f"  {backend}: {count}")
    print("Quality:")
    for status, count in summary["page_status_counts"].items():
        print(f"  {status}: {count}")
    print()
    print(f"Report:  {args.output / 'report.txt'}")
    print(f"Manifest:{args.output / 'manifest.json'}")


if __name__ == "__main__":
    main()
