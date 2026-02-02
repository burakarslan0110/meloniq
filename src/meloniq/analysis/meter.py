"""
Zaman işareti / ölçü algılama modülü.

Algoritma (artırılmış doğruluk):
1. Çoklu yöntemle başlangıç (onset) algılama
2. Vuruş pozisyonları için vuruş takibi
3. Spektral akı desenleri kullanarak güçlü vuruş (downbeat) algılama
4. Periyodiklik için otokorelasyon analizi
5. Yaygın ölçülerle şablon eşleştirme
6. Desen gücüne dayalı güven puanlaması

Not: Ölçü algılama zordur; belirsiz durumlarda varsayılan 4/4'tür.
"""

import numpy as np
import librosa
from typing import Optional, List, Tuple

from ..models.results import MeterResult


class MeterAnalyzer:
    """
    Geliştirilmiş zaman işareti / ölçü analizcisi.
    
    Yaygın ölçüleri ayırt eder:
    - 4/4 (en yaygın)
    - 3/4 (vals)
    - 6/8 (bileşik ikili)
    - 2/4 (marş)
    - 5/4 ve 7/8 (tek/aksak ölçüler)
    
    Güven tabanlı geri çekilme ile çoklu algılama yöntemleri kullanır.
    """
    
    # Test edilecek yaygın ölçüler (isim, bar_başına_vuruş, vuruş_birimi)
    METERS = [
        ("4/4", 4, 4),
        ("3/4", 3, 4),
        ("6/8", 6, 8),
        ("2/4", 2, 4),
        ("5/4", 5, 4),
        ("7/8", 7, 8),
    ]
    
    # Eşikler
    HIGH_CONFIDENCE = 0.70
    MEDIUM_CONFIDENCE = 0.50
    LOW_CONFIDENCE = 0.35
    
    def __init__(self, hop_length: int = 512):
        self.hop_length = hop_length
    
    def _compute_beat_strengths(
        self, 
        y: np.ndarray, 
        sr: int, 
        beat_times: List[float],
    ) -> np.ndarray:
        """
        Birden fazla özellik kullanarak her vuruştaki gücü hesapla.
        """
        strengths = []
        
        # Başlangıç (onset) güç zarfını al
        onset_env = librosa.onset.onset_strength(
            y=y, sr=sr, hop_length=self.hop_length
        )
        times = librosa.times_like(onset_env, sr=sr, hop_length=self.hop_length)
        
        # Mevcutsa daha iyi vuruş gücü tahmini için PLP (Baskın Yerel Nabız) kullan
        try:
            pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr, hop_length=self.hop_length)
        except:
            pulse = onset_env
            
        for t in beat_times:
            # En yakın çerçeveyi bul
            idx = np.argmin(np.abs(times - t))
            
            # Başlangıç zarfından ve nabızdan güç al (küçük pencere ile)
            start_idx = max(0, idx - 1)
            end_idx = min(len(onset_env), idx + 2)
            
            if end_idx > start_idx:
                # Başlangıç gücü ve nabız gücünü birleştir
                onset_val = np.max(onset_env[start_idx:end_idx])
                if hasattr(pulse, '__len__') and len(pulse) > idx:
                    pulse_val = np.mean(pulse[start_idx:end_idx])
                else:
                    pulse_val = 0
                
                strengths.append(onset_val + pulse_val)
            else:
                strengths.append(0.0)
        
        strengths = np.array(strengths)
        
        # Normalize et
        if np.max(strengths) > 0:
            strengths = strengths / np.max(strengths)
        
        return strengths
    
    def _analyze_strength_patterns(
        self, 
        beat_strengths: np.ndarray,
    ) -> dict:
        """
        Vuruş gücü desenlerine göre ölçüleri puanla.
        """
        scores = {}
        
        if len(beat_strengths) < 4:
            return {m: 0.5 for m, _, _ in self.METERS}

        # Tekrarlayan vurgu desenlerini bulmak için vuruş güçlerinin otokorelasyonunu analiz et
        max_lag = min(len(beat_strengths) // 2, 8)
        if max_lag < 2:
             return {m: 0.5 for m, _, _ in self.METERS}
             
        autocorr = np.correlate(beat_strengths, beat_strengths, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        # Normalize et
        if autocorr[0] > 0:
            autocorr = autocorr / autocorr[0]
            
        for meter_str, beats_per_bar, _ in self.METERS:
            # beats_per_bar'da periyodikliği kontrol et
            if beats_per_bar < len(autocorr):
                score = autocorr[beats_per_bar]
                
                # Birden fazla ölçü eşleşirse artır (2*beats_per_bar)
                if 2 * beats_per_bar < len(autocorr):
                    score = 0.7 * score + 0.3 * autocorr[2 * beats_per_bar]
                    
                scores[meter_str] = score
            else:
                scores[meter_str] = 0.0
                
        return scores
        
    # ... (other methods)

    def analyze(
        self, 
        y: np.ndarray, 
        sr: int,
        tempo: Optional[float] = None,
        beat_times: Optional[List[float]] = None,
    ) -> MeterResult:
        """Sesi ölçü için analiz et."""
        
        # Vuruş zamanlarını al (verilmemişse)
        if beat_times is None:
            if tempo is not None:
                _, beat_frames = librosa.beat.beat_track(
                    y=y, sr=sr, 
                    hop_length=self.hop_length,
                    bpm=tempo
                )
            else:
                _, beat_frames = librosa.beat.beat_track(
                    y=y, sr=sr, 
                    hop_length=self.hop_length
                )
            beat_times = librosa.frames_to_time(
                beat_frames, sr=sr, hop_length=self.hop_length
            ).tolist()
        
        if len(beat_times) < 12:
            return self._fallback_result("Yetersiz beat sayısı")
        
        # Yöntem 1: Geliştirilmiş PLP ile vuruş gücü deseni analizi
        beat_strengths = self._compute_beat_strengths(y, sr, beat_times)
        strength_scores = self._analyze_strength_patterns(beat_strengths)
        
        # Yöntem 2: Başlangıç (onset) tabanlı güçlü vuruş algılama
        onset_env = librosa.onset.onset_strength(
            y=y, sr=sr, hop_length=self.hop_length
        )
        onset_scores = self._analyze_onset_patterns(onset_env, sr, beat_times)
        
        # Yöntem 3: Spektral akı periyodikliği
        periodicity_scores = self._analyze_periodicity(onset_env, sr)
        
        # Yöntem 4: Armonik Ritim (Akor değişim deseni) -> Ölçü için ÇOK DOĞRU
        harmonic_scores = self._analyze_harmonic_rhythm(y, sr, beat_times)
        
        # Puanları birleştir - YAYGIN ÖLÇÜLERE (4/4, 3/4) ÖNCELİK VER
        combined_scores = {}
        for meter_str, _, _ in self.METERS:
            s1 = strength_scores.get(meter_str, 0)
            s2 = onset_scores.get(meter_str, 0)
            s3 = periodicity_scores.get(meter_str, 0)
            s4 = harmonic_scores.get(meter_str, 0)
            
            # Ağırlıklı skor hesaplama
            base_score = 0.30 * s1 + 0.20 * s2 + 0.15 * s3 + 0.35 * s4
            
            # YAYGIN ÖLÇÜ BONUSU (User Feedback: "En yaygın olanlar doğru tespit edilsin")
            # 4/4 ve 3/4 için ekstra puan, karmaşık ölçüler için ceza
            if meter_str == "4/4":
                base_score *= 1.25  # %25 bonus
            elif meter_str == "3/4" or meter_str == "6/8":
                base_score *= 1.15  # %15 bonus
            elif meter_str in ["5/4", "7/8"]:
                base_score *= 0.85  # %15 ceza (Kanıt çok güçlüyse yine seçilebilir)
                
            combined_scores[meter_str] = base_score
        
        # En iyi ölçüyü bul
        best_meter = max(combined_scores, key=combined_scores.get)
        best_score = combined_scores[best_meter]
        
        # Güvenilirliği hesapla
        confidence = self._calculate_confidence(combined_scores, best_meter)
        
        # Ölçü detaylarını al
        num, denom = 4, 4  # varsayılan
        for m, n, d in self.METERS:
            if m == best_meter:
                num, denom = n, d
                break
        
        # GÜVENLİK KONTROLÜ VE GERİ ÇEKİLME (FALLBACK)
        # Eğer güvenilirlik düşükse, karmaşık bir ölçü yerine 4/4'e zorla
        fallback_used = False
        
        # Eğer en iyi tahmin karmaşık bir ölçüyse (5/4, 7/8) ve güven düşükse (< 0.65)
        if best_meter in ["5/4", "7/8", "2/4"] and confidence < 0.65:
            # 4/4'ün puanı çok kötü değilse 4/4'e geç
            score_4_4 = combined_scores.get("4/4", 0)
            if score_4_4 > best_score * 0.7:
                best_meter = "4/4"
                num, denom = 4, 4
                fallback_used = True
                confidence = 0.60
                
        # Genel düşük güvenilirlik durumu
        elif confidence < 0.25:
             best_meter = "4/4"
             num, denom = 4, 4
             fallback_used = True
             confidence = 0.50 
        
        # Açıklama oluştur
        explanation = self._generate_explanation(
            best_meter, confidence, combined_scores, fallback_used
        )
        
        return MeterResult(
            value=best_meter,
            numerator=num,
            denominator=denom,
            confidence=round(confidence, 2),
            explanation=explanation,
            needs_confirmation=confidence < self.MEDIUM_CONFIDENCE,
            fallback_used=fallback_used,
        )

    def _analyze_harmonic_rhythm(
        self,
        y: np.ndarray,
        sr: int,
        beat_times: List[float],
    ) -> dict:
        """
        Armonik Ritmi Analiz Et: Akorlar ne sıklıkla değişiyor?
        (3/4 ve 4/4 ayrımı için son derece etkili)
        """
        scores = {}
        if len(beat_times) < 8:
            return {m: 0.5 for m, _, _ in self.METERS}
            
        try:
            # 1. Kroma Özelliklerini Hesapla (Armonik içerik)
            # Düşük frekanslarda daha iyi perde çözünürlüğü için CQT kullan
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=self.hop_length)
            
            # 2. Kromayı Vuruşlara Senkronize Et
            # Bu bize vuruş başına bir kroma vektörü verir
            beat_frames = librosa.time_to_frames(beat_times, sr=sr, hop_length=self.hop_length)
            # Vuruş karelerinin sınırlar içinde olduğundan emin ol
            beat_frames = [b for b in beat_frames if b < chroma.shape[1]]
            
            if len(beat_frames) < 4:
                 return {m: 0.5 for m, _, _ in self.METERS}

            beat_chroma = librosa.util.sync(chroma, beat_frames, aggregate=np.median)
            
            # 3. Armonik Değişimi Hesapla (HCDF)
            # Ardışık vuruş vektörleri arasındaki Öklid mesafesi
            # Yüksek değer = Akor Değişimi / Düşük değer = Sürdürme
            beat_chroma = librosa.util.normalize(beat_chroma, axis=0)
            
            # Bitişik sütunlar arasındaki 1 - kosinüs benzerliğini hesapla
            # normalize edilmişse dist = 1 - nokta_çarpımına eşdeğerdir
            cosine_sim = np.sum(beat_chroma[:, :-1] * beat_chroma[:, 1:], axis=0)
            hcdf = 1 - cosine_sim
            
            # 4. Değişimlerin Periyodikliğini Analiz Et
            # Değişim fonksiyonunu otokorelasyona tabi tut
            if len(hcdf) < 6:
                return {m: 0.5 for m, _, _ in self.METERS}
                
            autocorr = np.correlate(hcdf, hcdf, mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            
            # Normalize et
            if autocorr[0] > 0:
                autocorr = autocorr / autocorr[0]
            
            for meter_str, beats_per_bar, _ in self.METERS:
                if beats_per_bar < len(autocorr):
                    score = autocorr[beats_per_bar]
                    
                    # Armonik değişimler genellikle daha yavaştır (örn. bar başına bir akor)
                    # Bu yüzden 1x bar uzunluğunda da periyodiklik arıyoruz
                    
                    # 2x bar uzunluğu da eşleşirse artır (düzenli frazlama)
                    if 2 * beats_per_bar < len(autocorr):
                        score = 0.6 * score + 0.4 * autocorr[2 * beats_per_bar]
                    
                    scores[meter_str] = score
                else:
                    scores[meter_str] = 0.0
                    
        except Exception:
             # Kroma başarısız olursa geri çekil
             scores = {m: 0.5 for m, _, _ in self.METERS}
             
        return scores

    def _analyze_onset_patterns(
        self, 
        onset_env: np.ndarray, 
        sr: int, 
        beat_times: List[float],
    ) -> dict:
        """
        Ölçü desenleri için başlangıç zarfını analiz et.
        """
        scores = {}
        
        if len(beat_times) < 8:
            for meter_str, _, _ in self.METERS:
                scores[meter_str] = 0.5
            return scores
        
        # Vuruş aralıklarını hesapla
        intervals = np.diff(beat_times)
        mean_interval = np.mean(intervals)
        
        for meter_str, beats_per_bar, _ in self.METERS:
            # Beklenen bar süresi
            bar_duration = mean_interval * beats_per_bar
            
            # Bar periyodunda otokorelasyonu analiz et
            lag_samples = int(bar_duration * sr / self.hop_length)
            
            if lag_samples <= 0 or lag_samples >= len(onset_env) // 2:
                scores[meter_str] = 0.5
                continue
            
            # Otokorelasyonu hesapla
            autocorr = np.correlate(onset_env, onset_env, mode='full')
            autocorr = autocorr[len(autocorr) // 2:]
            
            # Normalize et
            if autocorr[0] > 0:
                autocorr = autocorr / autocorr[0]
            
            # Bu ölçünün bar periyodundaki korelasyonunu al
            if lag_samples < len(autocorr):
                meter_corr = autocorr[lag_samples]
                scores[meter_str] = max(0, (meter_corr + 1) / 2)  # 0-1 aralığına eşle
            else:
                scores[meter_str] = 0.5
        
        return scores
    
    def _analyze_periodicity(
        self, 
        onset_env: np.ndarray, 
        sr: int,
    ) -> dict:
        """
        Tempogram kullanarak periyodikliği analiz et.
        """
        scores = {}
        
        try:
            # Tempogramı hesapla
            tempogram = librosa.feature.tempogram(
                onset_envelope=onset_env,
                sr=sr,
                hop_length=self.hop_length,
            )
            
            # Zaman üzerinden ortalama al
            avg_tempogram = np.mean(tempogram, axis=1)
            
            # Tempo eksenini al
            tempo_axis = librosa.tempo_frequencies(
                n_bins=len(avg_tempogram),
                sr=sr,
                hop_length=self.hop_length,
            )
            
            # Ana tempo zirvesini bul (çok düşük tempoları atla)
            valid_mask = (tempo_axis > 40) & (tempo_axis < 240)
            if np.any(valid_mask):
                valid_tempogram = avg_tempogram.copy()
                valid_tempogram[~valid_mask] = 0
                main_tempo_idx = np.argmax(valid_tempogram)
                main_tempo = tempo_axis[main_tempo_idx]
            else:
                main_tempo = 120  # varsayılan
            
            # Her ölçü için, beklenen periyodikliklerin mevcut olup olmadığını kontrol et
            for meter_str, beats_per_bar, _ in self.METERS:
                # Beklenen bar temposu
                bar_tempo = main_tempo / beats_per_bar
                
                # Bar periyodunda enerji olup olmadığını kontrol et
                bar_idx = np.argmin(np.abs(tempo_axis - bar_tempo))
                
                # Ayrıca bileşik ölçüler için yarım barı kontrol et
                half_bar_idx = np.argmin(np.abs(tempo_axis - bar_tempo * 2))
                
                # Bu periyotlardaki göreceli güce göre puanla
                max_val = np.max(avg_tempogram) + 1e-10
                bar_strength = avg_tempogram[bar_idx] / max_val
                half_bar_strength = avg_tempogram[half_bar_idx] / max_val if half_bar_idx < len(avg_tempogram) else 0
                
                scores[meter_str] = 0.6 * bar_strength + 0.4 * half_bar_strength
                
        except Exception:
            # Tempogram başarısız olursa geri çekil
            for meter_str, _, _ in self.METERS:
                scores[meter_str] = 0.5
        
        return scores
    
    def _calculate_confidence(
        self, 
        scores: dict, 
        best_meter: str,
    ) -> float:
        """En iyi ölçünün ne kadar öne çıktığına göre güvenilirliği hesapla."""
        if not scores:
            return 0.35
        
        best_score = scores[best_meter]
        other_scores = [s for m, s in scores.items() if m != best_meter]
        
        if not other_scores:
            return 0.50
        
        second_best = max(other_scores)
        mean_score = np.mean(other_scores)
        
        # Faktör 1: İkinci en iyiden ayrılma
        if second_best > 0:
            separation = (best_score - second_best) / second_best
        else:
            separation = 1.0
        
        # Faktör 2: Ortalamanın ne kadar üzerinde
        if mean_score > 0:
            above_avg = (best_score - mean_score) / mean_score
        else:
            above_avg = 1.0
        
        # Birleşik güvenilirlik
        confidence = 0.6 * min(1.0, separation) + 0.4 * min(1.0, above_avg * 0.5 + 0.5)
        confidence = max(0.25, min(0.90, confidence))
        
        return confidence
    
    def _fallback_result(self1, reason: str) -> MeterResult:
        """Varsayılan 4/4 sonucunu döndür."""
        return MeterResult(
            value="4/4",
            numerator=4,
            denominator=4,
            confidence=0.50,
            explanation=f"{reason}. Varsayılan 4/4.",
            needs_confirmation=True,
            fallback_used=True,
        )
    
    def _generate_explanation(
        self,
        meter: str,
        confidence: float,
        scores: dict,
        fallback_used: bool,
    ) -> str:
        """Ölçü algılama açıklamasını oluştur."""
        parts = []
        
        if fallback_used:
            parts.append(f"Düşük güvenilirlik; varsayılan 4/4.")
        elif confidence >= self.HIGH_CONFIDENCE:
            parts.append(f"Güçlü {meter} paterni tespit edildi.")
        elif confidence >= self.MEDIUM_CONFIDENCE:
            parts.append(f"Orta güvenilirlik: {meter}.")
        else:
            parts.append(f"{meter} tahmini (düşük güvenilirlik).")
        
        # Yakınsa alternatifi belirt
        if not fallback_used:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_scores) >= 2:
                second = sorted_scores[1]
                if second[1] > 0.85 * sorted_scores[0][1]:
                    parts.append(f"{second[0]} de olası.")
        
        return " ".join(parts)
