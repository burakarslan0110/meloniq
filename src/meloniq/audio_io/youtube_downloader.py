"""
YouTube ses indirme modülü.

YouTube linklerinden ses indirmek için yt-dlp kullanır.
En iyi kalitede indirir ve analiz için WAV'a dönüştürür.
"""

import os
import sys
import tempfile
import shutil
import re
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

# yt-dlp'nin mevcut olup olmadığını kontrol et
_YTDLP_AVAILABLE = False
try:
    import yt_dlp
    _YTDLP_AVAILABLE = True
except ImportError:
    pass


@dataclass
class DownloadResult:
    """YouTube indirme sonucu."""
    success: bool
    file_path: Optional[Path] = None
    title: str = ""
    duration: float = 0.0
    error: str = ""


class YouTubeDownloader:
    """
    YouTube URL'lerinden ses indirir.
    
    En iyi ses kalitesi çıkarımı için yt-dlp kullanır.
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        İndiriciyi başlat.
        
        Args:
            output_dir: İndirilen dosyaların kaydedileceği dizin.
                       Belirtilmezse Downloads/Meloniq_Downloads kullanılır.
        """
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            # Kullanıcının İndirilenler klasöründe Meloniq_Downloads oluştur
            downloads_dir = Path.home() / "Downloads" / "Meloniq_Downloads"
            self.output_dir = downloads_dir
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_progress = 0.0
        self._progress_callback: Optional[Callable[[float, str], None]] = None
    
    @staticmethod
    def is_available() -> bool:
        """yt-dlp'nin yüklü olup olmadığını kontrol et."""
        return _YTDLP_AVAILABLE
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """URL'nin bir YouTube URL'si olup olmadığını kontrol et."""
        if not url:
            return False
        
        # Donmaya neden olan link tiplerini kesin olarak reddet
        invalid_patterns = [
            "youtube.com/playlist",
            "/playlist?",
            "list=",          # Playlist parametresi
            "start_radio=",   # Radyo mix parametresi
            "index=",         # Playlist index parametresi
            "mix=",           # Mix parametresi
        ]
        
        if any(pattern in url for pattern in invalid_patterns):
            # Eğer video ID'si varsa ve list parametresi de varsa, temizleyip kabul edebiliriz
            # Ancak kullanıcıdan temiz link beklemek daha güvenli
            # (Veya download metodunda temizleyeceğiz)
            pass 

        # Temel domain kontrolü
        youtube_patterns = [
            "youtube.com/watch",
            "youtu.be/",
            "youtube.com/shorts/",
            "music.youtube.com/watch",
        ]
        
        return any(pattern in url for pattern in youtube_patterns)
    
    def download(
        self, 
        url: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """
        YouTube URL'sinden ses indir.
        
        Args:
            url: YouTube video URL'si
            progress_callback: İsteğe bağlı geri çağırma(progress_0_to_1, status_message)
            
        Returns:
            Dosya yolu veya hata içeren DownloadResult
        """
        if not _YTDLP_AVAILABLE:
            return DownloadResult(
                success=False,
                error="yt-dlp yüklü değil. Çalıştırın: pip install yt-dlp"
            )
        
        # URL Temizleme işlemi
        # Playlist ve Mix parametrelerini sil ki donmasın
        url = re.sub(r'[&?]list=[^&]*', '', url)
        url = re.sub(r'[&?]start_radio=[^&]*', '', url)
        url = re.sub(r'[&?]index=[^&]*', '', url)
        url = re.sub(r'[&?]mix=[^&]*', '', url)
        url = re.sub(r'[&?]$', '', url)
        
        if not self.is_valid_url(url):
             return DownloadResult(
                success=False,
                error="Geçersiz (veya desteklenmeyen Playlist/Mix) YouTube Linki"
            )
            
        self._progress_callback = progress_callback
        self._current_progress = 0.0
        
        # Benzersiz dosya adı oluştur
        import uuid
        temp_name = f"yt_{uuid.uuid4().hex[:8]}"
        output_template = str(self.output_dir / temp_name)
        
        # FFmpeg yolunu al
        ffmpeg_path = self._find_ffmpeg()
        
        # yt-dlp seçenekleri
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template + '.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,  # Playlist'i kesinlikle indirme
            'playlist_items': '1', # Garanti olsun diye sadece 1. öğe
            'progress_hooks': [self._progress_hook],
            'socket_timeout': 15, # 15 saniye timeout (donmayı önlemek için)
            'retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['dash', 'hls'], # Canlı yayın vs geç
                }
            },
        }
        
        # Logger
        class MyLogger:
            def debug(self, msg): pass
            def warning(self, msg): pass
            def error(self, msg): pass
            
        ydl_opts['logger'] = MyLogger()
        
        # Varsa FFmpeg son işlemcisini ekle
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        try:
            if progress_callback:
                progress_callback(0.0, "YouTube'a bağlanılıyor...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Önce video bilgilerini al (download=False)
                # process=False yaparak hızlıca (extract_flat) bakabiliriz ama başlık için lazım
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as e:
                    if "playlist" in str(e).lower():
                        raise ValueError("Playlist linkleri desteklenmiyor.")
                    raise e

                # Eğer bir playlist ise (noplaylist=True olmasına rağmen dönerse)
                if 'entries' in info:
                     # Genellikle ilk videoyu alırız ama bu riskli, direkt hata verelim
                     # veya ilk entry'i alalım:
                     entries = list(info['entries'])
                     if entries:
                         info = entries[0]
                     else:
                        raise ValueError("Video bilgisi alınamadı.")

                title = info.get('title', 'Bilinmiyor')
                duration = info.get('duration', 0)
                
                # Canlı yayın kontrolü
                if info.get('is_live'):
                    raise ValueError("Canlı yayınlar indirilemez.")

                if progress_callback:
                    progress_callback(0.1, f"İndiriliyor: {title[:40]}...")
                
                # İndir
                ydl.download([url])
            
            # İndirilen dosyayı bul
            downloaded_file = self._find_downloaded_file(output_template)
            
            if downloaded_file:
                if progress_callback:
                    progress_callback(1.0, "İndirme tamamlandı!")
                
                return DownloadResult(
                    success=True,
                    file_path=downloaded_file,
                    title=title,
                    duration=duration,
                )
            else:
                return DownloadResult(
                    success=False,
                    error="Dosya indirildi ancak diskte bulunamadı."
                )
                
        except Exception as e:
            error_msg = str(e)
            self._cleanup_partial(output_template)
            return DownloadResult(
                success=False,
                error=f"İndirme hatası: {error_msg[:100]}"
            )

    def _find_ffmpeg(self) -> Optional[str]:
        """FFmpeg yolunu bul."""
        ffmpeg_path = None
        
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
            possible_paths = [
                base_path / 'ffmpeg.exe',
                base_path / 'ffmpeg' / 'ffmpeg.exe',
                base_path / 'bin' / 'ffmpeg.exe',
            ]
            for p in possible_paths:
                if p.exists():
                    return str(p)
        
        # imageio_ffmpeg dene
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except:
            pass
            
        return None

    def _find_downloaded_file(self, template: str) -> Optional[Path]:
        """İndirilen dosyayı dizinde bul."""
        # Önce mp3 (dönüştürülmüş)
        mp3_path = Path(template + '.mp3')
        if mp3_path.exists():
            return mp3_path
            
        # Diğer formatlar
        import glob
        pattern = template + ".*"
        matches = glob.glob(pattern)
        matches = [m for m in matches if not m.endswith('.part')]
        return Path(matches[0]) if matches else None

    def _cleanup_partial(self, template: str):
        """Kısmi dosyaları temizle."""
        for ext in ['.wav', '.m4a', '.mp3', '.webm', '.opus', '.part']:
            path = Path(template + ext)
            if path.exists():
                try:
                    path.unlink()
                except:
                    pass

    def _progress_hook(self, d):
        """yt-dlp ilerleme kancası."""
        if d['status'] == 'downloading':
            if 'total_bytes' in d and d['total_bytes'] > 0:
                progress = d.get('downloaded_bytes', 0) / d['total_bytes']
            elif 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
                progress = d.get('downloaded_bytes', 0) / d['total_bytes_estimate']
            else:
                progress = 0.5
            
            self._current_progress = 0.1 + progress * 0.8
            
            if self._progress_callback:
                percent = d.get('_percent_str', '?%').strip()
                status = f"İndiriliyor... {percent}"
                self._progress_callback(self._current_progress, status)
        
        elif d['status'] == 'finished':
            if self._progress_callback:
                self._progress_callback(0.95, "WAV formatına dönüştürülüyor...")
    
    def cleanup_all(self):
        """Çıktı dizinindeki tüm indirilen dosyaları sil."""
        if self.output_dir.exists():
            for f in self.output_dir.glob("yt_*"):
                try:
                    f.unlink()
                except:
                    pass
