"""
Validation script for new bass-weighted key detection.

Run this AFTER backend-specialist completes the implementation.
Compares baseline vs optimized vs new implementation.
"""

import time
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def generate_fsharp_vocal_track(duration_sec: int = 180, sr: int = 22050) -> np.ndarray:
    """
    Generate synthetic vocal-like track in F# major.
    Simulates the problematic case (vocals causing F# → D major confusion).
    """
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # F# major scale (with emphasis on relative minor D notes)
    # This simulates vocal melodies that might confuse key detection
    melody_freqs = [185.0, 207.65, 233.08, 246.94, 277.18]  # F#, G#, A#, B, C#
    bass_freqs = [92.5, 123.47, 138.59]  # F#, B, C# (roots)

    signal = np.zeros_like(t)

    # Simulate vocals (higher frequencies, more variation)
    for i, freq in enumerate(melody_freqs):
        # Add vibrato
        vibrato = 5 * np.sin(2 * np.pi * 6 * t)  # 6 Hz vibrato
        mod_freq = freq * (1 + vibrato / 1000)

        signal += (0.5 / (i + 1)) * np.sin(2 * np.pi * mod_freq * t)

    # Simulate bass (lower frequencies, more stable)
    for i, freq in enumerate(bass_freqs):
        signal += (0.8 / (i + 1)) * np.sin(2 * np.pi * freq * t)
        signal += (0.3 / (i + 1)) * np.sin(2 * np.pi * freq * 2 * t)

    # Add noise
    signal += 0.03 * np.random.randn(len(t))

    signal = signal / np.max(np.abs(signal)) * 0.9

    return signal.astype(np.float32)


def test_implementation(implementation_name: str, analyzer, y: np.ndarray, sr: int) -> dict:
    """Test a specific key analyzer implementation."""
    print(f"\nTesting: {implementation_name}")
    print("-" * 60)

    start = time.perf_counter()
    result = analyzer.analyze(y, sr, detect_modulations=True)
    end = time.perf_counter()

    exec_time = end - start

    print(f"  Key detected: {result.global_key}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Execution time: {exec_time:.3f}s")
    print(f"  Segments: {len(result.segments)}")

    # Check if F# is correctly detected (not D major)
    is_correct = "F#" in result.global_key and "major" in result.global_key.lower()

    return {
        "name": implementation_name,
        "key": result.global_key,
        "confidence": result.confidence,
        "time": exec_time,
        "correct": is_correct,
        "segments": len(result.segments),
    }


def main():
    """Run validation tests."""
    print("=" * 70)
    print("NEW IMPLEMENTATION VALIDATION")
    print("Testing bass-weighted key detection for vocal tracks")
    print("=" * 70)

    # Generate problematic test case
    print("\nGenerating F# major vocal track (3 minutes)...")
    y = generate_fsharp_vocal_track(180)
    sr = 22050

    results = []

    # Test 1: Import original implementation
    try:
        from meloniq.analysis.key import KeyAnalyzer

        print("\n" + "=" * 70)
        print("TEST 1: BASELINE (if HPSS still enabled)")
        print("=" * 70)

        analyzer_baseline = KeyAnalyzer(hop_length=512)
        r1 = test_implementation("Baseline (HPSS + hop=512)", analyzer_baseline, y, sr)
        results.append(r1)

    except Exception as e:
        print(f"Could not test baseline: {e}")

    # Test 2: Optimized baseline
    try:
        print("\n" + "=" * 70)
        print("TEST 2: OPTIMIZED BASELINE (Phase 1)")
        print("=" * 70)

        analyzer_opt = KeyAnalyzer(hop_length=1024)
        # Assuming use_hpss parameter was added
        if hasattr(analyzer_opt, 'use_hpss'):
            analyzer_opt.use_hpss = False

        r2 = test_implementation("Optimized (no HPSS + hop=1024)", analyzer_opt, y, sr)
        results.append(r2)

    except Exception as e:
        print(f"Could not test optimized: {e}")

    # Test 3: New bass-weighted implementation
    try:
        print("\n" + "=" * 70)
        print("TEST 3: NEW BASS-WEIGHTED IMPLEMENTATION")
        print("=" * 70)

        # Check if new method exists
        analyzer_new = KeyAnalyzer(hop_length=1024)

        if hasattr(analyzer_new, '_extract_bass_weighted_chroma'):
            print("Bass-weighted method detected!")
            r3 = test_implementation("New bass-weighted", analyzer_new, y, sr)
            results.append(r3)
        else:
            print("Bass-weighted method NOT YET IMPLEMENTED")
            print("Run this script after backend-specialist completes implementation.")

    except Exception as e:
        print(f"Could not test new implementation: {e}")

    # Summary
    if results:
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        print()

        print(f"{'Implementation':<35} | {'Key':<12} | {'Correct?':<8} | {'Time':<8} | {'Conf':<6}")
        print("-" * 70)

        for r in results:
            correct_str = "YES" if r['correct'] else "NO"
            print(f"{r['name']:<35} | {r['key']:<12} | {correct_str:<8} | "
                  f"{r['time']:>6.3f}s | {r['confidence']:.2f}")

        print()

        # Check constraints
        print("=" * 70)
        print("CONSTRAINT CHECKS")
        print("=" * 70)
        print()

        for r in results:
            # Accuracy check
            if r['correct']:
                print(f"[PASS] {r['name']}: Correctly detected F# major")
            else:
                print(f"[FAIL] {r['name']}: Incorrect key ({r['key']} instead of F# major)")

            # Performance check
            if r['time'] < 5.0:
                print(f"[PASS] {r['name']}: Performance OK ({r['time']:.3f}s < 5s)")
            else:
                print(f"[FAIL] {r['name']}: Too slow ({r['time']:.3f}s > 5s)")

            # Confidence check
            if r['confidence'] >= 0.70:
                print(f"[PASS] {r['name']}: High confidence ({r['confidence']:.2f})")
            elif r['confidence'] >= 0.55:
                print(f"[WARN] {r['name']}: Medium confidence ({r['confidence']:.2f})")
            else:
                print(f"[FAIL] {r['name']}: Low confidence ({r['confidence']:.2f})")

            print()

        # Recommendations
        print("=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)
        print()

        # Find best implementation
        correct_results = [r for r in results if r['correct']]

        if correct_results:
            best = min(correct_results, key=lambda x: x['time'])
            print(f"Best implementation: {best['name']}")
            print(f"  Accuracy: Correct (F# major)")
            print(f"  Performance: {best['time']:.3f}s")
            print(f"  Confidence: {best['confidence']:.2f}")
            print()
            print("Status: READY FOR DEPLOYMENT")
        else:
            print("WARNING: No implementation correctly detects F# major")
            print("The vocal key detection bug is NOT FIXED")
            print()
            print("Suggested actions:")
            print("1. Verify bass-weighted method is implemented")
            print("2. Test on real F# vocal tracks")
            print("3. Adjust ensemble weights (increase bass-weighted weight)")

    else:
        print("\nNo tests completed. Check implementation.")


if __name__ == "__main__":
    main()
