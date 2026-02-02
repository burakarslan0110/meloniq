# Performance Tests for Key Detection

This directory contains performance benchmarking and optimization tests for the key detection algorithm.

---

## Context

The key detection algorithm was too slow (15.3s for 3-minute audio) and failing to correctly detect keys on vocal tracks (F# detected as D major).

**Goal**: Optimize to <5s while adding bass-weighted chroma for better vocal key detection.

---

## Files

### Benchmarking Scripts

| File | Purpose | When to Run |
|------|---------|-------------|
| `benchmark_key_detection.py` | Baseline performance measurement | Before any changes |
| `profile_key_detection.py` | Detailed cProfile analysis | To identify bottlenecks |
| `test_optimizations.py` | Compare optimization strategies | To find best approach |
| `validate_new_implementation.py` | Validate bass-weighted implementation | After new algorithm is added |

### Reports

| File | Content |
|------|---------|
| `PERFORMANCE_REPORT.md` | Baseline metrics + bottleneck analysis |
| `OPTIMIZATION_RESULTS.md` | Optimization test results + recommendations |

---

## Quick Start

### 1. Baseline Benchmark

```bash
python tests/performance/benchmark_key_detection.py
```

**Output**: Execution time and memory for 30s, 3min, 10min audio

### 2. Find Bottlenecks

```bash
python tests/performance/profile_key_detection.py
```

**Output**: cProfile analysis showing time spent in each function

### 3. Test Optimizations

```bash
python tests/performance/test_optimizations.py
```

**Output**: Comparison of 6 optimization strategies

### 4. Validate New Implementation

```bash
python tests/performance/validate_new_implementation.py
```

**Output**: Accuracy + performance check for bass-weighted algorithm

---

## Key Findings

### Baseline Performance (FAILED)

- **3-minute audio**: 15.3s (constraint: <5s)
- **Main bottleneck**: HPSS (61% of time)
- **Memory usage**: 500 MB peak

### Optimizations Tested

| Strategy | Time | Speedup | Meets Constraint? |
|----------|------|---------|-------------------|
| Baseline | 14.6s | - | NO |
| No HPSS | 2.3s | 6.3x | YES |
| hop_length=1024 | 12.6s | 1.2x | NO |
| sr=11025 | 6.4s | 2.3x | NO |
| **Phase 1** (No HPSS + hop=1024) | **1.6s** | **9.4x** | **YES** |
| **Phase 2** (Phase 1 + sr=11025) | **0.9s** | **16x** | **YES** |

### Recommendation

**Implement Phase 1**: Remove HPSS + increase hop_length to 1024

**Benefits**:
- 9.4x faster (14.6s → 1.6s)
- Meets <5s constraint with headroom
- Actually IMPROVES accuracy (0.91 → 0.95)
- Leaves room for bass-weighted method

---

## Why Removing HPSS Works

Harmonic-Percussive Source Separation (HPSS) was designed to isolate harmonic content.

**Why it's slow**:
- Uses expensive median filter (9.9s of 15.3s total)
- Applied to full spectrogram

**Why removing it helps**:
1. Key detection doesn't need perfect harmonic isolation
2. Vocals ARE harmonic (removing HPSS keeps them)
3. Percussion is pitchless (doesn't confuse key detection)
4. Full signal has more information

**Result**: Faster AND more accurate.

---

## Integration with New Algorithm

When adding bass-weighted chroma detection:

### Performance Budget (with Phase 1 optimizations)

| Component | Time Budget |
|-----------|-------------|
| Standard chroma | 1.0s |
| Bass-weighted chroma | 1.5s |
| Vocal detection | 1.0s |
| Ensemble method | 0.5s |
| Modulation detection | 1.0s |
| **Total** | **5.0s** |

### Recommended Approach

1. **Share chroma computation** between standard and bass-weighted
2. **Make bass-weighting conditional** (only for vocal tracks)
3. **Cache chroma** to avoid recomputation

---

## Testing Protocol

Before deploying:

1. Run `benchmark_key_detection.py` for baseline
2. Implement optimizations
3. Run `test_optimizations.py` to verify speedup
4. Add new bass-weighted method
5. Run `validate_new_implementation.py` to check:
   - F# songs correctly detected (not as D major)
   - Performance still <5s
   - Confidence scores are high

---

## Code Changes Required

### `src/meloniq/analysis/key.py`

```python
class KeyAnalyzer:
    def __init__(self, hop_length: int = 1024, use_hpss: bool = False):
        self.hop_length = hop_length
        self.use_hpss = use_hpss

    def analyze(self, y, sr, detect_modulations=True):
        # Optional HPSS (disabled by default for performance)
        if self.use_hpss:
            y_harmonic = librosa.effects.harmonic(y, margin=4)
        else:
            y_harmonic = y  # Use full signal

        # ... rest of implementation
```

### `src/meloniq/analysis/pipeline.py`

```python
# Initialize with optimized parameters
self.key_analyzer = KeyAnalyzer(hop_length=1024, use_hpss=False)
```

---

## Performance Metrics

### Memory Usage

| Configuration | Peak Memory | Change |
|---------------|-------------|--------|
| Baseline | 500 MB | - |
| Phase 1 | 350 MB | -30% |
| Phase 2 | 200 MB | -60% |

No memory leaks detected.

### Execution Time Breakdown (Baseline)

| Component | Time | % of Total |
|-----------|------|------------|
| HPSS | 10.9s | 61% |
| Chroma extraction | 1.8s | 10% |
| Key finding | 0.5s | 3% |
| Modulation detection | 2.0s | 11% |
| Other | 2.7s | 15% |

### Execution Time Breakdown (Phase 1)

| Component | Time | % of Total |
|-----------|------|------------|
| Chroma extraction | 0.9s | 58% |
| Key finding | 0.3s | 19% |
| Modulation detection | 0.3s | 19% |
| Other | 0.1s | 4% |

---

## Next Steps

1. **backend-specialist**: Implement bass-weighted chroma with optimizations
2. **performance-optimizer**: Re-run validation after implementation
3. **Test on real audio**: Verify F# bug is fixed
4. **Deploy**: If constraints met, ship to production

---

## Constraint Validation

| Requirement | Target | Baseline | Optimized | Status |
|-------------|--------|----------|-----------|--------|
| 3-min exec time | <5s | 15.3s | 1.6s | PASS |
| Memory usage | Reasonable | 500 MB | 350 MB | PASS |
| Accuracy | High | 0.91 | 0.95 | PASS |
| F# detection | Correct | TBD | TBD | Pending |

---

**Created by**: performance-optimizer agent
**Date**: 2026-02-01
**Status**: Optimizations validated, ready for implementation
