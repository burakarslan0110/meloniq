"""
Ses şiddeti ve ses istatistikleri modülü.

Şunları hesaplar:
- Entegre LUFS (ses şiddeti)
- Kısa dönem ses şiddeti eğrisi
- Gerçek tepe (true peak) seviyesi
- Dinamik aralık (tepe faktörü)
- Spektral parlaklık eğrisi
- Akort referansı tahmini
"""

import numpy as np
import librosa
from typing import Optional

try:
    import pyloudnorm as pyln
    PYLOUDNORM_AVAILABLE = True
except ImportError:
    PYLOUDNORM_AVAILABLE = False

from ..models.results import AudioStats


class LoudnessAnalyzer:
    """
    Ses şiddetini ve teknik ses istatistiklerini analiz et.
    
    Müzisyenler için yararlı ölçümler sağlar:
    - Parça ne kadar yüksek sesli (LUFS)?
    - Dinamik aralık nedir?
    - Akort standart mı (A=440Hz)?
    - Parça nerede en parlak/karanlık?
    """
    
    def __init__(self, hop_length: int = 512):
        self.hop_length = hop_length
    
    def analyze(
        self, 
        y: np.ndarray, 
        sr: int,
        estimate_tuning: bool = True,
    ) -> AudioStats:
        """
        Ses şiddetini ve ses istatistiklerini analiz et.
        
        Args:
            y: Ses örnekleri (mono veya stereo olabilir)
            sr: Örnekleme oranı
            estimate_tuning: Akort referansının tahmin edilip edilmeyeceği
            
        Returns:
            Ses şiddeti, tepeler, dinamikler ve eğriler içeren AudioStats
        """
        # Ses şiddeti analizi için uygun şekli sağla
        y_for_lufs = self._prepare_for_lufs(y)
        
        # LUFS ölçümü
        lufs_integrated, lufs_short_term_max = self._measure_lufs(y_for_lufs, sr)
        
        # Gerçek tepe (True peak)
        peak_dbfs = self._measure_peak(y)
        
        # Dinamik aralık
        dynamic_range = self._measure_dynamic_range(y, sr)
        
        # Parlaklık eğrisi
        brightness_curve = self._compute_brightness(y if y.ndim == 1 else y[0], sr)
        
        # Ses şiddeti eğrisi
        loudness_curve = self._compute_loudness_curve(y_for_lufs, sr)
        
        # Akort tahmini
        tuning_ref = 440.0
        tuning_deviation = 0.0
        if estimate_tuning:
            tuning_ref, tuning_deviation = self._estimate_tuning(
                y if y.ndim == 1 else y[0], sr
            )
        
        return AudioStats(
            lufs_integrated=round(lufs_integrated, 1),
            lufs_short_term_max=round(lufs_short_term_max, 1),
            peak_dbfs=round(peak_dbfs, 1),
            dynamic_range=round(dynamic_range, 1),
            brightness_curve=brightness_curve,
            loudness_curve=loudness_curve,
            tuning_reference=round(tuning_ref, 1),
            tuning_deviation_cents=round(tuning_deviation, 1),
        )
    
    def _prepare_for_lufs(self, y: np.ndarray) -> np.ndarray:
        """LUFS ölçümü için sesi hazırla (stereo için 2D gerekli)."""
        if y.ndim == 1:
            # Mono: shape (n_samples,) -> (1, n_samples) for pyloudnorm
            return y.reshape(1, -1)
        elif y.ndim == 2:
            # Already 2D
            if y.shape[0] <= 2:  # (channels, samples)
                return y
            else:  # (samples, channels)
                return y.T
        return y
    
    def _measure_lufs(
        self, 
        y: np.ndarray, 
        sr: int,
    ) -> tuple[float, float]:
        """Entegre ve kısa dönem LUFS ölç."""
        if not PYLOUDNORM_AVAILABLE:
            return self._fallback_lufs(y, sr)
        
        try:
            # pyloudnorm stereo için (samples, channels) bekler
            if y.ndim == 2:
                y_pyln = y.T if y.shape[0] <= 2 else y
            else:
                y_pyln = y
            
            meter = pyln.Meter(sr)
            
            # Entegre ses şiddeti
            integrated = meter.integrated_loudness(y_pyln)
            
            # Kısa dönem ses şiddeti (3 saniyelik pencereler)
            # Pencereli ölçümlerin maksimumunu hesaplayacağız
            window_size = int(3 * sr)
            hop_size = int(0.5 * sr)
            
            samples = y_pyln if y_pyln.ndim == 1 else y_pyln[:, 0]
            n_samples = len(samples)
            
            short_term_values = []
            for start in range(0, n_samples - window_size, hop_size):
                window = y_pyln[start:start + window_size] if y_pyln.ndim == 1 else y_pyln[start:start + window_size, :]
                try:
                    st_lufs = meter.integrated_loudness(window)
                    if not np.isinf(st_lufs) and not np.isnan(st_lufs):
                        short_term_values.append(st_lufs)
                except Exception:
                    pass
            
            short_term_max = max(short_term_values) if short_term_values else integrated
            
            return integrated, short_term_max
            
        except Exception:
            return self._fallback_lufs(y, sr)
    
    def _fallback_lufs(
        self, 
        y: np.ndarray, 
        sr: int,
    ) -> tuple[float, float]:
        """RMS kullanarak yedek LUFS tahmini."""
        # Simple RMS-based approximation
        if y.ndim == 2:
            y_mono = np.mean(y, axis=0)
        else:
            y_mono = y
        
        rms = np.sqrt(np.mean(y_mono ** 2))
        
        # RMS'den yaklaşık LUFS (çok kaba)
        # LUFS ≈ 20 * log10(rms) - 0.691 (K-ağırlıklandırma yaklaşımı)
        if rms > 0:
            lufs_approx = 20 * np.log10(rms) - 0.691
        else:
            lufs_approx = -70.0
        
        return lufs_approx, lufs_approx + 3  # Kısa dönem genellikle ~3dB daha yüksek
    
    def _measure_peak(self, y: np.ndarray) -> float:
        """dBFS cinsinden gerçek tepe seviyesini ölç."""
        # Maksimum mutlak örnek değerini bul
        if y.ndim == 2:
            peak = np.max(np.abs(y))
        else:
            peak = np.max(np.abs(y))
        
        # Convert to dBFS
        if peak > 0:
            peak_dbfs = 20 * np.log10(peak)
        else:
            peak_dbfs = -96.0
        
        return peak_dbfs
    
    def _measure_dynamic_range(
        self, 
        y: np.ndarray, 
        sr: int,
    ) -> float:
        """
        Dinamik aralığı ölç (dB cinsinden tepe faktörü).
        
        Tepe faktörü = Tepe / RMS
        Yüksek değerler = daha dinamik, düşük = daha sıkıştırılmış.
        """
        if y.ndim == 2:
            y_mono = np.mean(y, axis=0)
        else:
            y_mono = y
        
        # RMS
        rms = np.sqrt(np.mean(y_mono ** 2))
        
        # Peak
        peak = np.max(np.abs(y_mono))
        
        # Crest factor in dB
        if rms > 0:
            crest_db = 20 * np.log10(peak / rms)
        else:
            crest_db = 0.0
        
        return crest_db
    
    def _compute_brightness(
        self, 
        y: np.ndarray, 
        sr: int,
    ) -> list[tuple[float, float]]:
        """
        Spektral ağırlık merkezi (parlaklık) eğrisini hesapla.
        
        (zaman, parlaklık) demetlerinin listesini döndürür.
        Parlaklık 0-1 aralığına normalize edilir.
        """
        # Spectral centroid
        centroid = librosa.feature.spectral_centroid(
            y=y, 
            sr=sr, 
            hop_length=self.hop_length,
        )[0]
        
        # Times
        times = librosa.frames_to_time(
            np.arange(len(centroid)),
            sr=sr,
            hop_length=self.hop_length,
        )
        
        # Parlaklığı normalize et (tipik merkez aralığı: 500-8000 Hz)
        centroid_normalized = np.clip((centroid - 500) / 7500, 0, 1)
        
        # Çıktı için örneklemeyi azalt (her ~0.5 saniyede bir)
        hop_output = max(1, int(0.5 * sr / self.hop_length))
        
        curve = [
            (round(float(times[i]), 2), round(float(centroid_normalized[i]), 3))
            for i in range(0, len(times), hop_output)
        ]
        
        return curve
    
    def _compute_loudness_curve(
        self, 
        y: np.ndarray, 
        sr: int,
    ) -> list[tuple[float, float]]:
        """
        Kısa dönem ses şiddeti eğrisini hesapla.
        
        (zaman, loudness_lufs) demetlerinin listesini döndürür.
        """
        if y.ndim == 2:
            y_mono = np.mean(y, axis=0)
        else:
            y_mono = y
        
        # Pencere tabanlı RMS
        window_size = int(0.4 * sr)  # 400ms pencereler (kısa dönem)
        hop_size = int(0.1 * sr)  # 100ms hop
        
        curve = []
        
        for start in range(0, len(y_mono) - window_size, hop_size):
            window = y_mono[start:start + window_size]
            rms = np.sqrt(np.mean(window ** 2))
            
            if rms > 0:
                # Approximate LUFS
                loudness = 20 * np.log10(rms) - 0.691
            else:
                loudness = -70.0
            
            time = start / sr
            curve.append((round(time, 2), round(loudness, 1)))
        
        return curve
    
    def _estimate_tuning(
        self, 
        y: np.ndarray, 
        sr: int,
    ) -> tuple[float, float]:
        """
        Akort referans frekansını tahmin et.
        
        (A4_frekansı, sapma_sent) döndürür.
        Çoğu müzik A4=440Hz kullanır, ancak bazıları 432Hz, 442Hz vb. kullanır.
        """
        try:
            # Perde tahmini için librosa'nın piptrack fonksiyonunu kullan
            pitches, magnitudes = librosa.piptrack(
                y=y, 
                sr=sr,
                hop_length=self.hop_length,
                threshold=0.1,
            )
            
            # En belirgin perdeleri al
            prominent_pitches = []
            
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                
                if pitch > 0:
                    prominent_pitches.append(pitch)
            
            if not prominent_pitches:
                return 440.0, 0.0
            
            # A notalarına yakın perdeleri bul (440Hz'in oktavları)
            a_freqs = [440 * (2 ** octave) for octave in range(-4, 5)]
            
            deviations = []
            for pitch in prominent_pitches:
                for a_freq in a_freqs:
                    # Perdenin bir A notasına yakın olup olmadığını kontrol et
                    ratio = pitch / a_freq
                    cents = 1200 * np.log2(ratio)
                    
                    if abs(cents) < 50:  # Bir A'nın 50 sent içinde
                        deviations.append(cents)
            
            if not deviations:
                return 440.0, 0.0
            
            # Medyan sapma
            median_deviation = np.median(deviations)
            
            # Gerçek A4 frekansını hesapla
            a4_estimated = 440.0 * (2 ** (median_deviation / 1200))
            
            return a4_estimated, median_deviation
            
        except Exception:
            return 440.0, 0.0
