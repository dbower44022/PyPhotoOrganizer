"""
Query Panel

Modern left sidebar panel with collapsible sections, icons, saved queries,
search, filters, and folder browser for the Photo Review application.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QGroupBox, QDateEdit,
    QTreeWidget, QTreeWidgetItem, QScrollArea, QFrame,
    QInputDialog, QMessageBox, QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QDate, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QFont

from photo_review.query_builder import PhotoQueryBuilder

logger = logging.getLogger(__name__)


class CollapsibleSection(QWidget):
    """
    Modern collapsible section with icon, title, and animated expand/collapse.
    """

    def __init__(self, title: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.is_expanded = True
        self._animation_duration = 150

        self._init_ui(title, icon)

        # Set size policy to not expand vertically
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def _init_ui(self, title: str, icon: str):
        """Initialize the collapsible section UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)

        # Header button
        self.header_btn = QPushButton()
        self.header_btn.setObjectName("sectionHeader")
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.clicked.connect(self.toggle)

        # Build header text with icon
        arrow = "▼" if self.is_expanded else "▶"
        header_text = f"{arrow}  {icon}  {title}" if icon else f"{arrow}  {title}"
        self.header_btn.setText(header_text)
        self._title = title
        self._icon = icon

        self.header_btn.setStyleSheet("""
            QPushButton#sectionHeader {
                background-color: #333333;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                text-align: left;
                font-weight: 600;
                font-size: 13px;
                color: #FAFAFA;
            }
            QPushButton#sectionHeader:hover {
                background-color: #404040;
            }
        """)

        layout.addWidget(self.header_btn)

        # Content container
        self.content_widget = QWidget()
        self.content_widget.setObjectName("sectionContent")
        self.content_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 12, 16, 8)
        self.content_layout.setSpacing(8)

        self.content_widget.setStyleSheet("""
            QWidget#sectionContent {
                background-color: #2A2A2A;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)

        layout.addWidget(self.content_widget)

    def add_widget(self, widget: QWidget):
        """Add a widget to the section content."""
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        """Add a layout to the section content."""
        self.content_layout.addLayout(layout)

    def toggle(self):
        """Toggle expand/collapse state."""
        self.is_expanded = not self.is_expanded
        self.content_widget.setVisible(self.is_expanded)

        # Update arrow
        arrow = "▼" if self.is_expanded else "▶"
        header_text = f"{arrow}  {self._icon}  {self._title}" if self._icon else f"{arrow}  {self._title}"
        self.header_btn.setText(header_text)

    def set_expanded(self, expanded: bool):
        """Set expanded state."""
        if self.is_expanded != expanded:
            self.toggle()


class QueryPanel(QWidget):
    """
    Modern left panel with collapsible sections, icons, and query builder.

    Signals:
        query_executed(list): Emits list of file records matching query
        folder_selected(str): Emits folder path for folder-based viewing
    """

    query_executed = Signal(list)  # List of matching records
    folder_selected = Signal(str)  # Folder path

    def __init__(self, db_metadata, db_path: str, parent=None):
        super().__init__(parent)
        self.db_metadata = db_metadata
        self.db_path = db_path
        self.query_builder = PhotoQueryBuilder(db_path)

        self._current_folder = None
        self._current_filters = {}
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._on_search_timeout)

        self._init_ui()
        self._load_saved_queries()

        # Initialize system queries
        self.db_metadata.initialize_system_queries()
        self._load_saved_queries()

    def _init_ui(self):
        """Initialize the modern user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # Panel styling
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #E0E0E0;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #333333;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0066FF;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
            QComboBox {
                background-color: #333333;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 6px 10px;
                color: #FFFFFF;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #0066FF;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #888888;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #333333;
                border: 1px solid #444444;
                selection-background-color: #0066FF;
            }
            QCheckBox {
                color: #E0E0E0;
                spacing: 8px;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 4px;
                background-color: #333333;
            }
            QCheckBox::indicator:hover {
                border-color: #0066FF;
            }
            QCheckBox::indicator:checked {
                background-color: #0066FF;
                border-color: #0066FF;
            }
            QPushButton {
                background-color: #333333;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 8px 16px;
                color: #FFFFFF;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #404040;
                border-color: #0066FF;
            }
            QPushButton:pressed {
                background-color: #0066FF;
            }
            QDateEdit {
                background-color: #333333;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 4px 8px;
                color: #FFFFFF;
                font-size: 12px;
            }
            QDateEdit:focus {
                border-color: #0066FF;
            }
            QTreeWidget {
                background-color: #2A2A2A;
                border: 1px solid #444444;
                border-radius: 6px;
                color: #E0E0E0;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: rgba(0, 102, 255, 0.3);
            }
            QTreeWidget::item:hover {
                background-color: rgba(0, 102, 255, 0.15);
            }
        """)

        # Create scroll area for the panel content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(8)
        scroll_layout.setAlignment(Qt.AlignTop)  # Keep all content at top

        # -----------------------------------------------------------------
        # Saved Queries Section
        # -----------------------------------------------------------------
        self.queries_section = CollapsibleSection("Saved Queries", "⭐")
        queries_content = QVBoxLayout()
        queries_content.setSpacing(8)

        self.queries_combo = QComboBox()
        self.queries_combo.setMinimumHeight(32)
        self.queries_combo.currentIndexChanged.connect(self._on_query_selected)
        queries_content.addWidget(self.queries_combo)

        query_buttons = QHBoxLayout()
        query_buttons.setSpacing(6)

        self.save_query_btn = QPushButton("💾 Save")
        self.save_query_btn.clicked.connect(self.save_current_query)
        query_buttons.addWidget(self.save_query_btn)

        self.delete_query_btn = QPushButton("🗑 Delete")
        self.delete_query_btn.clicked.connect(self._delete_selected_query)
        query_buttons.addWidget(self.delete_query_btn)

        queries_content.addLayout(query_buttons)

        # Add to section
        container = QWidget()
        container.setLayout(queries_content)
        self.queries_section.add_widget(container)
        scroll_layout.addWidget(self.queries_section)

        # -----------------------------------------------------------------
        # Quick Search Section
        # -----------------------------------------------------------------
        self.search_section = CollapsibleSection("Search", "🔍")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename, path...")
        self.search_input.setMinimumHeight(36)
        self.search_input.textChanged.connect(self._on_search_changed)
        self.search_input.returnPressed.connect(self.execute_query)
        self.search_section.add_widget(self.search_input)

        scroll_layout.addWidget(self.search_section)

        # -----------------------------------------------------------------
        # Date Filters Section
        # -----------------------------------------------------------------
        self.date_section = CollapsibleSection("Date Filters", "📅")
        date_content = QVBoxLayout()
        date_content.setSpacing(8)

        # Quick date buttons
        quick_date_row = QHBoxLayout()
        quick_date_row.setSpacing(6)

        today_btn = QPushButton("Today")
        today_btn.clicked.connect(lambda: self._set_quick_date(0))
        quick_date_row.addWidget(today_btn)

        week_btn = QPushButton("7 Days")
        week_btn.clicked.connect(lambda: self._set_quick_date(7))
        quick_date_row.addWidget(week_btn)

        month_btn = QPushButton("30 Days")
        month_btn.clicked.connect(lambda: self._set_quick_date(30))
        quick_date_row.addWidget(month_btn)

        date_content.addLayout(quick_date_row)

        # Enable creation date filter
        self.use_creation_date = QCheckBox("Filter by creation date")
        self.use_creation_date.setChecked(False)
        date_content.addWidget(self.use_creation_date)

        # Creation date range
        creation_label = QLabel("Creation Date Range:")
        creation_label.setStyleSheet("font-weight: 600; margin-top: 4px;")
        date_content.addWidget(creation_label)

        creation_date_row = QHBoxLayout()
        creation_date_row.setSpacing(8)

        self.creation_date_from = QDateEdit()
        self.creation_date_from.setCalendarPopup(True)
        self.creation_date_from.setDate(QDate.currentDate().addYears(-1))
        self.creation_date_from.setSpecialValueText("Any")
        self.creation_date_from.setMinimumDate(QDate(1990, 1, 1))
        creation_date_row.addWidget(QLabel("From:"))
        creation_date_row.addWidget(self.creation_date_from, 1)

        self.creation_date_to = QDateEdit()
        self.creation_date_to.setCalendarPopup(True)
        self.creation_date_to.setDate(QDate.currentDate())
        self.creation_date_to.setSpecialValueText("Any")
        creation_date_row.addWidget(QLabel("To:"))
        creation_date_row.addWidget(self.creation_date_to, 1)

        date_content.addLayout(creation_date_row)

        # Correction date
        self.use_correction_date = QCheckBox("Filter by correction date")
        self.use_correction_date.setChecked(False)
        date_content.addWidget(self.use_correction_date)

        correction_date_row = QHBoxLayout()
        correction_date_row.setSpacing(8)

        self.correction_date_from = QDateEdit()
        self.correction_date_from.setCalendarPopup(True)
        self.correction_date_from.setDate(QDate.currentDate().addMonths(-1))
        correction_date_row.addWidget(QLabel("From:"))
        correction_date_row.addWidget(self.correction_date_from, 1)

        self.correction_date_to = QDateEdit()
        self.correction_date_to.setCalendarPopup(True)
        self.correction_date_to.setDate(QDate.currentDate())
        correction_date_row.addWidget(QLabel("To:"))
        correction_date_row.addWidget(self.correction_date_to, 1)

        date_content.addLayout(correction_date_row)

        container = QWidget()
        container.setLayout(date_content)
        self.date_section.add_widget(container)
        scroll_layout.addWidget(self.date_section)

        # -----------------------------------------------------------------
        # Status Filters Section
        # -----------------------------------------------------------------
        self.status_section = CollapsibleSection("Status Filters", "🏷")
        status_content = QVBoxLayout()
        status_content.setSpacing(8)

        # Version filter dropdown
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel("Show:"))
        self.version_filter_combo = QComboBox()
        self.version_filter_combo.addItem("Current Versions Only", "current")
        self.version_filter_combo.addItem("All Versions", "all")
        self.version_filter_combo.addItem("Prior Versions Only", "prior")
        self.version_filter_combo.setCurrentIndex(0)
        version_layout.addWidget(self.version_filter_combo, 1)
        status_content.addLayout(version_layout)

        # Status checkboxes with colored indicators
        self.unreliable_dates_cb = QCheckBox("⚠ Has unreliable date")
        self.unreliable_dates_cb.setStyleSheet("QCheckBox { color: #F59E0B; }")
        status_content.addWidget(self.unreliable_dates_cb)

        self.needs_correction_cb = QCheckBox("❓ Needs date correction")
        status_content.addWidget(self.needs_correction_cb)

        self.needs_reorganization_cb = QCheckBox("📦 Needs reorganization")
        self.needs_reorganization_cb.setStyleSheet("QCheckBox { color: #10B981; }")
        status_content.addWidget(self.needs_reorganization_cb)

        self.has_revisions_cb = QCheckBox("🔄 Has revisions")
        self.has_revisions_cb.setStyleSheet("QCheckBox { color: #8B5CF6; }")
        status_content.addWidget(self.has_revisions_cb)

        container = QWidget()
        container.setLayout(status_content)
        self.status_section.add_widget(container)
        scroll_layout.addWidget(self.status_section)

        # -----------------------------------------------------------------
        # Filename Pattern Section
        # -----------------------------------------------------------------
        self.pattern_section = CollapsibleSection("Filename Pattern", "📝")
        self.pattern_section.set_expanded(False)  # Collapsed by default

        self.filename_pattern = QLineEdit()
        self.filename_pattern.setPlaceholderText("e.g., IMG_, vacation, 2024")
        self.pattern_section.add_widget(self.filename_pattern)

        scroll_layout.addWidget(self.pattern_section)

        # -----------------------------------------------------------------
        # Execute Button (Always Visible)
        # -----------------------------------------------------------------
        execute_container = QWidget()
        execute_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        execute_layout = QHBoxLayout(execute_container)
        execute_layout.setContentsMargins(0, 12, 0, 12)
        execute_layout.setSpacing(8)

        self.execute_btn = QPushButton("🚀 Execute Query")
        self.execute_btn.setMinimumHeight(40)
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066FF;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0052CC;
            }
            QPushButton:pressed {
                background-color: #003D99;
            }
        """)
        self.execute_btn.clicked.connect(self.execute_query)
        execute_layout.addWidget(self.execute_btn)

        self.clear_btn = QPushButton("✕ Clear")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setMaximumWidth(80)
        self.clear_btn.clicked.connect(self.clear_filters)
        execute_layout.addWidget(self.clear_btn)

        scroll_layout.addWidget(execute_container)

        # -----------------------------------------------------------------
        # Folder Browser Section
        # -----------------------------------------------------------------
        self.folder_section = CollapsibleSection("Archive Folders", "📁")

        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setMinimumHeight(150)
        self.folder_tree.setMaximumHeight(300)
        self.folder_tree.itemClicked.connect(self._on_folder_clicked)
        self.folder_tree.itemExpanded.connect(self._on_folder_expanded)
        self.folder_section.add_widget(self.folder_tree)

        refresh_btn = QPushButton("🔄 Refresh Folders")
        refresh_btn.clicked.connect(self._load_folder_tree)
        self.folder_section.add_widget(refresh_btn)

        scroll_layout.addWidget(self.folder_section)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Load folder tree
        QTimer.singleShot(100, self._load_folder_tree)

    def _load_saved_queries(self):
        """Load saved queries into the combo box."""
        self.queries_combo.blockSignals(True)
        self.queries_combo.clear()

        # Add placeholder
        self.queries_combo.addItem("-- Select a saved query --", None)

        # Load queries from database
        queries = self.db_metadata.get_saved_queries()
        for query in queries:
            name = query['name']
            if query['is_favorite']:
                name = f"★ {name}"
            self.queries_combo.addItem(name, query)

        self.queries_combo.blockSignals(False)

    def _on_query_selected(self, index: int):
        """Handle saved query selection - auto-executes the query."""
        if index <= 0:
            return

        query_data = self.queries_combo.itemData(index)
        if query_data:
            self.set_filters(query_data.get('filters', {}))
            # Auto-execute the selected query
            self.execute_query()

    def _delete_selected_query(self):
        """Delete the currently selected saved query."""
        index = self.queries_combo.currentIndex()
        if index <= 0:
            return

        query_data = self.queries_combo.itemData(index)
        if not query_data:
            return

        if query_data.get('is_system'):
            QMessageBox.warning(
                self, "Cannot Delete",
                "System queries cannot be deleted."
            )
            return

        name = query_data.get('name', '')
        reply = QMessageBox.question(
            self, "Delete Query",
            f"Delete saved query '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.db_metadata.delete_saved_query(name):
                self._load_saved_queries()

    def _on_search_changed(self, text: str):
        """Handle search text change with debounce."""
        self._search_timer.stop()
        self._search_timer.start(300)  # 300ms debounce

    def _on_search_timeout(self):
        """Execute search after debounce."""
        self.execute_query()

    def _set_quick_date(self, days_ago: int):
        """Set quick date filter."""
        self.use_creation_date.setChecked(True)

        if days_ago == 0:
            # Today
            today = QDate.currentDate()
            self.creation_date_from.setDate(today)
            self.creation_date_to.setDate(today)
        else:
            # Last N days
            today = QDate.currentDate()
            from_date = today.addDays(-days_ago)
            self.creation_date_from.setDate(from_date)
            self.creation_date_to.setDate(today)

        self.execute_query()

    def _load_folder_tree(self):
        """Load the archive folder tree."""
        self.folder_tree.clear()

        # Get archive location
        archive_location = self.db_metadata.get_archive_location()
        if not archive_location:
            return

        # Get year folders from query builder
        years = self.query_builder.get_archive_folders()

        for year_data in years:
            year = year_data['year']
            count = year_data['count']

            year_item = QTreeWidgetItem([f"📅 {year} ({count:,} photos)"])
            year_item.setData(0, Qt.UserRole, {'type': 'year', 'year': year})
            year_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            self.folder_tree.addTopLevelItem(year_item)

    def _on_folder_expanded(self, item: QTreeWidgetItem):
        """Handle folder expansion - load children."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        # Check if already loaded
        if item.childCount() > 0 and item.child(0).data(0, Qt.UserRole):
            return

        # Remove placeholder child
        item.takeChildren()

        if data.get('type') == 'year':
            # Load months for this year
            year = data['year']
            months = self.query_builder.get_months_in_year(year)

            for month_data in months:
                month = month_data['month']
                count = month_data['count']

                # Format month name
                try:
                    month_num = int(month)
                    month_name = datetime(2000, month_num, 1).strftime('%B')
                except:
                    month_name = month

                month_item = QTreeWidgetItem([f"📆 {month_name} ({count:,})"])
                month_item.setData(0, Qt.UserRole, {
                    'type': 'month',
                    'year': year,
                    'month': month
                })
                month_item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                item.addChild(month_item)

        elif data.get('type') == 'month':
            # Load days for this month
            year = data['year']
            month = data['month']
            days = self.query_builder.get_days_in_month(year, month)

            for day_data in days:
                day = day_data['day']
                count = day_data['count']

                day_item = QTreeWidgetItem([f"📄 Day {day} ({count:,})"])
                day_item.setData(0, Qt.UserRole, {
                    'type': 'day',
                    'year': year,
                    'month': month,
                    'day': day
                })
                item.addChild(day_item)

    def _on_folder_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle folder click - execute query for that folder."""
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        # Clear other filters and search
        self.clear_filters()

        # Build date filter based on folder level
        if data.get('type') == 'year':
            year = int(data['year'])
            results = self.query_builder.get_photos_by_date(year)
        elif data.get('type') == 'month':
            year = int(data['year'])
            month = int(data['month'])
            results = self.query_builder.get_photos_by_date(year, month)
        elif data.get('type') == 'day':
            year = int(data['year'])
            month = int(data['month'])
            day = int(data['day'])
            results = self.query_builder.get_photos_by_date(year, month, day)
        else:
            return

        # Store current folder selection
        self._current_folder = f"{data.get('year', '')}/{data.get('month', '')}/{data.get('day', '')}"

        # Emit results
        self.query_executed.emit(results)

    def get_current_filters(self) -> Dict[str, Any]:
        """Get the current filter settings."""
        filters = {}

        # Search text
        search = self.search_input.text().strip()
        if search:
            filters['search_text'] = search

        # Creation date
        if self.use_creation_date.isChecked():
            filters['creation_date_from'] = self.creation_date_from.date().toString('yyyy-MM-dd')
            filters['creation_date_to'] = self.creation_date_to.date().toString('yyyy-MM-dd')

        # Correction date
        if self.use_correction_date.isChecked():
            filters['correction_date_from'] = self.correction_date_from.date().toString('yyyy-MM-dd')
            filters['correction_date_to'] = self.correction_date_to.date().toString('yyyy-MM-dd')

        # Version filter
        version_filter = self.version_filter_combo.currentData()
        if version_filter and version_filter != "current":
            filters['version_filter'] = version_filter

        # Status filters
        if self.unreliable_dates_cb.isChecked():
            filters['has_unreliable_date'] = True

        if self.needs_correction_cb.isChecked():
            filters['has_unreliable_date'] = True
            filters['has_corrected_date'] = False

        if self.needs_reorganization_cb.isChecked():
            filters['needs_reorganization'] = True

        if self.has_revisions_cb.isChecked():
            filters['has_revisions'] = True

        # Filename pattern
        pattern = self.filename_pattern.text().strip()
        if pattern:
            filters['filename_pattern'] = pattern

        return filters

    def set_filters(self, filters: Dict[str, Any]):
        """Set filter controls from a filter dict."""
        # Block signals during update
        self.search_input.blockSignals(True)

        # Clear all
        self.search_input.clear()
        self.use_creation_date.setChecked(False)
        self.use_correction_date.setChecked(False)
        self.version_filter_combo.setCurrentIndex(0)
        self.unreliable_dates_cb.setChecked(False)
        self.needs_correction_cb.setChecked(False)
        self.needs_reorganization_cb.setChecked(False)
        self.has_revisions_cb.setChecked(False)
        self.filename_pattern.clear()

        # Apply filters
        if filters.get('search_text'):
            self.search_input.setText(filters['search_text'])

        if filters.get('creation_date_from'):
            self.use_creation_date.setChecked(True)
            date = QDate.fromString(filters['creation_date_from'], 'yyyy-MM-dd')
            if date.isValid():
                self.creation_date_from.setDate(date)

        if filters.get('creation_date_to'):
            self.use_creation_date.setChecked(True)
            date = QDate.fromString(filters['creation_date_to'], 'yyyy-MM-dd')
            if date.isValid():
                self.creation_date_to.setDate(date)

        if filters.get('correction_date_from'):
            self.use_correction_date.setChecked(True)
            date = QDate.fromString(filters['correction_date_from'], 'yyyy-MM-dd')
            if date.isValid():
                self.correction_date_from.setDate(date)

        if filters.get('correction_date_to'):
            self.use_correction_date.setChecked(True)
            date = QDate.fromString(filters['correction_date_to'], 'yyyy-MM-dd')
            if date.isValid():
                self.correction_date_to.setDate(date)

        if filters.get('has_unreliable_date'):
            self.unreliable_dates_cb.setChecked(True)

        if filters.get('has_corrected_date') is False:
            self.needs_correction_cb.setChecked(True)

        if filters.get('needs_reorganization'):
            self.needs_reorganization_cb.setChecked(True)

        if filters.get('has_revisions'):
            self.has_revisions_cb.setChecked(True)

        if filters.get('filename_pattern'):
            self.filename_pattern.setText(filters['filename_pattern'])

        # Version filter
        version_filter = filters.get('version_filter', 'current')
        version_index = self.version_filter_combo.findData(version_filter)
        if version_index >= 0:
            self.version_filter_combo.setCurrentIndex(version_index)

        self.search_input.blockSignals(False)
        self._current_filters = filters

    def get_current_folder(self) -> Optional[str]:
        """Get the currently selected folder path."""
        return self._current_folder

    def set_folder(self, folder_path: str):
        """Set the current folder selection."""
        self._current_folder = folder_path
        # TODO: Expand and select the folder in the tree

    def clear_filters(self):
        """Clear all filter controls."""
        self.search_input.clear()
        self.use_creation_date.setChecked(False)
        self.use_correction_date.setChecked(False)
        self.version_filter_combo.setCurrentIndex(0)
        self.unreliable_dates_cb.setChecked(False)
        self.needs_correction_cb.setChecked(False)
        self.needs_reorganization_cb.setChecked(False)
        self.has_revisions_cb.setChecked(False)
        self.filename_pattern.clear()
        self._current_folder = None
        self._current_filters = {}

        # Clear folder selection
        self.folder_tree.clearSelection()

    def execute_query(self):
        """Execute the current query and emit results."""
        filters = self.get_current_filters()
        self._current_filters = filters
        self._current_folder = None  # Clear folder selection when running manual query

        logger.info(f"Executing query with filters: {filters}")

        # Execute query
        results = self.query_builder.execute_query(filters)

        # Update query usage if using a saved query
        index = self.queries_combo.currentIndex()
        if index > 0:
            query_data = self.queries_combo.itemData(index)
            if query_data:
                self.db_metadata.update_query_usage(query_data.get('name', ''))

        # Emit results
        self.query_executed.emit(results)

    def save_current_query(self):
        """Save the current query configuration."""
        filters = self.get_current_filters()

        if not filters:
            QMessageBox.information(
                self, "No Filters",
                "Please set some filters before saving a query."
            )
            return

        # Get query name
        name, ok = QInputDialog.getText(
            self, "Save Query",
            "Enter a name for this query:"
        )

        if ok and name:
            # Check if name already exists
            existing = self.db_metadata.get_query_by_name(name)
            if existing and not existing.get('is_system'):
                reply = QMessageBox.question(
                    self, "Query Exists",
                    f"Query '{name}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            # Save query
            if self.db_metadata.save_query(name, filters):
                QMessageBox.information(
                    self, "Query Saved",
                    f"Query '{name}' has been saved."
                )
                self._load_saved_queries()
            else:
                QMessageBox.warning(
                    self, "Save Failed",
                    "Failed to save query. Please try again."
                )
