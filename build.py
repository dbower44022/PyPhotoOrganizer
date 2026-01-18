#!/usr/bin/env python3
"""
PyPhotoOrganizer Build Script

This script automates the build process for PyPhotoOrganizer, creating:
1. Standalone executables using PyInstaller
2. Python wheel/sdist packages for pip installation

Usage:
    python build.py                    # Build everything
    python build.py --exe              # Build executables only
    python build.py --wheel            # Build wheel package only
    python build.py --clean            # Clean build artifacts
    python build.py --exe --onefile    # Build single-file executables

Requirements:
    pip install pyinstaller build

Cross-platform:
    - Windows: Creates .exe files
    - macOS: Creates .app bundles (with --windowed)
    - Linux: Creates executable binaries
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime


# ==============================================================================
# Configuration
# ==============================================================================

PROJECT_NAME = "PyPhotoOrganizer"
VERSION = "3.2.0"

# Directories
ROOT_DIR = Path(__file__).parent.resolve()
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = ROOT_DIR / "dist"
SPEC_FILE = ROOT_DIR / "PyPhotoOrganizer.spec"

# Entry points
ENTRY_POINTS = {
    "PyPhotoOrganizer": "main_gui.py",
    "PhotoReview": "photo_review.py",
    "PyPhotoOrganizer-CLI": "main.py",
}


# ==============================================================================
# Utility Functions
# ==============================================================================

def print_header(text: str):
    """Print a formatted header."""
    width = 70
    print("\n" + "=" * width)
    print(f" {text}")
    print("=" * width)


def print_step(text: str):
    """Print a step message."""
    print(f"\n>>> {text}")


def print_success(text: str):
    """Print a success message."""
    print(f"    [OK] {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"    [ERROR] {text}", file=sys.stderr)


def run_command(cmd: list, cwd: Path = None) -> bool:
    """Run a command and return success status."""
    try:
        print(f"    Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd or ROOT_DIR,
            check=True,
            capture_output=False,
        )
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print_error(f"Command not found: {cmd[0]}")
        return False


def check_dependencies() -> bool:
    """Check that required build tools are installed."""
    print_step("Checking build dependencies...")

    missing = []

    # Check PyInstaller
    try:
        import PyInstaller
        print_success(f"PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        missing.append("pyinstaller")
        print_error("PyInstaller not found")

    # Check build module
    try:
        import build
        print_success("build module found")
    except ImportError:
        missing.append("build")
        print_error("build module not found")

    if missing:
        print(f"\n    Install missing dependencies with:")
        print(f"    pip install {' '.join(missing)}")
        return False

    return True


def get_version() -> str:
    """Get version from pyproject.toml or default."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # Fallback for older Python
        except ImportError:
            return VERSION

    pyproject = ROOT_DIR / "pyproject.toml"
    if pyproject.exists():
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
            return data.get("project", {}).get("version", VERSION)

    return VERSION


# ==============================================================================
# Build Functions
# ==============================================================================

def clean_build():
    """Remove all build artifacts."""
    print_header("Cleaning Build Artifacts")

    dirs_to_clean = [
        BUILD_DIR,
        DIST_DIR,
        ROOT_DIR / f"{PROJECT_NAME}.egg-info",
        ROOT_DIR / "__pycache__",
    ]

    # Also clean PyInstaller work directories
    for entry_name in ENTRY_POINTS:
        dirs_to_clean.append(ROOT_DIR / f"{entry_name}.build")

    for dir_path in dirs_to_clean:
        if dir_path.exists():
            print_step(f"Removing {dir_path.name}/")
            shutil.rmtree(dir_path)
            print_success(f"Removed {dir_path}")

    # Clean .pyc files
    print_step("Removing .pyc files...")
    count = 0
    for pyc in ROOT_DIR.rglob("*.pyc"):
        pyc.unlink()
        count += 1
    print_success(f"Removed {count} .pyc files")

    # Clean __pycache__ directories
    print_step("Removing __pycache__ directories...")
    count = 0
    for pycache in ROOT_DIR.rglob("__pycache__"):
        if "venv" not in str(pycache) and ".venv" not in str(pycache):
            shutil.rmtree(pycache)
            count += 1
    print_success(f"Removed {count} __pycache__ directories")


def build_executables(onefile: bool = False, debug: bool = False):
    """Build standalone executables using PyInstaller."""
    print_header("Building Executables with PyInstaller")

    version = get_version()
    print(f"    Version: {version}")
    print(f"    Platform: {platform.system()} {platform.machine()}")
    print(f"    Python: {sys.version.split()[0]}")

    if SPEC_FILE.exists():
        print_step("Building from spec file...")
        cmd = [sys.executable, "-m", "PyInstaller", "--clean", str(SPEC_FILE)]

        if debug:
            cmd.append("--log-level=DEBUG")

        if not run_command(cmd):
            return False

        print_success("Build completed successfully!")
        print(f"\n    Output: {DIST_DIR / PROJECT_NAME}/")

    else:
        # Build each entry point separately if no spec file
        print_step("Building individual executables...")

        for name, script in ENTRY_POINTS.items():
            if not (ROOT_DIR / script).exists():
                print_error(f"Script not found: {script}")
                continue

            print_step(f"Building {name}...")

            cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--name", name]

            if onefile:
                cmd.append("--onefile")

            if platform.system() != "Linux":
                cmd.append("--windowed")  # No console window

            if debug:
                cmd.append("--log-level=DEBUG")

            cmd.append(script)

            if not run_command(cmd):
                print_error(f"Failed to build {name}")
                continue

            print_success(f"Built {name}")

    # Print summary
    print_header("Build Summary")
    output_dir = DIST_DIR / PROJECT_NAME if SPEC_FILE.exists() else DIST_DIR

    if output_dir.exists():
        print(f"    Output directory: {output_dir}")
        print("\n    Executables:")
        for item in output_dir.iterdir():
            if item.is_file() and (item.suffix in [".exe", ""] or item.suffix == ""):
                size_mb = item.stat().st_size / (1024 * 1024)
                print(f"      - {item.name} ({size_mb:.1f} MB)")

    return True


