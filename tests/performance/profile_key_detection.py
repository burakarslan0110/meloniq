"""
Detailed profiling of key detection using cProfile.

Identifies specific bottlenecks in the algorithm.
"""

import cProfile
import pstats
import io
import sys
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from meloniq.analysis.key import KeyAnalyzer


def generate_test_audio(duration_sec: int = 180, sr: int = 22050) -> np.ndarray:
    """Generate synthetic 3-minute test audio in F# major."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # F# major scale
    freqs = [185.0, 207.65, 233.08, 246.94, 277.18, 311.13, 349.23]

    signal = np.zeros_like(t)

    for i, freq in enumerate(freqs):
        signal += (0.7 / (i + 1)) * np.sin(2 * np.pi * freq * t)
        signal += (0.3 / (i + 1)) * np.sin(2 * np.pi * freq * 2 * t)

    signal += 0.05 * np.random.randn(len(t))
    signal = signal / np.max(np.abs(signal)) * 0.9

    return signal.astype(np.float32)


def profile_key_analysis():
    """Profile key detection with cProfile."""
    print("Generating 3-minute test audio...")
    y = generate_test_audio(180)
    sr = 22050

    print("Running profiled key detection...")
    print("=" * 80)

    profiler = cProfile.Profile()
    profiler.enable()

    # Run key detection
    analyzer = KeyAnalyzer()
    result = analyzer.analyze(y, sr, detect_modulations=True)

    profiler.disable()

    # Print results
    print(f"\nDetected Key: {result.global_key}")
    print(f"Confidence: {result.confidence:.2f}")
    print()

    # Print profiling stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    ps.sort_stats('cumulative')

    print("=" * 80)
    print("TOP 30 FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 80)
    ps.print_stats(30)

    print("\n" + "=" * 80)
    print("TOP 20 FUNCTIONS BY TOTAL TIME (excluding children)")
    print("=" * 80)
    ps.sort_stats('tottime')
    ps.print_stats(20)

    print(s.getvalue())

    # Identify specific bottlenecks
    print("\n" + "=" * 80)
    print("BOTTLENECK ANALYSIS")
    print("=" * 80)

    stats = ps.stats
    total_time = sum(stat[2] for stat in stats.values())

    bottlenecks = []
    for func, (cc, nc, tt, ct, callers) in stats.items():
        if 'librosa' in str(func) or 'chroma' in str(func):
            pct = (ct / total_time * 100) if total_time > 0 else 0
            bottlenecks.append((pct, ct, nc, func))

    bottlenecks.sort(reverse=True)

    print("\nLibrosa/Chroma function calls:")
    for pct, ct, nc, func in bottlenecks[:10]:
        print(f"  {pct:5.1f}% | {ct:6.2f}s | {nc:6d} calls | {func}")


if __name__ == "__main__":
    profile_key_analysis()
