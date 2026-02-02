"""
Tests for key analysis module.
"""

import numpy as np
import pytest

from meloniq.analysis.key import KeyAnalyzer


class TestKeyAnalyzer:
    """Test cases for KeyAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return KeyAnalyzer()
    
    @pytest.fixture
    def c_major_chord(self):
        """Create a C major chord (C-E-G)."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)
        
        # C4 (261.63 Hz), E4 (329.63 Hz), G4 (392.00 Hz)
        frequencies = [261.63, 329.63, 392.00]
        
        y = np.zeros_like(t)
        for freq in frequencies:
            y += np.sin(2 * np.pi * freq * t)
        
        # Normalize
        y = y / np.max(np.abs(y)) * 0.8
        
        return y.astype(np.float32), sr, "C major"
    
    @pytest.fixture
    def a_minor_chord(self):
        """Create an A minor chord (A-C-E)."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)
        
        # A3 (220 Hz), C4 (261.63 Hz), E4 (329.63 Hz)
        frequencies = [220.00, 261.63, 329.63]
        
        y = np.zeros_like(t)
        for freq in frequencies:
            y += np.sin(2 * np.pi * freq * t)
        
        y = y / np.max(np.abs(y)) * 0.8
        
        return y.astype(np.float32), sr, "A minor"
    
    def test_analyze_returns_result(self, analyzer, c_major_chord):
        """Test that analyze returns a KeyResult."""
        y, sr, _ = c_major_chord
        result = analyzer.analyze(y, sr)
        
        assert result is not None
        assert result.global_key
        assert 0 <= result.confidence <= 1
    
    def test_c_major_detection(self, analyzer, c_major_chord):
        """Test detection of C major from chord."""
        y, sr, expected_key = c_major_chord
        result = analyzer.analyze(y, sr)
        
        # Should detect C major or its relative A minor
        valid_keys = ["C major", "A minor"]
        
        assert result.global_key in valid_keys or any(
            alt.key in valid_keys for alt in result.alternatives
        ), f"Expected {expected_key}, got {result.global_key}"
    
    def test_a_minor_detection(self, analyzer, a_minor_chord):
        """Test detection of A minor from chord."""
        y, sr, expected_key = a_minor_chord
        result = analyzer.analyze(y, sr)
        
        # Should detect A minor or its relative C major
        valid_keys = ["A minor", "C major"]
        
        assert result.global_key in valid_keys or any(
            alt.key in valid_keys for alt in result.alternatives
        )
    
    def test_alternatives_provided(self, analyzer, c_major_chord):
        """Test that alternatives are provided."""
        y, sr, _ = c_major_chord
        result = analyzer.analyze(y, sr)
        
        # Should have alternatives
        assert len(result.alternatives) >= 1
        
        # Alternatives should have valid confidence
        for alt in result.alternatives:
            assert 0 <= alt.confidence <= 1
    
    def test_relative_major_minor_relationship(self, analyzer, c_major_chord):
        """Test that relative major/minor is in alternatives."""
        y, sr, _ = c_major_chord
        result = analyzer.analyze(y, sr)
        
        # If detected C major, A minor should be alternative (or vice versa)
        if result.global_key == "C major":
            alt_keys = [a.key for a in result.alternatives]
            # A minor should be among top alternatives
            has_relative = "A minor" in alt_keys
            assert has_relative or result.confidence < 0.5
    
    def test_explanation_provided(self, analyzer, c_major_chord):
        """Test that explanation is provided."""
        y, sr, _ = c_major_chord
        result = analyzer.analyze(y, sr)
        
        assert result.explanation
        assert len(result.explanation) > 10


class TestKeyAnalyzerEdgeCases:
    """Edge case tests for KeyAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        return KeyAnalyzer()
    
    def test_silent_audio(self, analyzer):
        """Test handling of silent audio."""
        y = np.zeros(22050 * 5)
        sr = 22050
        
        result = analyzer.analyze(y, sr)
        
        assert result is not None
        # Should indicate low confidence
        assert result.confidence < 0.5
    
    def test_chromatic_audio(self, analyzer):
        """Test handling of chromatic/atonal audio."""
        sr = 22050
        duration = 5
        t = np.linspace(0, duration, sr * duration)
        
        # Play all 12 notes equally
        y = np.zeros_like(t)
        for semitone in range(12):
            freq = 440 * (2 ** (semitone / 12))
            y += np.sin(2 * np.pi * freq * t)
        
        y = y / np.max(np.abs(y)) * 0.5
        
        result = analyzer.analyze(y.astype(np.float32), sr)
        
        # Should indicate chromatic content or low confidence
        assert result.is_chromatic or result.confidence < 0.5
    
    def test_very_short_audio(self, analyzer):
        """Test handling of very short audio."""
        y = np.random.randn(22050).astype(np.float32)  # 1 second
        sr = 22050
        
        result = analyzer.analyze(y, sr)
        
        assert result is not None
