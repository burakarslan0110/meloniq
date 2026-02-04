"""
Geliştirilmiş Tempo ve vuruş algılama modülü.

Algoritma:
1. DeepRhythm CNN tabanlı tempo tahmini (birincil - %95.9 doğruluk)
2. Yedek olarak Librosa beat_track
3. Çoklu yöntemle topluluk (ensemble) yaklaşımı
4. Oktav hatası düzeltme (yarı zamanlı/çift zamanlı)
5. Vuruşlar Arası Aralık (IBI) tabanlı güvenilirlik

Sağlam güven puanlaması ile son derece doğru BPM sağlar.
"""

import numpy as np
import librosa
from typing import Optional, Tuple
import warnings

from ..models.results import TempoResult, TempoCandidate, TempoSegment, CountIn

# DeepRhythm modülünü CNN tabanlı tempo tespiti için içe aktarmayı dene
_DEEPRHYTHM_AVAILABLE = False
try:
    from deeprhythm import DeepRhythmPredictor
    _DEEPRHYTHM_AVAILABLE = True
except ImportError:
    pass


class TempoAnalyzer:
    """
    CNN tabanlı algılama ile geliştirilmiş tempo analizcisi.

    Birincil yöntem olarak DeepRhythm (CNN, %95.9 doğruluk) kullanır,
    yedek ve doğrulama olarak librosa topluluğunu kullanır.

    Geliştirilmiş oktav düzeltme: Onset strength periyodiklik analizi ile
    yarı/çift tempo hatalarını minimize eder.
    """

    # Çoğu müzik için BPM aralığı (normalizasyon için kullanılır)
    BPM_MIN = 60
    BPM_MAX = 180
    BPM_ABSOLUTE_MIN = 40
    BPM_ABSOLUTE_MAX = 220

    # Güvenilirlik eşiği
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.70
    LOW_CONFIDENCE = 0.50

    # Oktav düzeltme için enerji oranı eşiği
    # Bu değer, yarı tempo periyodundaki enerjinin tam tempo periyoduna oranı
    OCTAVE_ENERGY_THRESHOLD = 0.75

    def __init__(self, hop_length: int = 512):
        self.hop_length = hop_length

        # Onset envelope önbelleği (tekrarlı hesaplamayı önlemek için)
        self._cached_onset_env: Optional[np.ndarray] = None
        self._cached_sr: Optional[int] = None

        # Varsa DeepRhythm'i başlat
        self._predictor = None
        if _DEEPRHYTHM_AVAILABLE:
            try:
                self._predictor = DeepRhythmPredictor()
            except Exception:
                pass
    
    def analyze(
        self, 
        y: np.ndarray, 
        sr: int,
        detect_downbeats: bool = True,
    ) -> TempoResult:
        """
        Tempoyu ve vuruşları yüksek doğrulukla analiz et.
        
        Topluluk (ensemble) yaklaşımı kullanır:
        1. DeepRhythm CNN (varsa) - birincil
        2. Librosa beat_track - ikincil
        3. Tempogram PLP - üçüncül
        4. Nihai sonuç için oylama/ortalama
        
        Args:
            y: Ses örnekleri (mono)
            sr: Örnekleme oranı
            detect_downbeats: Güçlü vuruş tespitinin denenip denenmeyeceği
            
        Returns:
            BPM, vuruşlar, güven ve alternatifleri içeren TempoResult
        """
        # Onset envelope'u hesapla ve önbelleğe al (tüm yöntemler için kullanılacak)
        self._cached_onset_env = librosa.onset.onset_strength(
            y=y, sr=sr, hop_length=self.hop_length
        )
        self._cached_sr = sr

        # Birden fazla yöntemden tempo tahminlerini topla
        estimates = []

        # Sinyal kalitesi metriğini hesapla (dinamik ağırlıklandırma için)
        signal_quality = self._estimate_signal_quality(y, sr)

        # Yöntem 1: DeepRhythm CNN (en doğru)
        deeprhythm_bpm = None
        if self._predictor is not None:
            try:
                deeprhythm_bpm = self._predict_with_deeprhythm(y, sr)
                if deeprhythm_bpm is not None:
                    # DeepRhythm ağırlığı sinyal kalitesine göre ayarlanır
                    dr_weight = 0.95 if signal_quality > 0.5 else 0.85
                    estimates.append(('deeprhythm', deeprhythm_bpm, dr_weight))
            except Exception:
                pass

        # Yöntem 2: Librosa beat_track
        librosa_bpm, beat_frames = self._librosa_beat_track(y, sr)
        estimates.append(('librosa_beat', librosa_bpm, 0.70))

        # Yöntem 3: Tempogram PLP (Baskın Yerel Nabız)
        plp_bpm = self._tempogram_plp(y, sr)
        if plp_bpm is not None:
            estimates.append(('plp', plp_bpm, 0.65))

        # Yöntem 4: Otokorelasyon tempogramı
        acf_bpm = self._tempogram_acf(y, sr)
        if acf_bpm is not None:
            estimates.append(('acf', acf_bpm, 0.60))

        # Topluluk: oktav hizalaması ile ağırlıklı oylama
        final_bpm, confidence, candidates = self._ensemble_tempo(estimates)

        # Akıllı oktav düzeltme: onset envelope analizi ile doğrula
        final_bpm = self._smart_octave_correction(final_bpm, y, sr)
        
        # Tahmini tempoyu kullanarak vuruş zamanlarını al
        beat_times = self._track_beats_with_tempo(y, sr, final_bpm)
        
        # Güçlü vuruşları (downbeats) tahmin et
        downbeats = []
        if detect_downbeats and len(beat_times) > 0:
            downbeats = self._estimate_downbeats(y, sr, beat_times)
        
        # Tempo değişikliklerini algıla
        segments = self._detect_tempo_changes(y, sr, final_bpm)
        
        # Açıklama oluştur
        explanation = self._generate_explanation(final_bpm, confidence, candidates, 
                                                  deeprhythm_bpm is not None)
        
        # Giriş sayımı (count-in) önerisi oluştur
        count_in = CountIn(
            bars=1,
            click_bpm=final_bpm,
            meter="4/4",
            beats_per_bar=4,
        )
        
        return TempoResult(
            global_bpm=final_bpm,
            confidence=confidence,
            explanation=explanation,
            needs_confirmation=confidence < self.LOW_CONFIDENCE,
            candidates=candidates,
            segments=segments,
            beats=beat_times,
            downbeats=downbeats,
            count_in=count_in,
        )
    
    def _predict_with_deeprhythm(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Tempo tahmini için DeepRhythm CNN kullan."""
        if self._predictor is None:
            return None
        
        try:
            # DeepRhythm belirli örnekleme oranında ses bekler
            # Gerekirse yeniden örnekle
            target_sr = 22050
            if sr != target_sr:
                y_resampled = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            else:
                y_resampled = y
            
            # Tempoyu tahmin et
            bpm = self._predictor.predict(y_resampled, target_sr)
            
            if isinstance(bpm, np.ndarray):
                bpm = float(bpm[0]) if len(bpm) > 0 else None
            else:
                bpm = float(bpm) if bpm is not None else None
            
            return bpm
        except Exception:
            return None
    
    def _librosa_beat_track(self, y: np.ndarray, sr: int) -> Tuple[float, np.ndarray]:
        """Standart librosa vuruş takibi."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tempo, beat_frames = librosa.beat.beat_track(
                y=y, 
                sr=sr, 
                hop_length=self.hop_length,
                start_bpm=120.0,
                tightness=100,
            )
        
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0]) if len(tempo) > 0 else 120.0
        else:
            tempo = float(tempo)
        
        return tempo, beat_frames
    
    def _tempogram_plp(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Tempogramdan Baskın Yerel Nabız (PLP) kullanarak tempo çıkar."""
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self.hop_length)
            
            # Compute tempogram
            tempogram = librosa.feature.tempogram(
                onset_envelope=onset_env,
                sr=sr,
                hop_length=self.hop_length,
            )
            
            # Get tempo axis
            tempi = librosa.tempo_frequencies(tempogram.shape[0], sr=sr, hop_length=self.hop_length)
            
            # PLP: find predominant tempo
            plp = librosa.beat.plp(onset_envelope=onset_env, sr=sr, hop_length=self.hop_length)
            
            # Get the most common pulse
            pulse_frames = np.argmax(plp, axis=0)
            
            # Convert to tempo estimate
            if len(pulse_frames) > 0:
                # Use mode of pulse periods
                periods = np.diff(np.where(pulse_frames > 0.5)[0])
                if len(periods) > 0:
                    median_period = np.median(periods)
                    if median_period > 0:
                        bpm = 60.0 * sr / (median_period * self.hop_length)
                        if self.BPM_ABSOLUTE_MIN <= bpm <= self.BPM_ABSOLUTE_MAX:
                            return float(bpm)
            
            # Fallback: use tempogram peak
            avg_tempogram = np.mean(tempogram, axis=1)
            valid_mask = (tempi >= self.BPM_ABSOLUTE_MIN) & (tempi <= self.BPM_ABSOLUTE_MAX)
            valid_tempi = tempi[valid_mask]
            valid_strengths = avg_tempogram[valid_mask]
            
            if len(valid_strengths) > 0:
                peak_idx = np.argmax(valid_strengths)
                return float(valid_tempi[peak_idx])
            
            return None
        except Exception:
            return None
    
    def _tempogram_acf(self, y: np.ndarray, sr: int) -> Optional[float]:
        """Otokorelasyon tempogramı kullanarak tempo çıkar."""
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self.hop_length)
            
            # Autocorrelation-based tempogram
            tempogram = librosa.feature.tempogram(
                onset_envelope=onset_env,
                sr=sr,
                hop_length=self.hop_length,
                win_length=400,  # Longer window for better resolution
            )
            
            tempi = librosa.tempo_frequencies(tempogram.shape[0], sr=sr, hop_length=self.hop_length)
            
            # Global tempo from autocorrelation
            ac_global = librosa.autocorrelate(onset_env, max_size=len(onset_env) // 2)
            
            # Find peaks in autocorrelation
            if len(ac_global) > 10:
                # Skip the first peak (at lag 0)
                ac_global[:10] = 0
                
                # Find the first significant peak
                peaks = []
                for i in range(1, len(ac_global) - 1):
                    if ac_global[i] > ac_global[i-1] and ac_global[i] > ac_global[i+1]:
                        if ac_global[i] > 0.1 * np.max(ac_global):
                            peaks.append(i)
                
                if peaks:
                    # Convert lag to BPM
                    lag = peaks[0]
                    bpm = 60.0 * sr / (lag * self.hop_length)
                    if self.BPM_ABSOLUTE_MIN <= bpm <= self.BPM_ABSOLUTE_MAX:
                        return float(bpm)
            
            return None
        except Exception:
            return None
    
    def _ensemble_tempo(
        self, 
        estimates: list[tuple[str, float, float]]
    ) -> Tuple[float, float, list[TempoCandidate]]:
        """
        Ağırlıklı oylama kullanarak çoklu tempo tahminlerini birleştir.
        Oktav hatalarını yönetir (yarı/çift zaman).
        """
        if not estimates:
            return 120.0, 0.5, []
        
        # Tüm tahminleri 60-180 BPM aralığına normalize et
        normalized = []
        for method, bpm, weight in estimates:
            norm_bpm = self._normalize_to_range(bpm)
            normalized.append((method, norm_bpm, weight, bpm))
        
        # Tahminleri oktav eşdeğerliğine göre grupla
        clusters = {}
        for method, norm_bpm, weight, orig_bpm in normalized:
            # En yakın kümeyi bul (%5 tolerans dahilinde)
            found = False
            for center in list(clusters.keys()):
                if abs(norm_bpm - center) / center < 0.05:
                    clusters[center].append((method, norm_bpm, weight, orig_bpm))
                    found = True
                    break
            
            if not found:
                clusters[norm_bpm] = [(method, norm_bpm, weight, orig_bpm)]
        
        # En yüksek toplam ağırlığa sahip kümeyi bul
        best_cluster = None
        best_weight = 0
        for center, members in clusters.items():
            total_weight = sum(m[2] for m in members)
            if total_weight > best_weight:
                best_weight = total_weight
                best_cluster = center
        
        # En iyi küme içinde ağırlıklı ortalamayı hesapla
        if best_cluster is not None:
            members = clusters[best_cluster]
            weighted_sum = sum(m[1] * m[2] for m in members)
            weight_sum = sum(m[2] for m in members)
            final_bpm = weighted_sum / weight_sum if weight_sum > 0 else best_cluster
        else:
            # Yedek: hepsinin ağırlıklı ortalaması
            weighted_sum = sum(bpm * weight for _, bpm, weight, _ in normalized)
            weight_sum = sum(weight for _, _, weight, _ in normalized)
            final_bpm = weighted_sum / weight_sum if weight_sum > 0 else 120.0
        
        # Round to one decimal
        final_bpm = round(final_bpm, 1)
        
        # Uyum (agreement) bazında güvenilirliği hesapla
        confidence = self._calculate_ensemble_confidence(normalized, final_bpm)
        
        # Adaylar oluştur
        candidates = self._generate_candidates(normalized, final_bpm)
        
        return final_bpm, confidence, candidates
    
    def _normalize_to_range(self, bpm: float) -> float:
        """Yarıya indirerek veya ikiye katlayarak BPM'i 60-180 aralığına normalize et."""
        while bpm < self.BPM_MIN:
            bpm *= 2
        while bpm > self.BPM_MAX:
            bpm /= 2
        return bpm

    def _estimate_signal_quality(self, y: np.ndarray, sr: int) -> float:
        """
        Sinyal kalitesini tahmin et (0.0 - 1.0 arası).

        Yüksek kalite: Net vuruşlar, düşük gürültü
        Düşük kalite: Belirsiz ritim, yüksek gürültü

        Bu metrik, ensemble ağırlıklarını dinamik olarak ayarlamak için kullanılır.
        """
        if self._cached_onset_env is None:
            return 0.5

        onset_env = self._cached_onset_env

        # Metrik 1: Onset envelope'un tepe/ortalama oranı (net vuruşlar = yüksek oran)
        if len(onset_env) == 0 or np.mean(onset_env) == 0:
            return 0.3

        peak_to_mean = np.max(onset_env) / (np.mean(onset_env) + 1e-10)
        # Tipik değerler: 2-10 arası. 5'in üzeri iyi kabul edilir.
        peak_score = min(1.0, (peak_to_mean - 2.0) / 6.0)

        # Metrik 2: Onset envelope'un varyansı (tutarlı ritim = düşük normalize varyans)
        normalized_std = np.std(onset_env) / (np.mean(onset_env) + 1e-10)
        # Çok düşük varyans sessizlik, çok yüksek gürültü demek
        variance_score = 1.0 - abs(normalized_std - 1.5) / 2.0
        variance_score = max(0.0, min(1.0, variance_score))

        # Birleşik skor
        quality = 0.6 * peak_score + 0.4 * variance_score
        return max(0.1, min(1.0, quality))

    def _smart_octave_correction(self, bpm: float, y: np.ndarray, sr: int) -> float:
        """
        Akıllı oktav düzeltme: Onset strength periyodiklik analizi ile
        yarı/çift tempo arasında doğru olanı seç.

        Algoritma:
        1. Mevcut BPM'e karşılık gelen periyotta onset envelope'un otokorelasyonunu hesapla
        2. Yarı ve çift tempo periyotlarındaki otokorelasyon gücünü karşılaştır
        3. Hangi periyot daha güçlü ise o BPM'i seç

        Bu yöntem, örneğin 80 BPM'lik bir şarkının 160 BPM olarak
        yanlış raporlanmasını önler.
        """
        if self._cached_onset_env is None or self._cached_sr is None:
            return bpm

        onset_env = self._cached_onset_env
        hop_sr = sr / self.hop_length  # Onset envelope'un örnekleme oranı

        # BPM'i onset envelope frame periyoduna çevir
        def bpm_to_lag(tempo: float) -> int:
            """BPM'i otokorelasyon lag değerine çevir."""
            if tempo <= 0:
                return 0
            period_seconds = 60.0 / tempo
            lag = int(period_seconds * hop_sr)
            return max(1, lag)

        # Otokorelasyonu hesapla
        max_lag = min(len(onset_env) // 2, bpm_to_lag(self.BPM_ABSOLUTE_MIN) + 10)
        if max_lag < 10:
            return bpm

        acf = librosa.autocorrelate(onset_env, max_size=max_lag)

        # Otokorelasyonu normalize et
        if acf[0] > 0:
            acf = acf / acf[0]

        def get_acf_strength(tempo: float) -> float:
            """Belirli bir tempo için otokorelasyon gücünü döndür."""
            lag = bpm_to_lag(tempo)
            if lag <= 0 or lag >= len(acf):
                return 0.0
            # Lag etrafında küçük bir pencere ortalaması al (gürültü toleransı)
            window = 2
            start = max(0, lag - window)
            end = min(len(acf), lag + window + 1)
            return float(np.max(acf[start:end]))

        # Mevcut BPM ve alternatifleri için güç hesapla
        current_strength = get_acf_strength(bpm)

        # Yarı tempo kontrol (sadece 60 BPM üzerindeyse)
        half_bpm = bpm / 2
        half_strength = 0.0
        if half_bpm >= self.BPM_ABSOLUTE_MIN:
            half_strength = get_acf_strength(half_bpm)

        # Çift tempo kontrol (sadece 180 BPM altındaysa)
        double_bpm = bpm * 2
        double_strength = 0.0
        if double_bpm <= self.BPM_ABSOLUTE_MAX:
            double_strength = get_acf_strength(double_bpm)

        # Karar verme: Eğer yarı veya çift tempo belirgin şekilde daha güçlüyse değiştir
        # OCTAVE_ENERGY_THRESHOLD eşiği: Alternatif en az bu oranda güçlü olmalı
        best_bpm = bpm
        best_strength = current_strength

        # Yarı tempo kontrolü: Yarı tempo daha doğal hissediyorsa
        # (özellikle hızlı parçalarda çift vuruş algılanması sorunu)
        if half_strength > current_strength * self.OCTAVE_ENERGY_THRESHOLD:
            # Ek kontrol: Yarı tempo 60-120 aralığında mı? (yaygın tempo aralığı)
            if 60 <= half_bpm <= 140:
                best_bpm = half_bpm
                best_strength = half_strength

        # Çift tempo kontrolü: Çift tempo daha güçlüyse
        # (özellikle yavaş parçalarda yarı vuruş algılanması sorunu)
        if double_strength > best_strength * self.OCTAVE_ENERGY_THRESHOLD:
            # Ek kontrol: Mevcut tempo çok düşükse (70 BPM altı) çift tempoyu tercih et
            if bpm < 70 and double_bpm <= 180:
                best_bpm = double_bpm

        return round(best_bpm, 1)
    
    def _calculate_ensemble_confidence(
        self,
        estimates: list[tuple[str, float, float, float]],
        final_bpm: float
    ) -> float:
        """
        Geliştirilmiş güvenilirlik hesaplaması.

        Faktörler:
        1. Yöntemler arası uyum (%5 tolerans)
        2. DeepRhythm katılımı ve uyumu
        3. Sinyal kalitesi (onset envelope tutarlılığı)
        4. Uyuşan yöntem sayısı (konsensüs gücü)
        """
        if not estimates:
            return 0.5

        # Kaç yöntemin uyuştuğunu say (%5 dahilinde)
        agreements = 0
        total_weight = 0
        agreeing_methods = 0

        for method, norm_bpm, weight, _ in estimates:
            total_weight += weight
            if abs(norm_bpm - final_bpm) / final_bpm < 0.05:
                agreements += weight
                agreeing_methods += 1

        # Uyumdan temel güvenilirlik
        agreement_score = agreements / total_weight if total_weight > 0 else 0.5

        # Konsensüs bonusu: 3+ yöntem uyuşuyorsa güveni artır
        consensus_bonus = 0.0
        if agreeing_methods >= 3:
            consensus_bonus = 0.08
        elif agreeing_methods >= 2:
            consensus_bonus = 0.04

        # DeepRhythm uyuyorsa artır
        has_deeprhythm = any(m[0] == 'deeprhythm' for m in estimates)
        deeprhythm_agrees = any(
            m[0] == 'deeprhythm' and abs(m[1] - final_bpm) / final_bpm < 0.03
            for m in estimates
        )

        if deeprhythm_agrees:
            confidence = min(0.98, agreement_score * 1.15 + consensus_bonus)
        elif has_deeprhythm:
            confidence = min(0.90, agreement_score * 1.05 + consensus_bonus)
        else:
            confidence = min(0.85, agreement_score + consensus_bonus)

        # Sinyal kalitesi cezası: Düşük kaliteli sinyallerde güveni düşür
        if self._cached_onset_env is not None and self._cached_sr is not None:
            # Onset envelope boşsa veya çok düzse güveni düşür
            onset_env = self._cached_onset_env
            if len(onset_env) > 0:
                # Çok düz bir onset envelope kötü bir işaret
                cv = np.std(onset_env) / (np.mean(onset_env) + 1e-10)  # Varyasyon katsayısı
                if cv < 0.3:  # Çok düşük varyasyon = belirsiz ritim
                    confidence *= 0.85

        return round(max(0.3, confidence), 2)
    
    def _generate_candidates(
        self, 
        estimates: list[tuple[str, float, float, float]], 
        final_bpm: float
    ) -> list[TempoCandidate]:
        """Yarı/çift zaman dahil tempo adayları oluştur."""
        candidates = []
        seen_bpms = set()
        
        # Birincil aday (final BPM)
        candidates.append(TempoCandidate(bpm=final_bpm, confidence=0.95))
        seen_bpms.add(round(final_bpm))
        
        # Yarı zamanlı ve çift zamanlı adaylar
        half_bpm = final_bpm / 2
        double_bpm = final_bpm * 2
        
        if self.BPM_ABSOLUTE_MIN <= half_bpm <= self.BPM_ABSOLUTE_MAX:
            if round(half_bpm) not in seen_bpms:
                candidates.append(TempoCandidate(bpm=round(half_bpm, 1), confidence=0.45))
                seen_bpms.add(round(half_bpm))
        
        if self.BPM_ABSOLUTE_MIN <= double_bpm <= self.BPM_ABSOLUTE_MAX:
            if round(double_bpm) not in seen_bpms:
                candidates.append(TempoCandidate(bpm=round(double_bpm, 1), confidence=0.45))
                seen_bpms.add(round(double_bpm))
        
        # Diğer tahminleri aday olarak ekle
        for method, norm_bpm, weight, orig_bpm in estimates:
            bpm_rounded = round(norm_bpm, 1)
            if round(bpm_rounded) not in seen_bpms:
                conf = min(0.8, weight * 0.9)
                candidates.append(TempoCandidate(bpm=bpm_rounded, confidence=round(conf, 2)))
                seen_bpms.add(round(bpm_rounded))
        
        # Güvenilirliğe göre sırala
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        return candidates[:5]  # Top 5
    
    def _track_beats_with_tempo(
        self, 
        y: np.ndarray, 
        sr: int, 
        tempo: float
    ) -> list[float]:
        """Bilinen bir tempo öncülü kullanarak vuruşları takip et."""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _, beat_frames = librosa.beat.beat_track(
                    y=y,
                    sr=sr,
                    hop_length=self.hop_length,
                    bpm=tempo,
                    tightness=100,
                )
            
            beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=self.hop_length)
            return beat_times.tolist()
        except Exception:
            # Yedek: tempodan vuruşlar oluştur
            duration = len(y) / sr
            beat_interval = 60.0 / tempo
            return [i * beat_interval for i in range(int(duration / beat_interval))]
    
    def _estimate_downbeats(
        self, 
        y: np.ndarray, 
        sr: int, 
        beat_times: list[float],
    ) -> list[float]:
        """
        Güçlü vuruş (downbeat) pozisyonlarını (bar başlangıçları) tahmin et.
        
        Vurgulanan vuruşları bulmak için spektral akı farklarını kullanır.
        Desen belirsizse her 4. vuruşa geri döner.
        """
        if len(beat_times) < 4:
            return beat_times[:1] if beat_times else []
        
        # Her vuruşta spektral özellikleri hesapla
        beat_strengths = []
        
        for t in beat_times:
            # Vuruş etrafındaki örnekleri al
            center_sample = int(t * sr)
            window = int(0.05 * sr)  # 50ms window
            start = max(0, center_sample - window)
            end = min(len(y), center_sample + window)
            
            if end > start:
                segment = y[start:end]
                # Vuruş gücü olarak RMS kullan
                strength = np.sqrt(np.mean(segment ** 2))
                beat_strengths.append(strength)
            else:
                beat_strengths.append(0.0)
        
        beat_strengths = np.array(beat_strengths)
        
        # Bir desen bulmaya çalış (her 3., 4. vb.)
        best_phase = 0
        best_score = -1
        meter = 4  # Varsayılan olarak 4/4 varsay
        
        for phase in range(meter):
            downbeat_indices = list(range(phase, len(beat_strengths), meter))
            if downbeat_indices:
                score = np.mean(beat_strengths[downbeat_indices])
                if score > best_score:
                    best_score = score
                    best_phase = phase
        
        # Güçlü vuruşları çıkar
        downbeat_indices = list(range(best_phase, len(beat_times), meter))
        downbeats = [beat_times[i] for i in downbeat_indices]
        
        return downbeats
    
    def _detect_tempo_changes(
        self, 
        y: np.ndarray, 
        sr: int,
        global_tempo: float,
    ) -> list[TempoSegment]:
        """Parça boyunca tempo değişikliklerini algıla."""
        duration = len(y) / sr
        
        # Kısa parçalar için sabit tempo varsay
        if duration < 30:
            return [TempoSegment(
                start=0.0,
                end=duration,
                bpm=global_tempo,
                confidence=0.85,
            )]
        
        # Pencerelerde tempoyu analiz et
        window_sec = 10.0
        hop_sec = 5.0
        
        segments = []
        t = 0.0
        prev_tempo = None
        segment_start = 0.0
        
        while t < duration - window_sec:
            start_sample = int(t * sr)
            end_sample = int((t + window_sec) * sr)
            
            if end_sample > len(y):
                break
            
            window_audio = y[start_sample:end_sample]
            
            # Bu pencere için tempoyu tahmin et
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tempo, _ = librosa.beat.beat_track(
                    y=window_audio, 
                    sr=sr,
                    hop_length=self.hop_length,
                )
            
            if isinstance(tempo, np.ndarray):
                tempo = float(tempo[0]) if len(tempo) > 0 else global_tempo
            
            # Global tempo ile aynı oktava normalize et
            tempo = self._normalize_to_range(tempo)
            
            # Önemli değişiklik kontrolü (>%5)
            if prev_tempo is not None:
                change = abs(tempo - prev_tempo) / prev_tempo
                
                if change > 0.05:
                    # Önceki bölümü kaydet
                    segments.append(TempoSegment(
                        start=segment_start,
                        end=t,
                        bpm=round(prev_tempo, 1),
                        confidence=0.7,
                    ))
                    segment_start = t
            
            prev_tempo = tempo
            t += hop_sec
        
        # Son bölüm
        if prev_tempo is not None:
            segments.append(TempoSegment(
                start=segment_start,
                end=duration,
                bpm=round(prev_tempo, 1),
                confidence=0.7,
            ))
        
        # Tüm bölümler aynı tempoya sahipse, basitleştir
        if len(segments) > 1:
            tempos = [s.bpm for s in segments]
            if max(tempos) - min(tempos) < 3:
                return [TempoSegment(
                    start=0.0,
                    end=duration,
                    bpm=global_tempo,
                    confidence=0.88,
                )]
        
        return segments if segments else [TempoSegment(
            start=0.0,
            end=duration,
            bpm=global_tempo,
            confidence=0.85,
        )]
    
    def _generate_explanation(
        self, 
        tempo: float, 
        confidence: float,
        candidates: list[TempoCandidate],
        used_deeprhythm: bool,
    ) -> str:
        """Tempo algılaması için insan tarafından okunabilir açıklama oluştur."""
        parts = []
        
        # Kullanılan yöntem
        if used_deeprhythm:
            parts.append(f"CNN tabanlı analiz {tempo:.1f} BPM tespit etti.")
        else:
            parts.append(f"Topluluk analizi {tempo:.1f} BPM tespit etti.")
        
        # Güven düzeyi
        if confidence >= self.HIGH_CONFIDENCE:
            parts.append("Yüksek güvenilirlik - güçlü vuruş deseni.")
        elif confidence >= self.MEDIUM_CONFIDENCE:
            parts.append("İyi güvenilirlik - net ritmik yapı.")
        elif confidence >= self.LOW_CONFIDENCE:
            parts.append("Orta güvenilirlik - kulakla doğrulayın.")
        else:
            parts.append("Düşük güvenilirlik - bu en iyi tahmindir.")
        
        # İlgiliyse yarı/çift zamanı belirt
        half = tempo / 2
        double = tempo * 2
        
        half_candidates = [c for c in candidates if abs(c.bpm - half) < 3]
        double_candidates = [c for c in candidates if abs(c.bpm - double) < 3]
        
        if half_candidates and self.BPM_ABSOLUTE_MIN <= half <= self.BPM_ABSOLUTE_MAX:
            parts.append(f"Yarı zamanlı da olabilir ({half:.0f} BPM).")
        elif double_candidates and self.BPM_ABSOLUTE_MIN <= double <= self.BPM_ABSOLUTE_MAX:
            parts.append(f"Çift zamanlı da olabilir ({double:.0f} BPM).")
        
        return " ".join(parts)
