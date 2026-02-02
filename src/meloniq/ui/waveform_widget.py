"""
Waveform display widget with beat markers and section overlays.
"""

import numpy as np
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QMouseEvent, QPaintEvent

from ..models.results import AnalysisResult


class WaveformWidget(QWidget):
    """
    Widget that displays audio waveform with analysis overlays.
    
    Features:
    - Waveform visualization
    - Beat markers (vertical lines)
    - Downbeat markers (emphasized)
    - Section regions (colored backgrounds)
    - Click-to-seek functionality
    - Playhead position indicator
    """
    
    # Signals
    seek_requested = Signal(float)  # Time in seconds
    section_clicked = Signal(int)  # Section index
    
    # Colors
    WAVEFORM_COLOR = QColor(70, 130, 180)  # Steel blue
    BEAT_COLOR = QColor(100, 100, 100, 100)  # Semi-transparent gray
    DOWNBEAT_COLOR = QColor(255, 165, 0, 150)  # Orange
    PLAYHEAD_COLOR = QColor(255, 50, 50)  # Red
    BACKGROUND_COLOR = QColor(30, 30, 35)  # Dark gray
    
    # Section colors (pastel, semi-transparent)
    SECTION_COLORS = [
        QColor(100, 149, 237, 40),  # Cornflower blue
        QColor(144, 238, 144, 40),  # Light green
        QColor(255, 182, 193, 40),  # Light pink
        QColor(255, 218, 185, 40),  # Peach
        QColor(221, 160, 221, 40),  # Plum
        QColor(176, 224, 230, 40),  # Powder blue
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        
        # Data
        self._waveform_data: Optional[np.ndarray] = None
        self._duration: float = 0.0
        self._sample_rate: int = 22050
        
        # Analysis results
        self._beats: list[float] = []
        self._downbeats: list[float] = []
        self._sections: list[tuple[float, float, str]] = []  # (start, end, label)
        
        # Playhead
        self._playhead_position: float = 0.0
        
        # View range (for zooming)
        self._view_start: float = 0.0
        self._view_end: float = 0.0
        
        # Loop region
        self._loop_start: Optional[float] = None
        self._loop_end: Optional[float] = None
        
    def set_audio_data(self, samples: np.ndarray, sample_rate: int):
        """Set audio data for waveform display."""
        self._sample_rate = sample_rate
        self._duration = len(samples) / sample_rate
        
        # Downsample for display (keep ~2000 points)
        target_points = 2000
        if len(samples) > target_points:
            step = len(samples) // target_points
            # Get min/max for each chunk to preserve peaks
            n_chunks = len(samples) // step
            samples_reshaped = samples[:n_chunks * step].reshape(n_chunks, step)
            mins = samples_reshaped.min(axis=1)
            maxs = samples_reshaped.max(axis=1)
            self._waveform_data = np.column_stack([mins, maxs]).flatten()
        else:
            self._waveform_data = samples
        
        self._view_start = 0.0
        self._view_end = self._duration
        
        self.update()
    
    def set_analysis_result(self, result: AnalysisResult):
        """Set analysis result for overlays."""
        self._beats = result.tempo.beats
        self._downbeats = result.tempo.downbeats
        
        self._sections = [
            (seg.start, seg.end, seg.label)
            for seg in result.structure.segments
        ]
        
        self.update()
    
    def set_playhead_position(self, time_seconds: float):
        """Update playhead position."""
        self._playhead_position = time_seconds
        self.update()
    
    def set_loop_region(self, start: Optional[float], end: Optional[float]):
        """Set or clear loop region."""
        self._loop_start = start
        self._loop_end = end
        self.update()
    
    def set_view_range(self, start: float, end: float):
        """Set visible time range (for zooming)."""
        self._view_start = max(0, start)
        self._view_end = min(self._duration, end)
        self.update()
    
    def reset_view(self):
        """Reset to show full waveform."""
        self._view_start = 0.0
        self._view_end = self._duration
        self.update()
    
    def _time_to_x(self, time: float) -> float:
        """Convert time to x coordinate."""
        if self._view_end <= self._view_start:
            return 0
        
        view_duration = self._view_end - self._view_start
        relative_time = time - self._view_start
        return (relative_time / view_duration) * self.width()
    
    def _x_to_time(self, x: float) -> float:
        """Convert x coordinate to time."""
        if self.width() <= 0:
            return 0
        
        view_duration = self._view_end - self._view_start
        relative_x = x / self.width()
        return self._view_start + relative_x * view_duration
    
    def paintEvent(self, event: QPaintEvent):
        """Paint the waveform and overlays."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), self.BACKGROUND_COLOR)
        
        if self._waveform_data is None or self._duration <= 0:
            # No data - show placeholder
            painter.setPen(QPen(QColor(100, 100, 100)))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Drop an audio file here or click 'Open File'"
            )
            return
        
        width = self.width()
        height = self.height()
        center_y = height / 2
        
        # Draw sections (background)
        self._draw_sections(painter, height)
        
        # Draw waveform
        self._draw_waveform(painter, width, height, center_y)
        
        # Draw beat markers
        self._draw_beats(painter, height)
        
        # Draw loop region
        self._draw_loop_region(painter, height)
        
        # Draw playhead
        self._draw_playhead(painter, height)
    
    def _draw_waveform(
        self, 
        painter: QPainter, 
        width: int, 
        height: int, 
        center_y: float
    ):
        """Draw the waveform."""
        if self._waveform_data is None or len(self._waveform_data) == 0:
            return
        
        painter.setPen(QPen(self.WAVEFORM_COLOR, 1))
        
        # Calculate sample range for current view
        view_start_ratio = self._view_start / self._duration if self._duration > 0 else 0
        view_end_ratio = self._view_end / self._duration if self._duration > 0 else 1
        
        total_samples = len(self._waveform_data)
        start_idx = int(view_start_ratio * total_samples)
        end_idx = int(view_end_ratio * total_samples)
        
        visible_data = self._waveform_data[start_idx:end_idx]
        
        if len(visible_data) == 0:
            return
        
        # Scale factor for height
        max_val = max(abs(visible_data.max()), abs(visible_data.min()), 0.01)
        scale = (height / 2 - 10) / max_val
        
        # Draw waveform
        points_per_pixel = len(visible_data) / width
        
        for x in range(width):
            # Get sample range for this pixel
            start_sample = int(x * points_per_pixel)
            end_sample = int((x + 1) * points_per_pixel)
            
            if start_sample >= len(visible_data):
                break
            
            end_sample = min(end_sample, len(visible_data))
            
            if end_sample > start_sample:
                chunk = visible_data[start_sample:end_sample]
                min_val = chunk.min()
                max_val = chunk.max()
            else:
                min_val = max_val = visible_data[start_sample]
            
            y1 = center_y - max_val * scale
            y2 = center_y - min_val * scale
            
            painter.drawLine(int(x), int(y1), int(x), int(y2))
    
    def _draw_sections(self, painter: QPainter, height: int):
        """Draw section backgrounds."""
        for i, (start, end, label) in enumerate(self._sections):
            if end < self._view_start or start > self._view_end:
                continue
            
            x1 = self._time_to_x(max(start, self._view_start))
            x2 = self._time_to_x(min(end, self._view_end))
            
            color = self.SECTION_COLORS[i % len(self.SECTION_COLORS)]
            painter.fillRect(int(x1), 0, int(x2 - x1), height, color)
            
            # Section label
            if x2 - x1 > 40:  # Only if wide enough
                painter.setPen(QPen(QColor(200, 200, 200)))
                painter.drawText(int(x1 + 5), 15, label)
    
    def _draw_beats(self, painter: QPainter, height: int):
        """Draw beat markers."""
        # Regular beats
        painter.setPen(QPen(self.BEAT_COLOR, 1))
        
        for beat in self._beats:
            if self._view_start <= beat <= self._view_end:
                x = self._time_to_x(beat)
                painter.drawLine(int(x), 0, int(x), height)
        
        # Downbeats (emphasized)
        painter.setPen(QPen(self.DOWNBEAT_COLOR, 2))
        
        for downbeat in self._downbeats:
            if self._view_start <= downbeat <= self._view_end:
                x = self._time_to_x(downbeat)
                painter.drawLine(int(x), 0, int(x), height)
    
    def _draw_loop_region(self, painter: QPainter, height: int):
        """Draw loop region highlight."""
        if self._loop_start is None or self._loop_end is None:
            return
        
        x1 = self._time_to_x(self._loop_start)
        x2 = self._time_to_x(self._loop_end)
        
        # Semi-transparent highlight
        painter.fillRect(
            int(x1), 0, int(x2 - x1), height,
            QColor(255, 255, 0, 30)  # Yellow tint
        )
        
        # Loop boundaries
        painter.setPen(QPen(QColor(255, 255, 0), 2))
        painter.drawLine(int(x1), 0, int(x1), height)
        painter.drawLine(int(x2), 0, int(x2), height)
    
    def _draw_playhead(self, painter: QPainter, height: int):
        """Draw playhead position."""
        if self._view_start <= self._playhead_position <= self._view_end:
            x = self._time_to_x(self._playhead_position)
            
            painter.setPen(QPen(self.PLAYHEAD_COLOR, 2))
            painter.drawLine(int(x), 0, int(x), height)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse click for seeking."""
        if event.button() == Qt.MouseButton.LeftButton:
            time = self._x_to_time(event.position().x())
            time = max(0, min(self._duration, time))
            self.seek_requested.emit(time)
    
    def clear(self):
        """Clear all data."""
        self._waveform_data = None
        self._duration = 0.0
        self._beats = []
        self._downbeats = []
        self._sections = []
        self._playhead_position = 0.0
        self._loop_start = None
        self._loop_end = None
        self.update()
