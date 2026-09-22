from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from shapely.geometry import Polygon


class GreenThresholdDetector:
    def __init__(self, min_area: float = 1000.0) -> None:
        if min_area <= 0:
            raise ValueError("min_area must be > 0")
        self.min_area = float(min_area)
        self._lower_green = np.array([35, 40, 40], dtype=np.uint8)
        self._upper_green = np.array([85, 255, 255], dtype=np.uint8)

    def detect(self, frame: np.ndarray) -> Optional[Polygon]:
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        if frame.ndim != 3 or frame.shape[2] != 3:
            return None
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self._lower_green, self._upper_green)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < self.min_area:
            return None
        pts = largest.reshape(-1, 2)
        if len(pts) < 3:
            return None
        poly = Polygon(pts)
        if not poly.is_valid or poly.area < self.min_area:
            return None
        return poly


def create_detector(detector_type: str, min_area: float):
    """Factory: the only place that knows concrete detector classes."""
    normalized = (detector_type or "").strip().lower()
    if normalized in ("green_threshold", "sam_mask_v1"):
        return GreenThresholdDetector(min_area=min_area)
    raise ValueError(
        f"Unknown field_detector.type={detector_type!r}. "
        "Expected 'green_threshold' (or legacy 'sam_mask_v1')."
    )
