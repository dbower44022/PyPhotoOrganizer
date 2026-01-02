#!/usr/bin/env python3
"""
PyPhotoOrganizer GUI Entry Point

Launch the graphical user interface for PyPhotoOrganizer.
"""

import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("PyPhotoOrganizer")
    app.setOrganizationName("PyPhotoOrganizer")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
