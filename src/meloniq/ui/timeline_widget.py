"""
Timeline/scrubber widget for playback control.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QPushButton, QSlider, QStyle,
)
from PySide6.QtCore import Qt, Signal, Slot


class TimelineWidget(QWidget):
    """
    Timeline widget with playback controls.
    
    Features:
    - Play/Pause button
    - Time scrubber
    - Current time / duration display
    - Loop toggle
    """
    
    play_clicked = Signal()
    pause_clicked = Signal()
    seek_requested = Signal(float)  # Time in seconds
    loop_toggled = Signal(bool)  # Loop enabled/disabled
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._duration: float = 0.0
        self._position: float = 0.0
        self._is_playing: bool = False
        self._loop_enabled: bool = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Play/Pause button
        self._play_btn = QPushButton()
        self._play_btn.setFixedSize(40, 40)
        self._update_play_button()
        self._play_btn.clicked.connect(self._on_play_clicked)
        layout.addWidget(self._play_btn)
        
        # Current time
        self._time_label = QLabel("0:00.00")
        self._time_label.setFixedWidth(70)
        layout.addWidget(self._time_label)
        
        # Scrubber
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setRange(0, 10000)  # Use 10000 steps for smooth seeking
        self._scrubber.setValue(0)
        self._scrubber.sliderPressed.connect(self._on_scrubber_pressed)
        self._scrubber.sliderReleased.connect(self._on_scrubber_released)
        self._scrubber.valueChanged.connect(self._on_scrubber_changed)
        layout.addWidget(self._scrubber, stretch=1)
        
        # Duration
        self._duration_label = QLabel("0:00.00")
        self._duration_label.setFixedWidth(70)
        layout.addWidget(self._duration_label)
        
        # Loop button
        self._loop_btn = QPushButton("Loop")
        self._loop_btn.setCheckable(True)
        self._loop_btn.setFixedWidth(60)
        self._loop_btn.toggled.connect(self._on_loop_toggled)
        layout.addWidget(self._loop_btn)
        
        # Track whether we're dragging
        self._dragging = False
    
    def _update_play_button(self):
        """Update play button icon."""
        if self._is_playing:
            # Show pause icon
            self._play_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
            )
        else:
            # Show play icon
            self._play_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
    
    def set_duration(self, duration: float):
        """Set track duration."""
        self._duration = duration
        self._duration_label.setText(self._format_time(duration))
    
    def set_position(self, position: float):
        """Update current position."""
        self._position = position
        self._time_label.setText(self._format_time(position))
        
        # Update scrubber if not dragging
        if not self._dragging and self._duration > 0:
            value = int((position / self._duration) * 10000)
            self._scrubber.blockSignals(True)
            self._scrubber.setValue(value)
            self._scrubber.blockSignals(False)
    
    def set_playing(self, is_playing: bool):
        """Update playing state."""
        self._is_playing = is_playing
        self._update_play_button()
    
    def set_loop_enabled(self, enabled: bool):
        """Set loop button state."""
        self._loop_enabled = enabled
        self._loop_btn.setChecked(enabled)
    
    def _format_time(self, seconds: float) -> str:
        """Format time as M:SS.ss"""
        mins, secs = divmod(seconds, 60)
        return f"{int(mins)}:{secs:05.2f}"
    
    @Slot()
    def _on_play_clicked(self):
        """Handle play button click."""
        if self._is_playing:
            self.pause_clicked.emit()
        else:
            self.play_clicked.emit()
    
    @Slot()
    def _on_scrubber_pressed(self):
        """Handle scrubber press."""
        self._dragging = True
    
    @Slot()
    def _on_scrubber_released(self):
        """Handle scrubber release."""
        self._dragging = False
        
        # Seek to position
        if self._duration > 0:
            time = (self._scrubber.value() / 10000) * self._duration
            self.seek_requested.emit(time)
    
    @Slot(int)
    def _on_scrubber_changed(self, value: int):
        """Handle scrubber value change during drag."""
        if self._dragging and self._duration > 0:
            time = (value / 10000) * self._duration
            self._time_label.setText(self._format_time(time))
    
    @Slot(bool)
    def _on_loop_toggled(self, checked: bool):
        """Handle loop button toggle."""
        self._loop_enabled = checked
        self.loop_toggled.emit(checked)
    
    def reset(self):
        """Reset to initial state."""
        self._duration = 0.0
        self._position = 0.0
        self._is_playing = False
        
        self._time_label.setText("0:00.00")
        self._duration_label.setText("0:00.00")
        self._scrubber.setValue(0)
        self._update_play_button()
