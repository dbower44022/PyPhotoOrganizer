"""
Metadata Comparison Widget

Displays metadata differences between two files with visual highlighting.
Used in the upgrade candidate review dialog to help users understand
what differs between incoming and archive files.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.theme import get_theme

logger = logging.getLogger(__name__)


class MetadataFieldRow(QFrame):
    """
    A single row in the metadata comparison showing one field.

    Displays: Field Name | Incoming Value | Archive Value
    Highlights the row if values differ.
    """

    def __init__(self, field_name: str, incoming_value: str, archive_value: str,
                 is_different: bool = False, parent=None):
        super().__init__(parent)
        self._is_different = is_different
        self._field_name = field_name

        self._init_ui(field_name, incoming_value, archive_value)
        self._apply_styling()

    def _init_ui(self, field_name: str, incoming_value: str, archive_value: str):
        """Initialize the row UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        # Field name (fixed width)
        self.name_label = QLabel(field_name)
        self.name_label.setFixedWidth(120)
        self.name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.name_label)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFixedWidth(1)
        layout.addWidget(sep1)

        # Incoming value
        self.incoming_label = QLabel(incoming_value or "(none)")
        self.incoming_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.incoming_label.setWordWrap(True)
        self.incoming_label.setMinimumWidth(150)
        layout.addWidget(self.incoming_label, 1)

        # Difference indicator
        if self._is_different:
            self.diff_label = QLabel("\u2260")  # Not equal sign
            self.diff_label.setAlignment(Qt.AlignCenter)
            self.diff_label.setFixedWidth(30)
        else:
            self.diff_label = QLabel("=")
            self.diff_label.setAlignment(Qt.AlignCenter)
            self.diff_label.setFixedWidth(30)
        layout.addWidget(self.diff_label)

        # Archive value
        self.archive_label = QLabel(archive_value or "(none)")
        self.archive_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.archive_label.setWordWrap(True)
        self.archive_label.setMinimumWidth(150)
        layout.addWidget(self.archive_label, 1)

    def _apply_styling(self):
        """Apply visual styling based on difference state."""
        theme = get_theme()
        c = theme.colors

        if self._is_different:
            # Highlighted row for differences
            self.setStyleSheet(f"""
                MetadataFieldRow {{
                    background-color: {c.warning}20;
                    border: 1px solid {c.warning};
                    border-radius: 4px;
                }}
            """)

            # Bold the field name for differences
            font = self.name_label.font()
            font.setBold(True)
            self.name_label.setFont(font)

            # Style the diff indicator
            self.diff_label.setStyleSheet(f"""
                color: {c.warning};
                font-weight: bold;
                font-size: 14pt;
            """)

            # Highlight the values
            self.incoming_label.setStyleSheet(f"color: {c.success}; font-weight: bold;")
            self.archive_label.setStyleSheet(f"color: {c.text_muted};")
        else:
            # Normal row
            self.setStyleSheet(f"""
                MetadataFieldRow {{
                    background-color: transparent;
                    border: 1px solid transparent;
                }}
            """)
            self.diff_label.setStyleSheet(f"color: {c.text_muted};")


