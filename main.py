from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import AppConfig  # noqa: E402
from src.detectors.green_threshold import create_detector  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402
from src.pipeline.analyzer import FieldBoundaryAnalyzer  # noqa: E402
from src.pipeline.errors import ConfigError, PipelineError, ReportingError  # noqa: E402
from src.reporting.client import ReportingClient  # noqa: E402

log = logging.getLogger("main")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Pitch boundary & crop engine (production pipeline)")
    p.add_argument("--config", default="config.json", help="Path to JSON config file")
    p.add_argument("--video", default=None, help="Override video_path from config")
    p.add_argument("--generate-feed", action="store_true",
                   help="Generate the synthetic feed if missing (dev convenience)")
    return p.parse_args(argv)


def apply_env_overrides(cfg: AppConfig) -> AppConfig:
    """Docker-friendly overrides. Explicit env wins; all re-validated."""
    data = cfg.model_dump(mode="python")
    rep = data.get("reporting", {})
    if os.getenv("MOCK_API_URL"):
        rep["base_url"] = os.environ["MOCK_API_URL"]
    if os.getenv("JOB_ID"):
        rep["job_id"] = os.environ["JOB_ID"]
    if os.getenv("VIDEO_PATH"):
        data["video_path"] = os.environ["VIDEO_PATH"]
    data["reporting"] = rep
    return AppConfig.model_validate(data)


def ensure_input_video(path: str, generate: bool) -> None:
    import os as _os
    if _os.path.exists(path):
        return
    if not generate:
        raise PipelineError(
            f"Video not found: {path}. Pass --generate-feed (dev) or mount the feed."
        )
    from synthetic_generator import generate_synthetic_video
    log.info("Input %s missing; generating synthetic feed...", path)
    generate_synthetic_video(path)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        cfg = AppConfig.load_from_file(args.config)
        cfg = apply_env_overrides(cfg)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"CONFIG ERROR: invalid configuration: {e}", file=sys.stderr)
        return 2

    setup_logging(cfg.log_level)
    if args.video:
        try:
            cfg = AppConfig.model_validate({**cfg.model_dump(mode="python"), "video_path": args.video})
        except Exception as e:
            print(f"CONFIG ERROR: invalid --video override: {e}", file=sys.stderr)
            return 2

    log.info("Loaded config from %s (job_id=%s video=%s stride=%d)",
             args.config, cfg.reporting.job_id, cfg.video_path, cfg.sample_stride)
    try:
        detector = create_detector(cfg.field_detector.type, cfg.field_detector.min_area)
    except ValueError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        return 2

    reporter = ReportingClient(cfg.reporting)

    try:
        reporter.event("started", f"Pipeline started for {cfg.video_path}",
                       {"sample_stride": cfg.sample_stride})
    except ReportingError as e:
        log.warning("Reporting 'started' event failed (pipeline continues): %s", e)

    def on_progress(sampled: int, seen: int) -> None:
        try:
            reporter.progress(processed_frames=sampled, total_frames=None,
                              message=f"sampled={sampled} seen={seen}")
        except ReportingError as e:
            log.warning("Progress report failed (pipeline continues): %s", e)

    analyzer = FieldBoundaryAnalyzer(cfg, detector, progress_callback=on_progress)

    try:
        ensure_input_video(cfg.video_path, generate=args.generate_feed)
        result = analyzer.process_video()
    except PipelineError as e:
        log.error("Pipeline FAILED: %s", e, exc_info=True)
        try:
            reporter.event("failed", f"Pipeline failed: {e}", {"video": cfg.video_path})
        except ReportingError as re:
            log.warning("Could not report pipeline failure (distinct issue): %s", re)
        return 1
    except KeyboardInterrupt:
        log.error("Interrupted by operator.")
        return 1
    except Exception as e:
        log.error("Unexpected fatal error: %r", e, exc_info=True)
        try:
            reporter.event("failed", f"Unexpected error: {e!r}")
        except ReportingError as re:
            log.warning("Could not report failure: %s", re)
        return 1

    try:
        result.write_json(cfg.output_path)
        log.info("Wrote result JSON to %s", cfg.output_path)
    except OSError as e:
        log.error("Could not write output %s: %s", cfg.output_path, e)
        return 1

    try:
        reporter.progress(processed_frames=result.frames_sampled,
                          total_frames=result.total_frames_seen,
                          state="succeeded", message="Pipeline succeeded")
        reporter.event("completed",
                       f"Pipeline succeeded: {result.valid_count}/{result.frames_sampled} valid",
                       result.model_dump(mode="json"))
    except ReportingError as e:
        log.warning("Pipeline succeeded but final report failed: %s", e)
    log.info("Pipeline SUCCEEDED: %d valid / %d sampled (%.2fs).",
             result.valid_count, result.frames_sampled, result.duration_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
