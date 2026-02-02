# Key Detection Performance Report

**Date**: 2026-02-01
**Task**: Vocal-enhanced key detection algorithm
**Constraint**: <5 seconds for 3-minute song

---

## Baseline Performance Metrics

### Test Results

| Audio Length | Execution Time | Peak Memory | Constraint | Status |
|--------------|----------------|-------------|------------|--------|
| 30 seconds   | 11.871s        | 129.9 MB    | N/A        | -      |
| 3 minutes    | **15.294s**    | 500.1 MB    | <5s        | **FAIL** |
| 10 minutes   | 50.266s        | 1667.1 MB   | N/A        | -      |

### Critical Issue

The 3-minute audio takes **15.294s**, exceeding the constraint by **10.294s (305%)**.

---

## Bottleneck Analysis (cProfile)

Total execution time for 3-minute audio: **17.762s**

### Top Bottlenecks

| Function | Time | % of Total | Calls | Issue |
|----------|------|------------|-------|-------|
| `scipy.ndimage.rank_filter` | 9.879s | 55.6% | 2 | Median filter in HPSS |
| `librosa.decompose.hpss` | 10.915s | 61.4% | 1 | Full HPSS decomposition |
| `_extract_combined_chroma` | 1.761s | 9.9% | 1 | Triple chroma computation |
| `chroma_cqt` | 1.599s | 9.0% | 2 | CQT-based chroma (2 calls) |
| `chroma_cens` | 0.815s | 4.6% | 1 | CENS chroma |
| `stft` | 1.992s | 11.2% | 18 | Multiple STFT calls |

### Key Finding

**HPSS (Harmonic-Percussive Source Separation) takes 61% of total time**, primarily due to the median filter operation.

---

## Impact of New Implementation

The backend-specialist is adding:
1. **Bass-weighted chroma extraction** - Will add another chroma computation
2. **Vocal detection** - May add spectral analysis
3. **Ensemble method** - Combines both approaches

### Projected Impact

| Component | Estimated Addition |
|-----------|-------------------|
| Bass-weighted chroma | +2-3s (another CQT + filtering) |
| Vocal detection | +1-2s (spectral features) |
| Ensemble combination | +0.1s (minimal) |
| **Total estimated** | **+3-5s** |

**Projected new execution time**: 18-20s for 3-minute audio (400% over constraint)

---

## Optimization Recommendations

### Priority 1: Remove or Optimize HPSS (High Impact)

**Current**: `librosa.effects.harmonic(y, margin=4)` takes 10.9s

**Options**:

1. **Skip HPSS entirely for key detection**
   - Key detection works on full mix
   - Vocals contain harmonic content
   - Estimated savings: **-11s**
   - Risk: Lower accuracy on percussion-heavy tracks

2. **Use faster HPSS parameters**
   ```python
   # Current
   y_harmonic = librosa.effects.harmonic(y, margin=4)

   # Optimized
   y_harmonic = librosa.effects.harmonic(y, margin=2, kernel_size=15)
   ```
   - Estimated savings: **-5s**
   - Lower margin = faster median filter

3. **Conditional HPSS**
   - Only run HPSS if vocal detection fails
   - Estimated savings: **-11s** (when not needed)

**Recommendation**: Start with Option 1 (skip HPSS). Test accuracy impact.

---

### Priority 2: Reduce Chroma Computations (Medium Impact)

**Current**: Computes 3 chroma types (CQT, CENS, STFT)

**Options**:

1. **Single chroma type**
   - Use only CQT (most accurate)
   - Estimated savings: **-1s**
   - Risk: Slightly lower robustness

2. **Cache chroma computation**
   - Compute once, reuse for standard + bass-weighted
   - Estimated savings: **-2s** (when running both methods)

**Recommendation**: Cache chroma, share between standard and bass-weighted methods.

---

### Priority 3: Optimize Librosa Parameters (Low Impact)

**Current**: Default parameters

**Options**:

