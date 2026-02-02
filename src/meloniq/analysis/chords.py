"""
Akor algılama modülü (isteğe bağlı, en iyi çaba).

Algoritma:
1. Kromagram hesapla
2. Vuruş-senkronize kroma (her vuruş için bir kroma vektörü)
3. Akor şablonlarına göre eşleştirme
4. Hızlı akor değişimlerini önlemek için yumuşatma (smoothing)

UYARI: Sesten akor algılama doğası gereği yaklaşık bir işlemdir.
Daima kulakla doğrulayın.
"""

import numpy as np
import librosa
from typing import Optional

from ..models.results import ChordResult, ChordSegment


class ChordAnalyzer:
    """
    Sesten akorları algıla (en iyi çaba, yaklaşık).
    
    Temel majör/minör akor şablonlarına karşı şablon eşleştirme kullanır.
    Sonuçlar daima kulakla doğrulanmalıdır.
    """
    
    # Akor şablonları (perde sınıfı vektörleri)
    # Majör: 1, 3, 5
    # Minör: 1, b3, 5
    
    PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # Majör akor için şablon (kök pozisyon vurgusu)
    MAJOR_TEMPLATE = np.array([1.0, 0, 0, 0, 0.8, 0, 0, 0.7, 0, 0, 0, 0])
    
    # Minör akor için şablon
    MINOR_TEMPLATE = np.array([1.0, 0, 0, 0.8, 0, 0, 0, 0.7, 0, 0, 0, 0])
    
    # Diminished (eksik) akor için şablon
    DIM_TEMPLATE = np.array([1.0, 0, 0, 0.8, 0, 0, 0.7, 0, 0, 0, 0, 0])
    
    # Augmented (artık) akor için şablon
    AUG_TEMPLATE = np.array([1.0, 0, 0, 0, 0.8, 0, 0, 0, 0.7, 0, 0])
    
    # Bir akoru raporlamak için minimum güvenilirlik
    MIN_CONFIDENCE = 0.4
    
    def __init__(self, hop_length: int = 512):
        self.hop_length = hop_length
        
        # Build all chord templates
        self.templates = self._build_templates()
    
    def _build_templates(self) -> dict[str, np.ndarray]:
        """Tüm kökler ve nitelikler için akor şablonları oluştur."""
        templates = {}
        
        for i, root in enumerate(self.PITCH_CLASSES):
            # Majör
            templates[root] = np.roll(self.MAJOR_TEMPLATE, i)
            
            # Minör
            templates[f"{root}m"] = np.roll(self.MINOR_TEMPLATE, i)
            
            # Diminished - Eksik (daha az yaygın, düşük öncelikli)
            templates[f"{root}dim"] = np.roll(self.DIM_TEMPLATE, i)
        
        # Tüm şablonları normalize et
        for chord, template in templates.items():
            templates[chord] = template / np.linalg.norm(template)
        
        return templates
    
    def analyze(
        self,
        y: np.ndarray,
        sr: int,
        beat_times: Optional[list[float]] = None,
        enabled: bool = True,
    ) -> ChordResult:
        """
        Akorları algıla (en iyi çaba).
        
        Args:
            y: Ses örnekleri (mono)
            sr: Örnekleme oranı
            beat_times: Vuruş-senkronize analiz için vuruş zamanları
            enabled: Akor algılamanın yapılıp yapılmayacağı
            
        Returns:
            Akor bölümleri ve sorumluluk reddi içeren ChordResult
        """
        if not enabled:
            return ChordResult(
                enabled=False,
                warning="Chord detection disabled.",
                segments=[],
                needs_confirmation=True,
            )
        
        duration = len(y) / sr
        
        # Kromagram hesapla
        chroma = librosa.feature.chroma_cqt(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
        )
        
        # Vuruşlar sağlandıysa vuruş-senkronize kroma kullan
        if beat_times and len(beat_times) > 2:
            segments = self._beat_sync_chords(chroma, sr, beat_times, duration)
        else:
            segments = self._windowed_chords(chroma, sr, duration)
        
        # Akor dizisini yumuşat
        segments = self._smooth_chords(segments)
        
        return ChordResult(
            enabled=True,
            warning="Chord detection is approximate; verify by ear.",
            segments=segments,
            needs_confirmation=True,
        )
    
    def _beat_sync_chords(
        self,
        chroma: np.ndarray,
        sr: int,
        beat_times: list[float],
        duration: float,
    ) -> list[ChordSegment]:
        """Her vuruş için bir akor algıla."""
        segments = []
        
        # Vuruş zamanlarını çerçevelere dönüştür
        beat_frames = librosa.time_to_frames(
            beat_times,
            sr=sr,
            hop_length=self.hop_length,
        )
        
        for i in range(len(beat_frames) - 1):
            start_frame = beat_frames[i]
            end_frame = beat_frames[i + 1]
            
            if end_frame > start_frame and end_frame <= chroma.shape[1]:
                # Average chroma in this beat
                beat_chroma = np.mean(chroma[:, start_frame:end_frame], axis=1)
                
                # Find best matching chord
                chord, confidence = self._match_chord(beat_chroma)
                
                if confidence >= self.MIN_CONFIDENCE:
                    segments.append(ChordSegment(
                        start=beat_times[i],
                        end=beat_times[i + 1],
                        chord=chord,
                        confidence=round(confidence, 2),
                    ))
        
        return segments
    
    def _windowed_chords(
        self,
        chroma: np.ndarray,
        sr: int,
        duration: float,
    ) -> list[ChordSegment]:
        """Sabit pencerelerde akorları algıla (vuruşsuz yedek)."""
        window_sec = 0.5  # 500ms windows
        hop_sec = 0.25  # 250ms hop
        
        window_frames = int(window_sec * sr / self.hop_length)
        hop_frames = int(hop_sec * sr / self.hop_length)
        
        segments = []
        frame = 0
        
        while frame < chroma.shape[1] - window_frames:
            # Average chroma in window
            window_chroma = np.mean(chroma[:, frame:frame + window_frames], axis=1)
            
            # Find best matching chord
            chord, confidence = self._match_chord(window_chroma)
            
            start_time = frame * self.hop_length / sr
            end_time = (frame + window_frames) * self.hop_length / sr
            
            if confidence >= self.MIN_CONFIDENCE:
                segments.append(ChordSegment(
                    start=round(start_time, 2),
                    end=round(end_time, 2),
                    chord=chord,
                    confidence=round(confidence, 2),
                ))
            
            frame += hop_frames
        
        return segments
    
    def _match_chord(self, chroma: np.ndarray) -> tuple[str, float]:
        """Bir kroma vektörü için en iyi eşleşen akoru bul."""
        if np.sum(chroma) == 0:
            return "N.C.", 0.0  # No chord (silence)
        
        # Normalize
        chroma_norm = chroma / np.linalg.norm(chroma)
        
        best_chord = "N.C."
        best_score = 0.0
        
        for chord, template in self.templates.items():
            # Cosine similarity
            score = np.dot(chroma_norm, template)
            
            if score > best_score:
                best_score = score
                best_chord = chord
        
        return best_chord, best_score
    
    def _smooth_chords(
        self,
        segments: list[ChordSegment],
        min_duration: float = 0.3,
    ) -> list[ChordSegment]:
        """
        Ardışık aynı akorları birleştirerek ve çok kısa bölümleri kaldırarak
        akor dizisini yumuşat.
        """
        if not segments:
            return segments
        
        smoothed = []
        current = segments[0]
        
        for seg in segments[1:]:
            if seg.chord == current.chord:
                # Öncekiyle birleştir
                current = ChordSegment(
                    start=current.start,
                    end=seg.end,
                    chord=current.chord,
                    confidence=min(current.confidence, seg.confidence),
                )
            else:
                # Mevcut bölümün yeterince uzun olup olmadığını kontrol et
                if current.end - current.start >= min_duration:
                    smoothed.append(current)
                current = seg
        
        # Son bölümü unutma
        if current.end - current.start >= min_duration:
            smoothed.append(current)
        
        return smoothed
