"""
Audio playback using Qt's multimedia framework.
Provides play, pause, seek, and loop functionality.
"""

from pathlib import Path
from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal, QUrl, Slot
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class AudioPlayer(QObject):
    """
    Audio player with playback controls.
    
    Signals:
        position_changed: Emitted when playback position changes (ms)
        duration_changed: Emitted when duration is known (ms)
        state_changed: Emitted when playback state changes
        error_occurred: Emitted on playback errors
    """
    
    position_changed = Signal(int)  # Position in milliseconds
    duration_changed = Signal(int)  # Duration in milliseconds
    state_changed = Signal(str)  # "playing", "paused", "stopped"
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        
        # Connect signals
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.errorOccurred.connect(self._on_error)
        
        # Loop settings
        self._loop_start: Optional[int] = None  # ms
        self._loop_end: Optional[int] = None  # ms
        self._loop_enabled = False
        
        # Volume (0.0 - 1.0)
        self._audio_output.setVolume(1.0)
    
    def load(self, path: str | Path) -> bool:
        """
        Load an audio file for playback.
        
        Args:
            path: Path to audio file
            
        Returns:
            True if loaded successfully
        """
        path = Path(path)
        if not path.exists():
            self.error_occurred.emit(f"File not found: {path}")
            return False
        
        url = QUrl.fromLocalFile(str(path.absolute()))
        self._player.setSource(url)
        return True
    
    def play(self):
        """Start or resume playback."""
        self._player.play()
    
    def pause(self):
        """Pause playback."""
        self._player.pause()
    
    def stop(self):
        """Stop playback and reset position."""
        self._player.stop()
    
    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()
    
    def seek(self, position_ms: int):
        """
        Seek to a position.
        
        Args:
            position_ms: Position in milliseconds
        """
        self._player.setPosition(position_ms)
    
    def seek_seconds(self, position_sec: float):
        """Seek to a position in seconds."""
        self.seek(int(position_sec * 1000))
    
    @property
    def position(self) -> int:
        """Current position in milliseconds."""
        return self._player.position()
    
    @property
    def position_seconds(self) -> float:
        """Current position in seconds."""
        return self._player.position() / 1000.0
    
    @property
    def duration(self) -> int:
        """Duration in milliseconds."""
        return self._player.duration()
    
    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self._player.duration() / 1000.0
    
    @property
    def is_playing(self) -> bool:
        """True if currently playing."""
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    
    @property
    def volume(self) -> float:
        """Current volume (0.0 - 1.0)."""
        return self._audio_output.volume()
    
    @volume.setter
    def volume(self, value: float):
        """Set volume (0.0 - 1.0)."""
        self._audio_output.setVolume(max(0.0, min(1.0, value)))
    
    def set_loop(self, start_sec: float, end_sec: float):
        """
        Set loop region.
        
        Args:
            start_sec: Loop start in seconds
            end_sec: Loop end in seconds
        """
        self._loop_start = int(start_sec * 1000)
        self._loop_end = int(end_sec * 1000)
        self._loop_enabled = True
    
    def clear_loop(self):
        """Clear loop region."""
        self._loop_start = None
        self._loop_end = None
        self._loop_enabled = False
    
    @property
    def loop_enabled(self) -> bool:
        return self._loop_enabled
    
    @loop_enabled.setter
    def loop_enabled(self, value: bool):
        self._loop_enabled = value
    
    @Slot(int)
    def _on_position_changed(self, position: int):
        """Handle position change, including loop logic."""
        # Check for loop
        if self._loop_enabled and self._loop_end is not None:
            if position >= self._loop_end:
                self._player.setPosition(self._loop_start or 0)
                return
        
        self.position_changed.emit(position)
    
    @Slot(int)
    def _on_duration_changed(self, duration: int):
        self.duration_changed.emit(duration)
    
    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        state_map = {
            QMediaPlayer.PlaybackState.PlayingState: "playing",
            QMediaPlayer.PlaybackState.PausedState: "paused",
            QMediaPlayer.PlaybackState.StoppedState: "stopped",
        }
        self.state_changed.emit(state_map.get(state, "unknown"))
    
    @Slot(QMediaPlayer.Error, str)
    def _on_error(self, error: QMediaPlayer.Error, error_string: str):
        self.error_occurred.emit(error_string)
