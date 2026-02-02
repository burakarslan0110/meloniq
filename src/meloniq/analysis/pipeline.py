"""
Tüm analizcileri yöneten ana analiz boru hattı (pipeline).

Şunları sağlar:
- Tek bir çağrı ile uçtan uca analiz
- UI güncellemeleri için ilerleme geri aramaları (callbacks)
- Tekrarlanan analizler için önbellekleme
- Bireysel analizcilere erişim
"""

import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

import numpy as np

from ..audio_io.loader import AudioLoader, AudioData
from ..models.results import AnalysisResult, TrackInfo
from .tempo import TempoAnalyzer
from .key import KeyAnalyzer
from .meter import MeterAnalyzer
from .structure import StructureAnalyzer
from .loudness import LoudnessAnalyzer
from .chords import ChordAnalyzer


@dataclass
class AnalysisOptions:
    """Analiz boru hattı seçenekleri."""
    detect_tempo: bool = True
    detect_key: bool = True
    detect_meter: bool = True
    detect_structure: bool = True
    detect_chords: bool = False  # İsteğe bağlı, varsayılan olarak kapalı
    detect_loudness: bool = True
    
    # Gelişmiş seçenekler
    detect_tempo_changes: bool = True
    detect_key_changes: bool = True
    detect_downbeats: bool = True
    
    # Performans
    use_cache: bool = True
    cache_dir: Optional[Path] = None


