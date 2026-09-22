from __future__ import annotations

import logging
from typing import Optional

import requests

from src.config import ReportingConfig
from src.pipeline.errors import ReportingError
from src.reporting.models import JobEvent, JobProgress

log = logging.getLogger("reporter")


class ReportingClient:
    def __init__(self, config: ReportingConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.config.enabled)

    def _post(self, path: str, payload: JobProgress | JobEvent) -> None:
        if not self.enabled:
            log.debug("Reporting disabled; skipping POST %s", path)
            return
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.post(
                url,
                json=payload.model_dump(mode="json"),
                timeout=self.config.timeout_s,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ReportingError(f"POST {url} failed: {e}") from e

    def report_progress(self, payload: JobProgress) -> None:
        self._post("/api/v1/jobs/progress", payload)

    def report_event(self, payload: JobEvent) -> None:
        self._post("/api/v1/jobs/events", payload)

    # Convenience builders so callers never hand-assemble dicts.
    def progress(
        self,
        processed_frames: int,
        total_frames: Optional[int] = None,
        state: str = "running",
        message: Optional[str] = None,
    ) -> None:
        pct: Optional[float] = None
        if total_frames:
            pct = round(100.0 * processed_frames / max(1, total_frames), 2)
        self.report_progress(
            JobProgress(
                job_id=self.config.job_id,
                state=state,  # type: ignore[arg-type]
                processed_frames=processed_frames,
                total_frames=total_frames,
                progress_pct=pct,
                message=message,
            )
        )

    def event(self, event_type: str, message: str, details: Optional[dict] = None) -> None:
        self.report_event(
            JobEvent(
                job_id=self.config.job_id,
                event_type=event_type,  # type: ignore[arg-type]
                message=message,
                details=details,
            )
        )
