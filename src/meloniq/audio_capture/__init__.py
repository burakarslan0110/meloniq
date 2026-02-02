"""
Audio capture module for system audio, microphone, and file input.

Supports:
- System audio loopback (WASAPI on Windows, PulseAudio on Linux, virtual devices on macOS)
- Microphone input
- Thread-safe ring buffer for real-time analysis
"""

from .ring_buffer import RingBuffer
from .system_audio import SystemAudioCapture, AudioDevice, get_loopback_devices, get_input_devices
from .capture_manager import CaptureManager, CaptureState

__all__ = [
    "RingBuffer",
    "SystemAudioCapture",
    "AudioDevice",
    "get_loopback_devices",
    "get_input_devices",
    "CaptureManager",
    "CaptureState",
]
