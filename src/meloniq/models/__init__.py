"""
Data models for analysis results using Pydantic.
All models include confidence scores and explanations.
"""

from .results import (
    AnalysisResult,
    TempoResult,
    TempoCandidate,
    TempoSegment,
    KeyResult,
    KeyCandidate,
    KeySegment,
    MeterResult,
    StructureSegment,
    StructureResult,
    ChordSegment,
    ChordResult,
    AudioStats,
    TrackInfo,
    CountIn,
)

__all__ = [
    "AnalysisResult",
    "TempoResult",
    "TempoCandidate",
    "TempoSegment",
    "KeyResult",
    "KeyCandidate",
    "KeySegment",
    "MeterResult",
    "StructureSegment",
    "StructureResult",
    "ChordSegment",
    "ChordResult",
    "AudioStats",
    "TrackInfo",
    "CountIn",
]
