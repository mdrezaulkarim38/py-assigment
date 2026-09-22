from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import cv2
from shapely.geometry import Polygon

from src.config import AppConfig
from src.detectors.base import FieldDetector
from src.pipeline.errors import StreamBrokenError, VideoOpenError
from src.pipeline.results import PipelineResult

log = logging.getLogger("pitch_pipeline")

MAX_CONSECUTIVE_READ_FAILURES = 10
MAX_STORED_POLYGONS = 10000


class FieldBoundaryAnalyzer:
    def __init__(
        self,
        config: AppConfig,
        detector: FieldDetector,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self.config = config
        self.detector = detector
        self.progress_callback = progress_callback
        self._outer_boundary: Optional[Polygon] = None

    def _outer_for_frame(self, width: int, height: int) -> Polygon:
        # Built ONCE per video (cached), not per frame like prototype.
        if self._outer_boundary is None:
            self._outer_boundary = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        return self._outer_boundary

    def process_video(self, video_path: Optional[str] = None) -> PipelineResult:
        path = video_path or self.config.video_path
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise VideoOpenError(f"Could not open video stream: {path}")

        stride = max(1, self.config.sample_stride)
        max_frames = self.config.max_frames
        progress_every = self.config.reporting.progress_every_n_frames

        total_seen = 0
        sampled = 0
        valid = 0
        invalid = 0
        read_errors = 0
        consecutive_failures = 0
        areas: list[float] = []
        kept: list[tuple[int, Polygon, float]] = []
        frame_width = frame_height = 0

        start = time.perf_counter()
        try:
            idx = 0
            while True:
                if max_frames is not None and total_seen >= max_frames:
                    log.info("Reached max_frames=%d, stopping.", max_frames)
                    break
                # grab() is cheap (no decode); only sampled frames pay decode cost.
                grabbed = cap.grab()
                if not grabbed:
                    break
                total_seen += 1
                idx += 1
                if (idx - 1) % stride != 0:
                    continue
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    read_errors += 1
                    consecutive_failures += 1
                    log.warning("Frame %d: decode failed (%d consecutive).", idx, consecutive_failures)
                    if consecutive_failures >= MAX_CONSECUTIVE_READ_FAILURES:
                        raise StreamBrokenError(
                            f"Stream broken: {consecutive_failures} consecutive read failures at frame {idx}."
                        )
                    continue
                consecutive_failures = 0
                sampled += 1
                h, w = frame.shape[:2]
                if frame_width == 0:
                    frame_width, frame_height = w, h
                try:
                    poly = self.detector.detect(frame)
                except Exception as e:  # non-fatal: count + continue, never silent
                    invalid += 1
                    read_errors += 1
                    log.warning("Frame %d: detector raised %r; skipping.", idx, e)
                    continue
                if poly is None or not poly.is_valid:
                    invalid += 1
                    if invalid <= 5 or invalid % 100 == 0:
                        log.debug("Frame %d: no/invalid boundary (invalid total=%d).", idx, invalid)
                    continue
                try:
                    outer = self._outer_for_frame(w, h)
                    area = float(poly.intersection(outer).area)
                except Exception as e:
                    invalid += 1
                    log.warning("Frame %d: geometry failed %r; skipping.", idx, e)
                    continue
                if area <= 0:
                    invalid += 1
                    continue
                valid += 1
                areas.append(area)
                if len(kept) < MAX_STORED_POLYGONS:
                    kept.append((idx, poly, area))

                if sampled % progress_every == 0:
                    log.info(
                        "Progress: seen=%d sampled=%d valid=%d invalid=%d",
                        total_seen, sampled, valid, invalid,
                    )
                    if self.progress_callback is not None:
                        try:
                            self.progress_callback(sampled, total_seen)
                        except Exception as e:
                            # Callback (reporting) failures must not kill the pipeline.
                            log.warning("Progress callback failed (non-fatal): %r", e)
        finally:
            cap.release()

        duration = max(0.0, time.perf_counter() - start)
        mean_area = sum(areas) / len(areas) if areas else 0.0
        stable_wkt: Optional[str] = None
        stable_area = 0.0
        if kept:
            # Stable output = median-area polygon (robust to noise spikes
            # and close-ups), not the mean of garbage + good frames.
            ordered = sorted(kept, key=lambda t: t[2])
            _, stable_poly, stable_area = ordered[len(ordered) // 2]
            try:
                stable_wkt = stable_poly.wkt
            except Exception:
                stable_wkt = None

        result = PipelineResult(
            video_path=path,
            total_frames_seen=total_seen,
            frames_sampled=sampled,
            valid_count=valid,
            invalid_count=invalid,
            read_errors=read_errors,
            duration_s=duration,
            throughput_fps=(sampled / duration) if duration > 0 else 0.0,
            mean_intersection_area=mean_area,
            stable_polygon_wkt=stable_wkt,
            stable_polygon_area=float(stable_area),
        )
        log.info(
            "Done: seen=%d sampled=%d valid=%d invalid=%d read_errors=%d "
            "duration=%.2fs throughput=%.1f fps mean_area=%.1f",
            result.total_frames_seen, result.frames_sampled, result.valid_count,
            result.invalid_count, result.read_errors, result.duration_s,
            result.throughput_fps, result.mean_intersection_area,
        )
        if result.frames_sampled == 0:
            log.warning("No frames were sampled — check sample_stride/max_frames.")
        elif result.invalid_ratio > 0.5:
            log.warning("High invalid ratio %.1f%% — feed may be degraded.",
                        result.invalid_ratio * 100)
        return result
