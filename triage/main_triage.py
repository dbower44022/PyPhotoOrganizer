#!/usr/bin/env python3
"""
Photo Triage Application - Main Entry Point

High-performance photo review and organization tool.

Usage:
    python main_triage.py [--db DATABASE_PATH]

Keyboard Shortcuts:
    D - Toggle delete mark
    F - Toggle favorite mark
    C - Flag for date correction
    1/2/3 - Change grid size (small/medium/large)
    Space - Show large preview
    Arrows - Navigate
    Ctrl+A - Select all
    Escape - Clear selection
"""

# EXTREME ERROR CATCHING - Print before any imports
print("=" * 80)
print("TRIAGE APPLICATION STARTING - Import phase")
print("=" * 80)

import sys
import traceback

try:
    print("Importing standard libraries...")
    import logging
    from pathlib import Path
    import argparse
    print("✓ Standard libraries imported")

    # Add parent directory to path for imports
    parent_dir = str(Path(__file__).parent.parent)
    print(f"Adding to Python path: {parent_dir}")
    sys.path.insert(0, parent_dir)

    print("Importing PySide6...")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    print("✓ PySide6 imported")

    print("Importing triage modules...")
    from triage.ui.triage_window import TriageWindow
    print("✓ TriageWindow imported")

    from utils import setup_logger
    print("✓ All imports successful")

except Exception as e:
    print("=" * 80)
    print("FATAL ERROR DURING IMPORT!")
    print("=" * 80)
    print(f"Error: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("=" * 80)
    sys.exit(1)


def main():
    """Main entry point for triage application."""
    print("\n" + "=" * 80)
    print("MAIN FUNCTION STARTING")
    print("=" * 80)

    logger = None

    try:
        print("Parsing command line arguments...")
        # Parse arguments
        parser = argparse.ArgumentParser(description="Photo Triage Application")
        parser.add_argument('--db', type=str, help="Database path to open on startup")
        parser.add_argument('--debug', action='store_true', help="Enable debug logging")
        args = parser.parse_args()
        print("✓ Arguments parsed")

        print("Setting up logging...")
        # Setup logging
        log_level = logging.DEBUG if args.debug else logging.INFO
        setup_logger('triage', 'triage_app.log', level=log_level)
        logger = logging.getLogger('triage')
        print("✓ Logging configured")

        logger.info("="*80)
        logger.info("PHOTO TRIAGE APPLICATION STARTING")
        logger.info("="*80)

        print("Creating Qt application...")
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("Photo Triage")
        app.setOrganizationName("PyPhotoOrganizer")
        print("✓ Qt application created")

        # Enable high DPI scaling
        app.setAttribute(Qt.AA_UseHighDpiPixmaps)
        print("✓ High DPI enabled")

        print("Installing exception hook...")
        # Install exception hook for Qt events
        def exception_hook(exctype, value, tb):
            """Catch unhandled exceptions in Qt event loop."""
            import traceback
            error_msg = ''.join(traceback.format_exception(exctype, value, tb))
            logger.error(f"\n{'='*80}\nUNHANDLED EXCEPTION IN QT EVENT LOOP:\n{error_msg}{'='*80}")
            print(f"\n{'='*80}\nFATAL ERROR - Application crashed!\n{'='*80}")
            print(error_msg)
            print(f"{'='*80}\nCheck triage_app.log for details\n{'='*80}")

        sys.excepthook = exception_hook
        print("✓ Exception hook installed")

        # Create main window
        print("\nCreating main window...")
        logger.info("Creating main window...")
        try:
            window = TriageWindow()
            print("✓ Main window created successfully")
            logger.info("✓ Main window created successfully")
        except Exception as e:
            print(f"\n{'='*80}\nFATAL ERROR - Failed to create main window:\n{e}\n{'='*80}")
            logger.error(f"Failed to create main window: {e}", exc_info=True)
            traceback.print_exc()
            print("Check triage_app.log for full details")
            return 1

        # Load database if specified
        if args.db:
            print(f"\nLoading database from command line: {args.db}")
            db_path = Path(args.db)
            if db_path.exists():
                logger.info(f"Loading database from command line: {db_path}")
                try:
                    window._load_database(str(db_path))
                    print("✓ Database loaded")
                except Exception as e:
                    logger.error(f"Failed to load database: {e}", exc_info=True)
                    print(f"\nWarning: Failed to load database {db_path}: {e}")
                    traceback.print_exc()
            else:
                logger.warning(f"Database not found: {db_path}")
                print(f"\nWarning: Database not found: {db_path}")

        # Show window
        print("\nShowing window...")
        logger.info("Showing window...")
        try:
            window.show()
            print("✓ Window displayed")
            logger.info("✓ Window displayed")
        except Exception as e:
            print(f"\n{'='*80}\nFATAL ERROR - Failed to show window:\n{e}\n{'='*80}")
            logger.error(f"Failed to show window: {e}", exc_info=True)
            traceback.print_exc()
            return 1

        print("\n" + "="*80)
        print("TRIAGE APPLICATION READY")
        print("="*80)
        logger.info("Triage window displayed - ready for use")
        logger.info("\nKeyboard shortcuts:")
        logger.info("  D: Toggle delete mark")
        logger.info("  F: Toggle favorite mark")
        logger.info("  C: Flag for date correction")
        logger.info("  1/2/3: Change grid size")
        logger.info("  Space: Show large preview")
        logger.info("  Ctrl+A: Select all")
        logger.info("  Escape: Clear selection\n")

        # Run application
        print("\nStarting Qt event loop...")
        logger.info("Starting Qt event loop...")
        exit_code = app.exec()

        print("\n" + "="*80)
        print("TRIAGE APPLICATION EXITING NORMALLY")
        print(f"Exit code: {exit_code}")
        print("="*80)

        logger.info("="*80)
        logger.info("PHOTO TRIAGE APPLICATION EXITING NORMALLY")
        logger.info(f"Exit code: {exit_code}")
        logger.info("="*80)

        return exit_code

    except Exception as e:
        # Catch any exceptions not caught elsewhere
        print("\n" + "="*80)
        print("FATAL ERROR IN MAIN FUNCTION!")
        print("="*80)
        error_msg = traceback.format_exc()

        if logger:
            logger.critical(f"\n{'='*80}\nFATAL ERROR - Uncaught exception:\n{error_msg}{'='*80}")

        print(f"\nFATAL ERROR - Application crashed!")
        print(error_msg)
        print(f"{'='*80}\nCheck triage_app.log for full details\n{'='*80}")

        return 1


if __name__ == '__main__':
    try:
        print("Python version:", sys.version)
        print("Python executable:", sys.executable)
        print("Current working directory:", Path.cwd())
        print("\nStarting application...\n")
        sys.exit(main())
    except Exception as e:
        print("\n" + "="*80)
        print("CATASTROPHIC ERROR - Failed before main() could complete!")
        print("="*80)
        print(f"Error: {e}")
        traceback.print_exc()
        print("="*80)
        sys.exit(1)
