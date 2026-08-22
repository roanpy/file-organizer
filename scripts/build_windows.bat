@echo off
setlocal
REM ==========================================
REM      File Organizer - Windows Build
REM ==========================================
REM
REM Version: 1.5.3 (2026-08-22)
REM Function: Build standalone Windows application (.exe)
REM
REM Usage:
REM   scripts\build_windows.bat
REM
REM Output:
REM   dist\FileOrganizer\FileOrganizer.exe
REM ==========================================

echo ==========================================
echo      File Organizer - Windows Build
echo ==========================================

REM 导航到项目根目录
cd /d "%~dp0\.."

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    exit /b 1
)

echo [OK] Python found.

REM Build from an isolated environment so local development packages cannot leak in.
set "BUILD_ENV=%TEMP%\file-organizer-build-%RANDOM%-%RANDOM%"
echo [INFO] Creating isolated build environment...
python -m venv "%BUILD_ENV%"
if errorlevel 1 goto :error
set "BUILD_PYTHON=%BUILD_ENV%\Scripts\python.exe"

REM Install dependencies
echo [INFO] Installing dependencies...
"%BUILD_PYTHON%" -I -m pip install --require-hashes -r requirements.lock
if errorlevel 1 goto :error

REM Clean old build files
echo [INFO] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build the executable
echo [INFO] Building Executable (using spec file)...
"%BUILD_PYTHON%" -I -m PyInstaller --noconfirm --clean SoftwareOrganizer.windows.spec
if errorlevel 1 goto :error

if not exist "dist\FileOrganizer\FileOrganizer.exe" (
    echo.
    echo [ERROR] Build failed!
    goto :error
)

echo.
echo ==========================================
echo [SUCCESS] Build Complete!
echo.
echo Executable: dist\FileOrganizer\FileOrganizer.exe
echo.
echo ==========================================
if exist "%BUILD_ENV%" rmdir /s /q "%BUILD_ENV%"
exit /b 0

:error
if exist "%BUILD_ENV%" rmdir /s /q "%BUILD_ENV%"
exit /b 1
