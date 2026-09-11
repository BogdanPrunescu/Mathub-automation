from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import pymupdf

from . import SCHEMA_VERSION, __version__
from .hashing import sha256_bytes, sha256_file
from .io import write_json, write_text
from .poppler import PopplerInfo, extract_poppler_pages, find_pdftotext
from .quality import assess_text, status_rank


def _list4(value: Any) -> list[float] | None:
    if value is None:
        return None
    return [round(float(x), 3) for x in value]


def _list2(value: Any) -> list[float] | None:
    if value is None:
        return None
    return [round(float(x), 3) for x in value]


def _flag_names(flags: int) -> list[str]:
    names: list[str] = []
    if flags & (1 << 0):
        names.append("superscript")
    if flags & (1 << 1):
        names.append("italic")
    names.append("serif" if flags & (1 << 2) else "sans")
    names.append("monospaced" if flags & (1 << 3) else "proportional")
    if flags & (1 << 4):
        names.append("bold")
    return names


def _raw_span_text(span: dict[str, Any]) -> str:
    return "".join(str(char.get("c", "")) for char in span.get("chars", []))


def _raw_page_text(blocks: list[dict]) -> str:
    block_texts: list[str] = []
    for block in blocks:
        line_texts: list[str] = []
        for line in block.get("lines", []):
            line_texts.append("".join(span["text"] for span in line["spans"]))
        block_texts.append("\n".join(line_texts))
    return "\n\n".join(block_texts)


def _reading_order_map(page: pymupdf.Page) -> dict[int, int]:
    sorted_dict = page.get_text("dict", sort=True)
    mapping: dict[int, int] = {}
    for order_index, block in enumerate(sorted_dict.get("blocks", [])):
        number = block.get("number")
        if isinstance(number, int):
            mapping[number] = order_index
    return mapping


def _extract_native_text_blocks(page: pymupdf.Page, page_id: str) -> tuple[list[dict], str]:
    raw = page.get_text("rawdict", sort=False)
    reading_map = _reading_order_map(page)
    blocks_out: list[dict] = []

    for raw_order_index, block in enumerate(raw.get("blocks", [])):
        if int(block.get("type", -1)) != 0:
            continue

        block_id = f"{page_id}-b{raw_order_index + 1:04d}"
        lines_out: list[dict] = []

        for line_index, line in enumerate(block.get("lines", [])):
            spans_out: list[dict] = []
            for span_index, span in enumerate(line.get("spans", [])):
                text = _raw_span_text(span)
                spans_out.append(
                    {
                        "id": f"{block_id}-l{line_index + 1:03d}-s{span_index + 1:03d}",
                        "index": span_index,
                        "text": text,
                        "bbox": _list4(span.get("bbox")),
                        "origin": _list2(span.get("origin")),
                        "font": span.get("font"),
                        "size": float(span["size"]) if span.get("size") is not None else None,
                        "flags": int(span.get("flags", 0)),
                        "flag_names": _flag_names(int(span.get("flags", 0))),
                        "extraction_method": "PYMUPDF_NATIVE",
                        "extraction_confidence": "HIGH",
                    }
                )

            lines_out.append(
                {
                    "id": f"{block_id}-l{line_index + 1:03d}",
                    "index": line_index,
                    "bbox": _list4(line.get("bbox")),
                    "writing_mode": line.get("wmode"),
                    "direction": _list2(line.get("dir")),
                    "spans": spans_out,
                }
            )

        number = block.get("number")
        blocks_out.append(
            {
                "id": block_id,
                "type": "text",
                "source_block_number": number,
                "raw_order_index": raw_order_index,
                "reading_order_index": (
                    reading_map.get(number) if isinstance(number, int) else None
                ),
                "bbox": _list4(block.get("bbox")),
                "lines": lines_out,
            }
        )

    return blocks_out, _raw_page_text(blocks_out)


