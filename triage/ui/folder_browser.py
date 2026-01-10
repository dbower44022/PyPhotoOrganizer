"""
Folder Browser

Tree view for navigating archive folder structure.
Shows year/month/day hierarchy for easy folder selection.
"""

import logging
import os
from pathlib import Path

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                               QLabel, QLineEdit, QPushButton, QHBoxLayout)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

logger = logging.getLogger(__name__)


class FolderBrowser(QWidget):
    """
    Folder browser tree widget.

    Shows archive folder structure:
    - 2025/
      - 01/
        - 01/
        - 02/
      - 02/
    """

    # Signals
    folder_selected = Signal(str)  # Emits folder path when selected

    def __init__(self, parent=None):
        super().__init__(parent)

        self.archive_root = None

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("<b>Archive Folders</b>")
        layout.addWidget(header)

        # Filter box
        filter_layout = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter folders...")
        self.filter_edit.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_edit)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_tree)
        filter_layout.addWidget(refresh_btn)

        layout.addLayout(filter_layout)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        layout.addWidget(self.tree)

        # Statistics label
        self.stats_label = QLabel("Select archive location")
        self.stats_label.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self.stats_label)

    def set_archive_root(self, archive_path: str):
        """
        Set archive root directory and populate tree.

        Args:
            archive_path: Path to archive root directory
        """
        self.archive_root = Path(archive_path)

        if not self.archive_root.exists():
            logger.warning(f"Archive path does not exist: {archive_path}")
            self.stats_label.setText(f"Archive not found: {archive_path}")
            return

        logger.info(f"Setting archive root: {archive_path}")
        self._populate_tree()

    def _populate_tree(self):
        """Populate tree with folder structure."""
        self.tree.clear()

        if not self.archive_root or not self.archive_root.exists():
            return

        try:
            # Add root item
            root_item = QTreeWidgetItem(self.tree, [str(self.archive_root)])
            root_item.setData(0, Qt.UserRole, str(self.archive_root))

            # Find all year folders (top-level numeric directories)
            year_folders = sorted([
                d for d in self.archive_root.iterdir()
                if d.is_dir() and d.name.isdigit() and len(d.name) == 4
            ], reverse=True)  # Most recent first

            for year_folder in year_folders:
                year_item = QTreeWidgetItem(root_item, [year_folder.name])
                year_item.setData(0, Qt.UserRole, str(year_folder))

                # Add dummy child to make expandable
                year_item.addChild(QTreeWidgetItem(["Loading..."]))

            root_item.setExpanded(True)

            folder_count = len(year_folders)
            self.stats_label.setText(f"{folder_count} year folders")

            logger.info(f"Populated tree with {folder_count} year folders")

        except Exception as e:
            logger.error(f"Failed to populate tree: {e}", exc_info=True)
            self.stats_label.setText(f"Error loading folders: {e}")

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """
        Handle item expansion - lazy load children.

        Args:
            item: Tree item being expanded
        """
        # Remove dummy "Loading..." item
        if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
            item.removeChild(item.child(0))

            # Load actual children
            folder_path = Path(item.data(0, Qt.UserRole))

            try:
                # Find subdirectories (month or day folders)
                subdirs = sorted([
                    d for d in folder_path.iterdir()
                    if d.is_dir() and d.name.isdigit()
                ])

                for subdir in subdirs:
                    child_item = QTreeWidgetItem(item, [subdir.name])
                    child_item.setData(0, Qt.UserRole, str(subdir))

                    # Check if this folder has subdirectories
                    if any(d.is_dir() for d in subdir.iterdir() if d.name.isdigit()):
                        # Add dummy child to make expandable
                        child_item.addChild(QTreeWidgetItem(["Loading..."]))

            except Exception as e:
                logger.error(f"Failed to load folder contents: {e}", exc_info=True)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """
        Handle item click - emit folder path.

        Args:
            item: Clicked tree item
            column: Column index
        """
        folder_path = item.data(0, Qt.UserRole)
        if folder_path and folder_path != "Loading...":
            logger.info(f"Folder selected: {folder_path}")
            self.folder_selected.emit(folder_path)

    def _apply_filter(self, filter_text: str):
        """
        Filter tree items by text.

        Args:
            filter_text: Filter string
        """
        # Simple filter: hide items that don't match
        if not filter_text:
            # Show all
            self._show_all_items()
            return

        filter_text = filter_text.lower()

        def filter_item(item: QTreeWidgetItem) -> bool:
            """Recursively filter item and children. Returns True if item should be visible."""
            # Check if item text matches
            text_match = filter_text in item.text(0).lower()

            # Check children
            has_visible_child = False
            for i in range(item.childCount()):
                child = item.child(i)
                if filter_item(child):
                    has_visible_child = True

            # Show item if it matches or has visible children
            should_show = text_match or has_visible_child
            item.setHidden(not should_show)

            return should_show

        # Apply filter to all top-level items
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            filter_item(root.child(i))

    def _show_all_items(self):
        """Show all tree items (remove filter)."""
        def show_item(item: QTreeWidgetItem):
            item.setHidden(False)
            for i in range(item.childCount()):
                show_item(item.child(i))

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            show_item(root.child(i))

    def _refresh_tree(self):
        """Refresh tree from disk."""
        if self.archive_root:
            self._populate_tree()


if __name__ == '__main__':
    # Test folder browser
    from PySide6.QtWidgets import QApplication
    import sys

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)

    browser = FolderBrowser()
    browser.resize(300, 600)
    browser.show()

    # Set test archive path
    test_archive = "/archive"  # Change to your archive path
    if Path(test_archive).exists():
        browser.set_archive_root(test_archive)

    def on_folder_selected(folder_path):
        print(f"Folder selected: {folder_path}")

    browser.folder_selected.connect(on_folder_selected)

    sys.exit(app.exec())