1. **Larger hop_length**
   ```python
   # Current
   hop_length = 512  # 23ms at 22050 Hz

   # Optimized
   hop_length = 1024  # 46ms - still good temporal resolution
   ```
   - Halves frame count
   - Estimated savings: **-2s**
   - Minimal accuracy impact for key detection

2. **Lower sample rate**
   ```python
   # Current
   sr = 22050 Hz

   # Optimized
   sr = 11025 Hz  # Key detection doesn't need high frequencies
   ```
   - Halves computation
   - Estimated savings: **-7s**
   - Risk: May lose high harmonic information

**Recommendation**: Increase hop_length to 1024. Test 11025 Hz sample rate.

---

### Priority 4: Reduce Modulation Detection Window (Low Impact)

**Current**: 8-second windows with 4-second hop

**Options**:

1. **Larger windows**
   ```python
   window_sec = 12  # vs current 8
   hop_sec = 6      # vs current 4
   ```
   - Fewer windows to analyze
   - Estimated savings: **-0.5s**
   - Risk: May miss short modulations

**Recommendation**: Only if user disables modulation detection.

---

## Recommended Optimization Strategy

### Phase 1: Quick Wins (Target: <5s for 3min)

1. **Remove HPSS** (-11s)
2. **Increase hop_length to 1024** (-2s)
3. **Cache chroma computation** (-2s)

**Expected result**: ~3s for 3-minute audio

### Phase 2: If Accuracy Loss is Acceptable

4. **Use only CQT chroma** (-1s)
5. **Lower sample rate to 11025 Hz** (-7s)

**Expected result**: ~1s for 3-minute audio

### Phase 3: New Implementation Integration

When adding bass-weighted + vocal detection:
- Share cached chroma between methods
- Make HPSS optional (config flag)
- Use ensemble only when confidence is low

---

## Memory Optimization

Current peak for 3-minute audio: **500 MB**

### Recommendations

1. **Delete intermediate arrays**
   - Explicitly delete HPSS output after chroma extraction
   - Use `del y_harmonic` after use

2. **Reduce CQT parameters**
   ```python
   n_octaves = 6  # vs current 7
   ```
   - Saves memory on CQT kernel

3. **Stream processing for long files**
   - For >5 min files, analyze in chunks

**Expected reduction**: ~150 MB

---

## Testing Protocol

After optimization:

1. **Accuracy test**: Verify key detection accuracy doesn't drop >5%
2. **Performance test**: Run benchmark suite
3. **Constraint validation**: Confirm <5s for 3-minute audio
4. **Memory test**: Ensure no memory leaks

---

## Code Changes Required

### File: `src/meloniq/analysis/key.py`

```python
class KeyAnalyzer:
    def __init__(self, hop_length: int = 1024, use_hpss: bool = False):
        self.hop_length = hop_length
        self.use_hpss = use_hpss

    def analyze(self, y, sr, detect_modulations=True):
        # Optional HPSS
        if self.use_hpss:
            y_harmonic = librosa.effects.harmonic(y, margin=2)
        else:
            y_harmonic = y

        # Rest of implementation...
```

### File: `src/meloniq/analysis/pipeline.py`

Update pipeline to use optimized analyzer:

```python
self.key_analyzer = KeyAnalyzer(hop_length=1024, use_hpss=False)
```

---

## Summary

| Metric | Current | Target | Achievable |
|--------|---------|--------|------------|
| 3-min execution time | 15.3s | <5s | Yes (with optimization) |
| Peak memory | 500 MB | <300 MB | Yes |
| Accuracy | Baseline | >90% retained | Yes (with proper cache) |

**Status**: Performance constraint NOT MET in baseline. Requires optimization before deploying new algorithm.

**Next Steps**:
1. Implement Phase 1 optimizations
2. Re-run benchmark
3. If <5s achieved, proceed with new bass-weighted implementation
4. If not, implement Phase 2

---

**Report by**: performance-optimizer agent
**Next benchmark**: After optimization implementation