class MetadataComparisonWidget(QWidget):
    """
    Widget displaying side-by-side metadata comparison with highlighted differences.

    Shows:
    - Header with "Incoming" and "Archive" labels
    - Quality score comparison with visual bar
    - Field-by-field comparison with difference highlighting
    - Summary of what will change
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._incoming_data: Dict[str, Any] = {}
        self._archive_data: Dict[str, Any] = {}

        self._init_ui()

    def _init_ui(self):
        """Initialize the widget UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Header row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 8, 8, 8)

        # Field name header
        field_header = QLabel("Field")
        field_header.setFixedWidth(120)
        field_header.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(field_header)

        header_layout.addSpacing(25)

        # Incoming header
        self.incoming_header = QLabel("INCOMING (New)")
        self.incoming_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.incoming_header, 1)

        header_layout.addSpacing(30)

        # Archive header
        self.archive_header = QLabel("ARCHIVE (Existing)")
        self.archive_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.archive_header, 1)

        main_layout.addLayout(header_layout)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        main_layout.addWidget(sep)

        # Quality score comparison
        self.score_frame = QFrame()
        score_layout = QHBoxLayout(self.score_frame)
        score_layout.setContentsMargins(8, 8, 8, 8)

        score_label = QLabel("Quality Score")
        score_label.setFixedWidth(120)
        score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        score_layout.addWidget(score_label)

        score_layout.addSpacing(25)

        self.incoming_score_label = QLabel("--")
        self.incoming_score_label.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(self.incoming_score_label, 1)

        self.score_diff_label = QLabel(">")
        self.score_diff_label.setAlignment(Qt.AlignCenter)
        self.score_diff_label.setFixedWidth(30)
        score_layout.addWidget(self.score_diff_label)

        self.archive_score_label = QLabel("--")
        self.archive_score_label.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(self.archive_score_label, 1)

        main_layout.addWidget(self.score_frame)

        # Scrollable area for metadata fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.fields_container = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_container)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(4)

        scroll.setWidget(self.fields_container)
        main_layout.addWidget(scroll, 1)

        # Summary label
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.summary_label)

        self._apply_theme()

    def _apply_theme(self):
        """Apply theme styling."""
        theme = get_theme()
        c = theme.colors

        # Header styling
        header_style = f"""
            font-weight: bold;
            font-size: 11pt;
            color: {c.text_primary};
            padding: 4px;
        """
        self.incoming_header.setStyleSheet(header_style + f"background-color: {c.success}30; border-radius: 4px;")
        self.archive_header.setStyleSheet(header_style + f"background-color: {c.primary}30; border-radius: 4px;")

        # Score frame styling
        self.score_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_secondary};
                border-radius: 6px;
                padding: 4px;
            }}
        """)

    def set_data(self, incoming: Dict[str, Any], archive: Dict[str, Any]):
        """
        Set the metadata to compare.

        Args:
            incoming: Dict with incoming file metadata (from upgrade candidate)
            archive: Dict with archive file metadata
        """
        self._incoming_data = incoming
        self._archive_data = archive

        # Clear existing fields
        while self.fields_layout.count():
            item = self.fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Extract and compare fields
        fields = self._extract_comparison_fields(incoming, archive)

        differences_count = 0
        for field_name, incoming_val, archive_val, is_different in fields:
            row = MetadataFieldRow(field_name, incoming_val, archive_val, is_different)
            self.fields_layout.addWidget(row)
            if is_different:
                differences_count += 1

        # Add stretch at end
        self.fields_layout.addStretch()

        # Update score display
        incoming_score = incoming.get('incoming_metadata_score', 0)
        archive_score = incoming.get('archive_metadata_score', 0)

        self._update_score_display(incoming_score, archive_score)

        # Update summary
        self._update_summary(differences_count, incoming_score, archive_score)

    def _extract_comparison_fields(self, incoming: Dict[str, Any],
                                    archive: Dict[str, Any]) -> List[Tuple[str, str, str, bool]]:
        """
        Extract fields to compare and determine if they differ.

        Returns:
            List of tuples: (field_name, incoming_value, archive_value, is_different)
        """
        fields = []

        # Date
        incoming_date = incoming.get('incoming_date', '')
        archive_date = incoming.get('archive_date', '')
        fields.append((
            "Date",
            incoming_date,
            archive_date,
            incoming_date != archive_date
        ))

        # Date Source
        incoming_source = incoming.get('incoming_date_source', '')
        archive_source = incoming.get('archive_date_source', '')
        fields.append((
            "Date Source",
            self._format_date_source(incoming_source),
            self._format_date_source(archive_source),
            incoming_source != archive_source
        ))

        # Reliability
        incoming_reliable = incoming.get('incoming_is_reliable', False)
        archive_reliable = archive.get('date_reliable', True)
        fields.append((
            "Reliable",
            "Yes" if incoming_reliable else "No",
            "Yes" if archive_reliable else "No",
            incoming_reliable != archive_reliable
        ))

        # File Size
        incoming_size = incoming.get('incoming_file_size')
        archive_size = archive.get('file_size')
        if incoming_size is not None or archive_size is not None:
            fields.append((
                "File Size",
                self._format_file_size(incoming_size) if incoming_size else "(unknown)",
                self._format_file_size(archive_size) if archive_size else "(unknown)",
                incoming_size != archive_size if (incoming_size and archive_size) else False
            ))

        # Content Hash (if available)
        content_hash = incoming.get('content_hash')
        if content_hash:
            fields.append((
                "Content Match",
                "Identical pixels",
                "Identical pixels",
                False  # Same content, just different metadata
            ))

        # Upgrade Reason
        upgrade_reason = incoming.get('upgrade_reason', '')
        if upgrade_reason:
            fields.append((
                "Upgrade Reason",
                upgrade_reason,
                "",
                True  # Always highlight the reason
            ))

        return fields

    def _format_date_source(self, source: str) -> str:
        """Format date source for display."""
        source_names = {
            'exif': 'EXIF Original',
            'exif_digitized': 'EXIF Digitized',
            'exif_gps': 'GPS Timestamp',
            'exif_datetime': 'EXIF DateTime',
            'iptc': 'IPTC',
            'xmp': 'XMP',
            'video_metadata': 'Video Metadata',
            'video_quicktime': 'QuickTime',
            'os_metadata': 'OS Metadata',
            'fallback': 'Fallback (unreliable)',
        }
        return source_names.get(source, source or '(unknown)')

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def _update_score_display(self, incoming_score: int, archive_score: int):
        """Update the quality score comparison display."""
        theme = get_theme()
        c = theme.colors

        # Incoming score
        self.incoming_score_label.setText(f"{incoming_score}/100")
        if incoming_score > archive_score:
            self.incoming_score_label.setStyleSheet(f"""
                font-size: 14pt;
                font-weight: bold;
                color: {c.success};
                padding: 8px;
                background-color: {c.success}20;
                border-radius: 4px;
            """)
        else:
            self.incoming_score_label.setStyleSheet(f"""
                font-size: 14pt;
                font-weight: bold;
                color: {c.text_primary};
                padding: 8px;
            """)

        # Archive score
        self.archive_score_label.setText(f"{archive_score}/100")
        if archive_score > incoming_score:
            self.archive_score_label.setStyleSheet(f"""
                font-size: 14pt;
                font-weight: bold;
                color: {c.success};
                padding: 8px;
                background-color: {c.success}20;
                border-radius: 4px;
            """)
        else:
            self.archive_score_label.setStyleSheet(f"""
                font-size: 14pt;
                font-weight: bold;
                color: {c.text_muted};
                padding: 8px;
            """)

        # Comparison indicator
        if incoming_score > archive_score:
            self.score_diff_label.setText(">")
            self.score_diff_label.setStyleSheet(f"color: {c.success}; font-weight: bold; font-size: 16pt;")
        elif incoming_score < archive_score:
            self.score_diff_label.setText("<")
            self.score_diff_label.setStyleSheet(f"color: {c.error}; font-weight: bold; font-size: 16pt;")
        else:
            self.score_diff_label.setText("=")
            self.score_diff_label.setStyleSheet(f"color: {c.text_muted}; font-size: 16pt;")

    def _update_summary(self, differences_count: int, incoming_score: int, archive_score: int):
        """Update the summary text."""
        theme = get_theme()
        c = theme.colors

        if incoming_score > archive_score:
            score_diff = incoming_score - archive_score
            summary = f"Incoming file has better metadata (+{score_diff} quality points)"
            color = c.success
        elif incoming_score < archive_score:
            score_diff = archive_score - incoming_score
            summary = f"Archive file has better metadata (+{score_diff} quality points)"
            color = c.warning
        else:
            summary = "Both files have equivalent metadata quality"
            color = c.text_muted

        summary += f"\n{differences_count} field(s) differ between files"

        self.summary_label.setText(summary)
        self.summary_label.setStyleSheet(f"""
            color: {color};
            font-size: 10pt;
            padding: 8px;
            background-color: {c.bg_secondary};
            border-radius: 4px;
        """)
