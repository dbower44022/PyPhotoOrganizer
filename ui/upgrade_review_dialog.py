"""
Upgrade Candidate Review Dialog

Allows users to review duplicates with different metadata before importing.
Shows side-by-side image comparison with highlighted metadata differences.

Workflow:
1. New files and exact duplicates are processed automatically
2. Duplicates with different metadata are queued for review
3. User reviews each candidate and decides: Keep Archive / Use Incoming / Skip
4. After review, import proceeds with user's decisions
"""

import logging
import os
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QFrame, QGroupBox, QListWidget, QListWidgetItem,
    QWidget, QMessageBox, QCheckBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont

from ui.duplicate_comparison_dialog import SynchronizedImageViewer
from ui.metadata_comparison_widget import MetadataComparisonWidget
from ui.theme import get_theme

logger = logging.getLogger(__name__)


class CandidateListItem(QListWidgetItem):
    """List item representing an upgrade candidate."""

    def __init__(self, candidate: Dict[str, Any], index: int):
        # Display filename and date info
        incoming_path = candidate.get('incoming_path', '')
        filename = os.path.basename(incoming_path)
        incoming_source = candidate.get('incoming_date_source', '')
        archive_source = candidate.get('archive_date_source', '')

        display_text = f"{filename}\n{incoming_source} vs {archive_source}"
        super().__init__(display_text)

        self.candidate = candidate
        self.index = index
        self.decision: Optional[str] = None  # 'use_incoming', 'keep_archive', or None (pending)

        self._update_display()

    def set_decision(self, decision: Optional[str]):
        """Set the user's decision for this candidate."""
        self.decision = decision
        self._update_display()

    def _update_display(self):
        """Update visual display based on decision state."""
        theme = get_theme()
        c = theme.colors

        if self.decision == 'use_incoming':
            self.setBackground(Qt.darkGreen)
            self.setForeground(Qt.white)
            self.setText(f"\u2713 {os.path.basename(self.candidate.get('incoming_path', ''))}\n  (Use Incoming)")
        elif self.decision == 'keep_archive':
            self.setBackground(Qt.darkBlue)
            self.setForeground(Qt.white)
            self.setText(f"\u2717 {os.path.basename(self.candidate.get('incoming_path', ''))}\n  (Keep Archive)")
        else:
            self.setBackground(Qt.transparent)
            self.setForeground(Qt.white)
            filename = os.path.basename(self.candidate.get('incoming_path', ''))
            incoming_source = self.candidate.get('incoming_date_source', '')
            archive_source = self.candidate.get('archive_date_source', '')
            self.setText(f"? {filename}\n  {incoming_source} vs {archive_source}")


