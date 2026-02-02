"""
Pydantic models for all analysis results.
Each result includes confidence scores and explanations for transparency.
"""

from typing import Optional
from pydantic import BaseModel, Field


class TempoCandidate(BaseModel):
    """A candidate BPM with confidence score."""
    bpm: float = Field(..., description="Tempo in BPM")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")


class TempoSegment(BaseModel):
    """A segment of audio with consistent tempo."""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    bpm: float = Field(..., description="Tempo in BPM")
    confidence: float = Field(..., ge=0, le=1)


class CountIn(BaseModel):
    """Count-in suggestion for musicians."""
    bars: int = Field(default=1, description="Number of bars for count-in")
    click_bpm: float = Field(..., description="BPM for click track")
    meter: str = Field(default="4/4", description="Time signature")
    beats_per_bar: int = Field(default=4)


class TempoResult(BaseModel):
    """Complete tempo analysis result."""
    global_bpm: float = Field(..., description="Primary BPM estimate")
    confidence: float = Field(..., ge=0, le=1, description="Confidence in global BPM")
    explanation: str = Field(..., description="Why this tempo was detected")
    needs_confirmation: bool = Field(default=False, description="True if confidence is low")
    
    candidates: list[TempoCandidate] = Field(
        default_factory=list,
        description="Alternative BPM candidates (half-time, double-time)"
    )
    segments: list[TempoSegment] = Field(
        default_factory=list,
        description="Tempo segments if tempo varies"
    )
    beats: list[float] = Field(
        default_factory=list,
        description="Beat timestamps in seconds"
    )
    downbeats: list[float] = Field(
        default_factory=list,
        description="Downbeat (bar start) timestamps"
    )
    count_in: Optional[CountIn] = Field(
        default=None,
        description="Suggested count-in for playing along"
    )


class KeyCandidate(BaseModel):
    """A candidate key with confidence."""
    key: str = Field(..., description="Key name (e.g., 'A minor', 'C major')")
    confidence: float = Field(..., ge=0, le=1)


class KeySegment(BaseModel):
    """A segment with a specific key (for modulations)."""
    start: float
    end: float
    key: str
    confidence: float = Field(..., ge=0, le=1)


class KeyResult(BaseModel):
    """Complete key/tonality analysis result."""
    global_key: str = Field(..., description="Primary key estimate")
    confidence: float = Field(..., ge=0, le=1)
    explanation: str = Field(..., description="Why this key was detected")
    needs_confirmation: bool = Field(default=False)

    alternatives: list[KeyCandidate] = Field(
        default_factory=list,
        description="Alternative keys (relative major/minor)"
    )
    segments: list[KeySegment] = Field(
        default_factory=list,
        description="Key segments if modulations detected"
    )
    is_chromatic: bool = Field(
        default=False,
        description="True if highly chromatic/atonal"
    )
    vocal_detected: Optional[bool] = Field(
        default=None,
        description="True if vocals detected in audio (affects key detection strategy)"
    )


class MeterResult(BaseModel):
    """Time signature / meter analysis result."""
    value: str = Field(..., description="Time signature (e.g., '4/4', '3/4')")
    numerator: int = Field(..., description="Beats per bar")
    denominator: int = Field(default=4, description="Beat unit")
    confidence: float = Field(..., ge=0, le=1)
    explanation: str = Field(..., description="How meter was determined")
    needs_confirmation: bool = Field(default=False)
    fallback_used: bool = Field(
        default=False,
        description="True if defaulted to 4/4 due to low confidence"
    )


class StructureSegment(BaseModel):
    """A section of the song structure."""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    label: str = Field(..., description="Section label (Intro, Verse, Chorus, etc.)")
    confidence: float = Field(..., ge=0, le=1)
    similarity_to_previous: Optional[float] = Field(
        default=None,
        description="Similarity score to previous section"
    )


class StructureResult(BaseModel):
    """Complete song structure analysis."""
    segments: list[StructureSegment] = Field(default_factory=list)
    explanation: str = Field(
        default="",
        description="How structure was detected"
    )
    needs_confirmation: bool = Field(default=True)


