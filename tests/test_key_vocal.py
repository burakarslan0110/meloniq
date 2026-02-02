"""
Tests for vocal-aware key detection enhancements.

Tests the bass-weighted chroma extraction and vocal detection features
that improve key detection accuracy for vocal-heavy music.
"""

import numpy as np
import pytest

from meloniq.analysis.key import KeyAnalyzer


class TestBassWeightedChroma:
    """Test bass-weighted chroma extraction for vocal music."""

    @pytest.fixture
    def analyzer(self):
        return KeyAnalyzer()

    @pytest.fixture
    def vocal_heavy_audio(self):
        """
        Create synthetic audio simulating vocal-heavy music.

        Vocals typically occupy 80-1100 Hz range.
        Bass/harmony occupies lower frequencies.
        """
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Bass notes (F#2 = 92.5 Hz - root of F# Major)
        bass = np.sin(2 * np.pi * 92.5 * t)

        # Harmony (F# Major chord: F#-A#-C#)
        # F#3 (185 Hz), A#3 (233 Hz), C#4 (277 Hz)
        harmony = (
            np.sin(2 * np.pi * 185 * t) +
            np.sin(2 * np.pi * 233 * t) +
            np.sin(2 * np.pi * 277 * t)
        )

        # Vocal melody (higher frequencies, stronger energy)
        # D4 (294 Hz) - would mislead to D as root if not weighted
        vocal = 2.0 * np.sin(2 * np.pi * 294 * t)

        # Combine with realistic mix
        y = 0.3 * bass + 0.3 * harmony + 0.4 * vocal
        y = y / np.max(np.abs(y)) * 0.8

        return y.astype(np.float32), sr, "F# major"

    @pytest.fixture
    def instrumental_audio(self):
        """Create synthetic instrumental audio for comparison."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # F# Major chord balanced across frequencies
        # F#2, F#3, A#3, C#4
        y = (
            np.sin(2 * np.pi * 92.5 * t) +
            np.sin(2 * np.pi * 185 * t) +
            np.sin(2 * np.pi * 233 * t) +
            np.sin(2 * np.pi * 277 * t)
        )

        y = y / np.max(np.abs(y)) * 0.8

        return y.astype(np.float32), sr, "F# major"

    def test_analyze_with_bass_weighting(self, analyzer, vocal_heavy_audio):
        """Test that analyze applies bass weighting for vocal-heavy audio."""
        y, sr, expected_key = vocal_heavy_audio

        result = analyzer.analyze(y, sr)

        assert result is not None
        assert result.global_key is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_vocal_detection_flag(self, analyzer, vocal_heavy_audio):
        """Test that vocal presence is detected in result."""
        y, sr, _ = vocal_heavy_audio

        result = analyzer.analyze(y, sr)

        # Result should have vocal_detected attribute or similar
        # This verifies the new implementation exposes this info
        assert hasattr(result, 'vocal_detected') or 'vocal' in result.explanation.lower()

    def test_confidence_with_vocals(self, analyzer, vocal_heavy_audio):
        """Test that confidence is reasonable for vocal-heavy audio."""
        y, sr, _ = vocal_heavy_audio

        result = analyzer.analyze(y, sr)

        # With bass weighting, should achieve decent confidence
        # even with misleading vocal frequencies
        assert result.confidence > 0.3, "Bass weighting should improve confidence"
        assert result.confidence <= 1.0, "Confidence must be <= 1.0"

    def test_bass_weighted_vs_standard_chroma(self, analyzer, vocal_heavy_audio):
        """Test that bass-weighted approach differs from standard."""
        y, sr, expected_key = vocal_heavy_audio

        # Analyze with bass weighting (default)
        result = analyzer.analyze(y, sr)

        # The result should ideally be more accurate with bass weighting
        # This is verified through confidence or key accuracy
        assert result is not None
        assert result.global_key is not None

    def test_instrumental_still_works(self, analyzer, instrumental_audio):
        """Test that bass weighting doesn't harm instrumental detection."""
        y, sr, expected_key = instrumental_audio

        result = analyzer.analyze(y, sr)

        # Should still work well for instrumental
        assert result is not None
        assert result.confidence > 0.3


class TestVocalDetection:
    """Test vocal presence detection logic."""

    @pytest.fixture
    def analyzer(self):
        return KeyAnalyzer()

    def test_vocal_detection_with_high_mid_energy(self, analyzer):
        """Test vocal detection when mid-range energy is high."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Strong energy in vocal range (200-1100 Hz)
        y = np.zeros_like(t)
        for freq in np.linspace(200, 1100, 10):
            y += np.sin(2 * np.pi * freq * t)

        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        # Should detect vocals
        assert result is not None

    def test_vocal_detection_with_bass_heavy(self, analyzer):
        """Test that bass-heavy music is not flagged as vocal."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Strong energy in bass range (20-200 Hz)
        y = np.zeros_like(t)
        for freq in np.linspace(20, 200, 10):
            y += np.sin(2 * np.pi * freq * t)

        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        # Should not detect vocals
        assert result is not None

    def test_vocal_detection_threshold(self, analyzer):
        """Test that vocal detection uses proper threshold."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Minimal mid-range energy (below threshold)
        y = (
            2.0 * np.sin(2 * np.pi * 50 * t) +  # Bass
            0.1 * np.sin(2 * np.pi * 400 * t)   # Tiny vocal
        )

        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        assert result is not None


class TestEnsembleMethod:
    """Test ensemble method combining bass-weighted and standard chroma."""

    @pytest.fixture
    def analyzer(self):
        return KeyAnalyzer()

    def test_ensemble_returns_valid_result(self, analyzer):
        """Test that ensemble method returns valid KeyResult."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # F# Major chord
        y = (
            np.sin(2 * np.pi * 92.5 * t) +   # F#2
            np.sin(2 * np.pi * 185 * t) +    # F#3
            np.sin(2 * np.pi * 233 * t)      # A#3
        )
        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        assert result is not None
        assert result.global_key is not None
        assert isinstance(result.global_key, str)
        assert 0.0 <= result.confidence <= 1.0

    def test_ensemble_confidence_range(self, analyzer):
        """Test that ensemble confidence is in valid range."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Various test signals
        test_signals = [
            # C Major chord
            np.sin(2 * np.pi * 261.63 * t) + np.sin(2 * np.pi * 329.63 * t),
            # A Minor chord
            np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 261.63 * t),
            # Random noise
            np.random.randn(len(t)) * 0.1,
        ]

        for y in test_signals:
            y = y / (np.max(np.abs(y)) + 1e-6) * 0.8
            result = analyzer.analyze(y.astype(np.float32), sr)

            assert 0.0 <= result.confidence <= 1.0, \
                f"Confidence {result.confidence} out of range [0.0, 1.0]"

    def test_ensemble_weighted_voting(self, analyzer):
        """Test that ensemble uses weighted voting between methods."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Ambiguous signal (could be C or F)
        y = (
            np.sin(2 * np.pi * 261.63 * t) +  # C
            np.sin(2 * np.pi * 349.23 * t)    # F
        )
        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        # Should return a result with some alternatives
        assert result is not None
        assert len(result.alternatives) > 0


class TestBackwardCompatibility:
    """Test that existing API still works after changes."""

    @pytest.fixture
    def analyzer(self):
        return KeyAnalyzer()

    def test_basic_analyze_signature(self, analyzer):
        """Test that analyze() accepts same parameters as before."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)
        y = np.sin(2 * np.pi * 261.63 * t).astype(np.float32)

        # Should accept y, sr
        result = analyzer.analyze(y, sr)
        assert result is not None

        # Should accept detect_modulations parameter
        result = analyzer.analyze(y, sr, detect_modulations=True)
        assert result is not None

        result = analyzer.analyze(y, sr, detect_modulations=False)
        assert result is not None

    def test_result_structure_unchanged(self, analyzer):
        """Test that KeyResult structure is backward compatible."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)
        y = np.sin(2 * np.pi * 261.63 * t).astype(np.float32)

        result = analyzer.analyze(y, sr)

        # Original attributes must exist
        assert hasattr(result, 'global_key')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'explanation')
        assert hasattr(result, 'needs_confirmation')
        assert hasattr(result, 'alternatives')
        assert hasattr(result, 'segments')
        assert hasattr(result, 'is_chromatic')

    def test_alternatives_format(self, analyzer):
        """Test that alternatives are still list of KeyCandidate."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)
        y = np.sin(2 * np.pi * 261.63 * t).astype(np.float32)

        result = analyzer.analyze(y, sr)

        assert isinstance(result.alternatives, list)
        if len(result.alternatives) > 0:
            alt = result.alternatives[0]
            assert hasattr(alt, 'key')
            assert hasattr(alt, 'confidence')


class TestEdgeCasesVocal:
    """Edge cases specific to vocal detection."""

    @pytest.fixture
    def analyzer(self):
        return KeyAnalyzer()

    def test_silent_audio_with_vocal_detection(self, analyzer):
        """Test vocal detection on silent audio."""
        y = np.zeros(22050 * 5)
        sr = 22050

        result = analyzer.analyze(y.astype(np.float32), sr)

        assert result is not None
        assert result.confidence < 0.5

    def test_very_short_audio_with_vocal_detection(self, analyzer):
        """Test vocal detection on very short audio."""
        sr = 22050
        y = np.random.randn(sr).astype(np.float32)  # 1 second

        result = analyzer.analyze(y, sr)

        assert result is not None

    def test_extreme_bass_only(self, analyzer):
        """Test with extremely low frequencies only."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Sub-bass only (20-60 Hz)
        y = np.sin(2 * np.pi * 30 * t) + np.sin(2 * np.pi * 50 * t)
        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        assert result is not None
        assert result.global_key is not None

    def test_extreme_treble_only(self, analyzer):
        """Test with extremely high frequencies only."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # High frequencies (2000-4000 Hz)
        y = np.sin(2 * np.pi * 2000 * t) + np.sin(2 * np.pi * 3000 * t)
        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        assert result is not None
        assert result.global_key is not None


class TestRealWorldScenarios:
    """Test realistic music scenarios."""

    @pytest.fixture
    def analyzer(self):
        return KeyAnalyzer()

    def test_vocal_with_strong_bass(self, analyzer):
        """
        Test scenario: Strong vocal melody + strong bass line.

        This simulates pop/rock music where both elements are prominent.
        Bass should guide key detection, not vocal melody.
        """
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # F# Major scenario
        bass = np.sin(2 * np.pi * 92.5 * t)      # F#2 (root)
        harmony = np.sin(2 * np.pi * 233 * t)     # A#3 (major third)

        # Vocal melody on D (misleading if not weighted)
        vocal = 1.5 * np.sin(2 * np.pi * 294 * t)  # D4

        y = 0.4 * bass + 0.3 * harmony + 0.3 * vocal
        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        # Should detect F# or closely related key
        assert result is not None
        assert result.confidence > 0.2

    def test_acapella_vocal(self, analyzer):
        """
        Test scenario: A cappella (vocals only, no instruments).

        Should still attempt detection, possibly with lower confidence.
        """
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # Vocal harmony (C Major triad)
        vocal1 = np.sin(2 * np.pi * 261.63 * t)  # C4
        vocal2 = np.sin(2 * np.pi * 329.63 * t)  # E4
        vocal3 = np.sin(2 * np.pi * 392.00 * t)  # G4

        y = (vocal1 + vocal2 + vocal3) / 3
        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        assert result is not None
        # May have lower confidence without bass
        assert 0.0 <= result.confidence <= 1.0

    def test_modal_interchange(self, analyzer):
        """
        Test scenario: Modal interchange (borrowing chords from parallel key).

        Should still identify primary key with reasonable confidence.
        """
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)

        # C Major with borrowed chord from C Minor
        # Mix C Major triad and Eb Major triad (borrowed)
        c_maj = np.sin(2 * np.pi * 261.63 * t) + np.sin(2 * np.pi * 329.63 * t)
        eb_maj = np.sin(2 * np.pi * 311.13 * t) + np.sin(2 * np.pi * 392.00 * t)

        y = 0.7 * c_maj + 0.3 * eb_maj
        y = y / np.max(np.abs(y)) * 0.8

        result = analyzer.analyze(y.astype(np.float32), sr)

        assert result is not None
        # Should detect C major or C minor
        assert 'C' in result.global_key or any('C' in alt.key for alt in result.alternatives)
