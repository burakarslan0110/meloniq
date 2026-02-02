"""
Test script for Phase 1 vocal detection and bass-weighted chroma implementation.
"""
import sys
sys.path.insert(0, 'src')

import numpy as np
import librosa
from meloniq.analysis.key import KeyAnalyzer


def test_vocal_detection():
    """Test vocal detection with synthetic signals."""
    analyzer = KeyAnalyzer()
    sr = 22050
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration))

    # Test 1: High frequency signal (simulates vocals)
    print("Test 1: High frequency signal (vocal simulation)")
    high_freq = np.sin(2 * np.pi * 2000 * t) + np.sin(2 * np.pi * 3000 * t)
    high_freq = high_freq / np.max(np.abs(high_freq))
    vocal_detected, confidence = analyzer._detect_vocals(high_freq, sr)
    print(f"  Vocal detected: {vocal_detected}, Confidence: {confidence}")

    # Test 2: Low frequency signal (simulates bass/instruments)
    print("\nTest 2: Low frequency signal (instrument simulation)")
    low_freq = np.sin(2 * np.pi * 200 * t) + np.sin(2 * np.pi * 400 * t)
    low_freq = low_freq / np.max(np.abs(low_freq))
    vocal_detected, confidence = analyzer._detect_vocals(low_freq, sr)
    print(f"  Vocal detected: {vocal_detected}, Confidence: {confidence}")

    # Test 3: Mixed frequency (typical pop music)
    print("\nTest 3: Mixed frequency signal")
    mixed = high_freq * 0.6 + low_freq * 0.4
    mixed = mixed / np.max(np.abs(mixed))
    vocal_detected, confidence = analyzer._detect_vocals(mixed, sr)
    print(f"  Vocal detected: {vocal_detected}, Confidence: {confidence}")


def test_bass_weighted_chroma():
    """Test bass-weighted chroma extraction."""
    analyzer = KeyAnalyzer()
    sr = 22050
    duration = 3.0

    # Generate A major chord (A2 + C#3 + E3)
    print("\nTest 4: Bass-weighted chroma (A major chord)")
    t = np.linspace(0, duration, int(sr * duration))
    a2 = np.sin(2 * np.pi * librosa.note_to_hz('A2') * t)
    cs3 = np.sin(2 * np.pi * librosa.note_to_hz('C#3') * t)
    e3 = np.sin(2 * np.pi * librosa.note_to_hz('E3') * t)
    chord = a2 + cs3 + e3
    chord = chord / np.max(np.abs(chord))

    # Extract bass-weighted chroma
    chroma = analyzer._extract_bass_weighted_chroma(chord, sr, tuning=0.0)
    print(f"  Chroma shape: {chroma.shape}")

    # Find dominant pitch class
    avg_chroma = np.mean(chroma, axis=1)
    dominant_pitch = np.argmax(avg_chroma)
    print(f"  Dominant pitch class: {analyzer.PITCH_CLASSES[dominant_pitch]}")
    print(f"  Expected: A (index 9), Got: index {dominant_pitch}")


def test_full_analysis():
    """Test full key analysis with vocal detection."""
    print("\nTest 5: Full analysis integration")
    analyzer = KeyAnalyzer()
    sr = 22050
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration))

    # Create a simple chord progression in D major with high frequencies (vocals)
    # D major scale: D, E, F#, G, A, B, C#
    d_freq = librosa.note_to_hz('D3')
    fs_freq = librosa.note_to_hz('F#3')
    a_freq = librosa.note_to_hz('A3')
    vocal_freq = 2000  # Simulate vocal

    signal = (
        np.sin(2 * np.pi * d_freq * t) +
        np.sin(2 * np.pi * fs_freq * t) +
        np.sin(2 * np.pi * a_freq * t) +
        0.5 * np.sin(2 * np.pi * vocal_freq * t)  # Add vocal component
    )
    signal = signal / np.max(np.abs(signal))

    # Analyze
    result = analyzer.analyze(signal, sr, detect_modulations=False)

    print(f"  Detected key: {result.global_key}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Vocal detected: {result.vocal_detected}")
    print(f"  Explanation: {result.explanation}")

    if result.alternatives:
        print(f"  Alternatives: {', '.join([alt.key for alt in result.alternatives[:3]])}")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1 Vocal Detection Implementation Test")
    print("=" * 60)

    try:
        test_vocal_detection()
        test_bass_weighted_chroma()
        test_full_analysis()
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
