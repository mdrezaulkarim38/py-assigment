import numpy as np

from src.config import AppConfig
from src.detectors.green_threshold import GreenThresholdDetector, create_detector
from src.pipeline.analyzer import FieldBoundaryAnalyzer


def _green_frame(w=320, h=200):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = (34, 139, 34)  
    return img


def test_green_frame_detects():
    det = GreenThresholdDetector(min_area=100)
    assert det.detect(_green_frame()) is not None


def test_black_frame_returns_none():
    det = GreenThresholdDetector(min_area=100)
    black = np.zeros((200, 320, 3), dtype=np.uint8)
    assert det.detect(black) is None


def test_small_noise_filtered():
    det = GreenThresholdDetector(min_area=1000)
    import cv2
    img = np.zeros((200, 320, 3), dtype=np.uint8)
    img[:] = (34, 139, 34)
    assert det.detect(np.zeros((0, 0, 3), dtype=np.uint8)) is None
    assert det.detect(None) is None  


def test_factory_legacy_alias():
    assert isinstance(create_detector("sam_mask_v1", 100), GreenThresholdDetector)
    assert isinstance(create_detector("green_threshold", 100), GreenThresholdDetector)


def test_pipeline_handles_missing_video():
    import pytest
    from src.pipeline.errors import VideoOpenError
    cfg = AppConfig.model_validate({
        "video_path": "definitely-not-here.mp4",
        "sample_stride": 5,
        "field_detector": {"type": "green_threshold", "sport": "football", "min_area": 100},
        "crop_search": {"aspect_ratio": "16:9", "padding_px": 0},
        "reporting": {"enabled": False, "base_url": "http://x:5000", "job_id": "j"},
    })
    analyzer = FieldBoundaryAnalyzer(cfg, GreenThresholdDetector(min_area=100))
    with pytest.raises(VideoOpenError):
        analyzer.process_video()


def test_sampling_reduces_work(tmp_path):
    """Same video, larger stride -> fewer sampled frames (Part 2)."""
    import cv2
    vid = str(tmp_path / "tiny.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(vid, fourcc, 30, (160, 100))
    frame = _green_frame(160, 100)
    for _ in range(60):
        out.write(frame)
    out.release()

    def run(stride):
        cfg = AppConfig.model_validate({
            "video_path": vid,
            "sample_stride": stride,
            "field_detector": {"type": "green_threshold", "sport": "football", "min_area": 100},
            "crop_search": {"aspect_ratio": "16:9", "padding_px": 0},
            "reporting": {"enabled": False, "base_url": "http://x:5000", "job_id": "j"},
        })
        return FieldBoundaryAnalyzer(cfg, GreenThresholdDetector(min_area=100)).process_video()

    r1 = run(1)
    r5 = run(5)
    assert r1.frames_sampled == 60
    assert r5.frames_sampled <= 13
    assert r5.valid_count > 0
    assert r5.invalid_count == 0  