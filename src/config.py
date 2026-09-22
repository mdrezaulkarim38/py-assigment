from __future__ import annotations
import json 
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

class FieldDetectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["green_threshold", "sam_mask_v1"] = "green_threshold"
    sport: str = Field(default="football", min_length=1)
    min_area: float = Field(default=1000.0, gt=0)


class CropSearchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aspect_ratio: str = Field(default="16:9", pattern=r"^\d+:\d+$")
    padding_px: int = Field(default=20, ge=0)

    def aspect_tuple(self) -> tuple[int, int]:
        w, h = self.aspect_ratio.split(":")
        return int(w), int(h)



class ReportingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    base_url: str = "http://127.0.0.1:5000"
    job_id: str = Field(default="local-dev-job", min_length=1)
    progress_every_n_frames: int = Field(default=30, ge=1)
    timeout_s: float = Field(default=2.0, gt=0, le=60)

    @field_validator("base_url")
    @classmethod
    def _must_be_http(cls, v: str) -> str:
        v = v.rstrip("/")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v
   

class AppConfig(BaseModel):
    """Top-level pipeline configuration. Unknown keys are rejected."""

    model_config = ConfigDict(extra="forbid")

    video_path: str = Field(min_length=1)
    sample_stride: int = Field(default=15, ge=1)
    max_frames: Optional[int] = Field(default=None, gt=0)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    field_detector: FieldDetectorConfig = Field(default_factory=FieldDetectorConfig)
    crop_search: CropSearchConfig = Field(default_factory=CropSearchConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    output_path: str = "output/result.json"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug_mode: bool = False

    @field_validator("video_path", "output_path")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @classmethod
    def load_from_file(cls, path: str | Path) -> "AppConfig":
        """Load + validate config. Raises ConfigLoadError on ANY problem."""
        from src.pipeline.errors import ConfigError

        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"Config file not found: {p} (pass --config <path>)")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ConfigError(f"Unparsable config file {p}: {e}") from e
        except OSError as e:
            raise ConfigError(f"Cannot read config file {p}: {e}") from e
        try:
            return cls.model_validate(raw)
        except Exception as e:
            raise ConfigError(f"Invalid configuration in {p}:\n{e}") from e