class UpgradeReviewDialog(QDialog):
    """
    Dialog for reviewing upgrade candidates before import.

    Features:
    - List of all candidates needing review
    - Side-by-side image comparison with synchronized zoom
    - Metadata comparison with highlighted differences
    - Per-file decision: Use Incoming / Keep Archive / Skip
    - Batch actions: Apply decision to all remaining
    - Progress tracking

    Signals:
        review_completed: Emitted when user finishes review
            Args: list of candidates with 'decision' key added
    """

    review_completed = Signal(list)  # List of candidates with decisions

    def __init__(self, candidates: List[Dict[str, Any]], parent=None):
        """
        Initialize the review dialog.

        Args:
            candidates: List of upgrade candidate dicts from find_duplicates()
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Review Metadata Upgrades")
        self.setModal(True)
        self.resize(1600, 900)

        self._candidates = candidates
        self._current_index = 0
        self._sync_enabled = True

        self._init_ui()
        self._connect_signals()
        self._apply_theme()

        # Load first candidate
        if candidates:
            self._load_candidate(0)
            self._update_progress()

        logger.info(f"UpgradeReviewDialog initialized with {len(candidates)} candidates")

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Header with progress
        header_layout = QHBoxLayout()

        self.header_label = QLabel("Review files with different metadata")
        self.header_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(self.header_label)

        header_layout.addStretch()

        self.progress_label = QLabel("0 / 0")
        header_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setTextVisible(False)
        header_layout.addWidget(self.progress_bar)

        main_layout.addLayout(header_layout)

        # Main content area (splitter)
        main_splitter = QSplitter(Qt.Horizontal)

        # Left panel: Candidate list
        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)

        list_header = QLabel("Files to Review")
        list_header.setAlignment(Qt.AlignCenter)
        list_layout.addWidget(list_header)

        self.candidate_list = QListWidget()
        self.candidate_list.setMinimumWidth(250)
        self.candidate_list.setMaximumWidth(350)

        # Populate list
        for i, candidate in enumerate(self._candidates):
            item = CandidateListItem(candidate, i)
            self.candidate_list.addItem(item)

        list_layout.addWidget(self.candidate_list)

        # List legend
        legend_layout = QVBoxLayout()
        legend_layout.addWidget(QLabel("\u2713 = Use Incoming"))
        legend_layout.addWidget(QLabel("\u2717 = Keep Archive"))
        legend_layout.addWidget(QLabel("? = Pending review"))
        list_layout.addLayout(legend_layout)

        main_splitter.addWidget(list_panel)

        # Center panel: Image comparison
        comparison_panel = QWidget()
        comparison_layout = QVBoxLayout(comparison_panel)
        comparison_layout.setContentsMargins(0, 0, 0, 0)

        # Image comparison (horizontal splitter)
        image_splitter = QSplitter(Qt.Horizontal)

        # Incoming image
        incoming_group = QGroupBox("Incoming File")
        incoming_layout = QVBoxLayout(incoming_group)

        self.incoming_path_label = QLabel("Path: --")
        self.incoming_path_label.setWordWrap(True)
        self.incoming_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        incoming_layout.addWidget(self.incoming_path_label)

        self.incoming_viewer = SynchronizedImageViewer()
        self.incoming_viewer.setMinimumSize(300, 300)
        incoming_layout.addWidget(self.incoming_viewer, 1)

        image_splitter.addWidget(incoming_group)

        # Archive image
        archive_group = QGroupBox("Archive File")
        archive_layout = QVBoxLayout(archive_group)

        self.archive_path_label = QLabel("Path: --")
        self.archive_path_label.setWordWrap(True)
        self.archive_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        archive_layout.addWidget(self.archive_path_label)

        self.archive_viewer = SynchronizedImageViewer()
        self.archive_viewer.setMinimumSize(300, 300)
        archive_layout.addWidget(self.archive_viewer, 1)

        image_splitter.addWidget(archive_group)
        image_splitter.setSizes([400, 400])

        comparison_layout.addWidget(image_splitter, 2)

        # Zoom sync checkbox
        zoom_layout = QHBoxLayout()
        self.sync_checkbox = QCheckBox("Synchronize Zoom")
        self.sync_checkbox.setChecked(True)
        zoom_layout.addWidget(self.sync_checkbox)

        self.reset_zoom_btn = QPushButton("Reset Zoom")
        zoom_layout.addWidget(self.reset_zoom_btn)
        zoom_layout.addStretch()

        comparison_layout.addLayout(zoom_layout)

        main_splitter.addWidget(comparison_panel)

        # Right panel: Metadata comparison
        metadata_panel = QWidget()
        metadata_layout = QVBoxLayout(metadata_panel)
        metadata_layout.setContentsMargins(0, 0, 0, 0)

        metadata_header = QLabel("Metadata Comparison")
        metadata_header.setAlignment(Qt.AlignCenter)
        metadata_layout.addWidget(metadata_header)

        self.metadata_widget = MetadataComparisonWidget()
        self.metadata_widget.setMinimumWidth(400)
        metadata_layout.addWidget(self.metadata_widget, 1)

        main_splitter.addWidget(metadata_panel)

        # Set splitter sizes
        main_splitter.setSizes([280, 600, 400])

        main_layout.addWidget(main_splitter, 1)

        # Decision buttons
        decision_frame = QFrame()
        decision_layout = QHBoxLayout(decision_frame)
        decision_layout.setContentsMargins(8, 8, 8, 8)

        # Navigation
        self.prev_btn = QPushButton("\u25C0 Previous")
        self.prev_btn.setMinimumWidth(100)
        decision_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Next \u25B6")
        self.next_btn.setMinimumWidth(100)
        decision_layout.addWidget(self.next_btn)

        decision_layout.addSpacing(30)

        # Decision buttons
        self.use_incoming_btn = QPushButton("Use Incoming")
        self.use_incoming_btn.setMinimumWidth(120)
        self.use_incoming_btn.setToolTip("Replace archive file with incoming file (better metadata)")
        decision_layout.addWidget(self.use_incoming_btn)

        self.keep_archive_btn = QPushButton("Keep Archive")
        self.keep_archive_btn.setMinimumWidth(120)
        self.keep_archive_btn.setToolTip("Keep existing archive file, skip this incoming file")
        decision_layout.addWidget(self.keep_archive_btn)

        decision_layout.addStretch()

        # Batch actions
        self.use_all_btn = QPushButton("Use Incoming for All")
        self.use_all_btn.setToolTip("Apply 'Use Incoming' to all remaining pending candidates")
        decision_layout.addWidget(self.use_all_btn)

        self.keep_all_btn = QPushButton("Keep Archive for All")
        self.keep_all_btn.setToolTip("Apply 'Keep Archive' to all remaining pending candidates")
        decision_layout.addWidget(self.keep_all_btn)

        main_layout.addWidget(decision_frame)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        self.stats_label = QLabel("Pending: 0 | Use Incoming: 0 | Keep Archive: 0")
        bottom_layout.addWidget(self.stats_label)

        bottom_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel Import")
        self.cancel_btn.setMinimumWidth(120)
        bottom_layout.addWidget(self.cancel_btn)

        self.finish_btn = QPushButton("Finish Review")
        self.finish_btn.setMinimumWidth(120)
        self.finish_btn.setEnabled(False)  # Enabled when all reviewed
        bottom_layout.addWidget(self.finish_btn)

        main_layout.addLayout(bottom_layout)

    def _connect_signals(self):
        """Connect widget signals."""
        # List selection
        self.candidate_list.currentRowChanged.connect(self._on_list_selection_changed)

        # Navigation
        self.prev_btn.clicked.connect(self._go_previous)
        self.next_btn.clicked.connect(self._go_next)

        # Decisions
        self.use_incoming_btn.clicked.connect(lambda: self._set_decision('use_incoming'))
        self.keep_archive_btn.clicked.connect(lambda: self._set_decision('keep_archive'))
        self.use_all_btn.clicked.connect(self._use_all_incoming)
        self.keep_all_btn.clicked.connect(self._keep_all_archive)

        # Zoom sync
        self.sync_checkbox.stateChanged.connect(self._on_sync_changed)
        self.reset_zoom_btn.clicked.connect(self._reset_zoom)

        # Image sync
        self.incoming_viewer.zoom_region_changed.connect(self._on_incoming_zoom)
        self.incoming_viewer.zoom_reset.connect(self._on_incoming_reset)
        self.archive_viewer.zoom_region_changed.connect(self._on_archive_zoom)
        self.archive_viewer.zoom_reset.connect(self._on_archive_reset)

        # Dialog buttons
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.finish_btn.clicked.connect(self._on_finish)

    def _apply_theme(self):
        """Apply theme styling."""
        theme = get_theme()
        c = theme.colors

        self.setStyleSheet(theme.get_global_stylesheet())

        # Header
        self.header_label.setStyleSheet(f"""
            font-size: 14pt;
            font-weight: bold;
            color: {c.text_primary};
        """)

        # Decision buttons
        self.use_incoming_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.success};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {c.success}dd;
            }}
        """)

        self.keep_archive_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
        """)

        # Batch buttons (less prominent)
        batch_style = f"""
            QPushButton {{
                background-color: {c.bg_tertiary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {c.hover_bg};
            }}
        """
        self.use_all_btn.setStyleSheet(batch_style)
        self.keep_all_btn.setStyleSheet(batch_style)

        # Navigation buttons
        nav_style = f"""
            QPushButton {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {c.hover_bg};
            }}
            QPushButton:disabled {{
                color: {c.text_muted};
            }}
        """
        self.prev_btn.setStyleSheet(nav_style)
        self.next_btn.setStyleSheet(nav_style)

        # Cancel button
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.error};
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {c.error}dd;
            }}
        """)

        # Finish button
        self.finish_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.success};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {c.success}dd;
            }}
            QPushButton:disabled {{
                background-color: {c.bg_tertiary};
                color: {c.text_muted};
            }}
        """)

    def _load_candidate(self, index: int):
        """Load a candidate for display."""
        if index < 0 or index >= len(self._candidates):
            return

        self._current_index = index
        candidate = self._candidates[index]

        # Update list selection
        self.candidate_list.setCurrentRow(index)

        # Load images
        incoming_path = candidate.get('incoming_path', '')
        archive_path = candidate.get('archive_path', '')

        self.incoming_path_label.setText(f"Path: {incoming_path}")
        self.archive_path_label.setText(f"Path: {archive_path}")

        if incoming_path and os.path.exists(incoming_path):
            self.incoming_viewer.load_image(incoming_path)
        else:
            self.incoming_viewer.clear()

        if archive_path and os.path.exists(archive_path):
            self.archive_viewer.load_image(archive_path)
        else:
            self.archive_viewer.clear()

        # Load metadata comparison
        # Build archive metadata dict from candidate info
        archive_metadata = {
            'date_reliable': True,  # Assume reliable unless specified otherwise
            'file_size': candidate.get('incoming_file_size'),  # Will be overwritten if we have real data
        }
        self.metadata_widget.set_data(candidate, archive_metadata)

        # Update navigation buttons
        self.prev_btn.setEnabled(index > 0)
        self.next_btn.setEnabled(index < len(self._candidates) - 1)

    def _on_list_selection_changed(self, row: int):
        """Handle list selection change."""
        if row >= 0:
            self._load_candidate(row)

    def _go_previous(self):
        """Go to previous candidate."""
        if self._current_index > 0:
            self._load_candidate(self._current_index - 1)

    def _go_next(self):
        """Go to next candidate."""
        if self._current_index < len(self._candidates) - 1:
            self._load_candidate(self._current_index + 1)

    def _set_decision(self, decision: str):
        """Set decision for current candidate and advance."""
        item = self.candidate_list.item(self._current_index)
        if isinstance(item, CandidateListItem):
            item.set_decision(decision)
            self._candidates[self._current_index]['decision'] = decision

        self._update_progress()

        # Auto-advance to next pending
        self._go_to_next_pending()

    def _go_to_next_pending(self):
        """Go to next candidate without a decision."""
        # First try after current position
        for i in range(self._current_index + 1, len(self._candidates)):
            item = self.candidate_list.item(i)
            if isinstance(item, CandidateListItem) and item.decision is None:
                self._load_candidate(i)
                return

        # Then try from beginning
        for i in range(0, self._current_index):
            item = self.candidate_list.item(i)
            if isinstance(item, CandidateListItem) and item.decision is None:
                self._load_candidate(i)
                return

    def _use_all_incoming(self):
        """Apply 'use_incoming' to all pending candidates."""
        count = 0
        for i in range(len(self._candidates)):
            item = self.candidate_list.item(i)
            if isinstance(item, CandidateListItem) and item.decision is None:
                item.set_decision('use_incoming')
                self._candidates[i]['decision'] = 'use_incoming'
                count += 1

        self._update_progress()
        logger.info(f"Applied 'Use Incoming' to {count} pending candidates")

    def _keep_all_archive(self):
        """Apply 'keep_archive' to all pending candidates."""
        count = 0
        for i in range(len(self._candidates)):
            item = self.candidate_list.item(i)
            if isinstance(item, CandidateListItem) and item.decision is None:
                item.set_decision('keep_archive')
                self._candidates[i]['decision'] = 'keep_archive'
                count += 1

        self._update_progress()
        logger.info(f"Applied 'Keep Archive' to {count} pending candidates")

    def _update_progress(self):
        """Update progress display and stats."""
        pending = 0
        use_incoming = 0
        keep_archive = 0

        for i in range(len(self._candidates)):
            item = self.candidate_list.item(i)
            if isinstance(item, CandidateListItem):
                if item.decision is None:
                    pending += 1
                elif item.decision == 'use_incoming':
                    use_incoming += 1
                elif item.decision == 'keep_archive':
                    keep_archive += 1

        total = len(self._candidates)
        reviewed = total - pending

        self.progress_label.setText(f"{reviewed} / {total}")
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(reviewed)

        self.stats_label.setText(
            f"Pending: {pending} | Use Incoming: {use_incoming} | Keep Archive: {keep_archive}"
        )

        # Enable finish button when all reviewed
        self.finish_btn.setEnabled(pending == 0)

    def _on_sync_changed(self, state):
        """Handle zoom sync checkbox change."""
        self._sync_enabled = (state == Qt.Checked)

    def _reset_zoom(self):
        """Reset zoom on both viewers."""
        self.incoming_viewer.zoom_to_fit()
        self.archive_viewer.zoom_to_fit()

    def _on_incoming_zoom(self, x, y, w, h):
        """Mirror zoom from incoming to archive viewer."""
        if self._sync_enabled:
            self.archive_viewer.apply_normalized_zoom(x, y, w, h)

    def _on_archive_zoom(self, x, y, w, h):
        """Mirror zoom from archive to incoming viewer."""
        if self._sync_enabled:
            self.incoming_viewer.apply_normalized_zoom(x, y, w, h)

    def _on_incoming_reset(self):
        """Mirror reset from incoming to archive viewer."""
        if self._sync_enabled:
            self.archive_viewer.sync_zoom_to_fit()

    def _on_archive_reset(self):
        """Mirror reset from archive to incoming viewer."""
        if self._sync_enabled:
            self.incoming_viewer.sync_zoom_to_fit()

    def _on_cancel(self):
        """Handle cancel button - confirm and close without completing."""
        reply = QMessageBox.question(
            self,
            "Cancel Review",
            "Are you sure you want to cancel?\n\n"
            "Files that were marked 'Use Incoming' will NOT be upgraded.\n"
            "The import will proceed without any metadata upgrades.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Set all to keep_archive (no changes)
            for candidate in self._candidates:
                candidate['decision'] = 'keep_archive'

            self.review_completed.emit(self._candidates)
            self.reject()

    def _on_finish(self):
        """Handle finish button - complete review."""
        # Count decisions
        use_incoming = sum(1 for c in self._candidates if c.get('decision') == 'use_incoming')
        keep_archive = sum(1 for c in self._candidates if c.get('decision') == 'keep_archive')

        # Confirm
        reply = QMessageBox.question(
            self,
            "Confirm Review",
            f"Review complete:\n\n"
            f"  {use_incoming} file(s) will be upgraded (Use Incoming)\n"
            f"  {keep_archive} file(s) will be skipped (Keep Archive)\n\n"
            f"Proceed with import?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            self.review_completed.emit(self._candidates)
            self.accept()

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close."""
        # Treat close as cancel
        for candidate in self._candidates:
            if 'decision' not in candidate:
                candidate['decision'] = 'keep_archive'

        self.review_completed.emit(self._candidates)
        event.accept()

    def get_approved_upgrades(self) -> List[Dict[str, Any]]:
        """
        Get list of candidates approved for upgrade.

        Returns:
            List of candidate dicts where decision is 'use_incoming'
        """
        return [c for c in self._candidates if c.get('decision') == 'use_incoming']

    def get_rejected_upgrades(self) -> List[Dict[str, Any]]:
        """
        Get list of candidates rejected (keep archive).

        Returns:
            List of candidate dicts where decision is 'keep_archive'
        """
        return [c for c in self._candidates if c.get('decision') == 'keep_archive']


def show_upgrade_review(candidates: List[Dict[str, Any]], parent=None) -> List[Dict[str, Any]]:
    """
    Convenience function to show the upgrade review dialog.

    Args:
        candidates: List of upgrade candidate dicts
        parent: Parent widget

    Returns:
        List of candidates with 'decision' key added
        Empty list if no candidates or user cancelled
    """
    if not candidates:
        return []

    dialog = UpgradeReviewDialog(candidates, parent)
    result = dialog.exec()

    if result == QDialog.Accepted:
        return dialog.get_approved_upgrades()
    else:
        return []