def _extract_images(page: pymupdf.Page, page_id: str, assets_dir: Path) -> list[dict]:
    data = page.get_text("dict", sort=False)
    images_out: list[dict] = []
    image_index = 0

    for block in data.get("blocks", []):
        if int(block.get("type", -1)) != 1:
            continue

        image_bytes = block.get("image")
        asset_sha256 = None
        asset_path = None
        if isinstance(image_bytes, (bytes, bytearray)):
            payload = bytes(image_bytes)
            asset_sha256 = sha256_bytes(payload)
            ext = str(block.get("ext") or "bin").lower()
            filename = f"image-{asset_sha256}.{ext}"
            destination = assets_dir / filename
            if not destination.exists():
                destination.write_bytes(payload)
            asset_path = f"assets/{filename}"

        images_out.append(
            {
                "id": f"{page_id}-img{image_index + 1:03d}",
                "bbox": _list4(block.get("bbox")),
                "width_px": block.get("width"),
                "height_px": block.get("height"),
                "extension": block.get("ext"),
                "colorspace": block.get("colorspace"),
                "bits_per_component": block.get("bpc"),
                "asset_sha256": asset_sha256,
                "asset_path": asset_path,
            }
        )
        image_index += 1

    return images_out


def _aggregate_statuses(pages: list[dict]) -> dict:
    statuses = Counter(page["text_layer"]["quality"]["status"] for page in pages)
    methods = Counter(page["text_layer"]["backend"] for page in pages)
    return {
        "page_status_counts": dict(sorted(statuses.items())),
        "backend_page_counts": dict(sorted(methods.items())),
    }


def _overall_status(pages: list[dict]) -> str:
    statuses = [page["text_layer"]["quality"]["status"] for page in pages]
    if any(status == "UNUSABLE" for status in statuses):
        return "FAILED"
    if any(status == "SUSPECT" for status in statuses):
        return "USABLE_WITH_WARNINGS"
    return "USABLE"


def _report_text(manifest: dict) -> str:
    summary = manifest["extraction_summary"]
    source = manifest["source"]
    lines = [
        "Mathub deterministic extraction report",
        "=" * 39,
        "",
        f"Manual: {source['filename']}",
        f"Manual ID: {source['manual_id']}",
        f"Pages: {source['page_count']}",
        f"Source SHA-256: {source['sha256']}",
        "",
        f"Overall status: {summary['overall_status']}",
        "",
        "Canonical text backends:",
    ]
    for backend, count in summary["backend_page_counts"].items():
        lines.append(f"  {backend}: {count} page(s)")
    lines.extend(["", "Page text quality:"])
    for status, count in summary["page_status_counts"].items():
        lines.append(f"  {status}: {count} page(s)")

    poppler = summary.get("poppler")
    if poppler:
        lines.extend(
            [
                "",
                "Poppler fallback:",
                f"  {poppler['version']}",
                "  Illegal XML control glyphs preserved as unresolved: "
                f"{poppler['illegal_xml_controls_preserved_as_unresolved']}",
                f"  Unresolved glyph count: {poppler['unresolved_glyph_count']}",
            ]
        )

    lines.extend(
        [
            "",
            "Interpretation:",
            "  GOOD     = text can be used as machine-readable source text.",
            "  SUSPECT  = mostly usable, but unresolved glyphs require visual evidence/checking.",
            "  EMPTY    = no machine-readable text was found on the page.",
            "  UNUSABLE = text extraction failed; do not create semantic units from it.",
            "",
            "The original PDF remains the authority. The extracted representation is evidence indexing,",
            "not a replacement for the source document.",
            "",
        ]
    )
    return "\n".join(lines)


