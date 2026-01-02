#!/usr/bin/env python3
"""
PyPhotoOrganizer GUI Entry Point

Launch the graphical user interface for PyPhotoOrganizer.
"""

import sys
from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPalette, QColor, QFont
from ui.main_window import MainWindow


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("PyPhotoOrganizer")
    app.setOrganizationName("PyPhotoOrganizer")

    # Create splash screen
    splash = QSplashScreen()
    splash.setWindowFlag(Qt.WindowStaysOnTopHint)

    # Create a simple colored splash with text
    splash_pixmap = QPixmap(600, 400)
    splash_pixmap.fill(QColor("#2c3e50"))  # Dark blue-gray background
    splash.setPixmap(splash_pixmap)

    # Add text to splash screen
    splash.showMessage(
        "PyPhotoOrganizer\n\n"
        "Version 2.0\n\n"
        "Loading application...\n\n"
        "Initializing database and settings",
        Qt.AlignCenter | Qt.AlignVCenter,
        QColor("#ecf0f1")  # Light gray text
    )

    # Set font for splash text
    font = QFont("Arial", 16, QFont.Bold)
    splash.setFont(font)

    splash.show()
    app.processEvents()  # Force splash to display immediately

    # Create main window (this is where the delay happens)
    window = MainWindow()

    # Close splash and show main window
    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
