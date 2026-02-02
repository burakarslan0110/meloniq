"""
WAV, MP3, FLAC ve diğer yaygın formatları destekleyen ses dosyası yükleyicisi.
Birincil arka uç olarak soundfile, yedek olarak librosa kullanır.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np

import soundfile as sf
import librosa


@dataclass
class AudioData:
    """Yüklenen ses verisi için kapsayıcı."""
    samples: np.ndarray  # Ses örnekleri (mono veya stereo)
    sample_rate: int
    duration: float  # Saniye cinsinden süre
    channels: int  # mono için 1, stereo için 2
    path: Path
    
    # Analiz için mono karışım (her zaman mevcut)
    samples_mono: np.ndarray = None
    
    # Dosya meta verisi
    format: str = "unknown"
    subtype: Optional[str] = None
    bit_depth: Optional[int] = None
    
    def __post_init__(self):
        if self.samples_mono is None:
            self.samples_mono = self._to_mono(self.samples)
    
    def _to_mono(self, samples: np.ndarray) -> np.ndarray:
        """Stereo ise mono'ya dönüştür."""
        if samples.ndim == 1:
            return samples
        elif samples.ndim == 2:
            # Mono karışım için kanalların ortalamasını al
            if samples.shape[0] == 2:  # (2, n) format
                return np.mean(samples, axis=0)
            elif samples.shape[1] == 2:  # (n, 2) format
                return np.mean(samples, axis=1)
        return samples


class AudioLoader:
    """
    Diskten ses dosyalarını yükle.
    
    Soundfile/librosa aracılığıyla şunları destekler: WAV, MP3, FLAC, OGG, AIFF ve diğer formatlar.
    """
    
    SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a"}
    
    # Analiz için standart örnekleme oranı
    ANALYSIS_SR = 22050
    
    def __init__(self, target_sr: Optional[int] = None):
        """
        Yükleyiciyi başlat.
        
        Args:
            target_sr: Yeniden örnekleme için hedef oran. None ise, orijinali korur.
                      Analiz için 22050 Hz genellikle yeterli ve daha hızlıdır.
        """
        self.target_sr = target_sr
    
    def load(self, path: str | Path, mono: bool = False) -> AudioData:
        """
        Bir ses dosyası yükle.
        
        Args:
            path: Ses dosyasının yolu
            mono: True ise, hemen mono'ya dönüştür
            
        Returns:
            Örnekler ve meta veriler içeren AudioData
            
        Raises:
            FileNotFoundError: Dosya mevcut değilse
            ValueError: Dosya formatı desteklenmiyorsa
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        
        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported audio format: {ext}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )
        
        # Önce soundfile dene (daha hızlı, WAV/FLAC için daha iyi kalite)
        try:
            return self._load_soundfile(path, mono)
        except Exception:
            # librosa'ya dön (bazı sistemlerde MP3'ü daha iyi işler)
            return self._load_librosa(path, mono)
    
    def _load_soundfile(self, path: Path, mono: bool) -> AudioData:
        """soundfile kullanarak yükle."""
        info = sf.info(path)
        
        samples, sr = sf.read(path, dtype="float32", always_2d=False)
        
        # Kanal düzenini işle
        if samples.ndim == 2:
            # soundfile returns (n_samples, n_channels), transpose to (n_channels, n_samples)
            samples = samples.T
        
        # Gerekirse yeniden örnekle
        if self.target_sr and sr != self.target_sr:
            samples = librosa.resample(
                samples, 
                orig_sr=sr, 
                target_sr=self.target_sr,
                res_type="kaiser_fast"
            )
            sr = self.target_sr
        
        channels = 1 if samples.ndim == 1 else samples.shape[0]
        
        if mono and channels > 1:
            samples = np.mean(samples, axis=0)
            channels = 1
        
        # Bit derinliğini belirle
        bit_depth = None
        if info.subtype:
            if "16" in info.subtype:
                bit_depth = 16
            elif "24" in info.subtype:
                bit_depth = 24
            elif "32" in info.subtype:
                bit_depth = 32
        
        return AudioData(
            samples=samples,
            sample_rate=sr,
            duration=len(samples if samples.ndim == 1 else samples[0]) / sr,
            channels=channels,
            path=path,
            format=info.format,
            subtype=info.subtype,
            bit_depth=bit_depth,
        )
    
    def _load_librosa(self, path: Path, mono: bool) -> AudioData:
        """librosa kullanarak yükle (yedek)."""
        sr = self.target_sr or None  # None means keep original
        
        samples, sr = librosa.load(path, sr=sr, mono=mono)
        
        channels = 1 if samples.ndim == 1 else samples.shape[0]
        duration = len(samples if samples.ndim == 1 else samples[0]) / sr
        
        return AudioData(
            samples=samples,
            sample_rate=sr,
            duration=duration,
            channels=channels,
            path=path,
            format=path.suffix.lstrip(".").upper(),
        )
    
    def load_for_analysis(self, path: str | Path) -> AudioData:
        """
        Analiz için optimize edilmiş sesi yükle (mono, 22050 Hz).
        
        Bu daha hızlıdır ve çoğu analiz görevi için yeterlidir.
        """
        loader = AudioLoader(target_sr=self.ANALYSIS_SR)
        return loader.load(path, mono=True)
    
    @classmethod
    def is_supported(cls, path: str | Path) -> bool:
        """Dosya formatının desteklenip desteklenmediğini kontrol et."""
        return Path(path).suffix.lower() in cls.SUPPORTED_EXTENSIONS
