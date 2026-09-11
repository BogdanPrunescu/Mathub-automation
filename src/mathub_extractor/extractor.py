from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import pymupdf

from . import SCHEMA_VERSION, __version__
from .hashing import sha256_bytes, sha256_file
from .normalize import make_search_text


def _list4(value: Any) -> list[float] | None:
    if value is None:
        return None
    return [float(x) for x in value]


def _list2(value: Any) -> list[float] | None:
    if value is None:
        return None
    return [float(x) for x in value]


def _flag_names(flags: int) -> list[str]:
    names: list[str] = []
    if flags & (1 << 0):
        names.append("superscript")
    if flags & (1 << 1):
        names.append("italic")
    if flags & (1 << 2):
        names.append("serif")
    else:
        names.append("sans")
    if flags & (1 << 3):
        names.append("monospaced")
    else:
        names.append("proportional")
    if flags & (1 << 4):
        names.append("bold")
    return names


def _line_text(line: dict[str, Any]) -> str:
    return "".join(str(span.get("text", "")) for span in line.get("spans", []))


def _block_text(block: dict[str, Any]) -> str:
    return "\n".join(_line_text(line) for line in block.get("lines", []))


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    return {str(k): v for k, v in metadata.items()}


def _reading_order_map(page: pymupdf.Page) -> dict[int, int]:
    sorted_dict = page.get_text("dict", sort=True)
    mapping: dict[int, int] = {}
    for order_index, block in enumerate(sorted_dict.get("blocks", [])):
        number = block.get("number")
        if isinstance(number, int):
            mapping[number] = order_index
    return mapping


def _extract_span(
    span: dict[str, Any],
    *,
    page_id: str,
    block_index: int,
    line_index: int,
    span_index: int,
) -> dict[str, Any]:
    flags = int(span.get("flags", 0))
    span_id = f"{page_id}-b{block_index + 1:04d}-l{line_index + 1:03d}-s{span_index + 1:03d}"

    return {
        "id": span_id,
        "index": span_index,
        "text": str(span.get("text", "")),
        "bbox": _list4(span.get("bbox")),
        "origin": _list2(span.get("origin")),
        "font": span.get("font"),
        "size": float(span["size"]) if span.get("size") is not None else None,
        "flags": flags,
        "flag_names": _flag_names(flags),
        "color": span.get("color"),
        "ascender": float(span["ascender"]) if span.get("ascender") is not None else None,
        "descender": float(span["descender"]) if span.get("descender") is not None else None,
    }


def _extract_text_block(
    block: dict[str, Any],
    *,
    page_id: str,
    raw_order_index: int,
    reading_order_index: int | None,
) -> dict[str, Any]:
    block_id = f"{page_id}-b{raw_order_index + 1:04d}"
    lines_out: list[dict[str, Any]] = []

    for line_index, line in enumerate(block.get("lines", [])):
        spans_out = [
            _extract_span(
                span,
                page_id=page_id,
                block_index=raw_order_index,
                line_index=line_index,
                span_index=span_index,
            )
            for span_index, span in enumerate(line.get("spans", []))
        ]

        line_text = _line_text(line)
        lines_out.append(
            {
                "id": f"{block_id}-l{line_index + 1:03d}",
                "index": line_index,
                "bbox": _list4(line.get("bbox")),
                "writing_mode": line.get("wmode"),
                "direction": _list2(line.get("dir")),
                "text": line_text,
                "spans": spans_out,
            }
        )

    text = _block_text(block)

    return {
        "id": block_id,
        "type": "text",
        "source_block_number": block.get("number"),
        "raw_order_index": raw_order_index,
        "reading_order_index": reading_order_index,
        "bbox": _list4(block.get("bbox")),
        "text": text,
        "search_text": make_search_text(text),
        "lines": lines_out,
    }


