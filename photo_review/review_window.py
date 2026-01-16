"""
Photo Review Window

Modern main window for the Photo Review application with query-based photo selection,
floating search bar, selection action bar, and quick review actions.
"""

import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QMessageBox, QApplication, QMenu, QProgressDialog,
    QLabel, QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy
)
from PySide6.QtCore import Qt, QSettings, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence

from database_metadata import DatabaseMetadata
from ui.database_selector_dialog import DatabaseSelectorDialog

logger = logging.getLogger(__name__)


class FloatingSearchBar(QWidget):
    """
    Prominent floating search bar above the photo grid.
    """

    search_changed = Signal(str)
    search_submitted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

        # Fixed height - don't expand vertically
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Search icon label
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(search_icon)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search photos... (Ctrl+K)")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self.search_changed.emit)
        self.search_input.returnPressed.connect(self.search_submitted.emit)
        layout.addWidget(self.search_input, 1)

        # Clear button
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.clicked.connect(self._clear_search)
        self.clear_btn.setVisible(False)
        layout.addWidget(self.clear_btn)

        # Keyboard shortcut hint
        hint_label = QLabel("Ctrl+K")
        hint_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(hint_label)

        # Connect text change to show/hide clear button
        self.search_input.textChanged.connect(
            lambda t: self.clear_btn.setVisible(bool(t))
        )

        self.setStyleSheet("""
            QWidget {
                background-color: #262626;
                border-bottom: 1px solid #333333;
            }
            QLineEdit {
                background-color: #333333;
                border: 2px solid #444444;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 15px;
                color: #FFFFFF;
            }
            QLineEdit:focus {
                border-color: #0066FF;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
            QPushButton {
                background-color: #444444;
                border: none;
                border-radius: 16px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)

    def _clear_search(self):
        self.search_input.clear()

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def get_text(self):
        return self.search_input.text()

    def set_text(self, text):
        self.search_input.setText(text)


class SelectionActionBar(QWidget):
    """
    Floating action bar that appears when items are selected.
    """

    delete_clicked = Signal()
    rotate_clicked = Signal()
    correct_date_clicked = Signal()
    deselect_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection_count = 0
        self._init_ui()
        self.hide()  # Hidden by default

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        # Selection count
        self.count_label = QLabel("0 selected")
        self.count_label.setStyleSheet("""
            color: #FFFFFF;
            font-weight: 600;
            font-size: 14px;
            padding: 0 12px;
        """)
        layout.addWidget(self.count_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("background-color: #555555;")
        layout.addWidget(separator)

        # Action buttons
        self.delete_btn = self._create_action_button("🗑 Delete", self.delete_clicked)
        layout.addWidget(self.delete_btn)

        self.rotate_btn = self._create_action_button("🔄 Rotate", self.rotate_clicked)
        layout.addWidget(self.rotate_btn)

        self.date_btn = self._create_action_button("📅 Fix Date", self.correct_date_clicked)
        layout.addWidget(self.date_btn)

        layout.addStretch()

        # Deselect button
        self.deselect_btn = self._create_action_button("✕ Deselect All", self.deselect_clicked)
        self.deselect_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #666666;
                color: #CCCCCC;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #444444;
                border-color: #888888;
            }
        """)
        layout.addWidget(self.deselect_btn)

        self.setStyleSheet("""
            QWidget {
                background-color: #1A1A1A;
                border-radius: 12px;
            }
        """)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _create_action_button(self, text, signal):
        btn = QPushButton(text)
        btn.clicked.connect(signal.emit)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: none;
                color: #FFFFFF;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0066FF;
            }
        """)
        return btn

    def update_selection(self, count):
        """Update the selection count and visibility."""
        self._selection_count = count
        if count > 0:
            self.count_label.setText(f"{count:,} selected")
            self.show()
        else:
            self.hide()


class PreviewInfoBar(QWidget):
    """
    Info bar below the preview showing file metadata.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Filename
        self.filename_label = QLabel("No file selected")
        self.filename_label.setStyleSheet("""
            font-weight: 600;
            font-size: 13px;
            color: #FFFFFF;
        """)
        layout.addWidget(self.filename_label)

        # Details row
        self.details_label = QLabel("")
        self.details_label.setStyleSheet("""
            font-size: 12px;
            color: #888888;
        """)
        layout.addWidget(self.details_label)

        self.setStyleSheet("""
            QWidget {
                background-color: #262626;
                border-top: 1px solid #333333;
            }
        """)

    def update_info(self, record: dict):
        """Update info from a file record."""
        if not record:
            self.filename_label.setText("No file selected")
            self.details_label.setText("")
            return

        # Get file path
        file_path = record.get('archive_path') or record.get('source_path', '')
        filename = os.path.basename(file_path) if file_path else "Unknown"

        # Build details
        details = []

        # Date
        year = record.get('create_year')
        month = record.get('create_month')
        day = record.get('create_day')
        if year:
            date_str = f"{year}"
            if month:
                date_str += f"-{str(month).zfill(2)}"
                if day:
                    date_str += f"-{str(day).zfill(2)}"
            details.append(f"📅 {date_str}")

        # Date source
        date_source = record.get('date_source', '')
        if date_source:
            source_icons = {
                'exif': '✓ EXIF',
                'video_metadata': '🎬 Video',
                'os_metadata': '📂 File',
                'fallback': '⚠ Fallback'
            }
            details.append(source_icons.get(date_source, date_source))

        # Status
        status = self._get_status(record)
        if status and status != 'normal':
            status_labels = {
                'unreliable': '⚠ Unreliable',
                'corrected': '✓ Corrected',
                'reorganized': '📦 Reorganized',
                'revision': '🔄 Has Revisions'
            }
            details.append(status_labels.get(status, status))

        self.filename_label.setText(filename)
        self.details_label.setText("  •  ".join(details) if details else "")

    def _get_status(self, record):
        """Determine status from record."""
        has_unreliable = record.get('has_unreliable_date', False)
        corrected_date = record.get('corrected_date')
        needs_reorg = record.get('needs_reorganization', False)
        has_revisions = record.get('revised_photo') is not None

        if has_revisions:
            return 'revision'
        if corrected_date and not needs_reorg:
            return 'reorganized'
        if corrected_date and needs_reorg:
            return 'corrected'
        if has_unreliable:
            return 'unreliable'
        return 'normal'


