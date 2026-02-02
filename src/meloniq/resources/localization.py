from typing import Dict

# Dictionary of translations
# Key -> { 'en': 'English Text', 'tr': 'Turkish Text' }
TRANSLATIONS = {
    "app_title": {
        "en": "Meloniq - Music Analysis Tool",
        "tr": "Meloniq - Müzik Analiz Aracı"
    },
    "subtitle": {
        "en": "Music Analysis Tool",
        "tr": "Müzik Analiz Aracı"
    },
    "tab_file": {
        "en": "📁 File",
        "tr": "📁 Dosya"
    },
    "tab_youtube": {
        "en": "▶️ YouTube",
        "tr": "▶️ YouTube"
    },
    "tab_system": {
        "en": "🔊 System",
        "tr": "🔊 Sistem"
    },
    "tab_mic": {
        "en": "🎤 Mic",
        "tr": "🎤 Mikrofon"
    },
    "btn_open_file": {
        "en": "📂 Open File",
        "tr": "📂 Dosya Seç"
    },
    "drag_drop_hint": {
        "en": "Drag & Drop supported",
        "tr": "Sürükle-bırak desteklenir"
    },
    "yt_placeholder": {
        "en": "Paste YouTube link...",
        "tr": "YouTube linkini yapıştır..."
    },
    "btn_download_analyze": {
        "en": "⬇️ Download & Analyze",
        "tr": "⬇️ İndir ve Analiz Et"
    },
    "btn_record_system": {
        "en": "🔊 Record System Audio",
        "tr": "🔊 Sistem Sesini Kaydet"
    },
    "btn_stop": {
        "en": "⏹ Stop",
        "tr": "⏹ Durdur"
    },
    "status_ready": {
        "en": "Ready",
        "tr": "Hazır"
    },
    "status_unavailable": {
        "en": "Unavailable",
        "tr": "Kullanılamıyor"
    },
    "btn_analyze": {
        "en": "🔍 Analyze",
        "tr": "🔍 Analiz Et"
    },
    "btn_record_mic": {
        "en": "🎤 Record Mic",
        "tr": "🎤 Mikrofon Kaydı"
    },
    "btn_console": {
        "en": "📋 Console",
        "tr": "📋 Konsol"
    },
    "dev_name": {
        "en": "Burak Arslan",
        "tr": "Burak Arslan"
    },
    "card_bpm": {
        "en": "BPM",
        "tr": "BPM"
    },
    "card_key": {
        "en": "KEY",
        "tr": "TON"
    },
    "card_meter": {
        "en": "METER",
        "tr": "ÖLÇÜ"
    },
    "status_downloading": {
        "en": "Downloading...",
        "tr": "İndiriliyor..."
    },
    "status_completed": {
        "en": "Completed ✓",
        "tr": "Tamamlandı ✓"
    },
    "status_error": {
        "en": "Error",
        "tr": "Hata"
    },
    "err_yt_dlp_missing": {
        "en": "yt-dlp is not installed",
        "tr": "yt-dlp yüklü değil"
    },
    "err_invalid_link": {
        "en": "Invalid link",
        "tr": "Geçersiz link"
    },
    "err_no_device": {
        "en": "No device found",
        "tr": "Cihaz yok"
    },
    "msg_too_short": {
        "en": "Too short",
        "tr": "Çok kısa"
    },
    "msg_recorded": {
        "en": "{s:.0f}s recorded",
        "tr": "{s:.0f}s kaydedildi"
    },
    "msg_recording": {
        "en": "Recording...",
        "tr": "Kaydediliyor..."
    },
     "msg_connect_yt": {
        "en": "Connecting to YouTube...",
        "tr": "YouTube'a bağlanılıyor..."
    },
    "msg_converting": {
         "en": "Converting to WAV...",
         "tr": "WAV formatına dönüştürülüyor..."
    }
}

class Localization:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Localization, cls).__new__(cls)
        return cls._instance

    def __init__(self):
         # Config will be injected or imported
         pass

    @staticmethod
    def get(key: str, lang: str = "en", **kwargs) -> str:
        """Get translated string."""
        if key not in TRANSLATIONS:
            return key
        
        val_dict = TRANSLATIONS[key]
        text = val_dict.get(lang, val_dict.get("en", key))
        
        if kwargs:
            try:
                text = text.format(**kwargs)
            except:
                pass
        return text
