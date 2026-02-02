"""
Performance benchmark for key detection algorithm.

Tests execution time and memory usage for different audio lengths.
Compares baseline vs optimized implementation.
"""

import time
import sys
import tracemalloc
from pathlib import Path
from typing import Dict, List
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from meloniq.analysis.key import KeyAnalyzer
import librosa


class BenchmarkResult:
    """Store benchmark metrics."""

    def __init__(self, name: str):
        self.name = name
        self.execution_time = 0.0
        self.memory_peak = 0
        self.memory_current = 0

    def __repr__(self):
        return (
            f"{self.name}: "
            f"{self.execution_time:.3f}s, "
            f"Peak: {self.memory_peak / 1024 / 1024:.1f}MB, "
            f"Current: {self.memory_current / 1024 / 1024:.1f}MB"
        )


def generate_test_audio(duration_sec: int, sr: int = 22050) -> np.ndarray:
    """
    Generate synthetic test audio with harmonic content.
    Simulates a simple musical signal in F# major.
    """
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # F# major scale frequencies (F#, G#, A#, B, C#, D#, E#/F)
    freqs = [185.0, 207.65, 233.08, 246.94, 277.18, 311.13, 349.23]

    signal = np.zeros_like(t)

    # Add harmonic content
    for i, freq in enumerate(freqs):
        # Fundamental
        signal += (0.7 / (i + 1)) * np.sin(2 * np.pi * freq * t)
        # Second harmonic
        signal += (0.3 / (i + 1)) * np.sin(2 * np.pi * freq * 2 * t)

    # Add some noise to simulate real audio
    signal += 0.05 * np.random.randn(len(t))

    # Normalize
    signal = signal / np.max(np.abs(signal)) * 0.9

    return signal.astype(np.float32)


def benchmark_key_detection(
    y: np.ndarray,
    sr: int,
    test_name: str,
) -> BenchmarkResult:
    """
    Benchmark key detection on given audio.

    Args:
        y: Audio samples
        sr: Sample rate
        test_name: Name for this test

    Returns:
        BenchmarkResult with timing and memory stats
    """
    result = BenchmarkResult(test_name)

    # Start memory tracking
    tracemalloc.start()

    # Initialize analyzer
    analyzer = KeyAnalyzer()

    # Run key detection and time it
    start_time = time.perf_counter()

    key_result = analyzer.analyze(y, sr, detect_modulations=True)

    end_time = time.perf_counter()

    # Get memory stats
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Store results
    result.execution_time = end_time - start_time
    result.memory_peak = peak
    result.memory_current = current

    return result


def run_benchmark_suite() -> Dict[str, List[BenchmarkResult]]:
    """
    Run complete benchmark suite with different audio durations.

    Returns:
        Dictionary mapping test category to list of results
    """
    results = {
        "baseline": [],
    }

    # Test durations in seconds
    test_cases = [
        ("30s audio", 30),
        ("3min audio (180s)", 180),
        ("10min audio (600s)", 600),
    ]

    print("=" * 60)
    print("KEY DETECTION PERFORMANCE BENCHMARK")
    print("=" * 60)
    print()

    for test_name, duration in test_cases:
        print(f"Generating {test_name}...")
        y = generate_test_audio(duration)
        sr = 22050

        print(f"Running benchmark for {test_name}...")
        result = benchmark_key_detection(y, sr, test_name)
        results["baseline"].append(result)

        print(f"  {result}")
        print()

    return results


def validate_performance_constraints(results: Dict[str, List[BenchmarkResult]]) -> bool:
    """
    Validate that performance meets required constraints.

    Constraint from ACCURACY_NOTES.md:
    - Key detection must complete in <5 seconds for 3-minute song

    Returns:
        True if all constraints met, False otherwise
    """
    print("=" * 60)
    print("PERFORMANCE VALIDATION")
    print("=" * 60)
    print()

    all_passed = True

    # Check 3-minute constraint
    for category, result_list in results.items():
        for result in result_list:
            if "3min" in result.name:
                constraint_met = result.execution_time < 5.0
                status = "PASS" if constraint_met else "FAIL"

                print(f"[{status}] 3-min audio < 5s: {result.execution_time:.3f}s ({category})")

                if not constraint_met:
                    all_passed = False
                    print(f"  WARNING: Exceeds constraint by {result.execution_time - 5.0:.3f}s")

    print()
    return all_passed


def compare_implementations(
    baseline_results: List[BenchmarkResult],
    optimized_results: List[BenchmarkResult],
) -> Dict[str, float]:
    """
    Compare baseline vs optimized implementation.

    Args:
        baseline_results: Results from baseline implementation
        optimized_results: Results from optimized implementation

    Returns:
        Dictionary with performance deltas
    """
    print("=" * 60)
    print("BASELINE vs OPTIMIZED COMPARISON")
    print("=" * 60)
    print()

    comparison = {}

    for baseline, optimized in zip(baseline_results, optimized_results):
        time_delta_pct = ((optimized.execution_time - baseline.execution_time)
                          / baseline.execution_time * 100)

        mem_delta_pct = ((optimized.memory_peak - baseline.memory_peak)
                         / baseline.memory_peak * 100)

        print(f"{baseline.name}:")
        print(f"  Time:   {baseline.execution_time:.3f}s -> {optimized.execution_time:.3f}s "
              f"({time_delta_pct:+.1f}%)")
        print(f"  Memory: {baseline.memory_peak/1024/1024:.1f}MB -> "
              f"{optimized.memory_peak/1024/1024:.1f}MB ({mem_delta_pct:+.1f}%)")

        # Check thresholds
        if time_delta_pct > 10:
            print(f"  WARNING: Time degradation exceeds 10% threshold!")

        if mem_delta_pct > 100:  # 2x memory
            print(f"  WARNING: Memory usage doubled!")

        print()

        comparison[baseline.name] = {
            "time_delta_pct": time_delta_pct,
            "mem_delta_pct": mem_delta_pct,
        }

    return comparison


def generate_report(results: Dict[str, List[BenchmarkResult]]):
    """Generate performance report summary."""
    print("=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)
    print()

    for category, result_list in results.items():
        print(f"{category.upper()} Implementation:")
        for result in result_list:
            efficiency = result.execution_time / float(result.name.split("(")[1].split("s")[0] if "(" in result.name else result.name.split("s")[0])
            print(f"  {result.name:20s} | Time: {result.execution_time:6.3f}s | "
                  f"Memory: {result.memory_peak/1024/1024:5.1f}MB | "
                  f"Efficiency: {efficiency:.4f}s/s")
        print()


if __name__ == "__main__":
    print("Starting performance benchmark...")
    print()

    # Run baseline benchmark
    results = run_benchmark_suite()

    # Validate constraints
    constraints_met = validate_performance_constraints(results)

    # Generate summary
    generate_report(results)

    # Final status
    print("=" * 60)
    if constraints_met:
        print("STATUS: All performance constraints met")
    else:
        print("STATUS: FAILED - Performance constraints not met")
    print("=" * 60)
    print()

    print("Note: Run this script again after backend-specialist completes")
    print("      the new implementation to compare performance.")
