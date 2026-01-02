"""
Results Tab for PyPhotoOrganizer GUI

Displays processing results and statistics.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QLabel, QTreeWidget, QTreeWidgetItem, QPushButton,
                               QFileDialog, QMessageBox, QTextEdit, QApplication)
from PySide6.QtCore import Qt
import json
import csv


class ResultsTab(QWidget):
    """Tab for displaying processing results."""

    def __init__(self):
        super().__init__()
        self.results_data = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Summary statistics group
        summary_group = QGroupBox("Summary Statistics")
        summary_layout = QVBoxLayout()

        # Make statistics copyable using QTextEdit
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setStyleSheet("background-color: #f5f5f5; font-family: monospace;")
        self.summary_text.setPlainText(
            "Total files examined: 0\n"
            "New original photos: 0 (0%)\n"
            "Duplicate files: 0 (0%)\n"
            "Filtered files: 0 (0%)\n"
            "Processing time: 00:00:00\n"
            "Average speed: 0.0 files/sec"
        )
        summary_layout.addWidget(self.summary_text)

        # Copy to clipboard button
        copy_btn = QPushButton("Copy Statistics to Clipboard")
        copy_btn.clicked.connect(self.copy_statistics)
        summary_layout.addWidget(copy_btn)

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Breakdown tree group
        breakdown_group = QGroupBox("Breakdown by Category")
        breakdown_layout = QVBoxLayout()

        self.breakdown_tree = QTreeWidget()
        self.breakdown_tree.setHeaderLabels(["Category", "Count"])
        self.breakdown_tree.setColumnWidth(0, 400)
        breakdown_layout.addWidget(self.breakdown_tree)

        breakdown_group.setLayout(breakdown_layout)
        layout.addWidget(breakdown_group)

        # Export button
        button_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export Results...")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def display_results(self, results):
        """Display processing results."""
        self.results_data = results

        # Update summary statistics
        total = results.get('total_files_examined', 0)
        originals = results.get('total_new_original_files', 0)
        duplicates = results.get('total_duplicates', 0)
        filtered = results.get('total_filtered', 0)
        processing_time = results.get('processing_time', 0)

        # Build summary text
        summary_lines = []
        summary_lines.append(f"Total files examined: {total}")

        if total > 0:
            orig_pct = (originals / total) * 100
            dup_pct = (duplicates / total) * 100
            filt_pct = (filtered / total) * 100
            summary_lines.append(f"New original photos: {originals} ({orig_pct:.1f}%)")
            summary_lines.append(f"Duplicate files: {duplicates} ({dup_pct:.1f}%)")
            summary_lines.append(f"Filtered files: {filtered} ({filt_pct:.1f}%)")

            if processing_time > 0:
                avg_speed = total / processing_time
                summary_lines.append(f"Average speed: {avg_speed:.2f} files/sec")
            else:
                summary_lines.append(f"Average speed: 0.0 files/sec")
        else:
            summary_lines.append(f"New original photos: 0 (0%)")
            summary_lines.append(f"Duplicate files: 0 (0%)")
            summary_lines.append(f"Filtered files: 0 (0%)")
            summary_lines.append(f"Average speed: 0.0 files/sec")

        summary_lines.append(f"Processing time: {self._format_time(processing_time)}")

        # Update the summary text widget
        self.summary_text.setPlainText("\n".join(summary_lines))

        # Update breakdown tree
        self.breakdown_tree.clear()

        # Original files
        original_item = QTreeWidgetItem(["Original Files", str(originals)])
        self.breakdown_tree.addTopLevelItem(original_item)

        # Duplicate files
        duplicate_item = QTreeWidgetItem(["Duplicate Files", str(duplicates)])
        self.breakdown_tree.addTopLevelItem(duplicate_item)

        # Filtered files
        filtered_item = QTreeWidgetItem(["Filtered Files", str(filtered)])
        self.breakdown_tree.addTopLevelItem(filtered_item)

        # Add filter statistics if available
        filter_stats = results.get('filter_statistics', {})
        if filter_stats:
            for reason, count in filter_stats.items():
                reason_item = QTreeWidgetItem([f"  {reason}", str(count)])
                filtered_item.addChild(reason_item)
            filtered_item.setExpanded(True)

        # Enable export button
        self.export_btn.setEnabled(True)

    def export_results(self):
        """Export results to file."""
        if not self.results_data:
            QMessageBox.warning(self, "No Data", "No results to export")
            return

        # Ask user for file format
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Results",
            "results.json",
            "JSON Files (*.json);;CSV Files (*.csv)")

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                self._export_json(file_path)
            elif file_path.endswith('.csv'):
                self._export_csv(file_path)
            else:
                QMessageBox.warning(self, "Invalid Format",
                                   "Please select .json or .csv file")
                return

            QMessageBox.information(self, "Export Successful",
                                   f"Results exported to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export results:\n\n{str(e)}")

    def _export_json(self, file_path):
        """Export results as JSON."""
        with open(file_path, 'w') as f:
            json.dump(self.results_data, f, indent=2)

    def _export_csv(self, file_path):
        """Export results as CSV."""
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])

            total = self.results_data.get('total_files_examined', 0)
            originals = self.results_data.get('total_new_original_files', 0)
            duplicates = self.results_data.get('total_duplicates', 0)
            filtered = self.results_data.get('total_filtered', 0)

            writer.writerow(['Total Files Examined', total])
            writer.writerow(['New Original Photos', originals])
            writer.writerow(['Duplicate Files', duplicates])
            writer.writerow(['Filtered Files', filtered])

            if total > 0:
                writer.writerow(['Original %', f"{(originals/total)*100:.1f}"])
                writer.writerow(['Duplicate %', f"{(duplicates/total)*100:.1f}"])
                writer.writerow(['Filtered %', f"{(filtered/total)*100:.1f}"])

    def copy_statistics(self):
        """Copy summary statistics to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.summary_text.toPlainText())
        QMessageBox.information(self, "Copied",
                               "Statistics copied to clipboard!")

    def _format_time(self, seconds):
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
