"""
Audio analysis modules for extracting musical features.

Each module provides:
- analyze() function for standalone use
- Confidence scores and explanations
- Fallback strategies when primary method fails
"""

from .tempo import TempoAnalyzer
from .key import KeyAnalyzer
from .meter import MeterAnalyzer
from .structure import StructureAnalyzer
from .loudness import LoudnessAnalyzer
from .chords import ChordAnalyzer
from .pipeline import AnalysisPipeline

__all__ = [
    "TempoAnalyzer",
    "KeyAnalyzer", 
    "MeterAnalyzer",
    "StructureAnalyzer",
    "LoudnessAnalyzer",
    "ChordAnalyzer",
    "AnalysisPipeline",
]
