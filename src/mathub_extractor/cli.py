from __future__ import annotations

import argparse
from pathlib import Path

from .extractor import extract_pdf
from .io import write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mathub-extract",
        description="Create a deterministic source-faithful JSON representation of a PDF manual.",
    )
    parser.add_argument("pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "--manual-id",
        required=True,
        help="Stable logical manual identifier, e.g. manual-a.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory. document.json and assets/ will be created here.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF does not exist: {args.pdf}")
    if args.pdf.suffix.lower() != ".pdf":
        raise SystemExit(f"Expected a PDF file: {args.pdf}")

    data = extract_pdf(
        args.pdf,
        manual_id=args.manual_id,
        output_dir=args.output,
    )

    output_json = args.output / "document.json"
    write_json(data, output_json)

    print(f"Extracted: {args.pdf}")
    print(f"Pages:     {data['source']['page_count']}")
    print(f"SHA-256:   {data['source']['sha256']}")
    print(f"Output:    {output_json}")


if __name__ == "__main__":
    main()
