from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PipelineResult(BaseModel):
    """Final aggregated output. Invalid frames never pollute these stats."""

    model_config = ConfigDict(extra="forbid")

    video_path: str
    total_frames_seen: int = Field(ge=0)
    frames_sampled: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    read_errors: int = Field(ge=0)
    duration_s: float = Field(ge=0)
    throughput_fps: float = Field(ge=0)
    mean_intersection_area: float = Field(ge=0)
    stable_polygon_wkt: Optional[str] = None
    stable_polygon_area: float = Field(default=0.0, ge=0)

    @property
    def invalid_ratio(self) -> float:
        if self.frames_sampled == 0:
            return 0.0
        return self.invalid_count / self.frames_sampled

    def write_json(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.model_dump(mode="json"), indent=2), encoding="utf-8")
