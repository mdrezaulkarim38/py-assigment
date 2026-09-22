from __future__ import annotations

from typing import Optional, Protocol

import numpy as np
from shapely.geometry import Polygon

class FieldDetector(Protocol):
    def detect(self, frame: np.ndarray) -> Optional[Polygon]:
        ...