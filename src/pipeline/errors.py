from __future__ import annotations


class PipelineError(Exception):
    """Base for all video-pipeline failures."""


class ConfigError(PipelineError):
    """Bad / missing / unparsable configuration. Fail fast at load."""


class VideoOpenError(PipelineError):
    """Video source cannot be opened. Fatal — stop immediately."""


class StreamBrokenError(PipelineError):
    """Too many consecutive read failures. Fatal — stop immediately."""


class ReportingError(Exception):
    """Could not reach the reporting service. NOT a pipeline failure."""
