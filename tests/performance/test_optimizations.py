"""
Test performance impact of proposed optimizations.

Compares different optimization strategies:
1. Baseline (current)
2. No HPSS
3. Larger hop_length
4. Lower sample rate
5. Combined optimizations
"""

import time
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from meloniq.analysis.key import KeyAnalyzer
import librosa


def generate_test_audio(duration_sec: int = 180, sr: int = 22050) -> np.ndarray:
    """Generate synthetic test audio in F# major."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    freqs = [185.0, 207.65, 233.08, 246.94, 277.18, 311.13, 349.23]
    signal = np.zeros_like(t)

    for i, freq in enumerate(freqs):
        signal += (0.7 / (i + 1)) * np.sin(2 * np.pi * freq * t)
        signal += (0.3 / (i + 1)) * np.sin(2 * np.pi * freq * 2 * t)

    signal += 0.05 * np.random.randn(len(t))
    signal = signal / np.max(np.abs(signal)) * 0.9

    return signal.astype(np.float32)


class OptimizedKeyAnalyzer(KeyAnalyzer):
    """
    Optimized version of KeyAnalyzer for testing.
    Allows disabling HPSS and adjusting parameters.
    """

    def __init__(self, hop_length: int = 512, use_hpss: bool = True):
        super().__init__(hop_length=hop_length)
        self.use_hpss = use_hpss

    def analyze(self, y, sr, detect_modulations=True):
        """Modified analyze with optional HPSS."""
        # Optional HPSS
        if self.use_hpss:
            y_harmonic = librosa.effects.harmonic(y, margin=4)
        else:
            y_harmonic = y

        tuning = librosa.estimate_tuning(y=y_harmonic, sr=sr)
        chroma = self._extract_combined_chroma(y_harmonic, sr, tuning)
        global_chroma = self._get_weighted_chroma(chroma)
        global_key, confidence, all_scores = self._find_key(global_chroma)
        alternatives = self._get_alternatives(all_scores, global_key, confidence)

        segments = []
        if detect_modulations:
            segments = self._detect_modulations(chroma, sr)

        explanation = self._generate_explanation(global_key, confidence, alternatives)

        # Create result (simplified for testing)
        from meloniq.models.results import KeyResult
        return KeyResult(
            global_key=global_key,
            confidence=confidence,
            explanation=explanation,
            needs_confirmation=confidence < self.MEDIUM_CONFIDENCE,
            alternatives=alternatives,
            segments=segments,
            is_chromatic=confidence < self.LOW_CONFIDENCE,
        )


def benchmark_optimization(
    y: np.ndarray,
    sr: int,
    name: str,
    use_hpss: bool = True,
    hop_length: int = 512,
) -> dict:
    """Benchmark a specific optimization configuration."""
    analyzer = OptimizedKeyAnalyzer(hop_length=hop_length, use_hpss=use_hpss)

    start = time.perf_counter()
    result = analyzer.analyze(y, sr, detect_modulations=True)
    end = time.perf_counter()

    exec_time = end - start

    return {
        "name": name,
        "time": exec_time,
        "key": result.global_key,
        "confidence": result.confidence,
    }


def main():
    """Run optimization comparison."""
    print("=" * 70)
    print("KEY DETECTION OPTIMIZATION TESTS")
    print("=" * 70)
    print()

    # Generate test audio at different sample rates
    print("Generating test audio...")
    y_22k = generate_test_audio(180, sr=22050)
    y_11k = generate_test_audio(180, sr=11025)
    print()

    results = []

    # Test 1: Baseline
    print("Test 1: Baseline (current implementation)")
    r1 = benchmark_optimization(y_22k, 22050, "Baseline", use_hpss=True, hop_length=512)
    results.append(r1)
    print(f"  Time: {r1['time']:.3f}s | Key: {r1['key']} | Confidence: {r1['confidence']:.2f}")
    print()

    # Test 2: No HPSS
    print("Test 2: No HPSS")
    r2 = benchmark_optimization(y_22k, 22050, "No HPSS", use_hpss=False, hop_length=512)
    results.append(r2)
    print(f"  Time: {r2['time']:.3f}s | Key: {r2['key']} | Confidence: {r2['confidence']:.2f}")
    improvement = (r1['time'] - r2['time']) / r1['time'] * 100
    print(f"  Improvement: {improvement:.1f}%")
    print()

    # Test 3: Larger hop_length
    print("Test 3: Larger hop_length (1024 vs 512)")
    r3 = benchmark_optimization(y_22k, 22050, "hop_length=1024", use_hpss=True, hop_length=1024)
    results.append(r3)
    print(f"  Time: {r3['time']:.3f}s | Key: {r3['key']} | Confidence: {r3['confidence']:.2f}")
    improvement = (r1['time'] - r3['time']) / r1['time'] * 100
    print(f"  Improvement: {improvement:.1f}%")
    print()

    # Test 4: Lower sample rate
    print("Test 4: Lower sample rate (11025 Hz)")
    r4 = benchmark_optimization(y_11k, 11025, "sr=11025", use_hpss=True, hop_length=512)
    results.append(r4)
    print(f"  Time: {r4['time']:.3f}s | Key: {r4['key']} | Confidence: {r4['confidence']:.2f}")
    improvement = (r1['time'] - r4['time']) / r1['time'] * 100
    print(f"  Improvement: {improvement:.1f}%")
    print()

    # Test 5: Combined (Phase 1)
    print("Test 5: Phase 1 Combined (No HPSS + hop_length=1024)")
    r5 = benchmark_optimization(y_22k, 22050, "Phase 1", use_hpss=False, hop_length=1024)
    results.append(r5)
    print(f"  Time: {r5['time']:.3f}s | Key: {r5['key']} | Confidence: {r5['confidence']:.2f}")
    improvement = (r1['time'] - r5['time']) / r1['time'] * 100
    print(f"  Improvement: {improvement:.1f}%")
    print()

    # Test 6: Combined (Phase 2)
    print("Test 6: Phase 2 Combined (No HPSS + hop_length=1024 + sr=11025)")
    r6 = benchmark_optimization(y_11k, 11025, "Phase 2", use_hpss=False, hop_length=1024)
    results.append(r6)
    print(f"  Time: {r6['time']:.3f}s | Key: {r6['key']} | Confidence: {r6['confidence']:.2f}")
    improvement = (r1['time'] - r6['time']) / r1['time'] * 100
    print(f"  Improvement: {improvement:.1f}%")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()

    print(f"{'Configuration':<30} | {'Time (s)':<10} | {'vs Baseline':<12} | {'<5s?'}")
    print("-" * 70)

    for r in results:
        vs_baseline = ((r['time'] - results[0]['time']) / results[0]['time'] * 100)
        status = "PASS" if r['time'] < 5.0 else "FAIL"
        print(f"{r['name']:<30} | {r['time']:>8.3f}s | {vs_baseline:>+10.1f}% | {status}")

    print()

    # Check constraint
    print("=" * 70)
    print("CONSTRAINT VALIDATION")
    print("=" * 70)
    print()

    target = 5.0
    for r in results:
        if r['time'] < target:
            print(f"[PASS] {r['name']}: {r['time']:.3f}s < {target}s - MEETS CONSTRAINT")
        else:
            print(f"[FAIL] {r['name']}: {r['time']:.3f}s > {target}s - FAILS CONSTRAINT")

    print()

    # Recommendation
    print("=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    print()

    # Find best that meets constraint
    passing = [r for r in results if r['time'] < target]

    if passing:
        best = min(passing, key=lambda x: x['time'])
        print(f"Recommended configuration: {best['name']}")
        print(f"  Execution time: {best['time']:.3f}s")
        print(f"  Speedup: {results[0]['time'] / best['time']:.1f}x")
        print(f"  Key detected: {best['key']} (confidence: {best['confidence']:.2f})")
    else:
        print("WARNING: No configuration meets <5s constraint.")
        print("Consider additional optimizations or relaxing constraint.")


if __name__ == "__main__":
    main()
