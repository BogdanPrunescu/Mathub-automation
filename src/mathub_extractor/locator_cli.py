from __future__ import annotations

import argparse
from pathlib import Path
import re
import unicodedata

from .locator import locate_lesson


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "lesson"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mathub-locate",
        description=(
            "Locate a requested lesson inside a v0.2+ deterministic manual extraction "
            "using only cheap structural and lexical signals."
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
        help='Requested lesson title, e.g. "Legi de compoziție".',
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional result JSON path. Defaults to "
            "<manual_dir>/locations/<lesson-slug>.json."
        ),
    )
    parser.add_argument(
        "--context-pages",
        type=int,
        default=1,
        help="Neighboring page context retained before/after the target region.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not (args.manual_dir / "manifest.json").exists():
        raise SystemExit(
            f"Not a Mathub extracted manual directory: {args.manual_dir}"
        )
    if args.context_pages < 0:
        raise SystemExit("--context-pages must be >= 0")

    output = args.output
    if output is None:
        output = args.manual_dir / "locations" / f"{_slug(args.lesson)}.json"

    result = locate_lesson(
        args.manual_dir,
        lesson_title=args.lesson,
        output_path=output,
        context_pages=args.context_pages,
    )

    print()
    print("Mathub lesson localization")
    print("=" * 26)
    print(f"Lesson: {args.lesson}")
    print(f"Status: {result['status']}")
    if result.get("anchor"):
        print(
            f"Anchor: p.{result['anchor']['pdf_page_number']} — "
            f"{result['anchor']['text']}"
        )
        print(f"Score:  {result['anchor']['score']:.3f}")
    if result.get("boundary"):
        print(
            f"End:    before p.{result['boundary']['pdf_page_number']} — "
            f"{result['boundary']['text']}"
        )
    print(f"JSON:   {output}")
    print(f"Report: {output.with_suffix('.txt')}")


if __name__ == "__main__":
    main()
