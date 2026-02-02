"""
Geliştirilmiş Ton / tonalite algılama modülü.

Algoritma (artırılmış doğruluk):
1. Armonik/Vurmalı kaynak ayrımı (HPSS)
2. Çok çözünürlüklü kroma çıkarımı (CQT + CENS + STFT)
3. Çoklu profilli Krumhansl-Schmuckler algoritması
4. Ağırlıklı korelasyon puanlaması
5. Relatif majör/minör ayrımı
6. Ton netliğine dayalı güven puanlaması

Essentia, MIREX değerlendirmeleri ve müzik teorisi araştırmalarına dayanmaktadır.
"""

import numpy as np
import librosa
from typing import Optional, Tuple, List
from enum import Enum

from ..models.results import KeyResult, KeyCandidate, KeySegment


class KeyProfile(Enum):
    """Farklı türler için mevcut ton profili tipleri."""
    KRUMHANSL = "krumhansl"      # Genel - bilişsel deneyler
    TEMPERLEY = "temperley"      # Klasik müzik
    SHAATH = "shaath"            # Pop/Elektronik
    EDMM = "edmm"                # EDM - derlem tabanlı


class KeyAnalyzer:
    """
    Yüksek doğruluklu müzikal ton/tonalite analizcisi.
    
    Krumhansl-Schmuckler algoritması ve ağırlıklı çoklu profil eşleştirme ile 
    birleştirilmiş çoklu kroma özellikleri kullanır.
    """
    
    # Perde sınıfı isimleri
    PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # Enharmonik eşdeğerler için alternatif isimler
    ENHARMONIC = {
        'C#': 'Db', 'D#': 'Eb', 'F#': 'Gb', 'G#': 'Ab', 'A#': 'Bb'
    }
    
    # ========== TON PROFİLLERİ (normalize edilmiş) ==========
    # Bunlar müzik biliş araştırmalarından elde edilen en doğru profillerdir
    
    # Krumhansl-Kessler (1990) - bilişsel deneyler, en yaygın kullanılan
    KRUMHANSL_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    KRUMHANSL_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    
    # Temperley (1999) - klasik müzik derlemi için optimize edilmiş
    TEMPERLEY_MAJOR = np.array([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0])
    TEMPERLEY_MINOR = np.array([5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0])
    
    # Shaath (2011) - pop/elektronik müzik için optimize edilmiş
    SHAATH_MAJOR = np.array([6.6, 2.0, 3.5, 2.3, 4.6, 4.0, 2.5, 5.2, 2.4, 3.8, 2.3, 3.4])
    SHAATH_MINOR = np.array([6.5, 2.8, 3.5, 5.4, 2.7, 3.5, 2.5, 5.2, 4.0, 2.7, 4.3, 3.2])
    
    # EDMA (Elektronik Dans Müziği Analizi) - derlem tabanlı
    EDMM_MAJOR = np.array([7.0, 1.8, 3.2, 1.8, 4.8, 3.8, 2.2, 5.5, 2.0, 3.5, 2.0, 3.0])
    EDMM_MINOR = np.array([7.0, 2.5, 3.0, 5.8, 2.2, 3.5, 2.2, 5.5, 4.2, 2.5, 4.5, 2.8])
    
    # Eşikler
    HIGH_CONFIDENCE = 0.70
    MEDIUM_CONFIDENCE = 0.55
    LOW_CONFIDENCE = 0.40
    
    def __init__(self, hop_length: int = 512):
        self.hop_length = hop_length
        self._init_profiles()
    
    def _init_profiles(self):
        """Tüm ton profillerini başlat ve normalize et."""
        self.profiles = {
            'krumhansl': {
                'major': self._normalize(self.KRUMHANSL_MAJOR),
                'minor': self._normalize(self.KRUMHANSL_MINOR),
                'weight': 1.0  # Referans ağırlık
            },
            'temperley': {
                'major': self._normalize(self.TEMPERLEY_MAJOR),
                'minor': self._normalize(self.TEMPERLEY_MINOR),
                'weight': 0.9
            },
            'shaath': {
                'major': self._normalize(self.SHAATH_MAJOR),
                'minor': self._normalize(self.SHAATH_MINOR),
                'weight': 1.1  # Modern müzik için iyi
            },
            'edmm': {
                'major': self._normalize(self.EDMM_MAJOR),
                'minor': self._normalize(self.EDMM_MINOR),
                'weight': 0.8
            }
        }
    
    def _normalize(self, profile: np.ndarray) -> np.ndarray:
        """Korelasyon için profili sıfır ortalama ve birim varyansa normalize et."""
        return (profile - np.mean(profile)) / np.std(profile)
    
    def analyze(
        self,
        y: np.ndarray,
        sr: int,
        detect_modulations: bool = True,
    ) -> KeyResult:
        """
        Ton/tonaliteyi yüksek doğrulukla analiz et.

        Args:
            y: Ses örnekleri (mono)
            sr: Örnekleme oranı
            detect_modulations: Ton değişimlerinin algılanıp algılanmayacağı

        Returns:
            Ton, güven, alternatifler ve bölümler içeren KeyResult
        """
        # Adım 1: Armonik içeriği ayır (davul/perküsyonu kaldırır)
        y_harmonic = librosa.effects.harmonic(y, margin=4)

        # Adım 2: A440'tan akort sapmasını tahmin et
        tuning = librosa.estimate_tuning(y=y_harmonic, sr=sr)

        # Adım 3: Vokal tespiti yap
        vocal_detected, vocal_confidence = self._detect_vocals(y, sr)

        # Adım 4: Vokal varlığına göre kroma stratejisi seç
        if vocal_detected:
            # Vokal varsa: bas ağırlıklı kroma (harmony foundation) + standart kroma
            bass_chroma = self._extract_bass_weighted_chroma(y_harmonic, sr, tuning)
            standard_chroma = self._extract_combined_chroma(y_harmonic, sr, tuning)
            # Bas ağırlıklı kromaya öncelik ver (harmonic foundation daha güvenilir)
            chroma = 0.70 * bass_chroma + 0.30 * standard_chroma
        else:
            # Vokal yoksa: standart çoklu kroma yaklaşımı
            chroma = self._extract_combined_chroma(y_harmonic, sr, tuning)

        # Adım 5: Global kroma profilini al (ağırlıklı ortalama)
        global_chroma = self._get_weighted_chroma(chroma)

        # Adım 6: Çok profilli Krumhansl-Schmuckler kullanarak tonu bul
        global_key, confidence, all_scores = self._find_key(global_chroma)

        # Adım 7: Alternatif tonları al
        alternatives = self._get_alternatives(all_scores, global_key, confidence)

        # Adım 8: Ton bölümlerini/modülasyonlarını algıla
        segments = []
        if detect_modulations:
            segments = self._detect_modulations(chroma, sr)

        # Adım 9: Açıklama oluştur
        explanation = self._generate_explanation(global_key, confidence, alternatives)

        return KeyResult(
            global_key=global_key,
            confidence=confidence,
            explanation=explanation,
            needs_confirmation=confidence < self.MEDIUM_CONFIDENCE,
            alternatives=alternatives,
            segments=segments,
            is_chromatic=confidence < self.LOW_CONFIDENCE,
            vocal_detected=vocal_detected,
        )
    
    def _detect_vocals(self, y: np.ndarray, sr: int) -> Tuple[bool, float]:
        """
        Ses sinyalinde vokal varlığını tespit et.

        Kullanır:
        - Spectral centroid: >1500 Hz vokal frekans aralığını gösterir
        - Zero-crossing rate: Yüksek ZCR sessiz harfleri/sibilance'ı gösterir

        Returns:
            (vocal_detected: bool, confidence: float)
        """
        # Spektral merkezi hesapla (parlaklık göstergesi)
        spectral_centroids = librosa.feature.spectral_centroid(
            y=y, sr=sr, hop_length=self.hop_length
        )[0]

        # Sıfır geçiş oranını hesapla
        zero_crossings = librosa.feature.zero_crossing_rate(
            y=y, hop_length=self.hop_length
        )[0]

        # Ortalama spektral merkez - vokaller genelde >1500 Hz
        avg_centroid = np.mean(spectral_centroids)
        # Ortalama ZCR - vokallerdeki sessiz harfler ZCR'yi artırır
        avg_zcr = np.mean(zero_crossings)

        # Vokal algılama eşikleri
        centroid_threshold = 1500  # Hz
        zcr_threshold = 0.15  # Normalize edilmiş ZCR

        # Her iki gösterge de vokal gösteriyorsa yüksek güven
        centroid_score = min(1.0, avg_centroid / 2500)  # 2500 Hz'de normalize et
        zcr_score = min(1.0, avg_zcr / 0.25)

        # Birleşik güven puanı
        confidence = 0.6 * centroid_score + 0.4 * zcr_score

        # Vokal varlığı kararı
        vocal_detected = avg_centroid > centroid_threshold and avg_zcr > zcr_threshold

        return vocal_detected, round(confidence, 2)

    def _extract_bass_weighted_chroma(
        self,
        y: np.ndarray,
        sr: int,
        tuning: float
    ) -> np.ndarray:
        """
        Bas/harmony odaklı kroma özelliklerini çıkar.

        Vokal yoğun müziklerde harmonic foundation (80-400 Hz) vokallerden
        daha güvenilir ton bilgisi sağlar. Bass notes genellikle tonun kök
        notlarını takip eder.

        Returns:
            12 x n_frames kroma matrisi (bas frekanslarına ağırlıklı)
        """
        # Bas ağırlıklı CQT kroma çıkar (80-400 Hz odaklı)
        chroma_bass = librosa.feature.chroma_cqt(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
            tuning=tuning,
            n_chroma=12,
            n_octaves=4,  # Daha az oktav = bas odaklı
            fmin=80,  # E2 - bas gitar/bass range başlangıcı
            norm=2,  # L2 normalize
        )

        return chroma_bass

    def _extract_combined_chroma(
        self,
        y: np.ndarray,
        sr: int,
        tuning: float
    ) -> np.ndarray:
        """
        Birden fazla kroma temsilini çıkar ve birleştir.

        Birleştirir:
        - CQT kroma (armonik doğruluk)
        - CENS kroma (gürültü dayanıklılığı)
        - STFT kroma (zamansal doğruluk)

        En iyi doğruluk için ağırlıklı kombinasyonu döndürür.
        """
        # CQT tabanlı kroma - armonik içerik için en doğru
        chroma_cqt = librosa.feature.chroma_cqt(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
            tuning=tuning,
            n_chroma=12,
            n_octaves=7,
            fmin=librosa.note_to_hz('C1'),
        )

        # CENS - Kroma Enerjisi Normalize Edilmiş İstatistikler (gürültü/tınıya dayanıklı)
        chroma_cens = librosa.feature.chroma_cens(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
            tuning=tuning,
            n_chroma=12,
        )

        # STFT kroma - iyi zamansal çözünürlük
        chroma_stft = librosa.feature.chroma_stft(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
            tuning=tuning,
            n_chroma=12,
        )

        # Ağırlıklı kombinasyon (CQT ton algılama için en önemlisidir)
        # MIREX ton algılama değerlendirmelerine dayalı ağırlıklar
        combined = (
            0.50 * chroma_cqt +
            0.30 * chroma_cens +
            0.20 * chroma_stft
        )

        return combined
    
    def _get_weighted_chroma(self, chroma: np.ndarray) -> np.ndarray:
        """
        Daha yüksek sesli/daha kararlı bölümleri vurgulayarak ağırlıklı ortalama kroma al.
        """
        # Çerçeve enerjilerini hesapla
        frame_energy = np.sum(chroma, axis=0)
        
        # Sıfıra bölünmeyi önle
        total_energy = np.sum(frame_energy) + 1e-10
        
        # Her çerçeveyi enerjisine göre ağırlıklandır
        weights = frame_energy / total_energy
        
        # Ağırlıklı ortalama
        weighted_chroma = np.sum(chroma * weights, axis=1)
        
        # Toplamı 1 olacak şekilde normalize et
        if np.sum(weighted_chroma) > 0:
            weighted_chroma = weighted_chroma / np.sum(weighted_chroma)
        
        return weighted_chroma
    
    def _find_key(self, chroma: np.ndarray) -> Tuple[str, float, dict]:
        """
        Çoklu profillerle Krumhansl-Schmuckler algoritmasını kullanarak tonu bul.
        
        Sağlam algılama için tüm profil tiplerinden ağırlıklı oylama kullanır.
        """
        all_scores = {}
        profile_results = {}
        
        # Korelasyon için kromayı normalize et
        chroma_norm = (chroma - np.mean(chroma)) / (np.std(chroma) + 1e-10)
        
        # Tüm 24 tonu tüm profillere karşı test et
        for profile_name, profile_data in self.profiles.items():
            major_profile = profile_data['major']
            minor_profile = profile_data['minor']
            weight = profile_data['weight']
            
            profile_scores = {}
            
            for i, pitch in enumerate(self.PITCH_CLASSES):
                # Bu kökü test etmek için kromayı döndür
                rotated = np.roll(chroma_norm, -i)
                
                # Majör profili ile Pearson korelasyonu
                major_corr = np.corrcoef(rotated, major_profile)[0, 1]
                major_key = f"{pitch} major"
                profile_scores[major_key] = major_corr
                
                # Minör profili ile Pearson korelasyonu
                minor_corr = np.corrcoef(rotated, minor_profile)[0, 1]
                minor_key = f"{pitch} minor"
                profile_scores[minor_key] = minor_corr
            
            profile_results[profile_name] = (profile_scores, weight)
        
        # Ağırlıklı oylama ile puanları topla
        for key in [f"{p} {m}" for p in self.PITCH_CLASSES for m in ['major', 'minor']]:
            weighted_sum = 0
            weight_sum = 0
            
            for profile_name, (scores, weight) in profile_results.items():
                if key in scores:
                    weighted_sum += scores[key] * weight
                    weight_sum += weight
            
            all_scores[key] = weighted_sum / weight_sum if weight_sum > 0 else 0
        
        # En iyi tonu bul
        best_key = max(all_scores, key=all_scores.get)
        best_score = all_scores[best_key]
        
        # Güvenilirliği hesapla
        confidence = self._calculate_confidence(all_scores, best_key, best_score)
        
        return best_key, confidence, all_scores
    
    def _calculate_confidence(
        self, 
        all_scores: dict, 
        best_key: str, 
        best_score: float
    ) -> float:
        """
        Şunlara dayalı güven puanını hesapla:
        1. Mutlak korelasyon gücü
        2. En iyi ve ikinci en iyi arasındaki fark (relatif ton hariç)
        3. Ton sinyalinin tutarlılığı
        """
        sorted_keys = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Relatif majör/minör al
        relative = self._get_relative_key(best_key)
        
        # İkinci en iyiyi bul (relatif ton değil)
        second_best_score = 0
        for key, score in sorted_keys:
            if key != best_key and key != relative:
                second_best_score = score
                break
        
        # Faktör 1: Mutlak korelasyon (0-1 ölçekli)
        # Korelasyon > 0.7 çok güçlü, > 0.5 orta
        abs_factor = max(0, min(1, (best_score + 1) / 2))  # [-1,1] aralığını [0,1]'e eşle
        
        # Faktör 2: İkinci en iyiden ayrılma
        separation = best_score - second_best_score
        sep_factor = max(0, min(1, separation * 3))  # Uygun şekilde ölçekle
        
        # Faktör 3: Ortalamadan ne kadar daha iyi
        avg_score = np.mean(list(all_scores.values()))
        above_avg = best_score - avg_score
        avg_factor = max(0, min(1, above_avg * 2))
        
        # Birleşik güvenilirlik
        confidence = 0.40 * abs_factor + 0.35 * sep_factor + 0.25 * avg_factor
        
        # Makul aralığa ölçekle ve kırp
        confidence = max(0.20, min(0.95, confidence * 1.3))
        
        return round(confidence, 2)
    
    def _get_relative_key(self, key: str) -> str:
        """Bir tonun relatif majör/minörünü al."""
        parts = key.split()
        if len(parts) != 2:
            return ""
        
        pitch, mode = parts[0], parts[1]
        
        try:
            pitch_idx = self.PITCH_CLASSES.index(pitch)
        except ValueError:
            return ""
        
        if mode == "major":
            # Relatif minör 3 yarım ton aşağıdadır (= 9 yukarı)
            rel_idx = (pitch_idx + 9) % 12
            return f"{self.PITCH_CLASSES[rel_idx]} minor"
        else:
            # Relatif majör 3 yarım ton yukarıdadır
            rel_idx = (pitch_idx + 3) % 12
            return f"{self.PITCH_CLASSES[rel_idx]} major"
    
    def _get_alternatives(
        self, 
        all_scores: dict, 
        primary_key: str,
        primary_confidence: float,
    ) -> List[KeyCandidate]:
        """Puana göre sıralanmış alternatif ton adaylarını al."""
        sorted_keys = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        
        alternatives = []
        primary_score = all_scores.get(primary_key, 0)
        
        for key, score in sorted_keys[:6]:
            if key != primary_key:
                # Güveni birincile göre ölçekle
                if primary_score > 0:
                    rel_conf = (score / primary_score) * primary_confidence
                else:
                    rel_conf = 0.3
                
                conf = max(0.10, min(0.90, rel_conf))
                
                alternatives.append(KeyCandidate(
                    key=key,
                    confidence=round(conf, 2),
                ))
        
        return alternatives[:4]
    
    def _detect_modulations(
        self, 
        chroma: np.ndarray, 
        sr: int,
    ) -> List[KeySegment]:
        """
        Pencreli analiz kullanarak parça boyunca ton değişikliklerini algıla.
        """
        # Pencreli analiz parametreleri
        window_sec = 8  # 8 saniyelik pencereler
        hop_sec = 4     # 4 saniyelik atlama
        
        window_frames = int(window_sec * sr / self.hop_length)
        hop_frames = int(hop_sec * sr / self.hop_length)
        
        n_frames = chroma.shape[1]
        duration = n_frames * self.hop_length / sr
        
        if n_frames < window_frames:
            # Parça çok kısa - tek bölüm döndür
            global_chroma = self._get_weighted_chroma(chroma)
            key, conf, _ = self._find_key(global_chroma)
            return [KeySegment(start=0.0, end=duration, key=key, confidence=conf)]
        
        segments = []
        current_key = None
        current_conf = 0
        segment_start = 0.0
        
        frame = 0
        while frame < n_frames - window_frames // 2:
            end_frame = min(frame + window_frames, n_frames)
            
            # Pencere kromasını al
            window_chroma = self._get_weighted_chroma(chroma[:, frame:end_frame])
            key, conf, _ = self._find_key(window_chroma)
            
            time = frame * self.hop_length / sr
            
            if current_key is None:
                current_key = key
                current_conf = conf
                segment_start = 0.0
            elif key != current_key and conf > self.LOW_CONFIDENCE:
                # Ton değişimi algılandı
                segments.append(KeySegment(
                    start=segment_start,
                    end=time,
                    key=current_key,
                    confidence=round(current_conf, 2),
                ))
                current_key = key
                current_conf = conf
                segment_start = time
            else:
                # Yumuşatma ile güveni güncelle
                current_conf = 0.7 * current_conf + 0.3 * conf
            
            frame += hop_frames
        
        # Son bölümü ekle
        if current_key is not None:
            segments.append(KeySegment(
                start=segment_start,
                end=duration,
                key=current_key,
                confidence=round(current_conf, 2),
            ))
        
        # Çok kısa bölümleri birleştir (< 6 saniye)
        return self._merge_short_segments(segments, min_duration=6.0)
    
    def _merge_short_segments(
        self, 
        segments: List[KeySegment],
        min_duration: float = 6.0,
    ) -> List[KeySegment]:
        """min_duration süresinden kısa bölümleri komşularıyla birleştir."""
        if len(segments) <= 1:
            return segments
        
        merged = []
        
        for seg in segments:
            if seg.end - seg.start < min_duration and merged:
                # Önceki bölümü uzat
                prev = merged[-1]
                merged[-1] = KeySegment(
                    start=prev.start,
                    end=seg.end,
                    key=prev.key,
                    confidence=min(prev.confidence, seg.confidence),
                )
            else:
                merged.append(seg)
        
        return merged
    
    def _generate_explanation(
        self,
        key: str,
        confidence: float,
        alternatives: List[KeyCandidate],
    ) -> str:
        """Ton algılama açıklamasını oluştur."""
        parts = []
        
        if confidence >= self.HIGH_CONFIDENCE:
            parts.append(f"Güçlü tonal merkez: {key}.")
        elif confidence >= self.MEDIUM_CONFIDENCE:
            parts.append(f"Net tonal merkez: {key}.")
        elif confidence >= self.LOW_CONFIDENCE:
            parts.append(f"Orta güvenilirlik: {key}.")
        else:
            parts.append(f"Belirsiz tonalite; {key} tahmini.")
        
        # Alternatiflerde varsa relatif majör/minörü belirt
        if alternatives:
            relative = self._get_relative_key(key)
            for alt in alternatives[:2]:
                if alt.key == relative:
                    if "major" in key.lower():
                        parts.append(f"Relatif minör ({alt.key}) da olası.")
                    else:
                        parts.append(f"Relatif majör ({alt.key}) da olası.")
                    break
        
        return " ".join(parts)