def _extract_image_block(
    block: dict[str, Any],
    *,
    page_id: str,
    raw_order_index: int,
    reading_order_index: int | None,
    assets_dir: Path,
) -> dict[str, Any]:
    image_bytes = block.get("image")
    asset_sha256 = None
    asset_path = None

    if isinstance(image_bytes, (bytes, bytearray)):
        data = bytes(image_bytes)
        asset_sha256 = sha256_bytes(data)
        ext = str(block.get("ext") or "bin").lower()
        filename = f"image-{asset_sha256}.{ext}"
        destination = assets_dir / filename
        if not destination.exists():
            destination.write_bytes(data)
        asset_path = f"assets/{filename}"

    return {
        "id": f"{page_id}-b{raw_order_index + 1:04d}",
        "type": "image",
        "source_block_number": block.get("number"),
        "raw_order_index": raw_order_index,
        "reading_order_index": reading_order_index,
        "bbox": _list4(block.get("bbox")),
        "width_px": block.get("width"),
        "height_px": block.get("height"),
        "extension": block.get("ext"),
        "colorspace": block.get("colorspace"),
        "bits_per_component": block.get("bpc"),
        "xres": block.get("xres"),
        "yres": block.get("yres"),
        "encoded_size_bytes": len(image_bytes) if isinstance(image_bytes, (bytes, bytearray)) else None,
        "transform": [float(x) for x in block.get("transform", [])] or None,
        "asset_sha256": asset_sha256,
        "asset_path": asset_path,
    }


def extract_pdf(
    pdf_path: Path,
    *,
    manual_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    pdf_path = pdf_path.resolve()
    output_dir = output_dir.resolve()
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(pdf_path)

    with pymupdf.open(pdf_path) as doc:
        if doc.needs_pass:
            raise ValueError("Password-protected PDFs are not supported in v0.1.")

        pages_out: list[dict[str, Any]] = []

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_id = f"p{page_index + 1:04d}"

            raw_dict = page.get_text("dict", sort=False)
            reading_map = _reading_order_map(page)

            blocks_out: list[dict[str, Any]] = []
            text_char_count = 0

            for raw_order_index, block in enumerate(raw_dict.get("blocks", [])):
                block_type = int(block.get("type", -1))
                source_number = block.get("number")
                reading_order_index = (
                    reading_map.get(source_number)
                    if isinstance(source_number, int)
                    else None
                )

                if block_type == 0:
                    extracted = _extract_text_block(
                        block,
                        page_id=page_id,
                        raw_order_index=raw_order_index,
                        reading_order_index=reading_order_index,
                    )
                    text_char_count += len(extracted["text"])
                    blocks_out.append(extracted)
                elif block_type == 1:
                    blocks_out.append(
                        _extract_image_block(
                            block,
                            page_id=page_id,
                            raw_order_index=raw_order_index,
                            reading_order_index=reading_order_index,
                            assets_dir=assets_dir,
                        )
                    )
                else:
                    blocks_out.append(
                        {
                            "id": f"{page_id}-b{raw_order_index + 1:04d}",
                            "type": f"unsupported_block_type_{block_type}",
                            "source_block_number": source_number,
                            "raw_order_index": raw_order_index,
                            "reading_order_index": reading_order_index,
                            "bbox": _list4(block.get("bbox")),
                        }
                    )

            warnings: list[str] = []
            if text_char_count == 0:
                warnings.append("no_text_extracted")

            reading_text_blocks = sorted(
                (block for block in blocks_out if block["type"] == "text"),
                key=lambda b: (
                    b["reading_order_index"] is None,
                    b["reading_order_index"]
                    if b["reading_order_index"] is not None
                    else b["raw_order_index"],
                ),
            )
            plain_text_reading_order = "\n\n".join(
                block["text"] for block in reading_text_blocks if block["text"]
            )

            try:
                page_label = page.get_label()
            except Exception:
                page_label = ""

            pages_out.append(
                {
                    "id": page_id,
                    "pdf_page_index": page_index,
                    "pdf_page_number": page_index + 1,
                    "page_label": page_label,
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                    "rotation": int(page.rotation),
                    "text_char_count": text_char_count,
                    "plain_text_reading_order": plain_text_reading_order,
                    "blocks": blocks_out,
                    "warnings": warnings,
                }
            )

        toc_out = []
        for item in doc.get_toc(simple=True):
            if len(item) >= 3:
                level, title, page_number = item[:3]
                toc_out.append(
                    {
                        "level": int(level),
                        "title": str(title),
                        "pdf_page_number": int(page_number),
                        "pdf_page_index": int(page_number) - 1 if int(page_number) > 0 else None,
                    }
                )

        result = {
            "schema_version": SCHEMA_VERSION,
            "extractor": {
                "name": "mathub-material-extractor",
                "version": __version__,
                "pymupdf_version": package_version("PyMuPDF"),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "source": {
                "manual_id": manual_id,
                "filename": pdf_path.name,
                "sha256": source_sha256,
                "size_bytes": pdf_path.stat().st_size,
                "page_count": doc.page_count,
            },
            "pdf_metadata": _safe_metadata(doc.metadata),
            "toc": toc_out,
            "pages": pages_out,
        }

    return result
