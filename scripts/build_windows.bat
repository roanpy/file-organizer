@echo off
REM ==========================================
REM      File Organizer - Windows Build
REM ==========================================
REM
REM Version: 1.0.0 (2025-01-19)
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
    pause
    exit /b 1
)

echo [OK] Python found.

REM Create virtual environment if it doesn't exist
if not exist venv (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate

REM Install dependencies
echo [INFO] Installing dependencies...
python -m pip install --upgrade pip
pip install --upgrade -r requirements.txt

REM Clean old build files
echo [INFO] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build the executable
echo [INFO] Building Executable (using spec file)...
pyinstaller --noconfirm --clean SoftwareOrganizer.windows.spec

if not exist "dist\FileOrganizer\FileOrganizer.exe" (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo [SUCCESS] Build Complete!
echo.
echo Executable: dist\FileOrganizer\FileOrganizer.exe
echo.
echo ==========================================
pause
