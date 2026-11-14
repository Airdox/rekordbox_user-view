@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================================
echo   Cuepoint v1.1.0 - 1-Klick Windows Portable EXE Builder
echo   Ziel-Artefakt: release\Cuepoint-1.1.0-Windows-x64.exe
echo   Standard-Datenbankpfad: E:\PIONEER\Master
echo ============================================================================
echo.

where node >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] Node.js wurde nicht gefunden. Bitte Node.js LTS von https://nodejs.org installieren.
    pause
    exit /b 1
)

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=python"
    )
)

if "%PY_CMD%"=="" (
    echo [FEHLER] Python 3 wurde nicht gefunden. Bitte Python 3.11+ von https://www.python.org installieren.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Erstelle Python Virtual Environment ^(.venv^) ...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [FEHLER] Konnte .venv nicht erstellen.
        pause
        exit /b 1
    )
)

echo [2/4] Installiere Python-Abhaengigkeiten ^(sqlcipher3, pyrekordbox, comtypes, pyinstaller^) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-dev.txt
if errorlevel 1 (
    echo [WARNUNG] Vollstaendige Installation meldete einen Fehler. Installiere Kernpakete fuer EXE-Build ...
    ".venv\Scripts\python.exe" -m pip install numpy comtypes pyinstaller pyrekordbox
)

echo [3/4] Pruefe Node.js-Abhaengigkeiten sowie Electron / Electron-Builder ...
if not exist "node_modules" (
    call npm install
    if errorlevel 1 (
        echo [FEHLER] npm install fehlgeschlagen.
        pause
        exit /b 1
    )
)

if not exist "node_modules\electron-builder" (
    echo Installiere electron und electron-builder fuer das Windows-Packaging ...
    call npm install --no-save electron@^35.7.5 electron-builder@^26.0.12
    if errorlevel 1 (
        echo [FEHLER] Installation von electron / electron-builder fehlgeschlagen.
        pause
        exit /b 1
    )
)

echo [4/4] Baue Frontend, PyInstaller-Backend ^(cuepoint-core.exe^) und Portable Windows-EXE ...
call npm run build
if errorlevel 1 (
    echo [FEHLER] Frontend-Build fehlgeschlagen.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-backend.ps1
if errorlevel 1 (
    echo [FEHLER] PyInstaller Backend-Build fehlgeschlagen.
    pause
    exit /b 1
)

call npx electron-builder --win portable
if errorlevel 1 (
    echo [FEHLER] electron-builder Packaging fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo   [ERFOLG] Die ausfuehrbare Datei wurde erfolgreich erstellt:
echo   %~dp0release\Cuepoint-1.1.0-Windows-x64.exe
echo ============================================================================
echo.

if exist "release\Cuepoint-1.1.0-Windows-x64.exe" (
    explorer /select,"%~dp0release\Cuepoint-1.1.0-Windows-x64.exe"
    echo Starte Cuepoint-1.1.0-Windows-x64.exe ...
    start "" "%~dp0release\Cuepoint-1.1.0-Windows-x64.exe"
)

pause
