"""
Cloud Settings Widget for PyPhotoOrganizer.

Provides UI for configuring cloud storage backends (S3, Azure, etc.)
for each vault type (archive, video_archive, prior_revision, delete_vault).

Features:
- Provider selection (Local, S3, Azure, GCS)
- Credential input with secure storage
- Connection testing
- Storage class selection
- Per-vault configuration
"""

import json
import logging
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox,
    QSpinBox, QTabWidget, QMessageBox, QFrame, QProgressBar,
    QSizePolicy
)

logger = logging.getLogger(__name__)

# Check for credential manager availability
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring not installed - credentials will not be stored securely")


# Storage provider options
STORAGE_PROVIDERS = [
    ('local', 'Local Filesystem'),
    ('s3', 'Amazon S3'),
    ('azure', 'Azure Blob Storage (Coming Soon)'),
    ('gcs', 'Google Cloud Storage (Coming Soon)'),
]

# S3 storage classes
S3_STORAGE_CLASSES = [
    ('INTELLIGENT_TIERING', 'Intelligent-Tiering (Recommended)'),
    ('STANDARD', 'Standard'),
    ('STANDARD_IA', 'Standard-IA (Infrequent Access)'),
    ('ONEZONE_IA', 'One Zone-IA'),
    ('GLACIER_IR', 'Glacier Instant Retrieval'),
    ('GLACIER', 'Glacier Flexible Retrieval'),
    ('DEEP_ARCHIVE', 'Glacier Deep Archive'),
]

# AWS regions
AWS_REGIONS = [
    ('us-east-1', 'US East (N. Virginia)'),
    ('us-east-2', 'US East (Ohio)'),
    ('us-west-1', 'US West (N. California)'),
    ('us-west-2', 'US West (Oregon)'),
    ('eu-west-1', 'EU (Ireland)'),
    ('eu-west-2', 'EU (London)'),
    ('eu-central-1', 'EU (Frankfurt)'),
    ('ap-northeast-1', 'Asia Pacific (Tokyo)'),
    ('ap-southeast-1', 'Asia Pacific (Singapore)'),
    ('ap-southeast-2', 'Asia Pacific (Sydney)'),
]

# Vault types with descriptions
VAULT_TYPES = [
    ('archive', 'Photo Archive', 'Main photo storage'),
    ('video_archive', 'Video Archive', 'Video file storage (optional)'),
    ('prior_revision', 'Prior Revisions', 'Original files before edits'),
    ('delete_vault', 'Delete Vault', 'Deleted files (recoverable)'),
]


class ConnectionTestWorker(QThread):
    """Worker thread for testing cloud connection."""

    finished = Signal(bool, str)  # success, message

    def __init__(self, provider: str, config: Dict[str, Any]):
        super().__init__()
        self.provider = provider
        self.config = config

    def run(self):
        """Test the connection."""
        try:
            if self.provider == 'local':
                # Test local path exists
                import os
                path = self.config.get('path', '')
                if not path:
                    self.finished.emit(False, "No path specified")
                    return

                if os.path.isdir(path):
                    self.finished.emit(True, f"Path exists: {path}")
                elif os.path.exists(path):
                    self.finished.emit(False, f"Path exists but is not a directory: {path}")
                else:
                    # Try to create it
                    try:
                        os.makedirs(path, exist_ok=True)
                        self.finished.emit(True, f"Created directory: {path}")
                    except Exception as e:
                        self.finished.emit(False, f"Cannot create directory: {e}")

            elif self.provider == 's3':
                # Test S3 connection
                try:
                    import boto3
                    from botocore.exceptions import ClientError, NoCredentialsError

                    bucket = self.config.get('bucket', '')
                    region = self.config.get('region', 'us-east-1')

                    if not bucket:
                        self.finished.emit(False, "No bucket specified")
                        return

                    # Create S3 client
                    session_kwargs = {}
                    if self.config.get('credentials_profile'):
                        session_kwargs['profile_name'] = self.config['credentials_profile']

                    session = boto3.Session(**session_kwargs)
                    s3 = session.client('s3', region_name=region)

                    # Test by listing bucket (HEAD bucket)
                    s3.head_bucket(Bucket=bucket)
                    self.finished.emit(True, f"Successfully connected to bucket: {bucket}")

                except NoCredentialsError:
                    self.finished.emit(False, "No AWS credentials found. Configure credentials via AWS CLI or environment variables.")
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code == '403':
                        self.finished.emit(False, f"Access denied to bucket: {bucket}. Check your permissions.")
                    elif error_code == '404':
                        self.finished.emit(False, f"Bucket not found: {bucket}")
                    else:
                        self.finished.emit(False, f"S3 error: {e}")
                except ImportError:
                    self.finished.emit(False, "boto3 not installed. Install with: pip install boto3")

            else:
                self.finished.emit(False, f"Provider not yet implemented: {self.provider}")

        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            self.finished.emit(False, f"Error: {str(e)}")


