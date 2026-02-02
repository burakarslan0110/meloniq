"""
Capture panel with input source selection, device selector, and level meter.
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QGroupBox, QProgressBar,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QPainter, QPen

from ..audio_capture.system_audio import (
    AudioDevice, DeviceType,
    get_loopback_devices, get_input_devices,
    SOUNDDEVICE_AVAILABLE,
)


class LevelMeter(QWidget):
    """
    Audio level meter widget.
    
    Shows current RMS level and peak hold.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setMinimumHeight(20)
        self.setMaximumHeight(30)
        
        self._level = 0.0
        self._peak = 0.0
        
        # Colors
        self._bg_color = QColor(40, 40, 45)
        self._low_color = QColor(76, 175, 80)  # Green
        self._mid_color = QColor(255, 193, 7)  # Yellow
        self._high_color = QColor(244, 67, 54)  # Red
        self._peak_color = QColor(255, 255, 255)
    
    def set_level(self, level: float, peak: float):
        """Set current level and peak (0-1 range)."""
        self._level = max(0, min(1, level))
        self._peak = max(0, min(1, peak))
        self.update()
    
    def reset(self):
        """Reset levels to zero."""
        self._level = 0.0
        self._peak = 0.0
        self.update()
    
    def paintEvent(self, event):
        """Paint the level meter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Background
        painter.fillRect(0, 0, width, height, self._bg_color)
        
        # Level bar
        level_width = int(self._level * width)
        
        if level_width > 0:
            # Draw gradient segments
            low_threshold = int(0.6 * width)
            mid_threshold = int(0.85 * width)
            
            # Green section (0-60%)
            green_width = min(level_width, low_threshold)
            if green_width > 0:
                painter.fillRect(0, 0, green_width, height, self._low_color)
            
            # Yellow section (60-85%)
            if level_width > low_threshold:
                yellow_width = min(level_width - low_threshold, mid_threshold - low_threshold)
                if yellow_width > 0:
                    painter.fillRect(low_threshold, 0, yellow_width, height, self._mid_color)
            
            # Red section (85-100%)
            if level_width > mid_threshold:
                red_width = level_width - mid_threshold
                if red_width > 0:
                    painter.fillRect(mid_threshold, 0, red_width, height, self._high_color)
        
        # Peak marker
        if self._peak > 0:
            peak_x = int(self._peak * width) - 2
            if peak_x >= 0:
                painter.setPen(QPen(self._peak_color, 2))
                painter.drawLine(peak_x, 0, peak_x, height)
        
        # Border
        painter.setPen(QPen(QColor(80, 80, 85), 1))
        painter.drawRect(0, 0, width - 1, height - 1)


class CapturePanel(QWidget):
    """
    Panel for audio capture controls.
    
    Contains:
    - Input source selector (File / System Audio / Microphone)
    - Device selector (for System Audio and Microphone)
    - Start/Stop capture buttons
    - Live level meter
    - Live analysis results
    """
    
    # Signals
    source_changed = Signal(str)  # "file", "system", "mic"
    device_changed = Signal(object)  # AudioDevice or None
    capture_start_requested = Signal()
    capture_stop_requested = Signal()
    analyze_captured_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._current_source = "file"
        self._devices: List[AudioDevice] = []
        self._is_capturing = False
        
        self._setup_ui()
        self._refresh_devices()
    
    def _setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Input source group
        source_group = QGroupBox("Input Source")
        source_layout = QVBoxLayout(source_group)
        
        # Source selector
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source:"))
        
        self._source_combo = QComboBox()
        self._source_combo.addItem("Audio File", "file")
        self._source_combo.addItem("System Audio", "system")
        self._source_combo.addItem("Microphone", "mic")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        source_row.addWidget(self._source_combo, stretch=1)
        
        source_layout.addLayout(source_row)
        
        # Device selector
        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Device:"))
        
        self._device_combo = QComboBox()
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        device_row.addWidget(self._device_combo, stretch=1)
        
        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedWidth(30)
        self._refresh_btn.setToolTip("Refresh device list")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        device_row.addWidget(self._refresh_btn)
        
        source_layout.addLayout(device_row)
        
        # Capture controls
        controls_row = QHBoxLayout()
        
        self._start_btn = QPushButton("Start Capture")
        self._start_btn.clicked.connect(self._on_start_clicked)
        controls_row.addWidget(self._start_btn)
        
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._stop_btn.setEnabled(False)
        controls_row.addWidget(self._stop_btn)
        
        source_layout.addLayout(controls_row)
        
        # Level meter
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Level:"))
        
        self._level_meter = LevelMeter()
        level_row.addWidget(self._level_meter, stretch=1)
        
        source_layout.addLayout(level_row)
        
        # Capture duration
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Captured:"))
        
        self._duration_label = QLabel("0.0s")
        duration_row.addWidget(self._duration_label)
        duration_row.addStretch()
        
        self._analyze_btn = QPushButton("Analyze Captured")
        self._analyze_btn.clicked.connect(self._on_analyze_clicked)
        self._analyze_btn.setEnabled(False)
        duration_row.addWidget(self._analyze_btn)
        
        source_layout.addLayout(duration_row)
        
        layout.addWidget(source_group)
        
        # Live results group
        live_group = QGroupBox("Live Estimate")
        live_layout = QVBoxLayout(live_group)
        
        # BPM
        bpm_row = QHBoxLayout()
        bpm_row.addWidget(QLabel("BPM:"))
        self._live_bpm_label = QLabel("---")
        self._live_bpm_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        bpm_row.addWidget(self._live_bpm_label)
        self._live_bpm_conf = QLabel("")
        bpm_row.addWidget(self._live_bpm_conf)
        bpm_row.addStretch()
        live_layout.addLayout(bpm_row)
        
        # Key
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Key:"))
        self._live_key_label = QLabel("---")
        self._live_key_label.setStyleSheet("font-weight: bold;")
        key_row.addWidget(self._live_key_label)
        self._live_key_conf = QLabel("")
        key_row.addWidget(self._live_key_conf)
        key_row.addStretch()
        live_layout.addLayout(key_row)
        
        # Status
        self._status_label = QLabel("Select System Audio or Microphone to capture")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #888;")
        live_layout.addWidget(self._status_label)
        
        layout.addWidget(live_group)
        
        # Check sounddevice availability
        if not SOUNDDEVICE_AVAILABLE:
            self._status_label.setText(
                "⚠️ sounddevice not installed. "
                "Install with: pip install sounddevice"
            )
            self._status_label.setStyleSheet("color: #f44336;")
            self._source_combo.setEnabled(False)
            self._device_combo.setEnabled(False)
            self._start_btn.setEnabled(False)
        
        # Initial state
        self._update_ui_state()
    
    def _refresh_devices(self):
        """Refresh the device list based on current source."""
        self._device_combo.clear()
        self._devices = []
        
        source = self._current_source
        
        if source == "file":
            self._device_combo.addItem("N/A (use Open File)", None)
            self._device_combo.setEnabled(False)
        
        elif source == "system":
            devices = get_loopback_devices()
            if devices:
                for dev in devices:
                    self._device_combo.addItem(dev.name, dev)
                    self._devices.append(dev)
                self._device_combo.setEnabled(True)
            else:
                self._device_combo.addItem("No loopback devices found", None)
                self._device_combo.setEnabled(False)
                self._status_label.setText(
                    "No system audio devices found. "
                    "On macOS, install BlackHole or Loopback."
                )
        
        elif source == "mic":
            devices = get_input_devices()
            if devices:
                for dev in devices:
                    label = f"{'★ ' if dev.is_default else ''}{dev.name}"
                    self._device_combo.addItem(label, dev)
                    self._devices.append(dev)
                self._device_combo.setEnabled(True)
            else:
                self._device_combo.addItem("No input devices found", None)
                self._device_combo.setEnabled(False)
    
    def _update_ui_state(self):
        """Update UI based on current state."""
        source = self._current_source
        capturing = self._is_capturing
        
        # Show/hide device selector based on source
        show_device = source in ("system", "mic")
        
        # Enable/disable controls
        self._source_combo.setEnabled(not capturing)
        self._device_combo.setEnabled(show_device and not capturing)
        self._refresh_btn.setEnabled(show_device and not capturing)
        self._start_btn.setEnabled(show_device and not capturing)
        self._stop_btn.setEnabled(capturing)
        
        # Update start button text
        if source == "system":
            self._start_btn.setText("Start System Capture")
        elif source == "mic":
            self._start_btn.setText("Start Recording")
        else:
            self._start_btn.setText("Start Capture")
    
    @Slot(int)
    def _on_source_changed(self, index: int):
        """Handle source selection change."""
        source = self._source_combo.currentData()
        if source != self._current_source:
            self._current_source = source
            self._refresh_devices()
            self._update_ui_state()
            self.source_changed.emit(source)
    
    @Slot(int)
    def _on_device_changed(self, index: int):
        """Handle device selection change."""
        device = self._device_combo.currentData()
        self.device_changed.emit(device)
    
    @Slot()
    def _on_start_clicked(self):
        """Handle start button click."""
        self.capture_start_requested.emit()
    
    @Slot()
    def _on_stop_clicked(self):
        """Handle stop button click."""
        self.capture_stop_requested.emit()
    
    @Slot()
    def _on_analyze_clicked(self):
        """Handle analyze captured button click."""
        self.analyze_captured_requested.emit()
    
    def set_capturing(self, is_capturing: bool):
        """Update capturing state."""
        self._is_capturing = is_capturing
        self._update_ui_state()
        
        if not is_capturing:
            self._level_meter.reset()
    
    def set_level(self, level: float, peak: float):
        """Update level meter."""
        self._level_meter.set_level(level, peak)
    
    def set_duration(self, seconds: float):
        """Update captured duration display."""
        self._duration_label.setText(f"{seconds:.1f}s")
        self._analyze_btn.setEnabled(seconds >= 5.0)
    
    def set_live_result(self, bpm: float, bpm_confidence: float, 
                        key: str, key_confidence: float):
        """Update live analysis results."""
        if bpm > 0:
            self._live_bpm_label.setText(f"{bpm:.1f}")
            self._live_bpm_conf.setText(f"({bpm_confidence:.0%})")
            
            # Color based on confidence
            if bpm_confidence >= 0.75:
                self._live_bpm_conf.setStyleSheet("color: #4CAF50;")
            elif bpm_confidence >= 0.5:
                self._live_bpm_conf.setStyleSheet("color: #FFC107;")
            else:
                self._live_bpm_conf.setStyleSheet("color: #F44336;")
        else:
            self._live_bpm_label.setText("---")
            self._live_bpm_conf.setText("")
        
        if key:
            self._live_key_label.setText(key)
            self._live_key_conf.setText(f"({key_confidence:.0%})")
            
            if key_confidence >= 0.6:
                self._live_key_conf.setStyleSheet("color: #4CAF50;")
            elif key_confidence >= 0.4:
                self._live_key_conf.setStyleSheet("color: #FFC107;")
            else:
                self._live_key_conf.setStyleSheet("color: #F44336;")
        else:
            self._live_key_label.setText("---")
            self._live_key_conf.setText("")
    
    def set_status(self, message: str, is_error: bool = False):
        """Update status message."""
        self._status_label.setText(message)
        if is_error:
            self._status_label.setStyleSheet("color: #f44336;")
        else:
            self._status_label.setStyleSheet("color: #888;")
    
    def get_selected_device(self) -> Optional[AudioDevice]:
        """Get currently selected device."""
        return self._device_combo.currentData()
    
    def get_current_source(self) -> str:
        """Get current input source."""
        return self._current_source
    
    def reset_live_results(self):
        """Reset live results display."""
        self._live_bpm_label.setText("---")
        self._live_bpm_conf.setText("")
        self._live_key_label.setText("---")
        self._live_key_conf.setText("")
        self._duration_label.setText("0.0s")
        self._analyze_btn.setEnabled(False)