class ChordSegment(BaseModel):
    """A chord segment."""
    start: float
    end: float
    chord: str = Field(..., description="Chord symbol (e.g., 'Am', 'C', 'G7')")
    confidence: float = Field(..., ge=0, le=1)


class ChordResult(BaseModel):
    """Chord progression analysis (optional, best-effort)."""
    enabled: bool = Field(default=False)
    warning: str = Field(
        default="Chord detection is approximate; verify by ear.",
        description="Disclaimer about accuracy"
    )
    segments: list[ChordSegment] = Field(default_factory=list)
    needs_confirmation: bool = Field(default=True)


class AudioStats(BaseModel):
    """Technical audio statistics useful for musicians."""
    lufs_integrated: float = Field(..., description="Integrated loudness in LUFS")
    lufs_short_term_max: float = Field(..., description="Max short-term loudness")
    peak_dbfs: float = Field(..., description="True peak level in dBFS")
    dynamic_range: float = Field(..., description="Dynamic range (crest factor) in dB")
    
    # Optional detailed curves
    brightness_curve: list[tuple[float, float]] = Field(
        default_factory=list,
        description="Spectral centroid over time [(time, brightness), ...]"
    )
    loudness_curve: list[tuple[float, float]] = Field(
        default_factory=list,
        description="Short-term loudness over time"
    )
    
    tuning_reference: float = Field(
        default=440.0,
        description="Estimated A4 tuning frequency (Hz)"
    )
    tuning_deviation_cents: float = Field(
        default=0.0,
        description="Deviation from 440Hz in cents"
    )


class TrackInfo(BaseModel):
    """Basic track information."""
    path: str
    filename: str
    duration: float = Field(..., description="Duration in seconds")
    sample_rate: int
    channels: int = Field(..., description="1=mono, 2=stereo")
    bit_depth: Optional[int] = None
    format: str = Field(default="unknown")


class AnalysisResult(BaseModel):
    """Complete analysis result for a track."""
    track: TrackInfo
    tempo: TempoResult
    key: KeyResult
    meter: MeterResult
    structure: StructureResult
    chords: Optional[ChordResult] = None
    audio_stats: AudioStats
    
    # Metadata
    analysis_version: str = Field(default="1.0.0")
    analysis_time_seconds: float = Field(default=0.0)
    
    def to_musician_summary(self) -> str:
        """Generate a human-readable summary for musicians."""
        lines = [
            f"=== Music Analysis Summary ===",
            f"File: {self.track.filename}",
            f"Duration: {self.track.duration:.1f}s ({self._format_duration(self.track.duration)})",
            f"",
            f"TEMPO: {self.tempo.global_bpm:.1f} BPM (confidence: {self.tempo.confidence:.0%})",
        ]
        
        if self.tempo.candidates:
            alts = [f"{c.bpm:.0f}" for c in self.tempo.candidates if c.bpm != self.tempo.global_bpm]
            if alts:
                lines.append(f"  Alternatives: {', '.join(alts)} BPM")
        
        lines.extend([
            f"",
            f"KEY: {self.key.global_key} (confidence: {self.key.confidence:.0%})",
        ])
        
        if self.key.alternatives:
            alts = [c.key for c in self.key.alternatives]
            lines.append(f"  Alternatives: {', '.join(alts)}")
        
        lines.extend([
            f"",
            f"METER: {self.meter.value} (confidence: {self.meter.confidence:.0%})",
            f"",
            f"LOUDNESS: {self.audio_stats.lufs_integrated:.1f} LUFS",
            f"PEAK: {self.audio_stats.peak_dbfs:.1f} dBFS",
            f"DYNAMIC RANGE: {self.audio_stats.dynamic_range:.1f} dB",
        ])
        
        if self.structure.segments:
            lines.extend([f"", f"STRUCTURE:"])
            for seg in self.structure.segments:
                lines.append(
                    f"  {self._format_time(seg.start)} - {self._format_time(seg.end)}: "
                    f"{seg.label} ({seg.confidence:.0%})"
                )
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        mins, secs = divmod(int(seconds), 60)
        return f"{mins}:{secs:02d}"
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        mins, secs = divmod(seconds, 60)
        return f"{int(mins)}:{secs:05.2f}"
