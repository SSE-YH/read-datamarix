from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


STATUS_SUCCESS = "success"
STATUS_NOT_FOUND = "not_found"
STATUS_DECODE_FAILED = "decode_failed"
STATUS_ERROR = "error"

RUNTIME_STATUSES = {
    STATUS_SUCCESS,
    STATUS_NOT_FOUND,
    STATUS_DECODE_FAILED,
    STATUS_ERROR,
}


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_points(cls, points: Iterable[tuple[float, float]]) -> "BBox | None":
        coords = list(points)
        if not coords:
            return None

        xs = [coord[0] for coord in coords]
        ys = [coord[1] for coord in coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x
        height = max_y - min_y
        if width <= 0 or height <= 0:
            return None

        return cls(
            x=int(round(min_x)),
            y=int(round(min_y)),
            width=int(round(width)),
            height=int(round(height)),
        )

    def corners(self) -> tuple[tuple[float, float], ...]:
        x1 = float(self.x)
        y1 = float(self.y)
        x2 = float(self.x + self.width)
        y2 = float(self.y + self.height)
        return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))

    def clamped(self, image_width: int, image_height: int) -> "BBox | None":
        x1 = max(0, min(image_width, self.x))
        y1 = max(0, min(image_height, self.y))
        x2 = max(0, min(image_width, self.x + self.width))
        y2 = max(0, min(image_height, self.y + self.height))

        width = x2 - x1
        height = y2 - y1
        if width <= 0 or height <= 0:
            return None

        return BBox(x=x1, y=y1, width=width, height=height)

    def intersection_over_union(self, other: "BBox") -> float:
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.width, other.x + other.width)
        bottom = min(self.y + self.height, other.y + other.height)

        intersection_width = max(0, right - left)
        intersection_height = max(0, bottom - top)
        intersection_area = intersection_width * intersection_height
        if intersection_area == 0:
            return 0.0

        self_area = self.width * self.height
        other_area = other.width * other.height
        union_area = self_area + other_area - intersection_area
        if union_area <= 0:
            return 0.0
        return intersection_area / union_area

    def is_near(self, other: "BBox", tolerance: int = 12) -> bool:
        return (
            abs(self.x - other.x) <= tolerance
            and abs(self.y - other.y) <= tolerance
            and abs(self.width - other.width) <= tolerance
            and abs(self.height - other.height) <= tolerance
        )


@dataclass(frozen=True)
class BarcodeResult:
    source_filename: str
    status: str
    barcode_index: int | None = None
    barcode_type: str = ""
    decoded_text: str = ""
    confidence: float | None = None
    bbox: BBox | None = None
    error_message: str = ""
    decoder_name: str = ""
    preprocess_variant: str = ""

    def __post_init__(self) -> None:
        if self.status not in RUNTIME_STATUSES:
            raise ValueError(f"unsupported barcode result status: {self.status}")
