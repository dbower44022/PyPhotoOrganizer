"""
Configuration management for the PhotoOrganizer application.

This module provides a centralized configuration system that handles loading,
validating, and accessing application settings with proper defaults.

Supports both legacy single-path configuration and new multi-vault storage
configuration for cloud storage integration.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import constants

if TYPE_CHECKING:
    from storage_backend import StorageManager


class Config:
    """
    Configuration manager for PhotoOrganizer.

    Loads settings from JSON file, provides defaults, validates required settings,
    and offers clean access to configuration values.

    Usage:
        config = Config('settings.json')
        source_dirs = config.get('source_directory')
        batch_size = config.get('batch_size', default=100)

        # Or access via attribute
        if config.copy_files:
            ...
    """

    # Define default values for all settings
    DEFAULTS = {
        'source_directory': [],
        'destination_directory': '',
        'database_path': constants.DEFAULT_DATABASE_NAME,
        'batch_size': constants.DEFAULT_BATCH_SIZE,
        'include_subdirectories': True,
        'file_endings': constants.DEFAULT_FILE_ENDINGS,
        'group_by_year': True,
        'group_by_day': True,
        'copy_files': True,
        'move_files': False,
        # Partial hashing optimization (for large files)
        'partial_hash_enabled': True,
        'partial_hash_bytes': constants.PARTIAL_HASH_BYTES,  # 16KB - good balance of speed vs accuracy
        'partial_hash_min_file_size': constants.PARTIAL_HASH_MIN_FILE_SIZE,  # 1MB - only use partial hash for files >= 1MB
        # Photo filtering (exclude icons, web graphics, thumbnails)
        'photo_filter_enabled': True,
        'min_file_size': constants.MIN_PHOTO_FILE_SIZE,  # 50KB - real photos are usually larger
        'min_width': constants.MIN_PHOTO_WIDTH,  # Minimum width in pixels
        'min_height': constants.MIN_PHOTO_HEIGHT,  # Minimum height in pixels
        'max_width': constants.MAX_PHOTO_WIDTH,  # Maximum width (exclude huge graphics)
        'max_height': constants.MAX_PHOTO_HEIGHT,  # Maximum height
        'exclude_square_smaller_than': constants.MIN_SQUARE_SIZE,  # Exclude squares < 400x400 (likely icons)
        'require_exif': False,  # If True, only accept images with EXIF data
        'excluded_filename_patterns': ['favicon', 'icon', 'logo', 'thumb', 'button', 'badge', 'sprite'],
        'move_filtered_files': False,  # If True, move filtered files to separate folder
        'filtered_files_folder': 'filtered_non_photos',  # Where to move filtered files
        # Metadata upgrade review (when duplicates have different metadata)
        'review_metadata_upgrades': True,  # If True, show review dialog before metadata upgrades
        # Cloud storage configuration (new format - see CLOUD_STORAGE_PLAN.md)
        # If 'storage' key is present, it takes precedence over destination_directory
        # 'storage': {
        #     'archive': {'type': 'local', 'path': '/path/to/archive'},
        #     'video_archive': {'type': 's3', 'bucket': 'my-bucket', ...},
        # }
        'cloud_defaults': {
            'upload_threads': 4,
            'chunk_size_mb': 8,
            'retry_attempts': 3,
            'retry_delay_seconds': 5
        },
    }

    # Required settings that must be provided (no defaults)
    REQUIRED = [
        'source_directory',
        'destination_directory',
    ]

    def __init__(self, config_file: str = 'settings.json', settings_dict: Dict[str, Any] = None):
        """
        Initialize configuration from JSON file or dictionary.

        Parameters:
            config_file (str): Path to the JSON configuration file (default: 'settings.json')
            settings_dict (dict): Optional dictionary of settings (bypasses file loading)

        Raises:
            FileNotFoundError: If config file doesn't exist and settings_dict not provided
            json.JSONDecodeError: If config file is invalid JSON
            ValueError: If required settings are missing
        """
        self.config_file = config_file
        self._settings: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

        # Load from dictionary if provided, otherwise from file
        if settings_dict is not None:
            # Start with defaults, then overlay provided settings
            self._settings = self.DEFAULTS.copy()

            # Log database_path before and after update
            self.logger.info(f"=" * 80)
            self.logger.info(f"CONFIG: Creating from settings_dict")
            self.logger.info(f"  DEFAULTS database_path: '{self.DEFAULTS['database_path']}'")
            self.logger.info(f"  settings_dict database_path: '{settings_dict.get('database_path', 'NOT SET')}'")

            self._settings.update(settings_dict)

            self.logger.info(f"  FINAL _settings database_path: '{self._settings['database_path']}'")
            self.logger.info(f"=" * 80)
            self.logger.info("Configuration loaded from dictionary")
        else:
            self.load()

        self.validate()

    def load(self) -> None:
        """
        Load configuration from JSON file.

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}\n"
                f"Please create {self.config_file} with required settings."
            )

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)

            # Start with defaults, then overlay loaded settings
            self._settings = self.DEFAULTS.copy()
            self._settings.update(loaded_settings)

            self.logger.info(f"Configuration loaded from {self.config_file}")
            self._log_settings()

        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in {self.config_file}: {e.msg}",
                e.doc,
                e.pos
            )

    def validate(self) -> None:
        """
        Validate that all required settings are present and valid.

        Raises:
            ValueError: If required settings are missing or invalid
        """
        # Check for required settings
        missing = [key for key in self.REQUIRED if not self._settings.get(key)]
        if missing:
            raise ValueError(
                f"Missing required settings: {', '.join(missing)}\n"
                f"Please add these to {self.config_file}"
            )

        # Validate specific settings
        self._validate_source_directory()
        self._validate_destination_directory()
        self._validate_paths()
        self._validate_file_endings()
        self._validate_batch_size()
        self._validate_copy_move_settings()

    def _validate_source_directory(self) -> None:
        """Ensure source_directory is a list."""
        source_dir = self._settings['source_directory']
        if isinstance(source_dir, str):
            # Convert single string to list
            self._settings['source_directory'] = [source_dir]
            self.logger.warning(
                f"Converted source_directory from string to list: {source_dir}"
            )
        elif not isinstance(source_dir, list):
            raise ValueError(
                f"source_directory must be a string or list, got {type(source_dir)}"
            )

    def _validate_file_endings(self) -> None:
        """Ensure file_endings is a list."""
        file_endings = self._settings['file_endings']
        if not isinstance(file_endings, list):
            raise ValueError(
                f"file_endings must be a list, got {type(file_endings)}"
            )

        # Ensure all endings start with a dot
        for i, ending in enumerate(file_endings):
            if not ending.startswith('.'):
                self._settings['file_endings'][i] = f'.{ending}'
                self.logger.warning(
                    f"Added missing dot to file ending: {ending} -> .{ending}"
                )

    def _validate_batch_size(self) -> None:
        """Ensure batch_size is a positive integer."""
        batch_size = self._settings['batch_size']
        if not isinstance(batch_size, int) or batch_size < 0:
            raise ValueError(
                f"batch_size must be a non-negative integer, got {batch_size}"
            )

    def _validate_destination_directory(self) -> None:
        """Ensure destination_directory is a string."""
        dest_dir = self._settings['destination_directory']
        if not isinstance(dest_dir, str):
            raise ValueError(
                f"destination_directory must be a string, got {type(dest_dir)}"
            )

    def _validate_paths(self) -> None:
        """
        Validate paths to prevent directory traversal attacks.

        Ensures paths don't contain potentially dangerous patterns like '..'
        which could be used to access files outside intended directories.
        """
        dangerous_patterns = constants.DANGEROUS_PATH_PATTERNS

        # Validate all source directories
        for source_dir in self._settings['source_directory']:
            # Normalize the path to resolve any '..' sequences
            normalized_path = os.path.normpath(source_dir)

            # Check if the path contains parent directory references
            if '..' in source_dir:
                raise ValueError(
                    f"Potentially dangerous path pattern '..' found in source directory: {source_dir}\n"
                    f"This could allow access to files outside the intended directory.\n"
                    f"Please use absolute paths without parent directory references."
                )

        # Validate destination directory
        dest_dir = self._settings['destination_directory']
        if '..' in dest_dir:
            raise ValueError(
                f"Potentially dangerous path pattern '..' found in destination directory: {dest_dir}\n"
                f"This could allow access to files outside the intended directory.\n"
                f"Please use absolute paths without parent directory references."
            )

        # Validate database path
        db_path = self._settings['database_path']
        if '..' in db_path:
            raise ValueError(
                f"Potentially dangerous path pattern '..' found in database path: {db_path}\n"
                f"This could allow access to files outside the intended directory.\n"
                f"Please use absolute or simple relative paths without parent directory references."
            )

    def _validate_copy_move_settings(self) -> None:
        """Ensure copy_files and move_files settings are valid."""
        copy_files = self._settings['copy_files']
        move_files = self._settings['move_files']

        # Check if both are True
        if copy_files and move_files:
            raise ValueError(
                "copy_files and move_files cannot both be True. "
                "Choose either copy or move operation."
            )

        # Check if both are False
        if not copy_files and not move_files:
            raise ValueError(
                "Either copy_files or move_files must be True. "
                "Please enable at least one operation mode."
            )

    def _log_settings(self) -> None:
        """Log all loaded settings (for debugging)."""
        self.logger.debug("Loaded configuration:")
        for key, value in self._settings.items():
            # Don't log sensitive data if we add any in the future
            self.logger.debug(f"  {key}: {value}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Parameters:
            key (str): Configuration key
            default (Any): Default value if key not found (overrides DEFAULTS)

        Returns:
            Any: Configuration value, or default if not found
        """
        if default is not None:
            return self._settings.get(key, default)
        return self._settings.get(key, self.DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value (in memory only, doesn't save to file).

        Parameters:
            key (str): Configuration key
            value (Any): Configuration value
        """
        self._settings[key] = value

    def save(self) -> None:
        """
        Save current configuration back to the JSON file.

        Note: This saves ALL settings, including defaults. Use sparingly.
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
            self.logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            self.logger.exception(f"Failed to save configuration: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """
        Get all settings as a dictionary.

        Returns:
            Dict[str, Any]: Copy of all settings
        """
        return self._settings.copy()

    # Convenience properties for common settings

    @property
    def source_directory(self) -> List[str]:
        """Get source directory list."""
        return self._settings['source_directory']

    @property
    def destination_directory(self) -> str:
        """Get destination directory path."""
        return self._settings['destination_directory']

    @property
    def database_path(self) -> str:
        """Get database file path."""
        db_path = self._settings['database_path']
        self.logger.info(f"CONFIG.database_path property accessed → returning: '{db_path}'")
        return db_path

    @property
    def batch_size(self) -> int:
        """Get batch size for database commits."""
        return self._settings['batch_size']

    @property
    def include_subdirectories(self) -> bool:
        """Check if subdirectories should be processed."""
        return self._settings['include_subdirectories']

    @property
    def file_endings(self) -> List[str]:
        """Get list of file extensions to process."""
        return self._settings['file_endings']

    @property
    def group_by_year(self) -> bool:
        """Check if files should be grouped by year."""
        return self._settings['group_by_year']

    @property
    def group_by_day(self) -> bool:
        """Check if files should be grouped by day."""
        return self._settings['group_by_day']

    @property
    def copy_files(self) -> bool:
        """Check if files should be copied (vs moved)."""
        return self._settings['copy_files']

    @property
    def move_files(self) -> bool:
        """Check if files should be moved (vs copied)."""
        return self._settings['move_files']

    @property
    def partial_hash_enabled(self) -> bool:
        """Check if partial hashing optimization is enabled."""
        return self._settings['partial_hash_enabled']

    @property
    def partial_hash_bytes(self) -> int:
        """Get number of bytes to use for partial hash."""
        return self._settings['partial_hash_bytes']

    @property
    def partial_hash_min_file_size(self) -> int:
        """Get minimum file size to use partial hashing (bytes)."""
        return self._settings['partial_hash_min_file_size']

    # Storage configuration methods for cloud integration

    def has_storage_config(self) -> bool:
        """
        Check if new-style storage configuration is present.

        Returns:
            True if 'storage' key exists with vault configurations
        """
        storage = self._settings.get('storage')
        return isinstance(storage, dict) and len(storage) > 0

    def get_storage_config(self) -> Dict[str, Dict[str, Any]]:
        """
        Get storage configuration for all vaults.

        Returns new-style storage config if present, otherwise creates
        backward-compatible config from legacy destination_directory setting.

        Returns:
            Dictionary mapping vault types to storage configurations
            Example:
            {
                'archive': {'type': 'local', 'path': '/archive'},
                'video_archive': {'type': 's3', 'bucket': 'videos', ...}
            }
        """
        # Check for new-style storage configuration
        if self.has_storage_config():
            return self._settings['storage']

        # Create backward-compatible config from legacy settings
        from storage_backend import create_storage_config_from_legacy

        # Get paths from database metadata if available, otherwise use defaults
        video_archive = self._settings.get('video_archive_location')
        prior_revision = self._settings.get('prior_revision_archive_location')
        delete_vault = self._settings.get('delete_vault_location')

        return create_storage_config_from_legacy(
            destination_directory=self.destination_directory,
            video_archive_location=video_archive,
            prior_revision_location=prior_revision,
            delete_vault_location=delete_vault
        )

    def create_storage_manager(self) -> 'StorageManager':
        """
        Create a StorageManager instance from this configuration.

        Returns:
            StorageManager with all configured vaults
        """
        from storage_backend import StorageManager

        storage_config = self.get_storage_config()
        return StorageManager(storage_config)

    def get_vault_storage_type(self, vault_type: str) -> str:
        """
        Get the storage type for a specific vault.

        Args:
            vault_type: One of 'archive', 'video_archive', 'prior_revision', 'delete_vault'

        Returns:
            Storage type string ('local', 's3', 'azure', etc.) or 'local' if not configured
        """
        storage_config = self.get_storage_config()
        vault_config = storage_config.get(vault_type, {})
        return vault_config.get('type', 'local')

    def is_vault_cloud_storage(self, vault_type: str) -> bool:
        """
        Check if a vault uses cloud storage.

        Args:
            vault_type: One of 'archive', 'video_archive', 'prior_revision', 'delete_vault'

        Returns:
            True if vault uses cloud storage (s3, azure, gcs, etc.)
        """
        storage_type = self.get_vault_storage_type(vault_type)
        return storage_type != 'local'

    def get_cloud_defaults(self) -> Dict[str, Any]:
        """
        Get default settings for cloud operations.

        Returns:
            Dictionary with upload_threads, chunk_size_mb, retry settings, etc.
        """
        return self._settings.get('cloud_defaults', self.DEFAULTS['cloud_defaults'])

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access: config['key']"""
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style setting: config['key'] = value"""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Allow 'key in config' checks."""
        return key in self._settings

    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config(file={self.config_file}, settings={len(self._settings)})"


if __name__ == '__main__':
    """Test the configuration system."""
    print("Testing config.py")

    # Test loading config
    try:
        config = Config('settings.json')
        print(f"✓ Loaded config: {config}")
        print(f"✓ Source directories: {config.source_directory}")
        print(f"✓ Destination: {config.destination_directory}")
        print(f"✓ Batch size: {config.batch_size}")
        print(f"✓ Database path: {config.database_path}")

        # Test property access
        print(f"✓ Copy files: {config.copy_files}")
        print(f"✓ Move files: {config.move_files}")

        # Test get() method
        custom_val = config.get('custom_key', 'default_value')
        print(f"✓ Custom key with default: {custom_val}")

        # Test dictionary-style access
        db_path = config['database_path']
        print(f"✓ Dict-style access: {db_path}")

        # Test contains
        has_batch = 'batch_size' in config
        print(f"✓ Contains check: {has_batch}")

        print("\nAll config tests passed!")

    except FileNotFoundError as e:
        print(f"✗ Config file not found: {e}")
    except ValueError as e:
        print(f"✗ Validation error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
