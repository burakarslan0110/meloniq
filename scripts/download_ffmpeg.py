#!/usr/bin/env python3
"""
FFmpeg Binary Downloader
========================
Windows icin FFmpeg essentials binary'lerini indirir.
BtbN'in GitHub releases'indan ffmpeg-release-essentials paketini kullanir.

Kullanim:
    python scripts/download_ffmpeg.py

Binary'ler vendor/ffmpeg/ dizinine cikarilir:
    - ffmpeg.exe
    - ffprobe.exe
"""

import os
import sys
import shutil
import zipfile
import tempfile
import urllib.request
from pathlib import Path

# FFmpeg indirme URL'si (BtbN releases - essentials paketi ~30MB)
# Full paket ~80MB, essentials yeterli
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_URL_ESSENTIALS = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

# Alternatif: gyan.dev essentials (~30MB vs BtbN ~80MB)
# Gyan.dev daha kucuk ve sadece gerekli binary'leri iceriyor


def get_project_root() -> Path:
    """Proje kok dizinini bul."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def download_with_progress(url: str, dest: Path) -> bool:
    """URL'den dosya indir, ilerleme goster."""
    print(f"Indiriliyor: {url}")
    print(f"Hedef: {dest}")

    try:
        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                sys.stdout.write(f"\r  [{percent:5.1f}%] {mb_downloaded:.1f}/{mb_total:.1f} MB")
                sys.stdout.flush()

        urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
        print()  # Yeni satir
        return True
    except Exception as e:
        print(f"\nIndirme hatasi: {e}")
        return False


def extract_ffmpeg_binaries(zip_path: Path, output_dir: Path) -> bool:
    """ZIP'ten ffmpeg.exe ve ffprobe.exe cikart."""
    print(f"Cikariliyor: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # ZIP icerigini listele ve ffmpeg/ffprobe bul
            members = zf.namelist()

            ffmpeg_found = False
            ffprobe_found = False

            for member in members:
                basename = os.path.basename(member)

                if basename == 'ffmpeg.exe':
                    print(f"  ffmpeg.exe bulundu: {member}")
                    source = zf.open(member)
                    target = output_dir / 'ffmpeg.exe'
                    with open(target, 'wb') as f:
                        f.write(source.read())
                    ffmpeg_found = True

                elif basename == 'ffprobe.exe':
                    print(f"  ffprobe.exe bulundu: {member}")
                    source = zf.open(member)
                    target = output_dir / 'ffprobe.exe'
                    with open(target, 'wb') as f:
                        f.write(source.read())
                    ffprobe_found = True

                if ffmpeg_found and ffprobe_found:
                    break

            if not ffmpeg_found:
                print("HATA: ffmpeg.exe ZIP icinde bulunamadi!")
                return False
            if not ffprobe_found:
                print("UYARI: ffprobe.exe bulunamadi (opsiyonel)")

            return True

    except Exception as e:
        print(f"Cikarma hatasi: {e}")
        return False


def main():
    """Ana fonksiyon."""
    print("=" * 60)
    print("FFmpeg Binary Downloader - Meloniq")
    print("=" * 60)

    # Platform kontrolu
    if sys.platform != 'win32':
        print("\nBu script sadece Windows icin FFmpeg indirir.")
        print("Linux/macOS icin paket yoneticinizi kullanin:")
        print("  - Ubuntu/Debian: sudo apt install ffmpeg")
        print("  - macOS: brew install ffmpeg")
        return 1

    project_root = get_project_root()
    vendor_dir = project_root / 'vendor' / 'ffmpeg'

    # Dizin olustur
    vendor_dir.mkdir(parents=True, exist_ok=True)

    # Mevcut binary'leri kontrol et
    ffmpeg_exe = vendor_dir / 'ffmpeg.exe'
    if ffmpeg_exe.exists():
        print(f"\nffmpeg.exe zaten mevcut: {ffmpeg_exe}")
        # --force parametresi veya interaktif mod kontrolu
        if '--force' in sys.argv:
            print("--force parametresi ile tekrar indiriliyor...")
        elif sys.stdin.isatty():
            response = input("Tekrar indirmek ister misiniz? [e/H]: ").strip().lower()
            if response != 'e':
                print("Iptal edildi.")
                return 0
        else:
            # Non-interactive mod (BAT'tan cagirildiginda)
            print("Mevcut binary kullanilacak.")
            return 0

    # Gecici dizinde indir
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / 'ffmpeg.zip'

        # Gyan.dev essentials paketi (daha kucuk)
        print("\nGyan.dev essentials paketi indiriliyor (~30MB)...")
        if not download_with_progress(FFMPEG_URL_ESSENTIALS, zip_path):
            print("\nAlternatif kaynak deneniyor (BtbN)...")
            if not download_with_progress(FFMPEG_URL, zip_path):
                print("HATA: FFmpeg indirilemedi!")
                return 1

        # Cikart
        print()
        if not extract_ffmpeg_binaries(zip_path, vendor_dir):
            return 1

    # Dogrula
    print("\n" + "=" * 60)
    print("Dogrulama:")

    ffmpeg_exe = vendor_dir / 'ffmpeg.exe'
    ffprobe_exe = vendor_dir / 'ffprobe.exe'

    if ffmpeg_exe.exists():
        size_mb = ffmpeg_exe.stat().st_size / (1024 * 1024)
        print(f"  [OK] ffmpeg.exe  ({size_mb:.1f} MB)")
    else:
        print("  [HATA] ffmpeg.exe bulunamadi!")
        return 1

    if ffprobe_exe.exists():
        size_mb = ffprobe_exe.stat().st_size / (1024 * 1024)
        print(f"  [OK] ffprobe.exe ({size_mb:.1f} MB)")
    else:
        print("  [UYARI] ffprobe.exe bulunamadi (opsiyonel)")

    print("\n" + "=" * 60)
    print("Tamamlandi!")
    print(f"Binary'ler: {vendor_dir}")
    print("\nSimdi PyInstaller ile build alabilirsiniz:")
    print("  pyinstaller meloniq_portable.spec --clean --noconfirm")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
