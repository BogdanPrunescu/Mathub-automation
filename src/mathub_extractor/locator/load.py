from __future__ import annotations

import json
from pathlib import Path

from .model import LineRecord


def _line_text(line: dict) -> str:
    spans = line.get("spans", [])
    # Poppler spans are words; native spans are text fragments.
    texts = [str(span.get("text", "")) for span in spans]
    if not texts:
        return ""
    if all((" " not in t and "\n" not in t) for t in texts):
        return " ".join(t for t in texts if t).strip()
    return "".join(texts).strip()


def load_manifest(manual_dir: Path) -> dict:
    path = manual_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"manifest.json not found in {manual_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_lines(manual_dir: Path, manifest: dict) -> tuple[list[LineRecord], dict[str, list[LineRecord]]]:
    lines: list[LineRecord] = []
    by_page: dict[str, list[LineRecord]] = {}

    for page_rel in manifest.get("page_files", []):
        page_path = manual_dir / page_rel
        page = json.loads(page_path.read_text(encoding="utf-8"))
        quality = page["text_layer"]["quality"]["status"]
        backend = page["text_layer"]["backend"]
        page_lines: list[LineRecord] = []

        for block_index, block in enumerate(page["text_layer"].get("blocks", [])):
            if block.get("type") != "text":
                continue
            block_id = str(block.get("id") or f"{page['id']}-b{block_index+1:04d}")
            for line_index, line in enumerate(block.get("lines", [])):
                text = _line_text(line)
                if not text.strip():
                    continue
                record = LineRecord(
                    page_id=page["id"],
                    pdf_page_number=int(page["pdf_page_number"]),
                    page_index=int(page["pdf_page_index"]),
                    block_id=block_id,
                    line_id=str(line.get("id") or f"{block_id}-l{line_index+1:03d}"),
                    block_index=block_index,
                    line_index=line_index,
                    text=text,
                    bbox=line.get("bbox"),
                    page_width=float(page["width"]),
                    page_height=float(page["height"]),
                    page_quality=quality,
                    backend=backend,
                )
                lines.append(record)
                page_lines.append(record)

        by_page[page["id"]] = page_lines

    return lines, by_page