class PhotoReviewWindow(QMainWindow):
    """Modern main window for Photo Review application."""

    def __init__(self, splash_callback=None):
        super().__init__()
        self.current_database_path = None
        self.database_metadata = None
        self.thumbnail_cache = None
        self.settings = QSettings("PyPhotoOrganizer", "PhotoReview")
        self.splash_callback = splash_callback
        self._is_dark_mode = True  # Default to dark mode

        # Components (initialized after database selection)
        self.query_panel = None
        self.grid_view = None
        self.grid_model = None
        self.preview_panel = None
        self.detached_preview = None
        self.search_bar = None
        self.action_bar = None
        self.preview_info = None

        if self.splash_callback:
            self.splash_callback("Creating interface...")

        self.init_ui()

        if self.splash_callback:
            self.splash_callback("Restoring window position...")

        self.restore_window_geometry()

        if self.splash_callback:
            self.splash_callback("Loading settings...")

        QTimer.singleShot(100, self.select_database_on_startup)

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Photo Review - PyPhotoOrganizer")
        self.resize(1400, 900)

        # Apply dark theme by default
        self._apply_theme()

        self._create_menu_bar()

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Select a database to begin")

        # Create central widget with placeholder
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Placeholder label
        self.placeholder_label = QLabel(
            "📸 Select a database to begin reviewing photos.\n\n"
            "Use File > Open Database to select a different database."
        )
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet(
            "font-size: 16px; color: #888888; padding: 50px;"
        )
        self.main_layout.addWidget(self.placeholder_label)

        # Set up keyboard shortcut for search
        self._setup_shortcuts()

    def _apply_theme(self):
        """Apply the current theme to the window."""
        if self._is_dark_mode:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1A1A1A;
                }
                QStatusBar {
                    background-color: #262626;
                    color: #888888;
                    border-top: 1px solid #333333;
                }
                QMenuBar {
                    background-color: #262626;
                    color: #FFFFFF;
                    border-bottom: 1px solid #333333;
                }
                QMenuBar::item:selected {
                    background-color: #333333;
                }
                QMenu {
                    background-color: #262626;
                    color: #FFFFFF;
                    border: 1px solid #333333;
                }
                QMenu::item:selected {
                    background-color: #0066FF;
                }
                QMenu::separator {
                    background-color: #333333;
                    height: 1px;
                    margin: 4px 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #F5F5F5;
                }
                QStatusBar {
                    background-color: #FFFFFF;
                    color: #666666;
                    border-top: 1px solid #E0E0E0;
                }
                QMenuBar {
                    background-color: #FFFFFF;
                    color: #333333;
                    border-bottom: 1px solid #E0E0E0;
                }
                QMenuBar::item:selected {
                    background-color: #E8E8E8;
                }
                QMenu {
                    background-color: #FFFFFF;
                    color: #333333;
                    border: 1px solid #E0E0E0;
                }
                QMenu::item:selected {
                    background-color: #0066FF;
                    color: white;
                }
            """)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+K for search focus
        from PySide6.QtGui import QShortcut
        search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        search_shortcut.activated.connect(self._focus_search)

    def _focus_search(self):
        """Focus the search bar."""
        if self.search_bar:
            self.search_bar.focus_search()

    def _create_menu_bar(self):
        """Create the menu bar with icons."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_db_action = QAction("📂 &Open Database...", self)
        open_db_action.setShortcut("Ctrl+O")
        open_db_action.triggered.connect(self.open_database_dialog)
        file_menu.addAction(open_db_action)

        file_menu.addSeparator()

        exit_action = QAction("🚪 E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Query menu
        query_menu = menubar.addMenu("&Query")

        run_query_action = QAction("▶ &Run Query", self)
        run_query_action.setShortcut("F5")
        run_query_action.triggered.connect(self.run_current_query)
        query_menu.addAction(run_query_action)

        save_query_action = QAction("💾 &Save Query...", self)
        save_query_action.setShortcut("Ctrl+S")
        save_query_action.triggered.connect(self.save_current_query)
        query_menu.addAction(save_query_action)

        query_menu.addSeparator()

        clear_filters_action = QAction("✕ &Clear All Filters", self)
        clear_filters_action.setShortcut("Ctrl+Shift+C")
        clear_filters_action.triggered.connect(self.clear_all_filters)
        query_menu.addAction(clear_filters_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        small_thumb_action = QAction("🔍 Small Thumbnails (150px)", self)
        small_thumb_action.setShortcut("1")
        small_thumb_action.triggered.connect(lambda: self.set_thumbnail_size(150))
        view_menu.addAction(small_thumb_action)

        medium_thumb_action = QAction("🔍 Medium Thumbnails (200px)", self)
        medium_thumb_action.setShortcut("2")
        medium_thumb_action.triggered.connect(lambda: self.set_thumbnail_size(200))
        view_menu.addAction(medium_thumb_action)

        large_thumb_action = QAction("🔍 Large Thumbnails (300px)", self)
        large_thumb_action.setShortcut("3")
        large_thumb_action.triggered.connect(lambda: self.set_thumbnail_size(300))
        view_menu.addAction(large_thumb_action)

        view_menu.addSeparator()

        toggle_preview_action = QAction("👁 Toggle &Preview Panel", self)
        toggle_preview_action.setShortcut("P")
        toggle_preview_action.triggered.connect(self.toggle_preview_panel)
        view_menu.addAction(toggle_preview_action)

        view_menu.addSeparator()

        # Theme toggle
        self.theme_action = QAction("🌙 Switch to Light Mode", self)
        self.theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.theme_action)

        # Actions menu
        actions_menu = menubar.addMenu("&Actions")

        delete_action = QAction("🗑 &Delete Selected...", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.delete_selected)
        actions_menu.addAction(delete_action)

        rotate_action = QAction("🔄 &Rotate Selected...", self)
        rotate_action.setShortcut("R")
        rotate_action.triggered.connect(self.rotate_selected)
        actions_menu.addAction(rotate_action)

        correct_date_action = QAction("📅 &Correct Date...", self)
        correct_date_action.setShortcut("D")
        correct_date_action.triggered.connect(self.correct_date_selected)
        actions_menu.addAction(correct_date_action)

        actions_menu.addSeparator()

        select_all_action = QAction("☑ Select &All", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.select_all)
        actions_menu.addAction(select_all_action)

        deselect_all_action = QAction("☐ D&eselect All", self)
        deselect_all_action.setShortcut("Escape")
        deselect_all_action.triggered.connect(self.deselect_all)
        actions_menu.addAction(deselect_all_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        shortcuts_action = QAction("⌨ &Keyboard Shortcuts", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("ℹ &About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_theme(self):
        """Toggle between light and dark mode."""
        self._is_dark_mode = not self._is_dark_mode
        self._apply_theme()

        if self._is_dark_mode:
            self.theme_action.setText("🌙 Switch to Light Mode")
        else:
            self.theme_action.setText("☀ Switch to Dark Mode")

        # Save preference
        self.settings.setValue("dark_mode", self._is_dark_mode)

    def select_database_on_startup(self):
        """Show database selector on startup."""
        dialog = DatabaseSelectorDialog(self)
        result = dialog.exec()

        if result:
            database_path = dialog.get_selected_database()
            if database_path:
                self.set_database(database_path)
        else:
            QMessageBox.warning(
                self,
                "Database Required",
                "Photo Review requires a database to operate.\n\n"
                "You must either:\n"
                "- Select an existing database\n"
                "- Create a new database\n\n"
                "The application will now close."
            )
            QApplication.quit()

    def open_database_dialog(self):
        """Show database selector dialog."""
        dialog = DatabaseSelectorDialog(self)
        result = dialog.exec()

        if result:
            database_path = dialog.get_selected_database()
            if database_path:
                self.set_database(database_path)

    def set_database(self, database_path: str):
        """Set the current database and initialize components."""
        logger.info(f"Loading database: {database_path}")

        self.current_database_path = database_path
        self.database_metadata = DatabaseMetadata(database_path)
        self.db_metadata = self.database_metadata

        self.database_metadata.ensure_all_tables()
        self._init_thumbnail_cache()
        self._build_main_ui()

        metadata = self.database_metadata.get_metadata()
        if metadata:
            db_name = metadata.get('database_name', 'Unknown')
            self.setWindowTitle(f"Photo Review - {db_name}")
            self.status_bar.showMessage(f"Database loaded: {db_name}")

        self._restore_last_query()

    def _init_thumbnail_cache(self):
        """Initialize the thumbnail cache system."""
        from triage.thumbnail_cache import ThumbnailCache

        cache_dir = self.database_metadata.get_thumbnail_cache_dir()
        if not cache_dir:
            archive_location = self.database_metadata.get_archive_location()
            if archive_location:
                cache_dir = os.path.join(archive_location, '.thumbnails')
            else:
                cache_dir = os.path.join(os.path.dirname(self.current_database_path), '.thumbnails')

        logger.info(f"Initializing thumbnail cache at: {cache_dir}")

        self.thumbnail_cache = ThumbnailCache(
            db_path=self.current_database_path,
            cache_dir=cache_dir,
            memory_size=500,
            disk_size_gb=5,
            worker_threads=8
        )

    def _build_main_ui(self):
        """Build the main UI after database is loaded."""
        if self.placeholder_label:
            self.main_layout.removeWidget(self.placeholder_label)
            self.placeholder_label.deleteLater()
            self.placeholder_label = None

        from photo_review.query_panel import QueryPanel
        from photo_review.photo_grid_view import PhotoGridView
        from photo_review.photo_grid_model import PhotoGridModel

        # Floating search bar at top
        self.search_bar = FloatingSearchBar()
        self.search_bar.search_changed.connect(self._on_search_changed)
        self.search_bar.search_submitted.connect(self._on_search_submitted)
        self.main_layout.addWidget(self.search_bar)

        # Main content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(self.main_splitter)

        # Left: Query Panel
        self.query_panel = QueryPanel(
            db_metadata=self.database_metadata,
            db_path=self.current_database_path,
            parent=self
        )
        self.query_panel.setMinimumWidth(280)
        self.query_panel.setMaximumWidth(400)
        self.main_splitter.addWidget(self.query_panel)

        # Right: Grid + Preview
        self.right_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.right_splitter)

        # Grid container
        grid_container = QWidget()
        grid_layout = QVBoxLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        # Grid info bar
        self.grid_info_bar = QWidget()
        self.grid_info_bar.setStyleSheet("""
            background-color: #262626;
            border-bottom: 1px solid #333333;
        """)
        info_layout = QHBoxLayout(self.grid_info_bar)
        info_layout.setContentsMargins(12, 8, 12, 8)

        self.photo_count_label = QLabel("No photos loaded")
        self.photo_count_label.setStyleSheet("color: #888888; font-size: 13px;")
        info_layout.addWidget(self.photo_count_label)
        info_layout.addStretch()

        self.selection_count_label = QLabel("")
        self.selection_count_label.setStyleSheet("color: #0066FF; font-weight: 600; font-size: 13px;")
        info_layout.addWidget(self.selection_count_label)

        grid_layout.addWidget(self.grid_info_bar)

        # Grid model and view
        self.grid_model = PhotoGridModel(self.thumbnail_cache, parent=self)
        self.grid_view = PhotoGridView(self.grid_model, parent=self)
        grid_layout.addWidget(self.grid_view)

        # Selection action bar (floating at bottom of grid)
        self.action_bar = SelectionActionBar()
        self.action_bar.delete_clicked.connect(self.delete_selected)
        self.action_bar.rotate_clicked.connect(self.rotate_selected)
        self.action_bar.correct_date_clicked.connect(self.correct_date_selected)
        self.action_bar.deselect_clicked.connect(self.deselect_all)

        # Position action bar at bottom center of grid
        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(20, 8, 20, 16)
        action_layout.addStretch()
        action_layout.addWidget(self.action_bar)
        action_layout.addStretch()
        grid_layout.addWidget(action_container)

        self.right_splitter.addWidget(grid_container)

        # Preview panel with info bar
        self._create_preview_panel()
        self.right_splitter.addWidget(self.preview_panel)

        self.main_layout.addWidget(content_widget)

        # Bottom bar with close button
        bottom_bar = QWidget()
        bottom_bar.setStyleSheet("""
            QWidget {
                background-color: #262626;
                border-top: 1px solid #333333;
            }
        """)
        bottom_bar.setFixedHeight(50)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 8, 16, 8)
        bottom_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(34)
        self.close_btn.setMinimumWidth(100)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                border: none;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self.close_btn)

        self.main_layout.addWidget(bottom_bar)

        # Set splitter sizes and stretch factors
        self.main_splitter.setSizes([300, 1100])
        # Query panel (index 0) doesn't stretch, grid area (index 1) takes all extra space
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        self.right_splitter.setSizes([700, 200])
        # Grid (index 0) takes extra space, preview (index 1) stays fixed
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 0)

        self._connect_signals()
        self._restore_splitter_states()

        saved_thumb_size = self.settings.value("thumbnail_size", 200, type=int)
        self.grid_view.set_thumbnail_size_pixels(saved_thumb_size)

    def _create_preview_panel(self):
        """Create the preview panel with info bar."""
        from ui.preview import ZoomableImageViewer

        self.preview_panel = QWidget()
        preview_layout = QVBoxLayout(self.preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # Preview header
        preview_header = QWidget()
        preview_header.setStyleSheet("""
            background-color: #262626;
            border-bottom: 1px solid #333333;
        """)
        header_layout = QHBoxLayout(preview_header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        header_label = QLabel("👁 Preview")
        header_label.setStyleSheet("font-weight: 600; color: #FFFFFF; font-size: 13px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        preview_layout.addWidget(preview_header)

        # Image viewer
        self.image_viewer = ZoomableImageViewer(dark_mode=True)
        preview_layout.addWidget(self.image_viewer, 1)

        # Preview info bar
        self.preview_info = PreviewInfoBar()
        preview_layout.addWidget(self.preview_info)

    def _connect_signals(self):
        """Connect component signals."""
        self.query_panel.query_executed.connect(self.on_query_executed)
        self.query_panel.folder_selected.connect(self.on_folder_selected)

        self.grid_model.data_loaded.connect(self.on_data_loaded)
        self.grid_view.selection_changed.connect(self.on_selection_changed)
        self.grid_view.item_activated.connect(self.on_item_activated)

        self.grid_view.delete_requested.connect(self.delete_selected)
        self.grid_view.rotate_requested.connect(self.rotate_selected)
        self.grid_view.correct_date_requested.connect(self.correct_date_selected)
        self.grid_view.open_file_requested.connect(self.open_selected_file)
        self.grid_view.open_folder_requested.connect(self.open_selected_folder)
        self.grid_view.copy_path_requested.connect(self.copy_selected_path)
        self.grid_view.refresh_thumbnail_requested.connect(self.refresh_selected_thumbnails)
        self.grid_view.deselect_all_requested.connect(self.deselect_all)

    def _on_search_changed(self, text):
        """Handle floating search bar text change."""
        # Sync with query panel
        if self.query_panel:
            self.query_panel.search_input.setText(text)

    def _on_search_submitted(self):
        """Handle search submit from floating search bar."""
        if self.query_panel:
            self.query_panel.execute_query()

    def _restore_last_query(self):
        """Restore the last query or folder from settings."""
        state = self.database_metadata.get_photo_review_state()
        if state:
            last_query = state.get('last_query')
            last_folder = state.get('last_folder')

            if last_query:
                logger.info(f"Restoring last query: {last_query}")
                self.query_panel.set_filters(last_query)

                # Sync search to floating bar
                if last_query.get('search_text') and self.search_bar:
                    self.search_bar.set_text(last_query['search_text'])

                self.query_panel.execute_query()
            elif last_folder:
                logger.info(f"Restoring last folder: {last_folder}")
                self.query_panel.set_folder(last_folder)

    def _restore_splitter_states(self):
        """Restore splitter states from settings."""
        main_splitter_state = self.settings.value("main_splitter")
        if main_splitter_state:
            self.main_splitter.restoreState(main_splitter_state)

        right_splitter_state = self.settings.value("right_splitter")
        if right_splitter_state:
            self.right_splitter.restoreState(right_splitter_state)

    # -------------------------------------------------------------------------
    # Query and Data Loading
    # -------------------------------------------------------------------------

    def on_query_executed(self, results: list):
        """Handle query execution results."""
        logger.info(f"Query returned {len(results)} results")
        self.grid_model.load_data(results)

    def on_folder_selected(self, folder_path: str):
        """Handle folder selection."""
        logger.info(f"Folder selected: {folder_path}")

    def on_data_loaded(self, count: int):
        """Handle data loaded into grid."""
        self.photo_count_label.setText(f"{count:,} photos")
        self.status_bar.showMessage(f"Loaded {count:,} photos")

    def on_selection_changed(self, selected_hashes: list):
        """Handle grid selection change."""
        count = len(selected_hashes)

        # Update selection count label
        if count > 0:
            self.selection_count_label.setText(f"{count:,} selected")
        else:
            self.selection_count_label.setText("")

        # Update action bar
        if self.action_bar:
            self.action_bar.update_selection(count)

        # Update preview
        if count == 1 and selected_hashes:
            record = self.grid_model.get_record_by_hash(selected_hashes[0])
            if record:
                file_path = record.get('archive_path') or record.get('source_path', '')
                if file_path and os.path.exists(file_path):
                    self.image_viewer.load_image(file_path)

                # Update preview info bar
                if self.preview_info:
                    self.preview_info.update_info(record)
        elif count == 0:
            # Clear preview info
            if self.preview_info:
                self.preview_info.update_info(None)

    def on_item_activated(self, record: dict):
        """Handle double-click or space on grid item."""
        self._show_detached_preview(record)

    def _show_detached_preview(self, record: dict):
        """Show the detached preview window with the given record."""
        from ui.detachable_preview_window import DetachablePreviewWindow

        if not self.detached_preview:
            self.detached_preview = DetachablePreviewWindow(
                db_metadata=self.database_metadata,
                parent=self
            )
            self.detached_preview.setWindowTitle("Photo Preview - Photo Review")
            self.detached_preview.correct_date_clicked.connect(self._on_preview_correct_date)

        self.detached_preview.update_preview(record)
        self.detached_preview.show()
        self.detached_preview.raise_()
        self.detached_preview.activateWindow()

    def _on_preview_correct_date(self, record: dict):
        """Handle correct date request from preview window."""
        from ui.date_correction_dialog import DateCorrectionDialog

        dialog = DateCorrectionDialog(self, [record], batch_mode=False)
        dialog.exec()
        self.run_current_query()

    # -------------------------------------------------------------------------
    # Query Actions
    # -------------------------------------------------------------------------

    def run_current_query(self):
        """Run the current query."""
        if self.query_panel:
            self.query_panel.execute_query()

    def save_current_query(self):
        """Save the current query."""
        if self.query_panel:
            self.query_panel.save_current_query()

    def clear_all_filters(self):
        """Clear all query filters."""
        if self.query_panel:
            self.query_panel.clear_filters()
        if self.search_bar:
            self.search_bar.set_text("")

    # -------------------------------------------------------------------------
    # View Actions
    # -------------------------------------------------------------------------

    def set_thumbnail_size(self, size: int):
        """Set thumbnail size."""
        if self.grid_view:
            self.grid_view.set_thumbnail_size_pixels(size)
        self.settings.setValue("thumbnail_size", size)

    def toggle_preview_panel(self):
        """Toggle preview panel visibility."""
        if self.preview_panel:
            if self.preview_panel.isVisible():
                self.preview_panel.hide()
            else:
                self.preview_panel.show()

    # -------------------------------------------------------------------------
    # File Actions
    # -------------------------------------------------------------------------

    def delete_selected(self):
        """Delete selected files to vault."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to delete.")
            return

        delete_vault = self.database_metadata.get_delete_vault_location()
        if not delete_vault:
            QMessageBox.warning(
                self, "Delete Vault Not Configured",
                "Please configure Delete Vault location in the main application settings."
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"🗑 Delete {len(selected)} file(s) to Delete Vault?\n\n"
            f"Files will be moved to:\n{delete_vault}\n\n"
            f"Files can be restored later.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        from ui.delete_worker import DeleteWorker

        self.delete_worker = DeleteWorker(
            records=selected,
            delete_vault_path=delete_vault,
            db_path=self.current_database_path,
            worker_logger=logger
        )

        self.delete_progress = QProgressDialog(
            "Deleting files...", "Cancel", 0, len(selected), self
        )
        self.delete_progress.setWindowModality(Qt.WindowModal)
        self.delete_progress.show()

        self.delete_worker.progress.connect(self._on_delete_progress)
        self.delete_worker.finished.connect(self._on_delete_finished)
        self.delete_worker.start()

    def _on_delete_progress(self, current, total, filename):
        """Handle delete progress."""
        self.delete_progress.setValue(current)
        self.delete_progress.setLabelText(f"Deleting: {filename}")

    def _on_delete_finished(self, results):
        """Handle delete completion."""
        self.delete_progress.close()

        success = results.get('success', 0)
        errors = results.get('errors', [])
        deleted_hashes = results.get('deleted_hashes', [])

        if deleted_hashes and self.grid_model:
            self.grid_model.remove_items(deleted_hashes)

        if errors:
            QMessageBox.warning(
                self, "Delete Complete with Errors",
                f"✓ Deleted {success} files.\n\n"
                f"✗ {len(errors)} errors occurred."
            )
        else:
            self.status_bar.showMessage(f"✓ Deleted {success} files")

        if self.grid_model:
            count = len(self.grid_model.file_items)
            self.photo_count_label.setText(f"{count:,} photos")

    def rotate_selected(self):
        """Rotate selected files."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to rotate.")
            return

        prior_archive = self.database_metadata.get_prior_revision_archive_location()
        if not prior_archive:
            QMessageBox.warning(
                self, "Prior Revision Archive Not Configured",
                "Please configure Prior Revision Archive location in the main application settings."
            )
            return

        from ui.rotate_image_dialog import RotateImageDialog

        dialog = RotateImageDialog(
            parent=self,
            selected_records=selected,
            db_metadata=self.database_metadata,
            logger=logger
        )
        dialog.exec()
        self.run_current_query()

    def correct_date_selected(self):
        """Correct dates for selected files."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to correct.")
            return

        from ui.date_correction_dialog import DateCorrectionDialog

        batch_mode = len(selected) > 1
        dialog = DateCorrectionDialog(self, selected, batch_mode=batch_mode)
        dialog.exec()
        self.run_current_query()

    def open_selected_file(self):
        """Open selected file with default application."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            return

        file_path = selected[0].get('archive_path') or selected[0].get('source_path', '')
        if file_path and os.path.exists(file_path):
            import subprocess
            import platform

            if platform.system() == 'Darwin':
                subprocess.call(('open', file_path))
            elif platform.system() == 'Windows':
                os.startfile(file_path)
            else:
                subprocess.call(('xdg-open', file_path))

    def open_selected_folder(self):
        """Open folder containing selected file."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            return

        file_path = selected[0].get('archive_path') or selected[0].get('source_path', '')
        if file_path:
            folder = os.path.dirname(file_path)
            if os.path.exists(folder):
                import subprocess
                import platform

                if platform.system() == 'Darwin':
                    subprocess.call(('open', folder))
                elif platform.system() == 'Windows':
                    os.startfile(folder)
                else:
                    subprocess.call(('xdg-open', folder))

    def copy_selected_path(self):
        """Copy path of first selected file to clipboard."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            return

        file_path = selected[0].get('archive_path') or selected[0].get('source_path', '')
        if file_path:
            clipboard = QApplication.clipboard()
            clipboard.setText(file_path)
            self.status_bar.showMessage(f"📋 Path copied: {file_path}")

    def refresh_selected_thumbnails(self):
        """Refresh thumbnails for selected files."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        for record in selected:
            file_hash = record.get('file_hash')
            if file_hash:
                self.grid_model.refresh_thumbnail(file_hash)

        self.status_bar.showMessage(f"🔄 Refreshed thumbnails for {len(selected)} items")

    # -------------------------------------------------------------------------
    # Selection Actions
    # -------------------------------------------------------------------------

    def select_all(self):
        """Select all items in grid."""
        if self.grid_view:
            self.grid_view.selectAll()

    def deselect_all(self):
        """Deselect all items in grid."""
        if self.grid_view:
            self.grid_view.clearSelection()

    # -------------------------------------------------------------------------
    # Help Actions
    # -------------------------------------------------------------------------

    def show_shortcuts(self):
        """Show keyboard shortcuts help."""
        shortcuts = """
<h3>⌨ Keyboard Shortcuts</h3>

<h4>🔍 Search & Navigation</h4>
<table>
<tr><td><b>Ctrl+K</b></td><td>Focus search bar</td></tr>
<tr><td><b>F5</b></td><td>Run query</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>Clear all filters</td></tr>
</table>

<h4>🖼 View</h4>
<table>
<tr><td><b>1</b></td><td>Small thumbnails (150px)</td></tr>
<tr><td><b>2</b></td><td>Medium thumbnails (200px)</td></tr>
<tr><td><b>3</b></td><td>Large thumbnails (300px)</td></tr>
<tr><td><b>P</b></td><td>Toggle preview panel</td></tr>
<tr><td><b>Space</b></td><td>Show selected in large preview</td></tr>
</table>

<h4>☑ Selection</h4>
<table>
<tr><td><b>Ctrl+A</b></td><td>Select all</td></tr>
<tr><td><b>Escape</b></td><td>Deselect all</td></tr>
<tr><td><b>Shift+Click</b></td><td>Select range</td></tr>
<tr><td><b>Ctrl+Click</b></td><td>Toggle selection</td></tr>
</table>

<h4>⚡ Actions</h4>
<table>
<tr><td><b>Delete</b></td><td>Delete selected to vault</td></tr>
<tr><td><b>R</b></td><td>Rotate selected</td></tr>
<tr><td><b>D</b></td><td>Correct date</td></tr>
</table>
"""
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About Photo Review",
            "📸 Photo Review\n"
            "Part of PyPhotoOrganizer\n\n"
            "Fast photo review with query-based selection.\n\n"
            "Built with PySide6"
        )

    # -------------------------------------------------------------------------
    # Window Geometry
    # -------------------------------------------------------------------------

    def restore_window_geometry(self):
        """Restore window geometry from settings."""
        geometry = self.settings.value("geometry")

        # Restore dark mode preference
        self._is_dark_mode = self.settings.value("dark_mode", True, type=bool)
        self._apply_theme()
        if self._is_dark_mode:
            self.theme_action.setText("🌙 Switch to Light Mode")
        else:
            self.theme_action.setText("☀ Switch to Dark Mode")

        if geometry:
            self.restoreGeometry(geometry)
            self.ensure_window_on_screen()
        else:
            self.center_on_screen()

    def center_on_screen(self):
        """Center window on primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())

    def ensure_window_on_screen(self):
        """Ensure window is visible on screen."""
        screen = QApplication.primaryScreen()
        if not screen:
            return

        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()

        if window_geometry.left() < screen_geometry.left():
            self.move(screen_geometry.left(), window_geometry.top())
            window_geometry = self.frameGeometry()
        elif window_geometry.right() > screen_geometry.right():
            self.move(screen_geometry.right() - window_geometry.width(), window_geometry.top())
            window_geometry = self.frameGeometry()

        if window_geometry.top() < screen_geometry.top():
            self.move(window_geometry.left(), screen_geometry.top())
        elif window_geometry.top() > screen_geometry.bottom() - 50:
            self.move(window_geometry.left(), screen_geometry.bottom() - 50)

    def closeEvent(self, event):
        """Handle window close event."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("dark_mode", self._is_dark_mode)

        if hasattr(self, 'main_splitter') and self.main_splitter:
            self.settings.setValue("main_splitter", self.main_splitter.saveState())
        if hasattr(self, 'right_splitter') and self.right_splitter:
            self.settings.setValue("right_splitter", self.right_splitter.saveState())

        if self.grid_model:
            self.settings.setValue("thumbnail_size", self.grid_model.thumbnail_size)

        if self.query_panel and self.database_metadata:
            state = {
                'last_query': self.query_panel.get_current_filters(),
                'last_folder': self.query_panel.get_current_folder()
            }
            self.database_metadata.set_photo_review_state(state)

        event.accept()
