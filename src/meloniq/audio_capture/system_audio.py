"""
System audio capture using WASAPI loopback on Windows.

Supports:
- Windows: WASAPI Loopback via pyaudiowpatch (captures system audio output)
- Linux: PulseAudio/PipeWire monitor sources via sounddevice
- macOS: Virtual audio devices (BlackHole, Loopback) via sounddevice
"""

import sys
import threading
import numpy as np
from dataclasses import dataclass
from typing import Optional, Callable, List
from enum import Enum

# Try to import pyaudiowpatch for Windows WASAPI loopback
PYAUDIO_AVAILABLE = False
try:
    import pyaudiowpatch as pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    try:
        import pyaudio
        PYAUDIO_AVAILABLE = True
    except ImportError:
        pass

# Fallback to sounddevice for non-Windows or if pyaudio not available
SOUNDDEVICE_AVAILABLE = False
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    pass


class DeviceType(Enum):
    """Type of audio device."""
    INPUT = "input"  # Microphone
    OUTPUT = "output"  # Speaker
    LOOPBACK = "loopback"  # System audio capture


@dataclass
class AudioDevice:
    """Audio device information."""
    index: int
    name: str
    device_type: DeviceType
    channels: int
    sample_rate: float
    is_default: bool = False
    host_api: str = ""
    is_loopback: bool = False
    
    def __str__(self):
        return f"{self.name} ({self.device_type.value})"


def get_loopback_devices() -> List[AudioDevice]:
    """
    Get available loopback devices for system audio capture.
    
    On Windows with WASAPI, uses pyaudiowpatch for true loopback.
    On Linux, returns PulseAudio/PipeWire monitor sources.
    On macOS, returns virtual audio devices if available.
    """
    devices = []
    
    # Windows: Use pyaudiowpatch for WASAPI loopback
    if sys.platform == 'win32' and PYAUDIO_AVAILABLE:
        devices.extend(_get_windows_loopback_devices())
    
    # Linux/macOS: Use sounddevice
    elif SOUNDDEVICE_AVAILABLE:
        devices.extend(_get_sounddevice_loopback_devices())
    
    return devices


def _get_windows_loopback_devices() -> List[AudioDevice]:
    """Get WASAPI loopback devices on Windows using pyaudiowpatch."""
    devices = []
    
    try:
        p = pyaudio.PyAudio()
        
        # Find WASAPI host API
        wasapi_info = None
        for i in range(p.get_host_api_count()):
            api_info = p.get_host_api_info_by_index(i)
            if 'WASAPI' in api_info['name']:
                wasapi_info = api_info
                break
        
        if wasapi_info is None:
            p.terminate()
            return devices
        
        # Get loopback devices (output devices that can be used as loopback)
        try:
            # pyaudiowpatch specific: get loopback devices
            loopback_devices = p.get_loopback_device_info_generator()
            
            for dev in loopback_devices:
                devices.append(AudioDevice(
                    index=dev['index'],
                    name=dev['name'],
                    device_type=DeviceType.LOOPBACK,
                    channels=dev['maxInputChannels'],
                    sample_rate=dev['defaultSampleRate'],
                    is_default=False,
                    host_api="WASAPI",
                    is_loopback=True,
                ))
        except AttributeError:
            # Fallback: list output devices as potential loopback
            for i in range(wasapi_info['deviceCount']):
                try:
                    dev_idx = wasapi_info['defaultOutputDevice']
                    dev = p.get_device_info_by_host_api_device_index(
                        wasapi_info['index'], i
                    )
                    
                    if dev['maxOutputChannels'] > 0:
                        devices.append(AudioDevice(
                            index=dev['index'],
                            name=f"{dev['name']} (Loopback)",
                            device_type=DeviceType.LOOPBACK,
                            channels=dev['maxOutputChannels'],
                            sample_rate=dev['defaultSampleRate'],
                            is_default=(dev['index'] == wasapi_info['defaultOutputDevice']),
                            host_api="WASAPI",
                            is_loopback=True,
                        ))
                except Exception:
                    pass
        
        p.terminate()
        
    except Exception as e:
        print(f"Error getting Windows loopback devices: {e}")
    
    return devices


