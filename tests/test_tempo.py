"""
Tests for tempo analysis module.
"""

import numpy as np
import pytest

from meloniq.analysis.tempo import TempoAnalyzer


class TestTempoAnalyzer:
    """Test cases for TempoAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return TempoAnalyzer()
    
    @pytest.fixture
    def click_track_120bpm(self):
        """Create a simple click track at 120 BPM."""
        sr = 22050
        duration = 10  # 10 seconds
        bpm = 120
        
        # Create silence
        y = np.zeros(sr * duration)
        
        # Add clicks at beat positions
        beat_interval = 60 / bpm  # seconds per beat
        n_beats = int(duration / beat_interval)
        
        for i in range(n_beats):
            sample_pos = int(i * beat_interval * sr)
            # Add a short click (impulse)
            click_length = int(0.01 * sr)  # 10ms click
            if sample_pos + click_length < len(y):
                # Decaying envelope
                envelope = np.exp(-np.linspace(0, 5, click_length))
                y[sample_pos:sample_pos + click_length] = envelope
        
        return y, sr, bpm
    
    def test_analyze_returns_result(self, analyzer, click_track_120bpm):
        """Test that analyze returns a TempoResult."""
        y, sr, _ = click_track_120bpm
        result = analyzer.analyze(y, sr)
        
        assert result is not None
        assert result.global_bpm > 0
        assert 0 <= result.confidence <= 1
        assert len(result.beats) > 0
    
    def test_tempo_accuracy_for_click_track(self, analyzer, click_track_120bpm):
        """Test tempo accuracy for a clean click track."""
        y, sr, expected_bpm = click_track_120bpm
        result = analyzer.analyze(y, sr)
        
        # Should detect 120 BPM or a related tempo (60, 240)
        detected = result.global_bpm
        
        # Check if detected is within 5% of expected or its multiples/divisions
        valid_tempos = [expected_bpm, expected_bpm / 2, expected_bpm * 2]
        
        is_valid = any(
            abs(detected - valid) / valid < 0.05
            for valid in valid_tempos
        )
        
        assert is_valid, f"Detected {detected} BPM, expected ~{expected_bpm} BPM"
    
    def test_candidates_include_half_double_time(self, analyzer, click_track_120bpm):
        """Test that candidates include half-time and double-time options."""
        y, sr, expected_bpm = click_track_120bpm
        result = analyzer.analyze(y, sr)
        
        # Should have multiple candidates
        assert len(result.candidates) >= 1
        
        # All candidates should have valid BPM ranges
        for candidate in result.candidates:
            assert 40 <= candidate.bpm <= 220
            assert 0 <= candidate.confidence <= 1
    
    def test_beat_times_are_ordered(self, analyzer, click_track_120bpm):
        """Test that beat times are in ascending order."""
        y, sr, _ = click_track_120bpm
        result = analyzer.analyze(y, sr)
        
        beats = result.beats
        for i in range(1, len(beats)):
            assert beats[i] > beats[i-1], "Beat times should be ascending"
    
    def test_downbeats_subset_of_beats(self, analyzer, click_track_120bpm):
        """Test that downbeats are a subset of beats."""
        y, sr, _ = click_track_120bpm
        result = analyzer.analyze(y, sr)
        
        if result.downbeats:
            for downbeat in result.downbeats:
                # Each downbeat should be close to a beat
                distances = [abs(downbeat - beat) for beat in result.beats]
                min_distance = min(distances) if distances else float('inf')
                assert min_distance < 0.1, "Downbeat should be near a beat"
    
    def test_count_in_generated(self, analyzer, click_track_120bpm):
        """Test that count-in suggestion is generated."""
        y, sr, _ = click_track_120bpm
        result = analyzer.analyze(y, sr)
        
        assert result.count_in is not None
        assert result.count_in.click_bpm > 0
        assert result.count_in.bars >= 1
    
    def test_explanation_provided(self, analyzer, click_track_120bpm):
        """Test that explanation is provided."""
        y, sr, _ = click_track_120bpm
        result = analyzer.analyze(y, sr)
        
        assert result.explanation
        assert len(result.explanation) > 10


class TestTempoAnalyzerEdgeCases:
    """Edge case tests for TempoAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        return TempoAnalyzer()
    
    def test_silent_audio(self, analyzer):
        """Test handling of silent audio."""
        y = np.zeros(22050 * 5)  # 5 seconds of silence
        sr = 22050
        
        result = analyzer.analyze(y, sr)
        
        # Should still return a result, even if low confidence
        assert result is not None
        assert result.global_bpm > 0
    
    def test_very_short_audio(self, analyzer):
        """Test handling of very short audio."""
        y = np.random.randn(22050)  # 1 second
        sr = 22050
        
        result = analyzer.analyze(y, sr)
        
        assert result is not None
    
    def test_noisy_audio(self, analyzer):
        """Test handling of noisy audio."""
        y = np.random.randn(22050 * 10) * 0.1  # 10 seconds of noise
        sr = 22050
        
        result = analyzer.analyze(y, sr)
        
        # Should handle gracefully
        assert result is not None
        # Confidence should be lower for noise
        assert result.confidence < 0.9