def build_wheel():
    """Build Python wheel package for pip installation."""
    print_header("Building Python Wheel Package")

    version = get_version()
    print(f"    Version: {version}")

    # Check for pyproject.toml
    if not (ROOT_DIR / "pyproject.toml").exists():
        print_error("pyproject.toml not found!")
        return False

    print_step("Building wheel and sdist...")

    cmd = [sys.executable, "-m", "build"]
    if not run_command(cmd):
        return False

    # Print summary
    print_header("Build Summary")
    if DIST_DIR.exists():
        print(f"    Output directory: {DIST_DIR}")
        print("\n    Packages:")
        for item in DIST_DIR.iterdir():
            if item.suffix in [".whl", ".gz"]:
                size_kb = item.stat().st_size / 1024
                print(f"      - {item.name} ({size_kb:.1f} KB)")

    print("\n    Install with:")
    print(f"      pip install {DIST_DIR}/*.whl")

    return True


def create_release_package():
    """Create a release package with executables and documentation."""
    print_header("Creating Release Package")

    version = get_version()
    timestamp = datetime.now().strftime("%Y%m%d")
    release_name = f"{PROJECT_NAME}-{version}-{platform.system().lower()}-{timestamp}"
    release_dir = DIST_DIR / release_name

    print(f"    Release: {release_name}")

    # Check that executables exist
    exe_dir = DIST_DIR / PROJECT_NAME
    if not exe_dir.exists():
        print_error("Executables not found. Run 'build.py --exe' first.")
        return False

    print_step("Creating release directory...")
    release_dir.mkdir(parents=True, exist_ok=True)

    # Copy executables
    print_step("Copying executables...")
    shutil.copytree(exe_dir, release_dir / PROJECT_NAME, dirs_exist_ok=True)
    print_success(f"Copied executables to {release_dir / PROJECT_NAME}")

    # Copy documentation
    docs_to_copy = [
        "README.md",
        "LICENSE",
        "BUILDING.md",
        "USER_GUIDE.md",
        "CHANGELOG.md",
    ]

    print_step("Copying documentation...")
    for doc in docs_to_copy:
        src = ROOT_DIR / doc
        if src.exists():
            shutil.copy2(src, release_dir)
            print_success(f"Copied {doc}")

    # Create ZIP archive
    print_step("Creating ZIP archive...")
    archive_path = DIST_DIR / f"{release_name}.zip"
    shutil.make_archive(str(DIST_DIR / release_name), "zip", DIST_DIR, release_name)
    print_success(f"Created {archive_path.name}")

    # Print summary
    print_header("Release Package Summary")
    if archive_path.exists():
        size_mb = archive_path.stat().st_size / (1024 * 1024)
        print(f"    Archive: {archive_path.name} ({size_mb:.1f} MB)")
        print(f"\n    Contents:")
        print(f"      - {PROJECT_NAME}/ (executables)")
        for doc in docs_to_copy:
            if (ROOT_DIR / doc).exists():
                print(f"      - {doc}")

    return True


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build PyPhotoOrganizer for distribution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python build.py                    Build executables and wheel
    python build.py --exe              Build executables only
    python build.py --exe --onefile    Build single-file executables
    python build.py --wheel            Build wheel package only
    python build.py --release          Build and create release package
    python build.py --clean            Clean build artifacts
        """,
    )

    parser.add_argument(
        "--exe",
        action="store_true",
        help="Build standalone executables with PyInstaller",
    )
    parser.add_argument(
        "--wheel",
        action="store_true",
        help="Build Python wheel package",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Create release package (builds exe if needed)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean all build artifacts",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Create single-file executables (with --exe)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output during build",
    )

    args = parser.parse_args()

    # Print banner
    print("\n" + "=" * 70)
    print(f" {PROJECT_NAME} Build Script")
    print(f" Version: {get_version()}")
    print("=" * 70)

    # Handle clean
    if args.clean:
        clean_build()
        return 0

    # Check dependencies
    if not check_dependencies():
        return 1

    # If no specific build type requested, build everything
    build_all = not (args.exe or args.wheel or args.release)

    success = True

    # Build executables
    if args.exe or args.release or build_all:
        if not build_executables(onefile=args.onefile, debug=args.debug):
            success = False

    # Build wheel
    if args.wheel or build_all:
        if not build_wheel():
            success = False

    # Create release package
    if args.release:
        if not create_release_package():
            success = False

    # Final status
    print("\n" + "=" * 70)
    if success:
        print(" BUILD COMPLETED SUCCESSFULLY")
    else:
        print(" BUILD COMPLETED WITH ERRORS")
    print("=" * 70 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
