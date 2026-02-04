# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Meloniq is a Python desktop application for music analysis. It extracts tempo (BPM), key, and meter from audio via file upload, YouTube links, system audio capture, or microphone input.

**Tech Stack**: Python 3.11+, PySide6 (Qt GUI), librosa/scipy (audio DSP), Pydantic (data models), PyTorch (optional DeepRhythm CNN)

## Commands

### Run Application
```bash
# Windows (handles venv + deps automatically)
start_meloniq.bat

# Manual
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
pip install -r requirements.txt
python run.py
```

### Testing
```bash
pytest tests/ -v                    # All tests
pytest tests/test_key.py -v         # Single module
pytest tests/test_key_vocal.py::test_function_name -v  # Single test
```

### Code Quality
```bash
black src/meloniq tests --line-length 100
ruff check src/meloniq tests
```

### Build Executable

**FFmpeg Kurulumu (YouTube indirme icin gerekli):**
```bash
# Windows - FFmpeg binary'lerini indir (~30MB)
python scripts/download_ffmpeg.py

# Binary'ler vendor/ffmpeg/ dizinine indirilir
# Bu adim build oncesi bir kez yapilmali
```

**Portable EXE (tek dosya, kurulum gerektirmez):**
```bash
# Windows BAT
build_portable.bat

# Windows PowerShell
.\build_portable.ps1

# veya manuel
pyinstaller meloniq_portable.spec --clean --noconfirm
```

**Installer Build (Inno Setup ile):**
```bash
# Once folder-mode EXE olustur, sonra Inno Setup calistir
pyinstaller meloniq.spec --clean --noconfirm
iscc setup.iss
```

## Architecture

```
src/meloniq/
├── analysis/           # Audio analysis algorithms
│   ├── pipeline.py     # Orchestrates analyzers, manages caching
│   ├── tempo.py        # BPM detection (DeepRhythm + librosa ensemble)
│   ├── key.py          # Key detection (Krumhansl-Schmuckler + multi-chroma)
│   └── meter.py        # Time signature estimation
├── audio_io/           # File loading, playback, YouTube download
├── audio_capture/      # Real-time capture (system audio via WASAPI, mic)
│   └── ring_buffer.py  # Thread-safe circular buffer
├── ui/                 # PySide6 GUI components
├── models/results.py   # Pydantic schemas (TempoResult, KeyResult, etc.)
└── resources/localization.py  # i18n (EN/TR)
```

### Key Patterns

1. **Analysis Pipeline**: `AnalysisPipeline` orchestrates all analyzers with progress callbacks and result caching (`~/.meloniq/cache`)

2. **Worker Threads**: Heavy operations run in QThread workers (`AnalysisWorker`, `YouTubeDownloadWorker`) with Qt signals for UI updates

3. **Pydantic Results**: All analysis outputs are strongly-typed with confidence scores (0.0-1.0), explanations, and fallback candidates

4. **Config Singleton**: User settings stored at `~/.meloniq/settings.json`

### Analysis Algorithms

- **Tempo**: Multi-method ensemble - DeepRhythm CNN primary (95.9% accuracy), librosa beat_track fallback, octave correction for half/double-time
- **Key**: Krumhansl-Schmuckler with multi-resolution chroma (HPSS, CQT, CENS, STFT), bass-weighted for vocal music, multiple key profiles
- **Meter**: Time signature from beat pattern analysis

## Code Style

- Line length: 100 (black + ruff)
- Python 3.11+ target
- Ruff rules: E, F, W, I, UP
