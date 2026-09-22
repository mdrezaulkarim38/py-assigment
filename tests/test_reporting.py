import pytest

from src.reporting.models import JobEvent, JobProgress


def test_progress_valid():
    p = JobProgress(job_id="j1", state="running", processed_frames=10, total_frames=100)
    assert p.job_id == "j1"


def test_progress_rejects_negative():
    with pytest.raises(Exception):
        JobProgress(job_id="j1", state="running", processed_frames=-1)


def test_progress_rejects_extra():
    with pytest.raises(Exception):
        JobProgress(job_id="j1", state="running", processed_frames=1, bogus=2)  # type: ignore[call-arg]


def test_event_requires_message():
    with pytest.raises(Exception):
        JobEvent(job_id="j1", event_type="started", message="")
