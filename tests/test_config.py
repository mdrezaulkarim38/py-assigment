import json

import pytest

from src.config import AppConfig
from src.pipeline.errors import ConfigError


def _base():
    return {
        "video_path": "vid.mp4",
        "sample_stride": 5,
        "field_detector": {"type": "green_threshold", "sport": "football", "min_area": 100},
        "crop_search": {"aspect_ratio": "16:9", "padding_px": 0},
        "reporting": {"enabled": False, "base_url": "http://x:5000", "job_id": "j1"},
    }


def test_valid_config_loads():
    cfg = AppConfig.model_validate(_base())
    assert cfg.sample_stride == 5


def test_unknown_key_rejected():
    bad = _base() | {"typo_field": 1}
    with pytest.raises(Exception):
        AppConfig.model_validate(bad)


def test_bad_stride_rejected():
    bad = _base() | {"sample_stride": 0}
    with pytest.raises(Exception):
        AppConfig.model_validate(bad)


def test_bad_url_rejected():
    bad = _base()
    bad["reporting"] = dict(bad["reporting"], base_url="not-a-url")
    with pytest.raises(Exception):
        AppConfig.model_validate(bad)


def test_bad_aspect_rejected():
    bad = _base()
    bad["crop_search"] = {"aspect_ratio": "wide", "padding_px": 0}
    with pytest.raises(Exception):
        AppConfig.model_validate(bad)


def test_missing_file_fails_fast(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        AppConfig.load_from_file(tmp_path / "nope.json")


def test_unparsable_file_fails_fast(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unparsable"):
        AppConfig.load_from_file(p)


def test_invalid_content_fails_fast(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"video_path": ""}), encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid configuration"):
        AppConfig.load_from_file(p)
