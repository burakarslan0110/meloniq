"""
Meloniq - Müzik Analiz Uygulaması
"""

import sys
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTabWidget, QSizePolicy,
    QFileDialog, QMessageBox, QFrame,
    QStackedWidget, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer, QSize
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap

from ..audio_io.loader import AudioLoader
from ..audio_io.youtube_downloader import YouTubeDownloader, DownloadResult
from ..analysis.pipeline import AnalysisPipeline, AnalysisOptions
from ..models.results import AnalysisResult
from ..config import Config
from ..resources.localization import Localization

try:
    from ..audio_capture.capture_manager import CaptureManager
    from ..audio_capture.system_audio import get_loopback_devices, SOUNDDEVICE_AVAILABLE
    CAPTURE_AVAILABLE = True
except ImportError:
    CAPTURE_AVAILABLE = False
    CaptureManager = None
    SOUNDDEVICE_AVAILABLE = False

try:
    import sounddevice as sd
    MICROPHONE_AVAILABLE = True
except ImportError:
    MICROPHONE_AVAILABLE = False


class AnalysisWorker(QThread):
    progress = Signal(str, float)
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, pipeline, path):
        super().__init__()
        self.pipeline = pipeline
        self.path = path
    
    def run(self):
        try:
            result = self.pipeline.analyze(self.path, progress_callback=lambda s, p: self.progress.emit(s, p))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ArrayAnalysisWorker(QThread):
    progress = Signal(str, float)
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, pipeline, audio, sample_rate):
        super().__init__()
        self.pipeline = pipeline
        self.audio = audio
        self.sample_rate = sample_rate
    
    def run(self):
        try:
            import soundfile as sf
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = Path(f.name)
            sf.write(temp_path, self.audio, self.sample_rate)
            result = self.pipeline.analyze(temp_path, progress_callback=lambda s, p: self.progress.emit(s, p))
            temp_path.unlink(missing_ok=True)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class YouTubeDownloadWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self, downloader, url):
        super().__init__()
        self.downloader = downloader
        self.url = url
    
    def run(self):
        try:
            result = self.downloader.download(self.url, progress_callback=lambda p, m: self.progress.emit(p, m))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    
    BG = "#F8F8F8"
    CARD = "#FFFFFF"
    TEXT = "#1A1A1A"
    TEXT2 = "#666666"
    GREEN = "#00C853"
    BLUE = "#2979FF"
    ORANGE = "#FF6D00"
    RED = "#E53935"
    
    def __init__(self):
        super().__init__()
        
        self.config = Config()
        self.current_lang = self.config.language
        
        self.setWindowTitle("Meloniq")
        self.setFixedSize(560, 640)  # Increased height to prevent overlapping
        self.setAcceptDrops(True)
        
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        
        self._load_icon()
        
        self.pipeline = AnalysisPipeline(AnalysisOptions(use_cache=False))
        self.youtube_downloader = YouTubeDownloader()
        self.audio_loader = AudioLoader()
        
        self.capture_manager = None
        if CAPTURE_AVAILABLE:
            self.capture_manager = CaptureManager(sample_rate=44100, channels=2, buffer_duration=120.0)
        
        self._mic_audio = []
        self._mic_recording = False
        self._mic_stream = None
        self._is_capturing = False
        self._worker = None
        
        self._capture_timer = QTimer()
        self._capture_timer.timeout.connect(self._update_capture_duration)
        
        self._setup_ui()
        self._update_texts()
        
    def tr(self, key, **kwargs):
        return Localization.get(key, self.current_lang, **kwargs)

    def _load_icon(self):
        try:
            icon_path = Path(__file__).parent.parent / "resources" / "icon.ico"
            if not icon_path.exists():
                icon_path = Path(__file__).parent.parent / "resources" / "logo.png"
            
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                self._logo_path = Path(__file__).parent.parent / "resources" / "logo.png"
            else:
                self._logo_path = None
        except:
            self._logo_path = None
    
    def _setup_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background-color: {self.BG};")
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 20, 24, 20)
        
        # === HEADER ===
        header = QVBoxLayout()
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setSpacing(8)
        
        if self._logo_path and self._logo_path.exists():
            logo = QLabel()
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(self._logo_path)).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo.setPixmap(pixmap)
            header.addWidget(logo)
        
        self.title_lbl = QLabel("Meloniq")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_lbl.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {self.GREEN}; letter-spacing: 2px;")
        header.addWidget(self.title_lbl)
        
        self.subtitle_lbl = QLabel()
        self.subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_lbl.setStyleSheet(f"color: {self.TEXT2}; font-size: 12px;")
        header.addWidget(self.subtitle_lbl)
        
        layout.addLayout(header)
        
        # === SEKMELER ===
        
        # Sekme butonları
        tab_btn_row = QHBoxLayout()
        tab_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tab_btn_row.setSpacing(0)
        
        self.tab_buttons = QButtonGroup()
        self.tab_buttons.setExclusive(True)
        self.tab_btn_widgets = []
        
        self.tab_keys = ["tab_file", "tab_youtube", "tab_system", "tab_mic"]
        
        for i, key in enumerate(self.tab_keys):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #E8E8E8;
                    border: none;
                    padding: 8px 16px;
                    margin: 0 2px;
                    border-radius: 6px 6px 0 0;
                    color: {self.TEXT2};
                    font-size: 12px;
                    outline: none;
                }}
                QPushButton:checked {{
                    background: {self.GREEN};
                    color: white;
                    font-weight: bold;
                }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tab_buttons.addButton(btn, i)
            tab_btn_row.addWidget(btn)
            self.tab_btn_widgets.append(btn)
        
        layout.addLayout(tab_btn_row)
        
        # İçerik alanı
        self.tab_stack = QStackedWidget()
        self.tab_stack.setMinimumHeight(130)
        self.tab_stack.setStyleSheet(f"""
            QStackedWidget {{
                background: {self.CARD};
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }}
        """)
        
        # Dosya
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setContentsMargins(12, 12, 12, 12)
        file_layout.setSpacing(8)
        
        self.open_btn = QPushButton()
        self.open_btn.setMinimumHeight(48)
        self.open_btn.setStyleSheet(self._btn_style(self.GREEN))
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(self._open_file)
        file_layout.addWidget(self.open_btn)
        
        self.drag_lbl = self._info_label("")
        file_layout.addWidget(self.drag_lbl)
        self.tab_stack.addWidget(file_tab)
        
        # YouTube
        yt_tab = QWidget()
        yt_layout = QVBoxLayout(yt_tab)
        yt_layout.setContentsMargins(12, 12, 12, 12)
        yt_layout.setSpacing(8)
        
        self.url_input = QLineEdit()
        self.url_input.setMinimumHeight(44)
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background: #F0F0F0;
                border: 2px solid #D0D0D0;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: {self.TEXT};
            }}
            QLineEdit:focus {{
                border-color: {self.GREEN};
                outline: none;
            }}
        """)
        self.url_input.returnPressed.connect(self._download_youtube)
        yt_layout.addWidget(self.url_input)
        
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(44)
        self.download_btn.setStyleSheet(self._btn_style(self.BLUE))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self._download_youtube)
        yt_layout.addWidget(self.download_btn)
        self.tab_stack.addWidget(yt_tab)
        
        # Sistem
        sys_tab = QWidget()
        sys_layout = QVBoxLayout(sys_tab)
        sys_layout.setContentsMargins(12, 12, 12, 12)
        sys_layout.setSpacing(8)
        
        self.sys_record_btn = QPushButton()
        self.sys_record_btn.setMinimumHeight(48)
        self.sys_record_btn.setStyleSheet(self._btn_style(self.ORANGE))
        self.sys_record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sys_record_btn.clicked.connect(self._toggle_system_capture)
        self.sys_record_btn.setEnabled(CAPTURE_AVAILABLE)
        sys_layout.addWidget(self.sys_record_btn)
        
        self.sys_status = QLabel("Hazır" if CAPTURE_AVAILABLE else "Kullanılamıyor")
        self.sys_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sys_status.setStyleSheet(f"color: {self.TEXT2}; font-size: 12px;")
        sys_layout.addWidget(self.sys_status)
        
        self.sys_analyze_btn = QPushButton()
        self.sys_analyze_btn.setMinimumHeight(40)
        self.sys_analyze_btn.setStyleSheet(self._btn_style(self.GREEN))
        self.sys_analyze_btn.clicked.connect(self._analyze_captured)
        self.sys_analyze_btn.hide()
        sys_layout.addWidget(self.sys_analyze_btn)
        self.tab_stack.addWidget(sys_tab)
        
        # Mikrofon
        mic_tab = QWidget()
        mic_layout = QVBoxLayout(mic_tab)
        mic_layout.setContentsMargins(12, 12, 12, 12)
        mic_layout.setSpacing(8)
        
        self.mic_record_btn = QPushButton()
        self.mic_record_btn.setMinimumHeight(48)
        self.mic_record_btn.setStyleSheet(self._btn_style(self.BLUE))
        self.mic_record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_record_btn.clicked.connect(self._toggle_mic_recording)
        self.mic_record_btn.setEnabled(MICROPHONE_AVAILABLE)
        mic_layout.addWidget(self.mic_record_btn)
        
        self.mic_status = QLabel("Hazır" if MICROPHONE_AVAILABLE else "Kullanılamıyor")
        self.mic_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mic_status.setStyleSheet(f"color: {self.TEXT2}; font-size: 12px;")
        mic_layout.addWidget(self.mic_status)
        
        self.mic_analyze_btn = QPushButton()
        self.mic_analyze_btn.setMinimumHeight(40)
        self.mic_analyze_btn.setStyleSheet(self._btn_style(self.GREEN))
        self.mic_analyze_btn.clicked.connect(self._analyze_mic)
        self.mic_analyze_btn.hide()
        mic_layout.addWidget(self.mic_analyze_btn)
        self.tab_stack.addWidget(mic_tab)
        
        self.tab_buttons.idClicked.connect(self._on_tab_changed)
        self.tab_buttons.button(0).setChecked(True)
        
        layout.addWidget(self.tab_stack)
        
        # === SONUÇLAR ===
        results = QHBoxLayout()
        results.setSpacing(12)
        
        self.bpm_card_lbl = None
        self.bpm_card = self._create_card("BPM", self.GREEN)
        self.bpm_value = self.bpm_card.findChild(QLabel, "value")
        self.bpm_card_lbl = self.bpm_card.findChild(QLabel, "label")
        results.addWidget(self.bpm_card)
        
        self.key_card = self._create_card("TON", self.BLUE)
        self.key_value = self.key_card.findChild(QLabel, "value")
        self.key_card_lbl = self.key_card.findChild(QLabel, "label")
        results.addWidget(self.key_card)
        
        self.meter_card = self._create_card("ÖLÇÜ", self.ORANGE)
        self.meter_value = self.meter_card.findChild(QLabel, "value")
        self.meter_card_lbl = self.meter_card.findChild(QLabel, "label")
        results.addWidget(self.meter_card)
        
        layout.addLayout(results)
        
        # === DURUM ===
        status_row = QHBoxLayout()
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color: {self.TEXT2}; font-size: 11px;")
        status_row.addWidget(self.status_label)
        
        status_row.addStretch()
        
        # Language Toggle
        self.lang_btn = QPushButton("EN" if self.current_lang == "tr" else "TR")
        self.lang_btn.setFixedSize(30, 26)
        self.lang_btn.setStyleSheet(self._small_btn_style())
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_btn.clicked.connect(self._toggle_language)
        status_row.addWidget(self.lang_btn)
        
        layout.addLayout(status_row)
        
        # === FOOTER ===
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        
        footer = QVBoxLayout()
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setSpacing(4)
        footer.setContentsMargins(0, 10, 0, 0)
        
        self.dev_label = QLabel()
        self.dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dev_label.setStyleSheet(f"color: {self.TEXT2}; font-size: 10px;")
        footer.addWidget(self.dev_label)
        
        github_btn = QPushButton("GitHub")
        github_btn.setFixedSize(60, 24)
        github_btn.setStyleSheet(f"""
            QPushButton {{
                background: #333333;
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 11px;
                font-weight: bold;
                outline: none;
            }}
            QPushButton:hover {{
                background: #000000;
            }}
        """)
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/burakarslan0110/meloniq")))
        
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.addWidget(github_btn)
        footer.addLayout(btn_row)
        
        layout.addLayout(footer)

    def _small_btn_style(self):
        return f"""
            QPushButton {{
                background: #E0E0E0;
                border: none;
                border-radius: 4px;
                padding: 4px 6px;
                color: {self.TEXT};
                font-size: 11px;
                outline: none;
            }}
        """

    def _toggle_language(self):
        new_lang = "tr" if self.current_lang == "en" else "en"
        self.current_lang = new_lang
        self.config.language = new_lang
        self._update_texts()
        self.lang_btn.setText("EN" if new_lang == "tr" else "TR")

    def _update_texts(self):
        self.setWindowTitle(self.tr("app_title"))
        self.subtitle_lbl.setText(self.tr("subtitle"))
        
        for i, key in enumerate(self.tab_keys):
            self.tab_btn_widgets[i].setText(self.tr(key))
            
        self.open_btn.setText(self.tr("btn_open_file"))
        self.drag_lbl.setText(self.tr("drag_drop_hint"))
        
        self.url_input.setPlaceholderText(self.tr("yt_placeholder"))
        self.download_btn.setText(self.tr("btn_download_analyze"))
        
        self.sys_status.setText(self.tr("status_ready") if CAPTURE_AVAILABLE else self.tr("status_unavailable"))
        if self._is_capturing:
            self.sys_record_btn.setText(self.tr("btn_stop"))
        else:
            self.sys_record_btn.setText(self.tr("btn_record_system"))
        self.sys_analyze_btn.setText(self.tr("btn_analyze"))
        
        self.mic_status.setText(self.tr("status_ready") if MICROPHONE_AVAILABLE else self.tr("status_unavailable"))
        if self._mic_recording:
             self.mic_record_btn.setText(self.tr("btn_stop"))
        else:
             self.mic_record_btn.setText(self.tr("btn_record_mic"))
        self.mic_analyze_btn.setText(self.tr("btn_analyze"))

        if self.bpm_card_lbl: self.bpm_card_lbl.setText(self.tr("card_bpm"))
        if self.key_card_lbl: self.key_card_lbl.setText(self.tr("card_key"))
        if self.meter_card_lbl: self.meter_card_lbl.setText(self.tr("card_meter"))
        
        self.status_label.setText(self.tr("status_ready"))
        self.dev_label.setText(self.tr("dev_name"))
    
    def _on_tab_changed(self, idx):
        if self._is_capturing:
            self._stop_system_capture()
        if self._mic_recording:
            self._stop_mic()
            
        self.tab_stack.setCurrentIndex(idx)
        
    def _btn_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                outline: none;
            }}
            QPushButton:focus {{
                outline: none;
                border: none;
            }}
            QPushButton:disabled {{
                background-color: #BDBDBD;
            }}
        """
    
    def _info_label(self, text):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {self.TEXT2}; font-size: 11px; margin-top: 6px;")
        return lbl
    
    def _create_card(self, label, color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {self.CARD};
                border-radius: 10px;
                border: none;
            }}
        """)
        card.setMinimumHeight(100)
        
        lo = QVBoxLayout(card)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.setSpacing(4)
        lo.setContentsMargins(10, 14, 10, 14)
        
        val = QLabel("---")
        val.setObjectName("value")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color}; border: none;")
        lo.addWidget(val)
        
        lbl = QLabel(label)
        lbl.setObjectName("label")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {self.TEXT2}; letter-spacing: 1px; border: none;")
        lo.addWidget(lbl)
        
        return card
    
    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("btn_open_file"), "", "Audio (*.mp3 *.wav *.flac *.ogg *.m4a)")
        if path:
            self._analyze_file(Path(path))
    
    def _download_youtube(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not YouTubeDownloader.is_available():
            QMessageBox.warning(self, self.tr("status_error"), self.tr("err_yt_dlp_missing"))
            return
        if not YouTubeDownloader.is_valid_url(url):
            QMessageBox.warning(self, self.tr("status_error"), self.tr("err_invalid_link"))
            return
        
        self.download_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.status_label.setText(self.tr("status_downloading"))
        
        if self._is_capturing: self._stop_system_capture()
        if self._mic_recording: self._stop_mic()
        
        for btn in self.tab_btn_widgets:
            btn.setEnabled(False)

        self._worker = YouTubeDownloadWorker(self.youtube_downloader, url)
        self._worker.progress.connect(lambda p, m: self.status_label.setText(m))
        self._worker.finished.connect(self._on_download_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()
    
    @Slot(object)
    def _on_download_done(self, result):
        self.download_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.url_input.clear()
        
        if result.success and result.file_path:
            self._analyze_file(result.file_path)
        else:
            for btn in self.tab_btn_widgets:
                btn.setEnabled(True)
            QMessageBox.warning(self, self.tr("status_error"), result.error)
            self.status_label.setText(self.tr("status_error"))
    
    def _toggle_system_capture(self):
        if self._is_capturing:
            self._stop_system_capture()
        else:
            self._start_system_capture()
    
    def _start_system_capture(self):
        if not self.capture_manager:
            return
        devices = get_loopback_devices()
        if not devices:
            QMessageBox.warning(self, self.tr("status_error"), self.tr("err_no_device"))
            return
        if self.capture_manager.start_capture(devices[0]):
            self._is_capturing = True
            self.sys_record_btn.setText(self.tr("btn_stop"))
            self.sys_record_btn.setStyleSheet(self._btn_style(self.RED))
            self.sys_status.setText("0s")
            self.sys_analyze_btn.hide()
            self._capture_timer.start(100)
    
    def _stop_system_capture(self):
        if self.capture_manager:
            self.capture_manager.stop_capture()
        self._is_capturing = False
        self._capture_timer.stop()
        self.sys_record_btn.setText(self.tr("btn_record_system"))
        self.sys_record_btn.setStyleSheet(self._btn_style(self.ORANGE))
        if self.capture_manager:
            dur = self.capture_manager.get_available_seconds()
            if dur >= 5:
                self.sys_status.setText(self.tr("msg_recorded", s=dur))
                self.sys_analyze_btn.show()
            else:
                self.sys_status.setText(self.tr("msg_too_short"))
    
    def _update_capture_duration(self):
        if self.capture_manager and self._is_capturing:
            dur = self.capture_manager.get_available_seconds()
            self.sys_status.setText(f"{dur:.0f}s")
    
    def _analyze_captured(self):
        if not self.capture_manager:
            return
        audio = self.capture_manager.get_captured_audio()
        if audio is None or len(audio) < 44100 * 5:
            return
        self._analyze_array(audio, 44100)
    
    def _toggle_mic_recording(self):
        if self._mic_recording:
            self._stop_mic()
        else:
            self._start_mic()
    
    def _start_mic(self):
        if not MICROPHONE_AVAILABLE:
            return
        self._mic_audio = []
        self._mic_recording = True
        
        def cb(indata, frames, time, status):
            if self._mic_recording:
                self._mic_audio.append(indata.copy())
        
        try:
            self._mic_stream = sd.InputStream(samplerate=44100, channels=1, callback=cb)
            self._mic_stream.start()
            self.mic_record_btn.setText(self.tr("btn_stop"))
            self.mic_record_btn.setStyleSheet(self._btn_style(self.RED))
            self.mic_status.setText(self.tr("msg_recording"))
            self.mic_analyze_btn.hide()
            self._mic_timer = QTimer()
            self._mic_timer.timeout.connect(self._update_mic_dur)
            self._mic_timer.start(100)
        except Exception as e:
            QMessageBox.warning(self, self.tr("status_error"), str(e))
            self._mic_recording = False
    
    def _stop_mic(self):
        self._mic_recording = False
        if hasattr(self, '_mic_timer'):
            self._mic_timer.stop()
        if self._mic_stream:
            self._mic_stream.stop()
            self._mic_stream.close()
            self._mic_stream = None
        self.mic_record_btn.setText(self.tr("btn_record_mic"))
        self.mic_record_btn.setStyleSheet(self._btn_style(self.BLUE))
        if self._mic_audio:
            dur = sum(len(c) for c in self._mic_audio) / 44100
            if dur >= 5:
                self.mic_status.setText(self.tr("msg_recorded", s=dur))
                self.mic_analyze_btn.show()
            else:
                self.mic_status.setText(self.tr("msg_too_short"))
    
    def _update_mic_dur(self):
        if self._mic_audio:
            dur = sum(len(c) for c in self._mic_audio) / 44100
            self.mic_status.setText(f"{dur:.0f}s")
    
    def _analyze_mic(self):
        if not self._mic_audio:
            return
        audio = np.concatenate(self._mic_audio, axis=0).flatten()
        self._analyze_array(audio, 44100)
    
    def _analyze_file(self, path):
        self.status_label.setText(f"Analiz: {path.name[:20]}")
        self._set_btns(False)
        self._worker = AnalysisWorker(self.pipeline, path)
        self._worker.progress.connect(lambda s, p: self.status_label.setText(f"{s}..."))
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()
    
    def _analyze_array(self, audio, sr):
        self.status_label.setText("Analiz...")
        self._set_btns(False)
        self._worker = ArrayAnalysisWorker(self.pipeline, audio, sr)
        self._worker.progress.connect(lambda s, p: self.status_label.setText(f"{s}..."))
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()
    
    def _set_btns(self, on):
        self.open_btn.setEnabled(on)
        self.download_btn.setEnabled(on)
        self.sys_record_btn.setEnabled(on and CAPTURE_AVAILABLE)
        self.mic_record_btn.setEnabled(on and MICROPHONE_AVAILABLE)
        
        for btn in self.tab_btn_widgets:
            btn.setEnabled(on)
    
    @Slot(object)
    def _on_done(self, result):
        self.bpm_value.setText(f"{result.tempo.global_bpm:.0f}")
        self.key_value.setText(result.key.global_key)
        self.meter_value.setText(result.meter.value)
        self._set_btns(True)
        self.status_label.setText(self.tr("status_completed"))
    
    @Slot(str)
    def _on_error(self, err):
        self._set_btns(True)
        QMessageBox.warning(self, self.tr("status_error"), err)
        self.status_label.setText(self.tr("status_error"))
    
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
    
    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in ['.mp3', '.wav', '.flac', '.ogg', '.m4a']:
                self._analyze_file(p)
                break
    
    def closeEvent(self, e):
        if self._mic_recording:
            self._stop_mic()
        if self._is_capturing and self.capture_manager:
            self.capture_manager.stop_capture()
        self.youtube_downloader.cleanup_all()
        e.accept()
