"""
Results panel showing analysis summary and detailed results.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QScrollArea, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from ..models.results import AnalysisResult


class ConfidenceLabel(QLabel):
    """Label that shows confidence with color coding."""
    
    def __init__(self, confidence: float, parent=None):
        super().__init__(parent)
        self.set_confidence(confidence)
    
    def set_confidence(self, confidence: float):
        """Set confidence value with color coding."""
        percentage = int(confidence * 100)
        self.setText(f"{percentage}%")
        
        # Color based on confidence
        if confidence >= 0.75:
            color = "#4CAF50"  # Green
        elif confidence >= 0.5:
            color = "#FFC107"  # Yellow/Orange
        else:
            color = "#F44336"  # Red
        
        self.setStyleSheet(f"color: {color}; font-weight: bold;")


class ResultsPanel(QWidget):
    """
    Panel displaying analysis results.
    
    Shows:
    - Quick summary (BPM, Key, Meter)
    - Detailed results with confidence scores
    - Section timeline
    - Audio statistics
    """
    
    section_selected = Signal(float, float)  # start, end times
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._result: Optional[AnalysisResult] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Quick summary section
        self._summary_group = self._create_summary_group()
        layout.addWidget(self._summary_group)
        
        # Scroll area for detailed results
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)
        
        # Tempo details
        self._tempo_group = self._create_tempo_group()
        scroll_layout.addWidget(self._tempo_group)
        
        # Key details
        self._key_group = self._create_key_group()
        scroll_layout.addWidget(self._key_group)
        
        # Structure details
        self._structure_group = self._create_structure_group()
        scroll_layout.addWidget(self._structure_group)
        
        # Audio stats
        self._stats_group = self._create_stats_group()
        scroll_layout.addWidget(self._stats_group)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
    
    def _create_summary_group(self) -> QGroupBox:
        """Create the quick summary group."""
        group = QGroupBox("Summary")
        layout = QVBoxLayout(group)
        
        # Main values display
        values_layout = QHBoxLayout()
        
        # BPM
        bpm_layout = QVBoxLayout()
        self._bpm_label = QLabel("---")
        self._bpm_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self._bpm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bpm_layout.addWidget(self._bpm_label)
        bpm_layout.addWidget(QLabel("BPM"))
        values_layout.addLayout(bpm_layout)
        
        # Key
        key_layout = QVBoxLayout()
        self._key_label = QLabel("---")
        self._key_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self._key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_layout.addWidget(self._key_label)
        key_layout.addWidget(QLabel("Key"))
        values_layout.addLayout(key_layout)
        
        # Meter
        meter_layout = QVBoxLayout()
        self._meter_label = QLabel("---")
        self._meter_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self._meter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meter_layout.addWidget(self._meter_label)
        meter_layout.addWidget(QLabel("Meter"))
        values_layout.addLayout(meter_layout)
        
        layout.addLayout(values_layout)
        
        # Confidence indicators
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confidence:"))
        
        self._bpm_conf = ConfidenceLabel(0.0)
        self._key_conf = ConfidenceLabel(0.0)
        self._meter_conf = ConfidenceLabel(0.0)
        
        conf_layout.addWidget(self._bpm_conf)
        conf_layout.addWidget(self._key_conf)
        conf_layout.addWidget(self._meter_conf)
        conf_layout.addStretch()
        
        layout.addLayout(conf_layout)
        
        return group
    
    def _create_tempo_group(self) -> QGroupBox:
        """Create tempo details group."""
        group = QGroupBox("Tempo Details")
        layout = QVBoxLayout(group)
        
        self._tempo_explanation = QLabel()
        self._tempo_explanation.setWordWrap(True)
        layout.addWidget(self._tempo_explanation)
        
        # Candidates table
        self._tempo_candidates_label = QLabel("Tempo candidates:")
        layout.addWidget(self._tempo_candidates_label)
        
        self._candidates_table = QTableWidget()
        self._candidates_table.setColumnCount(2)
        self._candidates_table.setHorizontalHeaderLabels(["BPM", "Confidence"])
        self._candidates_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._candidates_table.setMaximumHeight(120)
        layout.addWidget(self._candidates_table)
        
        return group
    
    def _create_key_group(self) -> QGroupBox:
        """Create key details group."""
        group = QGroupBox("Key Details")
        layout = QVBoxLayout(group)
        
        self._key_explanation = QLabel()
        self._key_explanation.setWordWrap(True)
        layout.addWidget(self._key_explanation)
        
        self._key_alternatives_label = QLabel()
        self._key_alternatives_label.setWordWrap(True)
        layout.addWidget(self._key_alternatives_label)
        
        return group
    
    def _create_structure_group(self) -> QGroupBox:
        """Create structure details group."""
        group = QGroupBox("Song Structure")
        layout = QVBoxLayout(group)
        
        self._structure_explanation = QLabel()
        self._structure_explanation.setWordWrap(True)
        layout.addWidget(self._structure_explanation)
        
        # Sections table
        self._sections_table = QTableWidget()
        self._sections_table.setColumnCount(4)
        self._sections_table.setHorizontalHeaderLabels(
            ["Start", "End", "Section", "Confidence"]
        )
        self._sections_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._sections_table.setMaximumHeight(200)
        self._sections_table.cellClicked.connect(self._on_section_clicked)
        layout.addWidget(self._sections_table)
        
        return group
    
    def _create_stats_group(self) -> QGroupBox:
        """Create audio stats group."""
        group = QGroupBox("Audio Statistics")
        layout = QVBoxLayout(group)
        
        self._stats_labels = {}
        
        for stat_name in ["Loudness (LUFS)", "Peak Level", "Dynamic Range", "Tuning"]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{stat_name}:"))
            value_label = QLabel("---")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(value_label)
            layout.addLayout(row)
            self._stats_labels[stat_name] = value_label
        
        return group
    
    def set_result(self, result: AnalysisResult):
        """Update display with analysis result."""
        self._result = result
        
        # Summary
        self._bpm_label.setText(f"{result.tempo.global_bpm:.1f}")
        self._key_label.setText(result.key.global_key)
        self._meter_label.setText(result.meter.value)
        
        self._bpm_conf.set_confidence(result.tempo.confidence)
        self._key_conf.set_confidence(result.key.confidence)
        self._meter_conf.set_confidence(result.meter.confidence)
        
        # Tempo details
        self._tempo_explanation.setText(result.tempo.explanation)
        
        # Candidates table
        candidates = result.tempo.candidates[:5]
        self._candidates_table.setRowCount(len(candidates))
        for i, cand in enumerate(candidates):
            self._candidates_table.setItem(i, 0, QTableWidgetItem(f"{cand.bpm:.1f}"))
            self._candidates_table.setItem(i, 1, QTableWidgetItem(f"{cand.confidence:.0%}"))
        
        # Key details
        self._key_explanation.setText(result.key.explanation)
        
        if result.key.alternatives:
            alts = ", ".join(
                f"{a.key} ({a.confidence:.0%})" 
                for a in result.key.alternatives[:3]
            )
            self._key_alternatives_label.setText(f"Alternatives: {alts}")
        else:
            self._key_alternatives_label.setText("")
        
        # Structure
        self._structure_explanation.setText(result.structure.explanation)
        
        sections = result.structure.segments
        self._sections_table.setRowCount(len(sections))
        for i, seg in enumerate(sections):
            self._sections_table.setItem(
                i, 0, QTableWidgetItem(self._format_time(seg.start))
            )
            self._sections_table.setItem(
                i, 1, QTableWidgetItem(self._format_time(seg.end))
            )
            self._sections_table.setItem(i, 2, QTableWidgetItem(seg.label))
            self._sections_table.setItem(
                i, 3, QTableWidgetItem(f"{seg.confidence:.0%}")
            )
        
        # Audio stats
        stats = result.audio_stats
        self._stats_labels["Loudness (LUFS)"].setText(f"{stats.lufs_integrated:.1f} LUFS")
        self._stats_labels["Peak Level"].setText(f"{stats.peak_dbfs:.1f} dBFS")
        self._stats_labels["Dynamic Range"].setText(f"{stats.dynamic_range:.1f} dB")
        
        if abs(stats.tuning_deviation_cents) < 5:
            tuning_text = "Standard (A=440Hz)"
        else:
            tuning_text = f"A={stats.tuning_reference:.1f}Hz ({stats.tuning_deviation_cents:+.0f} cents)"
        self._stats_labels["Tuning"].setText(tuning_text)
    
    def _format_time(self, seconds: float) -> str:
        """Format time as MM:SS.ss"""
        mins, secs = divmod(seconds, 60)
        return f"{int(mins)}:{secs:05.2f}"
    
    def _on_section_clicked(self, row: int, col: int):
        """Handle section table click."""
        if self._result and row < len(self._result.structure.segments):
            seg = self._result.structure.segments[row]
            self.section_selected.emit(seg.start, seg.end)
    
    def clear(self):
        """Clear all results."""
        self._result = None
        
        self._bpm_label.setText("---")
        self._key_label.setText("---")
        self._meter_label.setText("---")
        
        self._bpm_conf.set_confidence(0.0)
        self._key_conf.set_confidence(0.0)
        self._meter_conf.set_confidence(0.0)
        
        self._tempo_explanation.setText("")
        self._key_explanation.setText("")
        self._key_alternatives_label.setText("")
        self._structure_explanation.setText("")
        
        self._candidates_table.setRowCount(0)
        self._sections_table.setRowCount(0)
        
        for label in self._stats_labels.values():
            label.setText("---")
