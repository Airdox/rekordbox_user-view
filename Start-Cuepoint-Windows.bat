@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================================
echo   Cuepoint v1.1.0 - Lokaler Windows-Schnellstart
echo   Standard-Datenbankpfad: E:\PIONEER\Master
echo ============================================================================
echo.

set "CUEPOINT_SOURCE_PATH=E:\PIONEER\Master"

if exist "release\Cuepoint-1.1.0-Windows-x64.exe" (
    echo [INFO] Gefundene Portable-EXE wird direkt gestartet:
    echo        release\Cuepoint-1.1.0-Windows-x64.exe
    start "" "%~dp0release\Cuepoint-1.1.0-Windows-x64.exe"
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Richte lokale Python-Umgebung ^(.venv^) ein ...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

if not exist "node_modules" (
    echo [2/3] Installiere Node-Pakete ...
    call npm install
)

if exist "node_modules\.bin\electron.cmd" (
    echo [3/3] Baue Oberflaeche und starte Cuepoint Desktop ^(Electron^) ...
    call npm run build
    call npx electron .
) else (
    echo [3/3] Starte lokalen Cuepoint-Server auf http://127.0.0.1:3000 ...
    start "" "http://127.0.0.1:3000"
    call npm run dev
)
