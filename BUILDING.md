# Building PyPhotoOrganizer

This document explains how to build PyPhotoOrganizer for distribution and installation on other systems.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Building Options](#building-options)
  - [Option 1: Standalone Executables (Recommended for End Users)](#option-1-standalone-executables-recommended-for-end-users)
  - [Option 2: pip Installation (Recommended for Developers)](#option-2-pip-installation-recommended-for-developers)
- [Build Script Reference](#build-script-reference)
- [Platform-Specific Notes](#platform-specific-notes)
- [Troubleshooting](#troubleshooting)
- [Distribution](#distribution)

---

## Quick Start

```bash
# Install build dependencies
pip install pyinstaller build

# Build standalone executables
python build.py --exe

# Or build everything (executables + wheel)
python build.py

# Output will be in dist/PyPhotoOrganizer/
```

---

## Prerequisites

### Python Version

- Python 3.8 or higher required
- Python 3.10+ recommended for best compatibility

### Required Build Tools

Install the build dependencies:

```bash
# For building executables
pip install pyinstaller>=6.0.0

# For building wheel packages
pip install build

# Or install all dev dependencies
pip install -e ".[dev]"
```

### Application Dependencies

Ensure all application dependencies are installed:

```bash
pip install -r requirements.txt
```

Or install from pyproject.toml:

```bash
pip install -e .
```

---

## Building Options

### Option 1: Standalone Executables (Recommended for End Users)

Creates standalone executables that include Python and all dependencies. Users don't need Python installed.

#### Using the Build Script (Recommended)

```bash
# Build directory-based distribution (faster startup, shared libraries)
python build.py --exe

# Build single-file executables (easier to distribute, slower startup)
python build.py --exe --onefile

# Build with debug output
python build.py --exe --debug
```

**Output:** `dist/PyPhotoOrganizer/`
- `PyPhotoOrganizer` (or `.exe` on Windows) - Import GUI
- `PhotoReview` (or `.exe` on Windows) - Photo Review application
- Supporting libraries and files

#### Using PyInstaller Directly

```bash
# Build from spec file
pyinstaller PyPhotoOrganizer.spec

# Or build individual applications
pyinstaller --windowed --name PyPhotoOrganizer main_gui.py
pyinstaller --windowed --name PhotoReview photo_review.py
```

#### Distribution

1. Copy the entire `dist/PyPhotoOrganizer/` folder to the target system
2. Users run the executables directly - no installation needed
3. Optionally create a ZIP archive for easy distribution:

```bash
python build.py --release
# Creates: dist/PyPhotoOrganizer-3.2.0-linux-20260117.zip
```

---

### Option 2: pip Installation (Recommended for Developers)

Creates a Python package that can be installed with pip.

#### Building the Package

```bash
# Build wheel and source distribution
python build.py --wheel

# Or use the build module directly
python -m build
```

**Output:** `dist/`
- `PyPhotoOrganizer-3.2.0-py3-none-any.whl` - Wheel package
- `PyPhotoOrganizer-3.2.0.tar.gz` - Source distribution

#### Installation Methods

**From local wheel file:**
```bash
pip install dist/PyPhotoOrganizer-3.2.0-py3-none-any.whl
```

**From source directory (development mode):**
```bash
pip install -e .
```

**From source directory (regular install):**
```bash
pip install .
```

#### Running After pip Install

After pip installation, the applications are available as commands:

```bash
# GUI applications
pyphotoorganizer          # Import GUI
photoreview               # Photo Review

# Command-line interface
pyphotoorganizer-cli      # CLI mode
```

---

## Build Script Reference

The `build.py` script provides a unified interface for all build tasks:

```
Usage: python build.py [OPTIONS]

Options:
    --exe           Build standalone executables with PyInstaller
    --wheel         Build Python wheel package
    --release       Create release package (builds exe + docs)
    --clean         Clean all build artifacts
    --onefile       Create single-file executables (with --exe)
    --debug         Enable debug output during build

Examples:
    python build.py                    # Build everything
    python build.py --exe              # Build executables only
    python build.py --exe --onefile    # Build single-file executables
    python build.py --wheel            # Build wheel package only
    python build.py --release          # Build and package for release
    python build.py --clean            # Clean build artifacts
```

---

## Platform-Specific Notes

### Windows

**Requirements:**
- Python 3.8+ (from python.org, not Microsoft Store)
- Microsoft Visual C++ Redistributable (usually already installed)

**Building:**
```cmd
python build.py --exe
```

**Output:**
- `dist\PyPhotoOrganizer\PyPhotoOrganizer.exe`
- `dist\PyPhotoOrganizer\PhotoReview.exe`

**Notes:**
- The `--windowed` flag is automatic (no console window)
- UPX compression is enabled by default for smaller executables
- Antivirus may flag PyInstaller executables - add exclusions if needed

### macOS

**Requirements:**
- Python 3.8+ (via Homebrew or python.org)
- Xcode Command Line Tools: `xcode-select --install`

**Building:**
```bash
python build.py --exe
```

**Output:**
- `dist/PyPhotoOrganizer/PyPhotoOrganizer` (Unix executable)
- `dist/PyPhotoOrganizer/PhotoReview` (Unix executable)

**Creating .app Bundles:**
To create proper macOS app bundles, modify the spec file to use `BUNDLE`:

```python
app = BUNDLE(
    coll,
    name='PyPhotoOrganizer.app',
    icon='icon.icns',
    bundle_identifier='com.yourname.pyphotoorganizer',
)
```

**Code Signing (for distribution):**
```bash
codesign --deep --force --sign "Developer ID Application: Your Name" dist/PyPhotoOrganizer.app
```

### Linux

**Requirements:**
- Python 3.8+
- Development libraries (for building): `sudo apt install python3-dev`
- Runtime libraries (on target system): `sudo apt install libxcb-cursor0`

**IMPORTANT:** The target system must have `libxcb-cursor0` installed to run the application:
```bash
# Ubuntu/Debian
sudo apt install libxcb-cursor0

# Fedora
sudo dnf install xcb-util-cursor

# Arch Linux
sudo pacman -S xcb-util-cursor
```

**Building:**
```bash
python build.py --exe
```

**Output:**
- `dist/PyPhotoOrganizer/PyPhotoOrganizer` (executable)
- `dist/PyPhotoOrganizer/PhotoReview` (executable)

**AppImage (Recommended for Distribution):**

For universal Linux distribution, consider creating an AppImage:

```bash
pip install appimage-builder
# Create appimage.yml configuration, then:
appimage-builder --recipe appimage.yml
```

**Desktop Integration:**
Create `~/.local/share/applications/pyphotoorganizer.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=PyPhotoOrganizer
Comment=Photo Organization and Review
Exec=/path/to/PyPhotoOrganizer/PyPhotoOrganizer
Icon=/path/to/icon.png
Terminal=false
Categories=Graphics;Photography;
```

---

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError" at Runtime

Some modules may not be automatically detected by PyInstaller. Add them to `hiddenimports` in the spec file:

```python
hiddenimports=[
    'missing_module',
    'another_missing_module',
]
```

#### PySide6 Plugins Not Found

Ensure PySide6 plugins are included:

```python
from PyInstaller.utils.hooks import collect_data_files
pyside6_datas = collect_data_files('PySide6')
```

#### pillow-heif Issues

If HEIC support doesn't work, ensure pillow-heif data files are included:

```python
pillow_heif_datas = collect_data_files('pillow_heif')
datas = pillow_heif_datas
```

#### Large Executable Size

To reduce size:

1. Enable UPX compression (default in spec file)
2. Exclude unnecessary modules:
   ```python
   excludes=['tkinter', 'matplotlib', 'numpy']
   ```
3. Use `--onefile` for single-file builds

#### Antivirus False Positives (Windows)

PyInstaller executables are sometimes flagged by antivirus. Solutions:

1. Sign the executable with a code signing certificate
2. Submit to antivirus vendors as false positive
3. Provide users with checksum for verification

### Debug Build

Create a debug build to see error messages:

```bash
# Build with console window visible
python build.py --exe --debug

# Or edit the spec file:
# Change: console=False
# To:     console=True
```

### Clean Build

If builds fail with strange errors, try a clean build:

```bash
python build.py --clean
python build.py --exe
```

---

## Distribution

### Creating a Release

```bash
# Build executables and create release package
python build.py --release
```

This creates a ZIP archive with:
- Executables
- README.md
- LICENSE
- BUILDING.md
- USER_GUIDE.md (if present)

### Checksums

Generate checksums for verification:

```bash
# Linux/macOS
sha256sum dist/*.zip > dist/SHA256SUMS.txt

# Windows (PowerShell)
Get-FileHash dist\*.zip | Format-List > dist\SHA256SUMS.txt
```

### Version Updates

Before building a release, update the version in:

1. `pyproject.toml` - `version = "X.Y.Z"`
2. `build.py` - `VERSION = "X.Y.Z"`
3. `CLAUDE.md` - Version references

---

## File Structure

After building:

```
PyPhotoOrganizer/
├── build/                  # PyInstaller work files (can be deleted)
├── dist/
│   ├── PyPhotoOrganizer/   # Standalone executables
│   │   ├── PyPhotoOrganizer(.exe)
│   │   ├── PhotoReview(.exe)
│   │   └── ... (supporting files)
│   ├── PyPhotoOrganizer-3.2.0-py3-none-any.whl
│   └── PyPhotoOrganizer-3.2.0.tar.gz
├── pyproject.toml          # Package configuration
├── PyPhotoOrganizer.spec   # PyInstaller configuration
├── build.py                # Build script
├── requirements.txt        # Dependencies
└── BUILDING.md             # This file
```

---

## Publishing to PyPI (Optional)

If you want to publish to PyPI for `pip install PyPhotoOrganizer`:

```bash
# Install twine
pip install twine

# Build packages
python -m build

# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ PyPhotoOrganizer

# Upload to PyPI
twine upload dist/*
```

**Note:** You'll need a PyPI account and API token.
