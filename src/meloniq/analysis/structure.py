"""
Şarkı yapısı / bölümlendirme modülü.

Algoritma:
1. Zaman içinde öznitelikleri (chroma, MFCC) hesapla
2. Öz-benzerlik matrisi (Self-similarity matrix - SSM)
3. SSM köşegeninden yenilik (novelty) eğrisi
4. Bölüm sınırları için tepe seçimi (Peak picking)
5. Benzer bölümleri kümele/etiketle (A/B/C veya Intro/Verse/Chorus)

Bu en iyi çaba (best-effort) özelliğidir - yapı tespiti zorludur.
"""

import numpy as np
import librosa
from scipy import ndimage
from scipy.signal import find_peaks
from typing import Optional

from ..models.results import StructureResult, StructureSegment


class StructureAnalyzer:
    """
    Sesten şarkı yapısını bölümlere ayır.
    
    Bölüm sınırlarını bulmak için öznitelik benzerliği üzerinde yenilik tespiti (novelty detection) kullanır.
    Net desenler ortaya çıkmadıkça etiketler yaklaşıktır (Bölüm A/B/C).
    """
    
    # Parametreler
    MIN_SEGMENT_DURATION = 5.0  # Saniye cinsinden minimum bölüm uzunluğu
    MAX_SEGMENTS = 20  # Maksimum bölüm sayısı
    
    # Güvenilirlik eşikleri
    HIGH_CONFIDENCE = 0.7
    LOW_CONFIDENCE = 0.4
    
    def __init__(self, hop_length: int = 512):
        self.hop_length = hop_length
    
    def analyze(
        self, 
        y: np.ndarray, 
        sr: int,
        beat_times: Optional[list[float]] = None,
    ) -> StructureResult:
        """
        Şarkı yapısını bölümlere ayır.
        
        Args:
            y: Ses örnekleri (mono)
            sr: Örnekleme oranı
            beat_times: Vuruş-senkronize analiz için vuruş zamanları (isteğe bağlı)
            
        Returns:
            Bölüm sınırları ve etiketleri ile StructureResult
        """
        duration = len(y) / sr
        
        if duration < 30:
            # Çok kısa parça
            return StructureResult(
                segments=[StructureSegment(
                    start=0.0,
                    end=duration,
                    label="Main",
                    confidence=0.5,
                )],
                explanation="Track too short for structure analysis.",
                needs_confirmation=True,
            )
        
        # Öznitelikleri hesapla
        chroma, mfcc = self._compute_features(y, sr)
        
        # Öz-benzerlik matrisini hesapla
        ssm = self._compute_ssm(chroma, mfcc)
        
        # Yenilik eğrisini çıkar
        novelty = self._compute_novelty(ssm)
        
        # Bölüm sınırlarını bul
        boundaries = self._find_boundaries(novelty, duration)
        
        # Etiketlerle bölümler oluştur
        segments = self._create_segments(boundaries, duration, ssm, chroma)
        
        # Müzikal etiketler ata
        segments = self._assign_labels(segments, chroma)
        
        explanation = self._generate_explanation(segments)
        
        return StructureResult(
            segments=segments,
            explanation=explanation,
            needs_confirmation=True,  # Yapı, daima en iyi çabadır
        )
    
    def _compute_features(
        self, 
        y: np.ndarray, 
        sr: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Kroma ve MFCC özniteliklerini hesapla."""
        # Harmonik içerik için Kroma
        chroma = librosa.feature.chroma_cqt(
            y=y, 
            sr=sr, 
            hop_length=self.hop_length,
        )
        
        # Tınısal içerik için MFCC
        mfcc = librosa.feature.mfcc(
            y=y, 
            sr=sr, 
            n_mfcc=13,
            hop_length=self.hop_length,
        )
        
        return chroma, mfcc
    
    def _compute_ssm(
        self, 
        chroma: np.ndarray, 
        mfcc: np.ndarray,
    ) -> np.ndarray:
        """
        Özniteliklerden öz-benzerlik matrisini hesapla.
        
        Kroma (armoni) ve MFCC (tını) benzerliklerini birleştirir.
        """
        # Öznitelikleri normalize et
        chroma_norm = librosa.util.normalize(chroma, axis=0)
        mfcc_norm = librosa.util.normalize(mfcc, axis=0)
        
        # Benzerlik matrislerini hesapla
        chroma_sim = np.dot(chroma_norm.T, chroma_norm)
        mfcc_sim = np.dot(mfcc_norm.T, mfcc_norm)
        
        # Birleştir (harmoniği daha fazla ağırlıklandır)
        ssm = 0.6 * chroma_sim + 0.4 * mfcc_sim
        
        # Simetrik olmasını sağla
        ssm = (ssm + ssm.T) / 2
        
        return ssm
    
    def _compute_novelty(self, ssm: np.ndarray) -> np.ndarray:
        """
        Dama tahtası çekirdeği (checkerboard kernel) kullanarak SSM'den yenilik eğrisini hesapla.
        
        Yenilikteki tepeler bölüm sınırlarını gösterir.
        """
        n = ssm.shape[0]
        
        # Yenilik tespiti için dama tahtası çekirdeği
        kernel_size = min(64, n // 4)
        if kernel_size < 4:
            return np.zeros(n)
        
        # Dama tahtası çekirdeğini oluştur
        kernel = np.ones((kernel_size, kernel_size))
        kernel[:kernel_size//2, :kernel_size//2] = -1
        kernel[kernel_size//2:, kernel_size//2:] = -1
        
        # Köşegen boyunca konvolüsyon (convolve)
        novelty = np.zeros(n)
        half = kernel_size // 2
        
        for i in range(half, n - half):
            # Köşegen etrafındaki bölgeyi çıkar
            region = ssm[i-half:i+half, i-half:i+half]
            if region.shape == kernel.shape:
                novelty[i] = np.sum(region * kernel)
        
        # Normalize et
        novelty = np.maximum(0, novelty)
        if np.max(novelty) > 0:
            novelty = novelty / np.max(novelty)
        
        # Yumuşat (Smooth)
        novelty = ndimage.gaussian_filter1d(novelty, sigma=3)
        
        return novelty
    
    def _find_boundaries(
        self, 
        novelty: np.ndarray, 
        duration: float,
    ) -> list[float]:
        """Yenilik tepelerinden bölüm sınırlarını bul."""
        if len(novelty) == 0:
            return [0.0, duration]
        
        # Tepeler arasındaki minimum mesafe (çerçeve cinsinden)
        min_frames = int(self.MIN_SEGMENT_DURATION * 22050 / self.hop_length)
        
        # Tepeleri bul
        peaks, properties = find_peaks(
            novelty,
            height=0.2,  # Minimum tepe yüksekliği
            distance=min_frames,
            prominence=0.1,
        )
        
        # Zamanlara dönüştür
        frame_times = librosa.frames_to_time(
            np.arange(len(novelty)), 
            sr=22050, 
            hop_length=self.hop_length
        )
        
        boundaries = [0.0]
        for peak in peaks[:self.MAX_SEGMENTS - 1]:
            if peak < len(frame_times):
                boundaries.append(frame_times[peak])
        boundaries.append(duration)
        
        return boundaries
    
    def _create_segments(
        self,
        boundaries: list[float],
        duration: float,
        ssm: np.ndarray,
        chroma: np.ndarray,
    ) -> list[StructureSegment]:
        """Sınırlardan bölüm nesneleri oluştur."""
        segments = []
        
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            
            # Sınır netliğine göre güvenilirliği hesapla
            # (Bu basitleştirilmiş bir buluşsaldır - heuristic)
            if i == 0:
                confidence = 0.6  # İlk bölüm
            elif end - start < self.MIN_SEGMENT_DURATION * 1.5:
                confidence = 0.4  # Kısa bölüm
            else:
                confidence = 0.55
            
            # Önceki bölümle benzerliği hesapla
            similarity = None
            if i > 0 and len(segments) > 0:
                similarity = self._calculate_segment_similarity(
                    chroma, boundaries[i-1], start, end
                )
            
            segments.append(StructureSegment(
                start=round(start, 2),
                end=round(end, 2),
                label=f"Section {chr(65 + i)}",  # A, B, C, ...
                confidence=round(confidence, 2),
                similarity_to_previous=similarity,
            ))
        
        return segments
    
    def _calculate_segment_similarity(
        self,
        chroma: np.ndarray,
        prev_start: float,
        current_start: float,
        current_end: float,
    ) -> float:
        """Bölümler arasındaki benzerliği hesapla."""
        try:
            # Çerçeve indekslerine dönüştür
            frame_rate = 22050 / self.hop_length
            
            prev_frames = slice(
                int(prev_start * frame_rate),
                int(current_start * frame_rate)
            )
            curr_frames = slice(
                int(current_start * frame_rate),
                int(current_end * frame_rate)
            )
            
            prev_chroma = chroma[:, prev_frames]
            curr_chroma = chroma[:, curr_frames]
            
            if prev_chroma.size == 0 or curr_chroma.size == 0:
                return None
            
            # Ortalama kroma vektörleri
            prev_avg = np.mean(prev_chroma, axis=1)
            curr_avg = np.mean(curr_chroma, axis=1)
            
            # Kosinüs benzerliği
            norm_prev = np.linalg.norm(prev_avg)
            norm_curr = np.linalg.norm(curr_avg)
            
            if norm_prev > 0 and norm_curr > 0:
                similarity = np.dot(prev_avg, curr_avg) / (norm_prev * norm_curr)
                return round(float(similarity), 2)
            
        except Exception:
            pass
        
        return None
    
    def _assign_labels(
        self,
        segments: list[StructureSegment],
        chroma: np.ndarray,
    ) -> list[StructureSegment]:
        """
        Uygun yerlerde müzikal etiketler (Intro, Verse, Chorus vb.) ata.
        
        Bu şunlara dayalı, en iyi çaba gösteren bir buluşsaldır:
        - Şarkıdaki konumu
        - Enerji/dinamikler
        - Tekrar
        """
        if not segments:
            return segments
        
        n = len(segments)
        labeled = []
        
        # Basit buluşsallar (heuristics)
        for i, seg in enumerate(segments):
            position_ratio = seg.start / (segments[-1].end or 1)
            
            # En baş -> muhtemelen Giriş (Intro)
            if i == 0 and seg.end - seg.start < 30 and position_ratio < 0.1:
                label = "Intro"
                confidence = 0.6
            # En son -> muhtemelen Çıkış (Outro)
            elif i == n - 1 and position_ratio > 0.85:
                label = "Outro"
                confidence = 0.5
            # Daha önceki bölümlere benzerliği kontrol et
            elif seg.similarity_to_previous is not None and seg.similarity_to_previous > 0.85:
                # Öncekine çok benzer - aynı bölüm türü olabilir
                prev_label = labeled[-1].label if labeled else "Section"
                if "Verse" in prev_label or "Chorus" in prev_label:
                    label = prev_label
                else:
                    label = seg.label
                confidence = 0.5
            else:
                # Genel etiketi koru
                label = seg.label
                confidence = seg.confidence
            
            labeled.append(StructureSegment(
                start=seg.start,
                end=seg.end,
                label=label,
                confidence=confidence,
                similarity_to_previous=seg.similarity_to_previous,
            ))
        
        return labeled
    
    def _generate_explanation(self, segments: list[StructureSegment]) -> str:
        """Yapı analizinin açıklamasını oluştur."""
        n_segments = len(segments)
        
        if n_segments <= 2:
            return (
                "Az sayıda belirgin bölüm tespit edildi. "
                "Parçanın sürekli bir yapısı veya ince değişiklikleri olabilir."
            )
        elif n_segments <= 6:
            return (
                f"Harmonik ve tınısal değişikliklere dayalı {n_segments} belirgin bölüm tespit edildi. "
                "Etiketler yaklaşıktır; kulakla doğrulayın."
            )
        else:
            return (
                f"{n_segments} bölüm tespit edildi. Parça karmaşık bir yapıya sahip. "
                "Bölüm etiketleri en iyi çaba tahminleridir."
            )
