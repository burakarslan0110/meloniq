"""
Thread-safe ring buffer for audio capture.

Allows audio capture thread to write continuously while analysis threads read.
"""

import numpy as np
import threading
from typing import Optional
from dataclasses import dataclass


@dataclass
class BufferStats:
    """Statistics about the ring buffer state."""
    total_samples: int
    available_samples: int
    buffer_size: int
    overruns: int  # Number of times buffer overflowed
    underruns: int  # Number of times read requested more than available


class RingBuffer:
    """
    Thread-safe ring buffer for audio samples.
    
    Features:
    - Lock-free reads when possible
    - Handles wrap-around transparently
    - Tracks overruns/underruns
    - Supports reading last N seconds of audio
    """
    
    def __init__(
        self,
        max_duration_seconds: float = 60.0,
        sample_rate: int = 44100,
        channels: int = 1,
    ):
        """
        Initialize ring buffer.
        
        Args:
            max_duration_seconds: Maximum audio to keep in buffer
            sample_rate: Audio sample rate
            channels: Number of audio channels (1=mono, 2=stereo)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_samples = int(max_duration_seconds * sample_rate)
        
        # Pre-allocate buffer
        if channels == 1:
            self._buffer = np.zeros(self.max_samples, dtype=np.float32)
        else:
            self._buffer = np.zeros((self.max_samples, channels), dtype=np.float32)
        
        # Position tracking
        self._write_pos = 0
        self._total_written = 0
        
        # Statistics
        self._overruns = 0
        self._underruns = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Event for signaling new data
        self._data_event = threading.Event()
    
    def write(self, samples: np.ndarray):
        """
        Write samples to the buffer.
        
        Args:
            samples: Audio samples to write (float32)
        """
        n_samples = len(samples)
        
        if n_samples == 0:
            return
        
        with self._lock:
            # Handle wrap-around
            if self._write_pos + n_samples <= self.max_samples:
                # Simple case: no wrap
                self._buffer[self._write_pos:self._write_pos + n_samples] = samples
            else:
                # Wrap-around case
                first_part = self.max_samples - self._write_pos
                self._buffer[self._write_pos:] = samples[:first_part]
                self._buffer[:n_samples - first_part] = samples[first_part:]
            
            # Update position
            self._write_pos = (self._write_pos + n_samples) % self.max_samples
            self._total_written += n_samples
            
            # Check for overrun (buffer full)
            if n_samples > self.max_samples:
                self._overruns += 1
        
        # Signal new data available
        self._data_event.set()
    
    def read_last(self, duration_seconds: float) -> Optional[np.ndarray]:
        """
        Read the last N seconds of audio.
        
        Args:
            duration_seconds: How many seconds to read
            
        Returns:
            Audio samples or None if not enough data
        """
        n_samples = int(duration_seconds * self.sample_rate)
        
        with self._lock:
            available = min(self._total_written, self.max_samples)
            
            if available < n_samples:
                self._underruns += 1
                # Return what we have
                n_samples = available
            
            if n_samples == 0:
                return None
            
            # Calculate read position
            read_pos = (self._write_pos - n_samples) % self.max_samples
            
            # Handle wrap-around
            if read_pos + n_samples <= self.max_samples:
                # Simple case
                result = self._buffer[read_pos:read_pos + n_samples].copy()
            else:
                # Wrap-around
                first_part = self.max_samples - read_pos
                if self.channels == 1:
                    result = np.concatenate([
                        self._buffer[read_pos:],
                        self._buffer[:n_samples - first_part]
                    ])
                else:
                    result = np.vstack([
                        self._buffer[read_pos:],
                        self._buffer[:n_samples - first_part]
                    ])
            
            return result
    
    def read_all(self) -> Optional[np.ndarray]:
        """Read all available audio in the buffer."""
        with self._lock:
            available = min(self._total_written, self.max_samples)
            
            if available == 0:
                return None
            
            return self.read_last(available / self.sample_rate)
    
    def get_available_seconds(self) -> float:
        """Get how many seconds of audio are available."""
        with self._lock:
            available = min(self._total_written, self.max_samples)
            return available / self.sample_rate
    
    def get_stats(self) -> BufferStats:
        """Get buffer statistics."""
        with self._lock:
            return BufferStats(
                total_samples=self._total_written,
                available_samples=min(self._total_written, self.max_samples),
                buffer_size=self.max_samples,
                overruns=self._overruns,
                underruns=self._underruns,
            )
    
    def clear(self):
        """Clear the buffer."""
        with self._lock:
            self._buffer.fill(0)
            self._write_pos = 0
            self._total_written = 0
            self._overruns = 0
            self._underruns = 0
            self._data_event.clear()
    
    def wait_for_data(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for new data to be written.
        
        Args:
            timeout: Maximum time to wait (seconds)
            
        Returns:
            True if data available, False if timeout
        """
        result = self._data_event.wait(timeout)
        self._data_event.clear()
        return result
    
    @property
    def duration_seconds(self) -> float:
        """Maximum duration the buffer can hold."""
        return self.max_samples / self.sample_rate
