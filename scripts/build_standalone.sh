#!/bin/bash
# ==========================================
#      File Organizer - Mac Build Script
# ==========================================
#
# Version: 1.5.2 (2026-08-13)
# Function: Build standalone Mac application (.app)
#
# Key Features:
#   - Automatically creates virtual environment and installs dependencies
#   - Uses PyInstaller to package into a single application
#   - Supports UPX compression (optional)
#   - AI engines are runtime optional; core organizer features do not depend on them
#
# System Requirements:
#   - macOS 12.0+
#   - Python 3.10+
#
# Usage:
#   ./scripts/build_standalone.sh
#
# Output:
#   dist/FileOrganizer.app
#
# ==========================================

set -e  # Exit immediately if a command exits with a non-zero status

echo "=========================================="
echo "   File Organizer - Mac App Build"
echo "=========================================="

# Navigate to project root directory
cd "$(dirname "$0")/.." || exit

# Check if Python is installed
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    echo "❌ Error: Python3 is not installed or not in PATH"
    exit 1
fi

echo "✓ Python3 found: $($PYTHON_BIN --version)"

# Build from an isolated environment so local development packages cannot leak in.
BUILD_ENV_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/file-organizer-build.XXXXXX")"
trap 'rm -rf "$BUILD_ENV_ROOT"' EXIT
echo "📦 Creating isolated build environment..."
"$PYTHON_BIN" -m venv "$BUILD_ENV_ROOT/venv"
BUILD_PYTHON="$BUILD_ENV_ROOT/venv/bin/python"

# Install dependencies
echo "📥 Installing dependencies..."
"$BUILD_PYTHON" -I -m pip install --require-hashes -r requirements.lock

# Clean old build files
echo "🧹 Cleaning old build files..."
rm -rf build dist

# Prepare icon
# File Organizer uses static/icon.icns for the app bundle and static/favicon.png for the executable.
if [ -f "static/icon.icns" ] && [ -f "static/favicon.png" ]; then
    echo "✓ Icon files found: static/icon.icns, static/favicon.png"
    # Icons are configured in SoftwareOrganizer.spec, so this is mainly a packaging sanity check.
else
    echo "⚠️  Icon file missing (expected static/icon.icns and static/favicon.png)"
fi

# Check if UPX is available
if command -v upx &> /dev/null; then
    echo "✓ UPX is installed"
else
    echo "ℹ️  UPX not found, install it to reduce binary size: brew install upx"
fi

# Build application using PyInstaller
echo "🔨 Building Mac Application (using spec file)..."
# Ensure the spec file exists
if [ ! -f "SoftwareOrganizer.spec" ]; then
    echo "❌ Error: SoftwareOrganizer.spec file not found"
    echo "Recommendation for first run: pyinstaller --name FileOrganizer --onefile --windowed --icon=static/icon_512.png src/main.py"
    exit 1
fi

"$BUILD_PYTHON" -I -m PyInstaller --noconfirm --clean SoftwareOrganizer.spec

# Check if build was successful
if [ -d "dist/FileOrganizer.app" ]; then
    if command -v codesign &> /dev/null; then
        echo "🔎 Verifying app signature..."
        if codesign --verify --deep --strict --verbose=2 "dist/FileOrganizer.app"; then
            echo "✓ App signature is valid"
        else
            echo "ℹ️ App is not signed for public distribution; local build remains usable"
        fi
    fi

    # Calculate application size after optimization
    APP_SIZE=$(du -sh dist/FileOrganizer.app | cut -f1)
    
    echo ""
    echo "=========================================="
    echo "✅ Build Successful!"
    echo "App Location: dist/FileOrganizer.app"
    echo "App Size: $APP_SIZE"
    echo ""
    echo "📝 Next steps:"
    echo "1. Test application: open dist/FileOrganizer.app"
    echo "2. Verify scanning, matching, and transfer"
    echo "3. If everything works, you can distribute the .app file"
    echo "=========================================="
else
    echo ""
    echo "❌ Build Failed! Please check the error messages."
    exit 1
fi
