# -*- mode: python ; coding: utf-8 -*-
"""
Meloniq Folder Mode EXE - PyInstaller Spec Dosyasi
===================================================
Coklu dosya (folder mode) EXE uretimi icin yapilandirma.
Inno Setup ile installer olusturmak icin kullanilir.

Kullanim:
    pyinstaller meloniq.spec --clean --noconfirm
    iscc setup.iss

Notlar:
    - dist/Meloniq/ klasorune cikti uretir
    - Inno Setup bu klasoru paketler
    - Daha hizli baslangic suresi (--onefile'a gore)
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Proje kok dizini
PROJ_ROOT = Path(SPECPATH)

# FFmpeg binary'leri (Windows)
# vendor/ffmpeg/ dizininde ffmpeg.exe ve ffprobe.exe olmali
# Indir: python scripts/download_ffmpeg.py
FFMPEG_DIR = PROJ_ROOT / 'vendor' / 'ffmpeg'
FFMPEG_BINARIES = []

if sys.platform == 'win32':
    ffmpeg_exe = FFMPEG_DIR / 'ffmpeg.exe'
    ffprobe_exe = FFMPEG_DIR / 'ffprobe.exe'

    if ffmpeg_exe.exists():
        FFMPEG_BINARIES.append((str(ffmpeg_exe), '.'))
        print(f"[FFmpeg] ffmpeg.exe eklendi: {ffmpeg_exe}")
    else:
        print(f"[UYARI] ffmpeg.exe bulunamadi: {ffmpeg_exe}")
        print("         Indir: python scripts/download_ffmpeg.py")

    if ffprobe_exe.exists():
        FFMPEG_BINARIES.append((str(ffprobe_exe), '.'))
        print(f"[FFmpeg] ffprobe.exe eklendi: {ffprobe_exe}")

# Hidden imports - Dinamik olarak yuklenen moduller
hidden_imports = [
    # PySide6 / Qt
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'shiboken6',

    # Numpy / Scipy
    'numpy',
    'numpy.core._methods',
    'numpy.lib.format',
    'scipy',
    'scipy.signal',
    'scipy.sparse',
    'scipy.sparse.csgraph',
    'scipy.sparse.linalg',
    'scipy.ndimage',
    'scipy.interpolate',
    'scipy.fft',
    'scipy.io',
    'scipy.io.wavfile',

    # Librosa ve alt modulleri
    'librosa',
    'librosa.beat',
    'librosa.onset',
    'librosa.feature',
    'librosa.core',
    'librosa.effects',
    'librosa.decompose',
    'librosa.util',
    'audioread',
    'soundfile',
    'soxr',
    'pooch',
    'lazy_loader',
    'decorator',
    'numba',
    'llvmlite',

    # PyTorch ve DeepRhythm (CNN tempo)
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torchaudio',
    'deeprhythm',

    # Ses yakalama
    'sounddevice',
    'pyaudiowpatch',

    # Veri dogrulama
    'pydantic',
    'pydantic.fields',
    'pydantic_core',

    # Gorsellestirme
    'matplotlib',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_qtagg',

    # YouTube indirme
    'yt_dlp',
    'yt_dlp.extractor',
    'yt_dlp.downloader',
    'yt_dlp.postprocessor',

    # Loudness
    'pyloudnorm',

    # Meloniq modulleri
    'meloniq',
    'meloniq.main',
    'meloniq.config',
    'meloniq.ui',
    'meloniq.ui.main_window',
    'meloniq.ui.waveform_widget',
    'meloniq.ui.results_panel',
    'meloniq.ui.capture_panel',
    'meloniq.ui.timeline_widget',
    'meloniq.analysis',
    'meloniq.analysis.pipeline',
    'meloniq.analysis.tempo',
    'meloniq.analysis.key',
    'meloniq.analysis.meter',
    'meloniq.analysis.chords',
    'meloniq.analysis.structure',
    'meloniq.analysis.loudness',
    'meloniq.audio_io',
    'meloniq.audio_io.loader',
    'meloniq.audio_io.player',
    'meloniq.audio_io.youtube_downloader',
    'meloniq.audio_capture',
    'meloniq.audio_capture.system_audio',
    'meloniq.audio_capture.capture_manager',
    'meloniq.audio_capture.ring_buffer',
    'meloniq.models',
    'meloniq.models.results',
    'meloniq.resources',
    'meloniq.resources.localization',
]

# Tum scipy ve librosa alt modullerini topla
hidden_imports += collect_submodules('scipy')
hidden_imports += collect_submodules('librosa')
hidden_imports += collect_submodules('pydantic')
hidden_imports += collect_submodules('yt_dlp')

# Data dosyalari
datas = [
    # Meloniq resources
    (str(PROJ_ROOT / 'src' / 'meloniq' / 'resources' / 'icon.ico'), 'meloniq/resources'),
    (str(PROJ_ROOT / 'src' / 'meloniq' / 'resources' / 'logo.png'), 'meloniq/resources'),
    (str(PROJ_ROOT / 'src' / 'meloniq' / 'resources' / 'localization.py'), 'meloniq/resources'),
]

# Librosa data dosyalarini ekle
datas += collect_data_files('librosa')

# DeepRhythm model dosyalarini ekle
try:
    datas += collect_data_files('deeprhythm')
except Exception:
    pass

# PyInstaller Analysis
a = Analysis(
    [str(PROJ_ROOT / 'run.py')],
    pathex=[str(PROJ_ROOT / 'src')],
    binaries=FFMPEG_BINARIES,
    datas=datas,
    hiddenimports=list(set(hidden_imports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
        'pytest',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Duplicate temizligi
a.binaries = list(set(a.binaries))
a.datas = list(set(a.datas))

# PYZ arsivi
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Folder mode EXE
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Folder mode
    name='Meloniq',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJ_ROOT / 'src' / 'meloniq' / 'resources' / 'icon.ico'),
)

# COLLECT - tum dosyalari bir klasore topla
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Meloniq',
)