def extract_pdf(
    pdf_path: Path,
    *,
    manual_id: str,
    output_dir: Path,
    pdftotext_path: Path | None = None,
    force_backend: str = "auto",
) -> dict:
    pdf_path = pdf_path.resolve()
    output_dir = output_dir.resolve()
    pages_dir = output_dir / "pages"
    assets_dir = output_dir / "assets"
    pages_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(pdf_path)
    poppler_info: PopplerInfo | None = find_pdftotext(pdftotext_path)

    with pymupdf.open(pdf_path) as doc:
        if doc.needs_pass:
            raise ValueError("Password-protected PDFs are not supported in v0.2.")

        native_pages: list[dict] = []
        any_native_problem = False

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_id = f"p{page_index + 1:04d}"
            blocks, text = _extract_native_text_blocks(page, page_id)
            quality = assess_text(text)
            if quality.status in {"SUSPECT", "UNUSABLE"}:
                any_native_problem = True
            native_pages.append(
                {
                    "blocks": blocks,
                    "text": text,
                    "quality": quality.to_dict(),
                }
            )

        poppler_pages: list[dict] | None = None
        poppler_diagnostics: dict | None = None
        should_try_poppler = (
            force_backend == "poppler"
            or (force_backend == "auto" and any_native_problem)
        )

        if should_try_poppler:
            if poppler_info is not None:
                poppler_pages, poppler_diagnostics = extract_poppler_pages(
                    pdf_path, poppler_info
                )
                if len(poppler_pages) != doc.page_count:
                    raise RuntimeError(
                        "Poppler page count does not match PyMuPDF page count: "
                        f"{len(poppler_pages)} != {doc.page_count}"
                    )
            elif force_backend == "poppler":
                raise RuntimeError(
                    "--backend poppler requested, but pdftotext was not found. "
                    "Install Poppler or pass --pdftotext PATH."
                )

        pages_out: list[dict] = []

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_id = f"p{page_index + 1:04d}"
            native = native_pages[page_index]

            chosen = native
            backend = "PYMUPDF_NATIVE"
            backend_version = package_version("PyMuPDF")

            if force_backend == "poppler" and poppler_pages is not None:
                chosen = poppler_pages[page_index]
                backend = "POPPLER_PDFTOTEXT"
                backend_version = poppler_info.version if poppler_info else "unknown"
            elif force_backend == "native":
                pass
            elif poppler_pages is not None:
                alternative = poppler_pages[page_index]
                if status_rank(alternative["quality"]["status"]) > status_rank(
                    native["quality"]["status"]
                ):
                    chosen = alternative
                    backend = "POPPLER_PDFTOTEXT"
                    backend_version = poppler_info.version if poppler_info else "unknown"
                elif native["quality"]["status"] in {"SUSPECT", "UNUSABLE"} and (
                    alternative["quality"]["replacement_ratio"]
                    < native["quality"]["replacement_ratio"]
                    or alternative["quality"]["control_ratio"]
                    < native["quality"]["control_ratio"]
                ):
                    chosen = alternative
                    backend = "POPPLER_PDFTOTEXT"
                    backend_version = poppler_info.version if poppler_info else "unknown"

            warnings: list[str] = []
            status = chosen["quality"]["status"]
            if status == "EMPTY":
                warnings.append("no_machine_readable_text")
            if status == "SUSPECT":
                warnings.append("text_requires_visual_validation")
            if status == "UNUSABLE":
                warnings.append("do_not_create_semantic_units_from_this_page")
            if backend == "PYMUPDF_NATIVE" and native["quality"]["status"] in {
                "SUSPECT",
                "UNUSABLE",
            } and poppler_info is None:
                warnings.append("poppler_fallback_unavailable")

            try:
                page_label = page.get_label()
            except Exception:
                page_label = ""

            page_record = {
                "schema_version": SCHEMA_VERSION,
                "source_sha256": source_sha256,
                "manual_id": manual_id,
                "id": page_id,
                "pdf_page_index": page_index,
                "pdf_page_number": page_index + 1,
                "page_label": page_label,
                "width": float(page.rect.width),
                "height": float(page.rect.height),
                "rotation": int(page.rotation),
                "text_layer": {
                    "backend": backend,
                    "backend_version": backend_version,
                    "quality": chosen["quality"],
                    "blocks": chosen["blocks"],
                },
                "images": _extract_images(page, page_id, assets_dir),
                "warnings": warnings,
            }
            page_file = pages_dir / f"{page_id}.json"
            write_json(page_record, page_file, pretty=False)
            pages_out.append(page_record)

        toc_out = []
        for item in doc.get_toc(simple=True):
            if len(item) >= 3:
                level, title, page_number = item[:3]
                toc_out.append(
                    {
                        "level": int(level),
                        "title": str(title),
                        "pdf_page_number": int(page_number),
                        "pdf_page_index": int(page_number) - 1
                        if int(page_number) > 0
                        else None,
                    }
                )

        aggregation = _aggregate_statuses(pages_out)
        manifest = {
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
            "pdf_metadata": {str(k): v for k, v in (doc.metadata or {}).items()},
            "toc": toc_out,
            "extraction_summary": {
                "overall_status": _overall_status(pages_out),
                **aggregation,
                "poppler": poppler_diagnostics,
            },
            "page_files": [f"pages/p{index + 1:04d}.json" for index in range(doc.page_count)],
        }

    write_json(manifest, output_dir / "manifest.json")
    write_json(manifest["extraction_summary"], output_dir / "report.json")
    write_text(_report_text(manifest), output_dir / "report.txt")
    return manifest