class VaultConfigWidget(QFrame):
    """Configuration widget for a single vault type."""

    config_changed = Signal()

    def __init__(self, vault_type: str, vault_name: str, vault_desc: str, parent=None):
        super().__init__(parent)
        self.vault_type = vault_type
        self.vault_name = vault_name
        self._test_worker = None

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self._setup_ui(vault_desc)

    def _setup_ui(self, description: str):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header with enable checkbox
        header_layout = QHBoxLayout()

        self.enable_checkbox = QCheckBox(f"Enable {self.vault_name}")
        self.enable_checkbox.setChecked(self.vault_type == 'archive')  # Archive always enabled
        self.enable_checkbox.stateChanged.connect(self._on_enable_changed)
        header_layout.addWidget(self.enable_checkbox)

        header_layout.addStretch()

        # Status indicator
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray;")
        header_layout.addWidget(self.status_label)

        layout.addLayout(header_layout)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(desc_label)

        # Provider selection
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Storage Provider:"))

        self.provider_combo = QComboBox()
        for value, label in STORAGE_PROVIDERS:
            self.provider_combo.addItem(label, value)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()

        layout.addLayout(provider_layout)

        # Stacked config widgets
        self.config_container = QWidget()
        self.config_layout = QVBoxLayout(self.config_container)
        self.config_layout.setContentsMargins(0, 5, 0, 0)
        layout.addWidget(self.config_container)

        # Local config
        self.local_config = self._create_local_config()
        self.config_layout.addWidget(self.local_config)

        # S3 config
        self.s3_config = self._create_s3_config()
        self.s3_config.hide()
        self.config_layout.addWidget(self.s3_config)

        # Test connection button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self._test_connection)
        button_layout.addWidget(self.test_button)

        layout.addLayout(button_layout)

        # Progress bar for testing
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Initial state
        self._on_enable_changed()

    def _create_local_config(self) -> QWidget:
        """Create local storage config widget."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.local_path_edit = QLineEdit()
        self.local_path_edit.setPlaceholderText("/path/to/storage")
        self.local_path_edit.textChanged.connect(self.config_changed)
        layout.addRow("Path:", self.local_path_edit)

        return widget

    def _create_s3_config(self) -> QWidget:
        """Create S3 storage config widget."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Bucket
        self.s3_bucket_edit = QLineEdit()
        self.s3_bucket_edit.setPlaceholderText("my-photo-bucket")
        self.s3_bucket_edit.textChanged.connect(self.config_changed)
        layout.addRow("Bucket:", self.s3_bucket_edit)

        # Prefix (optional)
        self.s3_prefix_edit = QLineEdit()
        self.s3_prefix_edit.setPlaceholderText("photos (optional)")
        self.s3_prefix_edit.textChanged.connect(self.config_changed)
        layout.addRow("Prefix:", self.s3_prefix_edit)

        # Region
        self.s3_region_combo = QComboBox()
        for value, label in AWS_REGIONS:
            self.s3_region_combo.addItem(label, value)
        self.s3_region_combo.currentIndexChanged.connect(self.config_changed)
        layout.addRow("Region:", self.s3_region_combo)

        # Storage class
        self.s3_storage_class_combo = QComboBox()
        for value, label in S3_STORAGE_CLASSES:
            self.s3_storage_class_combo.addItem(label, value)
        self.s3_storage_class_combo.currentIndexChanged.connect(self.config_changed)
        layout.addRow("Storage Class:", self.s3_storage_class_combo)

        # Credentials profile (optional)
        self.s3_profile_edit = QLineEdit()
        self.s3_profile_edit.setPlaceholderText("default (optional)")
        self.s3_profile_edit.textChanged.connect(self.config_changed)
        layout.addRow("AWS Profile:", self.s3_profile_edit)

        # Info about credentials
        cred_info = QLabel(
            "Credentials are loaded from AWS CLI configuration (~/.aws/credentials)\n"
            "or environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)"
        )
        cred_info.setStyleSheet("color: gray; font-size: 10px;")
        cred_info.setWordWrap(True)
        layout.addRow("", cred_info)

        return widget

    def _on_enable_changed(self):
        """Handle enable/disable checkbox."""
        enabled = self.enable_checkbox.isChecked()
        self.config_container.setEnabled(enabled)
        self.test_button.setEnabled(enabled)

        if self.vault_type == 'archive':
            # Archive cannot be disabled
            self.enable_checkbox.setChecked(True)
            self.enable_checkbox.setEnabled(False)

        self.config_changed.emit()

    def _on_provider_changed(self):
        """Handle provider selection change."""
        provider = self.provider_combo.currentData()

        # Show/hide appropriate config
        self.local_config.setVisible(provider == 'local')
        self.s3_config.setVisible(provider == 's3')

        # Disable test for unimplemented providers
        self.test_button.setEnabled(provider in ('local', 's3'))

        self.config_changed.emit()

    def _test_connection(self):
        """Test the current configuration."""
        if self._test_worker and self._test_worker.isRunning():
            return

        provider = self.provider_combo.currentData()
        config = self.get_config()

        self.test_button.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText("Testing...")
        self.status_label.setStyleSheet("color: orange;")

        self._test_worker = ConnectionTestWorker(provider, config)
        self._test_worker.finished.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        """Handle connection test result."""
        self.test_button.setEnabled(True)
        self.progress_bar.hide()

        if success:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "Connection Test", message)
        else:
            self.status_label.setText("Failed")
            self.status_label.setStyleSheet("color: red;")
            QMessageBox.warning(self, "Connection Test Failed", message)

    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration."""
        if not self.enable_checkbox.isChecked():
            return None

        provider = self.provider_combo.currentData()
        config = {'type': provider}

        if provider == 'local':
            config['path'] = self.local_path_edit.text().strip()

        elif provider == 's3':
            config['bucket'] = self.s3_bucket_edit.text().strip()
            config['prefix'] = self.s3_prefix_edit.text().strip()
            config['region'] = self.s3_region_combo.currentData()
            config['storage_class'] = self.s3_storage_class_combo.currentData()

            profile = self.s3_profile_edit.text().strip()
            if profile:
                config['credentials_profile'] = profile

        return config

    def set_config(self, config: Dict[str, Any]):
        """Set the configuration."""
        if config is None:
            self.enable_checkbox.setChecked(False)
            return

        self.enable_checkbox.setChecked(True)
        provider = config.get('type', 'local')

        # Set provider
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == provider:
                self.provider_combo.setCurrentIndex(i)
                break

        if provider == 'local':
            self.local_path_edit.setText(config.get('path', ''))

        elif provider == 's3':
            self.s3_bucket_edit.setText(config.get('bucket', ''))
            self.s3_prefix_edit.setText(config.get('prefix', ''))

            # Set region
            region = config.get('region', 'us-east-1')
            for i in range(self.s3_region_combo.count()):
                if self.s3_region_combo.itemData(i) == region:
                    self.s3_region_combo.setCurrentIndex(i)
                    break

            # Set storage class
            storage_class = config.get('storage_class', 'INTELLIGENT_TIERING')
            for i in range(self.s3_storage_class_combo.count()):
                if self.s3_storage_class_combo.itemData(i) == storage_class:
                    self.s3_storage_class_combo.setCurrentIndex(i)
                    break

            self.s3_profile_edit.setText(config.get('credentials_profile', ''))


class CloudSettingsWidget(QWidget):
    """
    Main cloud settings widget with tabs for each vault type.

    Usage:
        widget = CloudSettingsWidget()
        widget.set_storage_config(existing_config)

        # Later...
        new_config = widget.get_storage_config()
    """

    config_changed = Signal(dict)  # Emitted when any config changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vault_widgets: Dict[str, VaultConfigWidget] = {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QLabel("Cloud Storage Configuration")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        info = QLabel(
            "Configure where each type of file is stored. "
            "You can use local storage or cloud providers like Amazon S3."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(info)

        # Tab widget for vault types
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create tabs for each vault type
        for vault_type, vault_name, vault_desc in VAULT_TYPES:
            vault_widget = VaultConfigWidget(vault_type, vault_name, vault_desc)
            vault_widget.config_changed.connect(self._on_config_changed)
            self.vault_widgets[vault_type] = vault_widget
            self.tab_widget.addTab(vault_widget, vault_name)

        # Cloud defaults section
        defaults_group = QGroupBox("Cloud Upload Settings")
        defaults_layout = QFormLayout(defaults_group)

        self.upload_threads_spin = QSpinBox()
        self.upload_threads_spin.setRange(1, 16)
        self.upload_threads_spin.setValue(4)
        self.upload_threads_spin.valueChanged.connect(self._on_config_changed)
        defaults_layout.addRow("Upload Threads:", self.upload_threads_spin)

        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(1, 100)
        self.chunk_size_spin.setValue(8)
        self.chunk_size_spin.setSuffix(" MB")
        self.chunk_size_spin.valueChanged.connect(self._on_config_changed)
        defaults_layout.addRow("Chunk Size:", self.chunk_size_spin)

        self.retry_attempts_spin = QSpinBox()
        self.retry_attempts_spin.setRange(1, 10)
        self.retry_attempts_spin.setValue(3)
        self.retry_attempts_spin.valueChanged.connect(self._on_config_changed)
        defaults_layout.addRow("Retry Attempts:", self.retry_attempts_spin)

        layout.addWidget(defaults_group)

        # Status bar
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.status_label)

        self._update_status()

    def _on_config_changed(self):
        """Handle configuration change."""
        self._update_status()
        self.config_changed.emit(self.get_storage_config())

    def _update_status(self):
        """Update status display."""
        config = self.get_storage_config()
        cloud_vaults = []

        for vault_type, vault_config in config.get('storage', {}).items():
            if vault_config and vault_config.get('type') != 'local':
                cloud_vaults.append(vault_type)

        if cloud_vaults:
            self.status_label.setText(
                f"Cloud storage enabled for: {', '.join(cloud_vaults)}"
            )
        else:
            self.status_label.setText("All storage is local")

    def get_storage_config(self) -> Dict[str, Any]:
        """
        Get the complete storage configuration.

        Returns:
            Dictionary with 'storage' and 'cloud_defaults' keys
        """
        storage = {}
        for vault_type, widget in self.vault_widgets.items():
            config = widget.get_config()
            if config:
                storage[vault_type] = config

        return {
            'storage': storage,
            'cloud_defaults': {
                'upload_threads': self.upload_threads_spin.value(),
                'chunk_size_mb': self.chunk_size_spin.value(),
                'retry_attempts': self.retry_attempts_spin.value(),
                'retry_delay_seconds': 5
            }
        }

    def set_storage_config(self, config: Dict[str, Any]):
        """
        Set the storage configuration.

        Args:
            config: Configuration dict with 'storage' and optionally 'cloud_defaults'
        """
        storage = config.get('storage', {})
        for vault_type, widget in self.vault_widgets.items():
            vault_config = storage.get(vault_type)
            widget.set_config(vault_config)

        cloud_defaults = config.get('cloud_defaults', {})
        if cloud_defaults:
            self.upload_threads_spin.setValue(
                cloud_defaults.get('upload_threads', 4)
            )
            self.chunk_size_spin.setValue(
                cloud_defaults.get('chunk_size_mb', 8)
            )
            self.retry_attempts_spin.setValue(
                cloud_defaults.get('retry_attempts', 3)
            )

        self._update_status()

    def has_cloud_storage(self) -> bool:
        """Check if any vault uses cloud storage."""
        config = self.get_storage_config()
        for vault_config in config.get('storage', {}).values():
            if vault_config and vault_config.get('type') != 'local':
                return True
        return False


if __name__ == '__main__':
    """Test the cloud settings widget."""
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("Cloud Settings Test")
    window.setMinimumSize(600, 500)

    widget = CloudSettingsWidget()

    # Set some test config
    test_config = {
        'storage': {
            'archive': {'type': 'local', 'path': '/home/user/photos'},
            'video_archive': {
                'type': 's3',
                'bucket': 'my-videos',
                'region': 'us-west-2',
                'storage_class': 'INTELLIGENT_TIERING'
            }
        },
        'cloud_defaults': {
            'upload_threads': 4,
            'chunk_size_mb': 8,
            'retry_attempts': 3
        }
    }
    widget.set_storage_config(test_config)

    def on_config_changed(config):
        print("Config changed:")
        print(json.dumps(config, indent=2))

    widget.config_changed.connect(on_config_changed)

    window.setCentralWidget(widget)
    window.show()

    sys.exit(app.exec())
