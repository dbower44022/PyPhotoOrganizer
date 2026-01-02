#!/usr/bin/env python3
"""
PyPhotoOrganizer GUI Entry Point

Launch the graphical user interface for PyPhotoOrganizer.
"""

import sys
from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QPalette, QColor, QFont


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

    # Set font for splash text
    font = QFont("Arial", 16, QFont.Bold)
    splash.setFont(font)

    # Center splash screen on primary monitor
    screen = app.primaryScreen()
    if screen:
        screen_geometry = screen.availableGeometry()
        splash_geometry = splash.frameGeometry()
        center_point = screen_geometry.center()
        splash_geometry.moveCenter(center_point)
        splash.move(splash_geometry.topLeft())

    # Show splash screen immediately
    splash.show()
    app.processEvents()  # Force splash to display immediately

    # Update splash with loading status
    def update_splash(message):
        """Update splash screen with current loading status."""
        splash.showMessage(
            f"PyPhotoOrganizer\n\n"
            f"Version 2.1\n\n"
            f"{message}",
            Qt.AlignCenter | Qt.AlignVCenter,
            QColor("#ecf0f1")  # Light gray text
        )
        app.processEvents()  # Force update to display

    update_splash("Loading application...")

    # Import MainWindow AFTER splash is shown (deferred import for faster startup)
    update_splash("Loading modules...")
    from ui.main_window import MainWindow

    # Create main window with status callback
    update_splash("Initializing user interface...")
    window = MainWindow(splash_callback=update_splash)

    # Close splash and show main window
    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