class AnalysisPipeline:
    """
    Müzik analizi için ana analiz boru hattı.
    
    Tüm analizcileri koordine eder ve birleşik bir arayüz sağlar.
    İlerleme geri aramalarını ve önbelleklemeyi destekler.
    """
    
    def __init__(self, options: Optional[AnalysisOptions] = None):
        self.options = options or AnalysisOptions()
        
        # Analizcileri başlat
        self.tempo_analyzer = TempoAnalyzer()
        self.key_analyzer = KeyAnalyzer()
        self.meter_analyzer = MeterAnalyzer()
        self.structure_analyzer = StructureAnalyzer()
        self.loudness_analyzer = LoudnessAnalyzer()
        self.chord_analyzer = ChordAnalyzer()
        
        # Ses yükleyici (analiz için - 22050 Hz mono)
        self.loader = AudioLoader(target_sr=22050)
        
        # Önbellek dizini
        if self.options.cache_dir:
            self.cache_dir = self.options.cache_dir
        else:
            self.cache_dir = Path.home() / ".meloniq" / "cache"
        
        if self.options.use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def analyze(
        self,
        path: str | Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> AnalysisResult:
        """
        Bir ses dosyasında tam analiz gerçekleştir.
        
        Args:
            path: Ses dosyasının yolu
            progress_callback: İsteğe bağlı callback(stage_name, progress_0_to_1)
            
        Returns:
            Tam AnalysisResult
        """
        path = Path(path)
        start_time = time.time()
        
        def update_progress(stage: str, progress: float):
            if progress_callback:
                progress_callback(stage, progress)
        
        # Önbelleği kontrol et
        if self.options.use_cache:
            cached = self._load_from_cache(path)
            if cached:
                update_progress("Complete (cached)", 1.0)
                return cached
        
        # Sesi yükle
        update_progress("Loading audio", 0.0)
        audio = self.loader.load(path, mono=True)
        y = audio.samples_mono
        sr = audio.sample_rate
        
        update_progress("Loading audio", 1.0)
        
        # Parça bilgisi
        track_info = TrackInfo(
            path=str(path.absolute()),
            filename=path.name,
            duration=audio.duration,
            sample_rate=audio.sample_rate,
            channels=audio.channels,
            bit_depth=audio.bit_depth,
            format=audio.format,
        )
        
        # Tempo analizi (önce, diğerleri vuruş bilgisini kullanabilir)
        update_progress("Analyzing tempo", 0.1)
        tempo_result = self.tempo_analyzer.analyze(
            y, sr,
            detect_downbeats=self.options.detect_downbeats,
        )
        beat_times = tempo_result.beats
        
        update_progress("Analyzing tempo", 0.25)
        
        # Ton analizi
        update_progress("Analyzing key", 0.3)
        key_result = self.key_analyzer.analyze(
            y, sr,
            detect_modulations=self.options.detect_key_changes,
        )
        update_progress("Analyzing key", 0.45)
        
        # Ölçü analizi
        update_progress("Analyzing meter", 0.5)
        meter_result = self.meter_analyzer.analyze(y, sr, beat_times=beat_times)
        
        # Giriş sayımını (count-in) algılanan ölçü ile güncelle
        if tempo_result.count_in:
            tempo_result.count_in.meter = meter_result.value
            tempo_result.count_in.beats_per_bar = meter_result.numerator
        
        update_progress("Analyzing meter", 0.6)
        
        # Yapı analizi
        update_progress("Analyzing structure", 0.65)
        structure_result = self.structure_analyzer.analyze(y, sr, beat_times=beat_times)
        update_progress("Analyzing structure", 0.75)
        
        # Ses şiddeti/istatistik analizi
        update_progress("Analyzing loudness", 0.8)
        
        # Zaten yüklenmiş ses verisini kullan (RAM tasarrufu)
        # Mono ses loudness analizi için yeterlidir
        loudness_result = self.loudness_analyzer.analyze(
            audio.samples,
            audio.sample_rate,
        )
        update_progress("Analyzing loudness", 0.9)
        
        # Akor analizi (isteğe bağlı)
        chord_result = None
        if self.options.detect_chords:
            update_progress("Analyzing chords", 0.92)
            chord_result = self.chord_analyzer.analyze(
                y, sr,
                beat_times=beat_times,
                enabled=True,
            )
        
        update_progress("Finalizing", 0.98)
        
        # Sonucu oluştur
        analysis_time = time.time() - start_time
        
        result = AnalysisResult(
            track=track_info,
            tempo=tempo_result,
            key=key_result,
            meter=meter_result,
            structure=structure_result,
            chords=chord_result,
            audio_stats=loudness_result,
            analysis_version="1.0.0",
            analysis_time_seconds=round(analysis_time, 2),
        )
        
        # Önbelleğe kaydet
        if self.options.use_cache:
            self._save_to_cache(path, result)
        
        update_progress("Complete", 1.0)
        
        return result
    
    def analyze_tempo_only(
        self,
        path: str | Path,
    ):
        """Hızlı sadece-tempo analizi."""
        audio = self.loader.load(path, mono=True)
        return self.tempo_analyzer.analyze(audio.samples_mono, audio.sample_rate)
    
    def analyze_key_only(
        self,
        path: str | Path,
    ):
        """Hızlı sadece-ton analizi."""
        audio = self.loader.load(path, mono=True)
        return self.key_analyzer.analyze(audio.samples_mono, audio.sample_rate)
    
    def _get_cache_path(self, audio_path: Path) -> Path:
        """Dosya hash'ine göre önbellek dosyası yolu oluştur."""
        # Hash girişi olarak dosya boyutu + değişiklik zamanı + yol kullan
        stat = audio_path.stat()
        hash_input = f"{audio_path.absolute()}:{stat.st_size}:{stat.st_mtime}"
        file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:16]
        return self.cache_dir / f"{file_hash}.json"
    
    def _load_from_cache(self, path: Path) -> Optional[AnalysisResult]:
        """Varsa önbelleğe alınmış analizi yükle."""
        cache_path = self._get_cache_path(path)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return AnalysisResult.model_validate(data)
        except Exception:
            # Geçersiz önbellek, kaldır
            cache_path.unlink(missing_ok=True)
            return None
    
    def _save_to_cache(self, path: Path, result: AnalysisResult):
        """Analizi önbelleğe kaydet."""
        cache_path = self._get_cache_path(path)
        
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, indent=2)
        except Exception:
            pass  # Önbellek hatası kritik değil
    
    def clear_cache(self):
        """Tüm önbelleğe alınmış analizleri temizle."""
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
    
    def export_json(self, result: AnalysisResult, output_path: str | Path):
        """Analiz sonucunu JSON dosyasına aktar."""
        output_path = Path(output_path)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load_json(path: str | Path) -> AnalysisResult:
        """JSON dosyasından analiz sonucunu yükle."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return AnalysisResult.model_validate(data)