def _get_sounddevice_loopback_devices() -> List[AudioDevice]:
    """Get loopback devices using sounddevice (Linux/macOS)."""
    devices = []
    
    if not SOUNDDEVICE_AVAILABLE:
        return devices
    
    try:
        all_devices = sd.query_devices()
        
        for i, dev in enumerate(all_devices):
            name = dev['name']
            
            # Linux: look for monitor sources
            if sys.platform.startswith('linux'):
                if 'monitor' in name.lower():
                    devices.append(AudioDevice(
                        index=i,
                        name=name,
                        device_type=DeviceType.LOOPBACK,
                        channels=dev['max_input_channels'],
                        sample_rate=dev['default_samplerate'],
                        host_api="PulseAudio/PipeWire",
                    ))
            
            # macOS: look for virtual audio devices
            elif sys.platform == 'darwin':
                lower_name = name.lower()
                if any(vd in lower_name for vd in ['blackhole', 'loopback', 'soundflower', 'virtual']):
                    if dev['max_input_channels'] > 0:
                        devices.append(AudioDevice(
                            index=i,
                            name=name,
                            device_type=DeviceType.LOOPBACK,
                            channels=dev['max_input_channels'],
                            sample_rate=dev['default_samplerate'],
                            host_api="CoreAudio",
                        ))
    
    except Exception as e:
        print(f"Error getting sounddevice loopback devices: {e}")
    
    return devices


def get_input_devices() -> List[AudioDevice]:
    """Get available input devices (microphones)."""
    devices = []
    
    if SOUNDDEVICE_AVAILABLE:
        try:
            all_devices = sd.query_devices()
            default_input = sd.default.device[0]
            
            for i, dev in enumerate(all_devices):
                if dev['max_input_channels'] > 0:
                    name = dev['name']
                    # Skip loopback/monitor devices
                    if 'monitor' in name.lower() or 'loopback' in name.lower():
                        continue
                    
                    devices.append(AudioDevice(
                        index=i,
                        name=name,
                        device_type=DeviceType.INPUT,
                        channels=dev['max_input_channels'],
                        sample_rate=dev['default_samplerate'],
                        is_default=(i == default_input),
                    ))
        except Exception as e:
            print(f"Error getting input devices: {e}")
    
    return devices


