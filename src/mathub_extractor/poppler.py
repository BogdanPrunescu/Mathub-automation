from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from .normalize import normalize_poppler_text
from .quality import assess_text

_XHTML_NS = "http://www.w3.org/1999/xhtml"
_NS = {"x": _XHTML_NS}
_PRIVATE_CONTROL_BASE = 0xE000


@dataclass(frozen=True)
class PopplerInfo:
    executable: Path
    version: str


def find_pdftotext(explicit_path: Path | None = None) -> PopplerInfo | None:
    candidate: str | None
    if explicit_path is not None:
        candidate = str(explicit_path.resolve())
    else:
        candidate = shutil.which("pdftotext")

    if not candidate:
        return None

    executable = Path(candidate)
    try:
        proc = subprocess.run(
            [str(executable), "-v"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    version_output = (proc.stderr or proc.stdout or "").strip().splitlines()
    version = version_output[0] if version_output else "unknown"
    return PopplerInfo(executable=executable, version=version)


def _escape_xml_illegal_controls(text: str) -> tuple[str, int]:
    out: list[str] = []
    count = 0
    for ch in text:
        code = ord(ch)
        if code < 32 and ch not in "\t\n\r":
            out.append(chr(_PRIVATE_CONTROL_BASE + code))
            count += 1
        else:
            out.append(ch)
    return "".join(out), count


def _restore_word(text: str) -> tuple[str, list[str]]:
    unresolved_codes: list[str] = []
    chars: list[str] = []
    for ch in text:
        code = ord(ch)
        if _PRIVATE_CONTROL_BASE <= code < _PRIVATE_CONTROL_BASE + 32:
            original = code - _PRIVATE_CONTROL_BASE
            unresolved_codes.append(f"U+{original:04X}")
            chars.append("\ufffd")
        else:
            chars.append(ch)
    return normalize_poppler_text("".join(chars)), unresolved_codes


def _bbox(element: ET.Element) -> list[float]:
    return [
        round(float(element.attrib["xMin"]), 3),
        round(float(element.attrib["yMin"]), 3),
        round(float(element.attrib["xMax"]), 3),
        round(float(element.attrib["yMax"]), 3),
    ]


def _page_text(blocks: list[dict]) -> str:
    block_texts: list[str] = []
    for block in blocks:
        line_texts: list[str] = []
        for line in block["lines"]:
            line_texts.append(" ".join(span["text"] for span in line["spans"]))
        block_texts.append("\n".join(line_texts))
    return "\n\n".join(block_texts)


def extract_poppler_pages(
    pdf_path: Path,
    info: PopplerInfo,
) -> tuple[list[dict], dict]:
    with tempfile.TemporaryDirectory(prefix="mathub-poppler-") as tmp_dir:
        xml_path = Path(tmp_dir) / "document.xhtml"
        proc = subprocess.run(
            [
                str(info.executable),
                "-bbox-layout",
                "-enc",
                "UTF-8",
                str(pdf_path),
                str(xml_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "pdftotext failed with exit code "
                f"{proc.returncode}: {(proc.stderr or proc.stdout).strip()}"
            )

        raw_xml = xml_path.read_text(encoding="utf-8", errors="replace")
        safe_xml, illegal_xml_controls = _escape_xml_illegal_controls(raw_xml)
        root = ET.fromstring(safe_xml)

    pages_out: list[dict] = []
    unresolved_total = 0

    for page_index, page_el in enumerate(root.findall(".//x:page", _NS)):
        page_id = f"p{page_index + 1:04d}"
        blocks_out: list[dict] = []
        block_index = 0

        for block_el in page_el.findall(".//x:block", _NS):
            block_id = f"{page_id}-b{block_index + 1:04d}"
            lines_out: list[dict] = []
            for line_index, line_el in enumerate(block_el.findall("./x:line", _NS)):
                spans_out: list[dict] = []
                for span_index, word_el in enumerate(line_el.findall("./x:word", _NS)):
                    raw_word = word_el.text or ""
                    text, unresolved_codes = _restore_word(raw_word)
                    unresolved_total += len(unresolved_codes)
                    span_out = {
                        "id": f"{block_id}-l{line_index + 1:03d}-s{span_index + 1:03d}",
                        "index": span_index,
                        "text": text,
                        "bbox": _bbox(word_el),
                        "extraction_method": "POPPLER_PDFTOTEXT",
                        "extraction_confidence": (
                            "REQUIRES_VISUAL_CHECK" if unresolved_codes else "HIGH"
                        ),
                    }
                    if unresolved_codes:
                        span_out["unresolved_source_codes"] = unresolved_codes
                    spans_out.append(span_out)

                lines_out.append(
                    {
                        "id": f"{block_id}-l{line_index + 1:03d}",
                        "index": line_index,
                        "bbox": _bbox(line_el),
                        "spans": spans_out,
                    }
                )

            blocks_out.append(
                {
                    "id": block_id,
                    "type": "text",
                    "raw_order_index": block_index,
                    "reading_order_index": block_index,
                    "bbox": _bbox(block_el),
                    "lines": lines_out,
                }
            )
            block_index += 1

        text = _page_text(blocks_out)
        quality = assess_text(text)
        pages_out.append(
            {
                "page_index": page_index,
                "blocks": blocks_out,
                "text": text,
                "quality": quality.to_dict(),
            }
        )

    diagnostics = {
        "backend": "pdftotext",
        "version": info.version,
        "illegal_xml_controls_preserved_as_unresolved": illegal_xml_controls,
        "unresolved_glyph_count": unresolved_total,
    }
    return pages_out, diagnostics
