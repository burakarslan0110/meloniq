@echo off
setlocal
title Meloniq Launcher

echo ==========================================
echo Meloniq Music Analysis Tool
echo ==========================================

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.8+ and add it to PATH.
    pause
    exit /b
)

:: Check Venv
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

:: Activate Venv
call venv\Scripts\activate.bat

:: Install Requirements
if exist "requirements.txt" (
    echo [INFO] Checking dependencies...
    pip install -r requirements.txt >nul 2>&1
)

:: Run Application
echo [INFO] Starting Meloniq...
python run.py

if %errorlevel% neq 0 (
    echo [ERROR] Application crashed or closed with error.
    pause
)
