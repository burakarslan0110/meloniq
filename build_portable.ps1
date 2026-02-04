#Requires -Version 5.1
<#
.SYNOPSIS
    Meloniq Portable EXE Build Script

.DESCRIPTION
    PyInstaller ile tek dosya portable EXE olusturur.
    Tum bagimliliklar EXE icinde gomulu olur.

.EXAMPLE
    .\build_portable.ps1

.EXAMPLE
    .\build_portable.ps1 -SkipDeps
    Bagimlilik kurulumunu atlar (zaten kuruluysa)

.NOTES
    Gereksinimler: Python 3.11+, pip
#>

[CmdletBinding()]
param(
    [switch]$SkipDeps,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Renkli cikti fonksiyonlari
function Write-Step { param($Step, $Message) Write-Host "[$Step] " -ForegroundColor Cyan -NoNewline; Write-Host $Message }
function Write-Success { param($Message) Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $Message }
function Write-Fail { param($Message) Write-Host "[HATA] " -ForegroundColor Red -NoNewline; Write-Host $Message }
function Write-Warn { param($Message) Write-Host "[UYARI] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }

# Banner
Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "  MELONIQ PORTABLE EXE BUILD" -ForegroundColor White
Write-Host "  Tek dosya portable EXE olusturucu" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""

# Calisma dizini kontrolu
$ProjectRoot = $PSScriptRoot
if (-not (Test-Path "$ProjectRoot\run.py")) {
    Write-Fail "Bu script proje kok dizininde calistirilmalidir!"
    Write-Host "       run.py bulunamadi: $ProjectRoot" -ForegroundColor Gray
    exit 1
}
Set-Location $ProjectRoot

# 1. Python kontrolu
Write-Step "1/6" "Python kontrolu..."
try {
    $pythonVersion = & python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Python bulunamadi" }
    Write-Success "Python bulundu: $pythonVersion"
} catch {
    Write-Fail "Python bulunamadi! Python 3.11+ yukleyin ve PATH'e ekleyin."
    exit 1
}

# 2. Virtual environment
Write-Step "2/6" "Virtual environment kontrolu..."
$venvPath = "$ProjectRoot\venv"
$venvActivate = "$venvPath\Scripts\Activate.ps1"

if (-not (Test-Path $venvPath)) {
    Write-Host "       venv bulunamadi, olusturuluyor..." -ForegroundColor Gray
    & python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "venv olusturulamadi!"
        exit 1
    }
}

# venv aktif et
if (Test-Path $venvActivate) {
    & $venvActivate
    Write-Success "venv aktif edildi"
} else {
    Write-Fail "venv aktivasyon scripti bulunamadi: $venvActivate"
    exit 1
}

# 3. Bagimliliklar
Write-Step "3/6" "Bagimliliklarin yuklenmesi..."
if (-not $SkipDeps) {
    try {
        & pip install -r requirements.txt -q 2>&1 | Out-Null
        Write-Success "Bagimliliklar yuklendi"
    } catch {
        Write-Warn "Bazi bagimliliklar yuklenemedi, devam ediliyor..."
    }

    # PyInstaller kontrolu
    $pyinstallerCheck = & pip show pyinstaller 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "       PyInstaller yukleniyor..." -ForegroundColor Gray
        & pip install pyinstaller -q
    }
} else {
    Write-Host "       Bagimlilik kurulumu atlandi (-SkipDeps)" -ForegroundColor Gray
}

# 4. Onceki build temizligi
Write-Step "4/6" "Onceki build dosyalari temizleniyor..."
$distExe = "$ProjectRoot\dist\Meloniq.exe"
$buildDir = "$ProjectRoot\build\Meloniq"

if (Test-Path $distExe) {
    Remove-Item $distExe -Force
    Write-Host "       Eski Meloniq.exe silindi" -ForegroundColor Gray
}
if (Test-Path $buildDir) {
    Remove-Item $buildDir -Recurse -Force
    Write-Host "       Build cache temizlendi" -ForegroundColor Gray
}
Write-Success "Temizlik tamamlandi"

# 5. PyInstaller derleme
Write-Step "5/6" "PyInstaller ile derleme basliyor..."
Write-Host "       Bu islem birkac dakika surebilir..." -ForegroundColor Gray
Write-Host ""

$specFile = "$ProjectRoot\meloniq_portable.spec"
if (-not (Test-Path $specFile)) {
    Write-Fail "Spec dosyasi bulunamadi: $specFile"
    exit 1
}

try {
    & pyinstaller $specFile --clean --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller hata kodu: $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Fail "PyInstaller derleme basarisiz!"
    Write-Host "       Hata: $_" -ForegroundColor Gray
    exit 1
}

# 6. Sonuc kontrolu
Write-Step "6/6" "Sonuc kontrolu..."
if (Test-Path $distExe) {
    $exeInfo = Get-Item $distExe
    $exeSizeMB = [math]::Round($exeInfo.Length / 1MB, 2)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  BUILD BASARILI!" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Dosya: " -NoNewline; Write-Host $distExe -ForegroundColor Cyan
    Write-Host "  Boyut: " -NoNewline; Write-Host "$exeSizeMB MB" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Bu dosya portable'dir - hicbir kurulum gerektirmez." -ForegroundColor Gray
    Write-Host "  Herhangi bir Windows bilgisayarinda calistirilabilir." -ForegroundColor Gray
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""

    # Dosya konumunu explorer'da ac
    Start-Process explorer.exe -ArgumentList "/select,`"$distExe`""

    exit 0
} else {
    Write-Fail "Meloniq.exe olusturulamadi!"
    Write-Host "       dist dizinini kontrol edin: $ProjectRoot\dist" -ForegroundColor Gray
    exit 1
}
