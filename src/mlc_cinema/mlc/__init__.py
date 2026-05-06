"""MLC parsing and timeline construction.

Only modules in this subpackage are allowed to interpret raw MLC NDJSON
records. Downstream consumers (scene, render, ui) work with the
parsed dataclasses and the ``MLCTimeline`` instead.
"""

from mlc_cinema.mlc.records import (
    MLCBody,
    MLCHeader,
    MLCParseResult,
    MLCState,
)
from mlc_cinema.mlc.reader import read_mlc_ndjson
from mlc_cinema.mlc.timeline import MLCTimeline, TimelineFrame, build_timeline

__all__ = [
    "MLCBody",
    "MLCHeader",
    "MLCParseResult",
    "MLCState",
    "MLCTimeline",
    "TimelineFrame",
    "build_timeline",
    "read_mlc_ndjson",
]
