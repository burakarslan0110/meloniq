@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title Meloniq Portable Build

echo.
echo ============================================================
echo   MELONIQ PORTABLE EXE BUILD
echo   Tek dosya portable EXE olusturucu
echo ============================================================
echo.

:: Calisma dizinini kontrol et
if not exist "run.py" (
    echo [HATA] Bu script proje kok dizininde calistirilmalidir!
    echo        run.py bulunamadi.
    pause
    exit /b 1
)

:: Python kontrolu
echo [1/6] Python kontrolu...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi! Python 3.11+ yukleyin ve PATH'e ekleyin.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo       Python %PYVER% bulundu.

:: Virtual environment kontrolu/olusturma
echo.
echo [2/6] Virtual environment kontrolu...
if not exist "venv" (
    echo       venv bulunamadi, olusturuluyor...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [HATA] venv olusturulamadi!
        pause
        exit /b 1
    )
)

:: venv aktif et
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [HATA] venv aktif edilemedi!
    pause
    exit /b 1
)
echo       venv aktif edildi.

:: Bagimliliklari kur
echo.
echo [3/7] Bagimliliklarin yuklenmesi...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [UYARI] Bazi bagimliliklar yuklenemedi, devam ediliyor...
)

:: PyInstaller kontrolu/kurulumu
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo       PyInstaller yukleniyor...
    pip install pyinstaller -q
)
echo       Bagimliliklar hazir.

:: FFmpeg kontrolu ve indirme
echo.
echo [4/7] FFmpeg kontrolu...
if not exist "vendor\ffmpeg\ffmpeg.exe" (
    echo       FFmpeg bulunamadi, indiriliyor...
    echo       Bu islem internet hizina bagli olarak biraz zaman alabilir...
    echo.
    python scripts\download_ffmpeg.py
    if %errorlevel% neq 0 (
        echo [HATA] FFmpeg indirilemedi!
        echo        Manuel olarak deneyin: python scripts\download_ffmpeg.py
        pause
        exit /b 1
    )
) else (
    echo       FFmpeg mevcut: vendor\ffmpeg\ffmpeg.exe
)

:: Onceki build dosyalarini temizle
echo.
echo [5/7] Onceki build dosyalari temizleniyor...
if exist "dist\Meloniq.exe" (
    del /f /q "dist\Meloniq.exe" 2>nul
    echo       Eski Meloniq.exe silindi.
)
if exist "build\Meloniq" (
    rmdir /s /q "build\Meloniq" 2>nul
    echo       Build cache temizlendi.
)

:: PyInstaller ile derleme
echo.
echo [6/7] PyInstaller ile derleme basliyor...
echo       Bu islem birkaç dakika surebilir...
echo.

pyinstaller meloniq_portable.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [HATA] PyInstaller derleme basarisiz!
    echo        Hata ciktisini kontrol edin.
    pause
    exit /b 1
)

:: Sonuc kontrolu
echo.
echo [7/7] Sonuc kontrolu...
if exist "dist\Meloniq.exe" (
    for %%A in ("dist\Meloniq.exe") do set EXESIZE=%%~zA
    set /a EXESIZE_MB=!EXESIZE! / 1048576

    echo.
    echo ============================================================
    echo   BUILD BASARILI!
    echo ============================================================
    echo.
    echo   Dosya: dist\Meloniq.exe
    echo   Boyut: !EXESIZE_MB! MB
    echo.
    echo   Bu dosya portable'dir - hicbir kurulum gerektirmez.
    echo   Herhangi bir Windows bilgisayarinda calistirilabilir.
    echo ============================================================
    echo.

    :: Dosya konumunu ac
    explorer /select,"dist\Meloniq.exe"
) else (
    echo [HATA] Meloniq.exe olusturulamadi!
    pause
    exit /b 1
)

pause
exit /b 0
