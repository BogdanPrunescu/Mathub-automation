from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class LineRecord:
    page_id: str
    pdf_page_number: int
    page_index: int
    block_id: str
    line_id: str
    block_index: int
    line_index: int
    text: str
    bbox: list[float] | None
    page_width: float
    page_height: float
    page_quality: str
    backend: str

    @property
    def y0(self) -> float:
        return float(self.bbox[1]) if self.bbox else 0.0

    @property
    def y1(self) -> float:
        return float(self.bbox[3]) if self.bbox else 0.0

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def top_fraction(self) -> float:
        if self.page_height <= 0:
            return 1.0
        return self.y0 / self.page_height

    def source_ref(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "pdf_page_number": self.pdf_page_number,
            "block_id": self.block_id,
            "line_id": self.line_id,
            "text": self.text,
            "bbox": self.bbox,
        }


@dataclass
class Candidate:
    line: LineRecord
    title_score: float
    heading_score: float
    toc_penalty: float
    quality_penalty: float
    toc_support: float
    final_score: float
    match_reasons: list[str]
    section_number: tuple[int, ...] | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["line"] = self.line.source_ref()
        payload["section_number"] = (
            ".".join(str(x) for x in self.section_number)
            if self.section_number
            else None
        )
        for key in (
            "title_score",
            "heading_score",
            "toc_penalty",
            "quality_penalty",
            "toc_support",
            "final_score",
        ):
            payload[key] = round(float(payload[key]), 4)
        return payload