class SystemAudioCapture:
    """
    Capture system audio (loopback) or microphone input.
    
    Uses pyaudiowpatch for WASAPI loopback on Windows.
    Falls back to sounddevice on other platforms.
    """
    
    def __init__(
        self,
        device: AudioDevice,
        sample_rate: int = 44100,
        channels: int = 2,
        block_size: int = 1024,
        callback: Optional[Callable[[np.ndarray], None]] = None,
    ):
        """
        Initialize audio capture.
        
        Args:
            device: Audio device to capture from
            sample_rate: Sample rate for capture
            channels: Number of channels (1=mono, 2=stereo)
            block_size: Audio block size
            callback: Function called with each audio block
        """
        self.device = device
        self.sample_rate = sample_rate
        self.channels = min(channels, device.channels) if device.channels > 0 else channels
        self.block_size = block_size
        self.callback = callback
        
        self._stream = None
        self._pyaudio = None
        self._running = False
        self._lock = threading.Lock()
        
        # Level tracking
        self._current_level = 0.0
        self._peak_level = 0.0
        
        # Use pyaudio for Windows loopback
        self._use_pyaudio = (
            sys.platform == 'win32' and 
            PYAUDIO_AVAILABLE and 
            device.is_loopback
        )
    
    def _pyaudio_callback(self, in_data, frame_count, time_info, status):
        """Callback for PyAudio stream."""
        if status:
            print(f"PyAudio status: {status}")
        
        # Convert bytes to numpy array
        audio = np.frombuffer(in_data, dtype=np.float32)
        
        # Convert to mono if needed
        if self.channels == 1 and len(audio) > frame_count:
            # Stereo to mono
            audio = audio.reshape(-1, 2).mean(axis=1)
        
        # Update levels
        rms = np.sqrt(np.mean(audio ** 2))
        peak = np.max(np.abs(audio))
        
        with self._lock:
            self._current_level = rms
            self._peak_level = max(self._peak_level * 0.95, peak)
        
        # Call user callback
        if self.callback:
            self.callback(audio.astype(np.float32))
        
        return (None, pyaudio.paContinue)
    
    def _sounddevice_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback for sounddevice stream."""
        if status:
            print(f"Sounddevice status: {status}")
        
        # Convert to mono if needed
        if indata.ndim == 2 and self.channels == 1:
            audio = np.mean(indata, axis=1).astype(np.float32)
        else:
            audio = indata.flatten().astype(np.float32)
        
        # Update levels
        rms = np.sqrt(np.mean(audio ** 2))
        peak = np.max(np.abs(audio))
        
        with self._lock:
            self._current_level = rms
            self._peak_level = max(self._peak_level * 0.95, peak)
        
        # Call user callback
        if self.callback:
            self.callback(audio)
    
    def start(self) -> bool:
        """
        Start audio capture.
        
        Returns:
            True if started successfully
        """
        if self._running:
            return True
        
        try:
            if self._use_pyaudio:
                return self._start_pyaudio()
            else:
                return self._start_sounddevice()
        except Exception as e:
            print(f"Failed to start audio capture: {e}")
            return False
    
    def _start_pyaudio(self) -> bool:
        """Start capture using PyAudio (Windows WASAPI loopback)."""
        try:
            self._pyaudio = pyaudio.PyAudio()
            
            # Get device info
            dev_info = self._pyaudio.get_device_info_by_index(self.device.index)
            
            # For loopback, use the device's default sample rate
            actual_rate = int(dev_info.get('defaultSampleRate', self.sample_rate))
            actual_channels = min(
                self.channels, 
                int(dev_info.get('maxInputChannels', 2))
            )
            
            if actual_channels == 0:
                # Loopback device - use output channels
                actual_channels = min(
                    self.channels,
                    int(dev_info.get('maxOutputChannels', 2))
                )
            
            print(f"Opening PyAudio stream: device={self.device.index}, rate={actual_rate}, channels={actual_channels}")
            
            self._stream = self._pyaudio.open(
                format=pyaudio.paFloat32,
                channels=actual_channels,
                rate=actual_rate,
                input=True,
                input_device_index=self.device.index,
                frames_per_buffer=self.block_size,
                stream_callback=self._pyaudio_callback,
            )
            
            self._stream.start_stream()
            self._running = True
            self.sample_rate = actual_rate
            self.channels = actual_channels
            
            print(f"PyAudio stream started successfully")
            return True
            
        except Exception as e:
            print(f"PyAudio start error: {e}")
            if self._pyaudio:
                self._pyaudio.terminate()
                self._pyaudio = None
            return False
    
    def _start_sounddevice(self) -> bool:
        """Start capture using sounddevice."""
        if not SOUNDDEVICE_AVAILABLE:
            print("sounddevice not available")
            return False
        
        try:
            self._stream = sd.InputStream(
                device=self.device.index,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.block_size,
                callback=self._sounddevice_callback,
                dtype=np.float32,
            )
            
            self._stream.start()
            self._running = True
            return True
            
        except Exception as e:
            print(f"Sounddevice start error: {e}")
            return False
    
    def stop(self):
        """Stop audio capture."""
        if self._use_pyaudio:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            
            if self._pyaudio:
                try:
                    self._pyaudio.terminate()
                except Exception:
                    pass
                self._pyaudio = None
        else:
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
        
        self._running = False
        
        with self._lock:
            self._current_level = 0.0
            self._peak_level = 0.0
    
    @property
    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._running
    
    @property
    def current_level(self) -> float:
        """Get current RMS level (0-1)."""
        with self._lock:
            return min(1.0, self._current_level * 3)
    
    @property
    def peak_level(self) -> float:
        """Get peak level (0-1)."""
        with self._lock:
            return min(1.0, self._peak_level)
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
