#!/usr/bin/env python3
"""
PyPhotoOrganizer Photo Review - Standalone Entry Point

Launch a fast, query-based photo review interface for reviewing archived photos.
Supports folder browsing, date/status queries, saved queries, and quick actions
(delete, rotate, correct date).
"""

import sys
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor, QFont


def main():
    """Main entry point for Photo Review application."""
    app = QApplication(sys.argv)
    app.setApplicationName("PyPhotoOrganizer Photo Review")
    app.setOrganizationName("PyPhotoOrganizer")

    # Create splash screen
    splash = QSplashScreen()
    splash.setWindowFlag(Qt.WindowStaysOnTopHint)

    # Create a simple colored splash with text
    splash_pixmap = QPixmap(600, 400)
    splash_pixmap.fill(QColor("#1a5276"))  # Dark blue background
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
            f"Photo Review\n\n"
            f"PyPhotoOrganizer\n\n"
            f"{message}",
            Qt.AlignCenter | Qt.AlignVCenter,
            QColor("#ecf0f1")  # Light gray text
        )
        app.processEvents()  # Force update to display

    update_splash("Loading application...")

    # Import PhotoReviewWindow AFTER splash is shown (deferred import for faster startup)
    update_splash("Loading modules...")
    from photo_review.review_window import PhotoReviewWindow

    # Create main window with status callback
    update_splash("Initializing user interface...")
    window = PhotoReviewWindow(splash_callback=update_splash)

    # Close splash and show main window
    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
