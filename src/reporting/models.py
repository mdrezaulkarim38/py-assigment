from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    state: Literal["running", "succeeded", "failed"] = "running"
    processed_frames: int = Field(ge=0)
    total_frames: Optional[int] = Field(default=None, ge=0)
    progress_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    message: Optional[str] = None


class JobEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    event_type: Literal["started", "progress", "completed", "failed"] = "started"
    message: str = Field(min_length=1)
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
