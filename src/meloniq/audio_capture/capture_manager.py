"""
Capture manager that coordinates audio capture and real-time analysis.

Manages:
- Audio capture thread
- Ring buffer
- Analysis worker threads
- Live and refined estimates
"""

import threading
import time
import numpy as np
from enum import Enum
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field

from .ring_buffer import RingBuffer
from .system_audio import SystemAudioCapture, AudioDevice, DeviceType


class CaptureState(Enum):
    """State of the capture manager."""
    IDLE = "idle"
    CAPTURING = "capturing"
    ANALYZING = "analyzing"
    ERROR = "error"


@dataclass
class LiveAnalysisResult:
    """Result from live analysis."""
    # Tempo
    bpm: float = 0.0
    bpm_confidence: float = 0.0
    bpm_candidates: list = field(default_factory=list)
    
    # Key
    key: str = ""
    key_confidence: float = 0.0
    key_alternatives: list = field(default_factory=list)
    
    # Meter
    meter: str = "4/4"
    meter_confidence: float = 0.0
    
    # Audio stats
    rms_level: float = 0.0
    peak_level: float = 0.0
    
    # Metadata
    analysis_duration: float = 0.0  # How much audio was analyzed
    timestamp: float = 0.0
    is_refined: bool = False  # True if this is a refined (longer window) result


class CaptureManager:
    """
    Manages audio capture and real-time analysis.
    
    Architecture:
    1. Audio capture thread writes to ring buffer
    2. Analysis worker reads from ring buffer periodically
    3. Provides live (fast) and refined (stable) estimates
    """
    
    def __init__(
        self,
        sample_rate: int = 44100,
        channels: int = 2,
        buffer_duration: float = 500.0,  # 500 seconds max capture
    ):
        """
        Initialize capture manager.
        
        Args:
            sample_rate: Audio sample rate
            channels: Number of channels
            buffer_duration: How much audio to keep in buffer
        """
        self.sample_rate = sample_rate
        self.channels = channels
        
        # Components
        self._capture: Optional[SystemAudioCapture] = None
        self._buffer = RingBuffer(
            max_duration_seconds=buffer_duration,
            sample_rate=sample_rate,
            channels=1,  # Always use mono for analysis
        )
        
        # State
        self._state = CaptureState.IDLE
        self._device: Optional[AudioDevice] = None
        
        # Callbacks
        self._on_state_changed: Optional[Callable[[CaptureState], None]] = None
        self._on_level_changed: Optional[Callable[[float, float], None]] = None
    
    def set_callbacks(
        self,
        on_state_changed: Optional[Callable[[CaptureState], None]] = None,
        on_level_changed: Optional[Callable[[float, float], None]] = None,
    ):
        """Set callback functions."""
        self._on_state_changed = on_state_changed
        self._on_level_changed = on_level_changed
    
    def _set_state(self, state: CaptureState):
        """Update state and notify."""
        self._state = state
        if self._on_state_changed:
            self._on_state_changed(state)
    
    def _audio_callback(self, audio: np.ndarray):
        """Called for each audio block from capture."""
        # Convert stereo to mono if needed
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)
        
        # Write to ring buffer
        self._buffer.write(audio)
        
        # Update levels
        if self._capture and self._on_level_changed:
            self._on_level_changed(
                self._capture.current_level,
                self._capture.peak_level
            )
    
    def start_capture(self, device: AudioDevice) -> bool:
        """
        Start capturing from a device.
        
        Args:
            device: Audio device to capture from
            
        Returns:
            True if started successfully
        """
        if self._state == CaptureState.CAPTURING:
            self.stop_capture()
        
        self._device = device
        self._buffer.clear()
        
        # Create capture
        self._capture = SystemAudioCapture(
            device=device,
            sample_rate=self.sample_rate,
            channels=self.channels,
            callback=self._audio_callback,
        )
        
        # Start capture
        if not self._capture.start():
            self._set_state(CaptureState.ERROR)
            return False
        
        self._set_state(CaptureState.CAPTURING)
        return True
    
    def stop_capture(self):
        """Stop capturing."""
        # Stop capture
        if self._capture:
            self._capture.stop()
            self._capture = None
        
        self._set_state(CaptureState.IDLE)
    

    
    def get_captured_audio(self) -> Optional[np.ndarray]:
        """Get all captured audio for file analysis."""
        return self._buffer.read_all()
    
    def get_available_seconds(self) -> float:
        """Get how much audio is captured."""
        return self._buffer.get_available_seconds()
    
    @property
    def state(self) -> CaptureState:
        """Get current state."""
        return self._state
    
    @property
    def is_capturing(self) -> bool:
        """Check if currently capturing."""
        return self._state == CaptureState.CAPTURING
