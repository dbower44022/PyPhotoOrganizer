"""
Triage Application Configuration Management

Loads and validates configuration from JSON file.
Provides default values for all settings.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "database_path": "PhotoDB.db",
    "thumbnail_cache_dir": "/tmp/ppo_triage_cache",
    "memory_cache_size": 500,
    "disk_cache_size_gb": 5,
    "default_thumbnail_size": "medium",
    "prefetch_count": 50,
    "worker_threads": 8,
    "favorites_archive": None,
    "auto_copy_favorites": False
}


class TriageConfig:
    """Configuration loader for triage application."""

    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize configuration.

        Args:
            config_dict: Configuration dictionary with settings
        """
        self.config = config_dict

    def __getitem__(self, key: str) -> Any:
        """Dictionary-style access to config values."""
        return self.config.get(key)

    def get(self, key: str, default=None) -> Any:
        """Get config value with optional default."""
        return self.config.get(key, default)

    # Property accessors for common config values
    @property
    def database_path(self) -> str:
        """Get database path."""
        return self.config.get('database_path')

    @database_path.setter
    def database_path(self, value: str):
        """Set database path."""
        self.config['database_path'] = value

    @property
    def thumbnail_cache_dir(self) -> str:
        """Get thumbnail cache directory."""
        return self.config.get('thumbnail_cache_dir')

    @property
    def memory_cache_size(self) -> int:
        """Get memory cache size."""
        return self.config.get('memory_cache_size', 500)

    @property
    def disk_cache_size_gb(self) -> int:
        """Get disk cache size in GB."""
        return self.config.get('disk_cache_size_gb', 5)

    @property
    def default_thumbnail_size(self) -> str:
        """Get default thumbnail size."""
        return self.config.get('default_thumbnail_size', 'medium')

    @property
    def prefetch_count(self) -> int:
        """Get prefetch count."""
        return self.config.get('prefetch_count', 50)

    @property
    def worker_threads(self) -> int:
        """Get worker thread count."""
        return self.config.get('worker_threads', 8)

    @property
    def favorites_archive(self) -> str:
        """Get favorites archive location."""
        return self.config.get('favorites_archive')

    @property
    def auto_copy_favorites(self) -> bool:
        """Get auto-copy favorites flag."""
        return self.config.get('auto_copy_favorites', False)

    @classmethod
    def load(cls, config_path: str = None) -> 'TriageConfig':
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to config file. If None, looks for triage_config.json
                        in current directory or creates default config.

        Returns:
            TriageConfig instance
        """
        if config_path is None:
            # Look for triage_config.json in triage directory
            config_path = Path(__file__).parent / "triage_config.json"
        else:
            config_path = Path(config_path)

        # Load from file if exists
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    logger.info(f"Loaded config from {config_path}")

                    # Merge with defaults (user config overrides defaults)
                    config = DEFAULT_CONFIG.copy()
                    config.update(user_config)

                    return cls(config)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse config file {config_path}: {e}")
                logger.info("Using default configuration")
                return cls(DEFAULT_CONFIG.copy())

            except Exception as e:
                logger.error(f"Failed to load config file {config_path}: {e}")
                logger.info("Using default configuration")
                return cls(DEFAULT_CONFIG.copy())

        else:
            # Create default config file
            logger.info(f"Config file not found at {config_path}, creating default")
            try:
                cls.save_default_config(config_path)
            except Exception as e:
                logger.warning(f"Failed to create default config file: {e}")

            return cls(DEFAULT_CONFIG.copy())

    @classmethod
    def save_default_config(cls, config_path: Path):
        """
        Save default configuration to file.

        Args:
            config_path: Path where config file should be created
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)

        logger.info(f"Created default config at {config_path}")

    def save(self, config_path: str = None):
        """
        Save current configuration to file.

        Args:
            config_path: Path to save config. If None, uses default location.
        """
        if config_path is None:
            config_path = Path(__file__).parent / "triage_config.json"
        else:
            config_path = Path(config_path)

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

        logger.info(f"Saved config to {config_path}")

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate configuration values.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Validate database path
        if not self.config.get('database_path'):
            errors.append("database_path cannot be empty")

        # Validate cache directory
        cache_dir = self.config.get('thumbnail_cache_dir')
        if not cache_dir:
            errors.append("thumbnail_cache_dir cannot be empty")
        elif not os.path.isabs(cache_dir):
            errors.append("thumbnail_cache_dir must be an absolute path")

        # Validate numeric values
        memory_size = self.config.get('memory_cache_size', 0)
        if not isinstance(memory_size, int) or memory_size <= 0:
            errors.append("memory_cache_size must be a positive integer")

        disk_size = self.config.get('disk_cache_size_gb', 0)
        if not isinstance(disk_size, (int, float)) or disk_size <= 0:
            errors.append("disk_cache_size_gb must be a positive number")

        prefetch_count = self.config.get('prefetch_count', 0)
        if not isinstance(prefetch_count, int) or prefetch_count <= 0:
            errors.append("prefetch_count must be a positive integer")

        worker_threads = self.config.get('worker_threads', 0)
        if not isinstance(worker_threads, int) or worker_threads <= 0 or worker_threads > 32:
            errors.append("worker_threads must be between 1 and 32")

        # Validate thumbnail size
        thumbnail_size = self.config.get('default_thumbnail_size')
        if thumbnail_size not in ('small', 'medium', 'large'):
            errors.append("default_thumbnail_size must be 'small', 'medium', or 'large'")

        is_valid = len(errors) == 0
        return is_valid, errors


if __name__ == '__main__':
    # Test configuration loading
    import sys
    import logging

    logging.basicConfig(level=logging.INFO)

    # Create test config
    test_config_path = Path(__file__).parent / "test_config.json"

    # Load (will create default)
    config = TriageConfig.load(test_config_path)

    print("Loaded configuration:")
    for key, value in config.config.items():
        print(f"  {key}: {value}")

    # Validate
    is_valid, errors = config.validate()
    if is_valid:
        print("\n✓ Configuration is valid")
    else:
        print("\n✗ Configuration errors:")
        for error in errors:
            print(f"  - {error}")

    # Clean up test file
    if test_config_path.exists():
        test_config_path.unlink()
        print(f"\nCleaned up test config file")
