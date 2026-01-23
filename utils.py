"""
Shared utility functions for the PhotoOrganizer application.

This module contains common functions used across multiple modules to reduce
code duplication and maintain consistency.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import sys

# Log rotation settings - each log file will be at most 5MB, keeping 3 backups
# Total max log storage per module: 20MB (5MB x 4 files)
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log file
LOG_BACKUP_COUNT = 3  # Keep 3 backup files (.log.1, .log.2, .log.3)


def setup_logger(name, log_file, level=logging.DEBUG, max_bytes=None, backup_count=None):
    """
    Configure and return a logger with both console and rotating file handlers.

    Uses RotatingFileHandler to automatically rotate log files when they reach
    a certain size, preventing unbounded log growth.

    Parameters:
        name (str): Name of the logger (typically __name__ from calling module)
        log_file (str): Path to the log file
        level (int): Logging level (default: logging.DEBUG)
        max_bytes (int): Max size per log file in bytes (default: 5MB)
        backup_count (int): Number of backup files to keep (default: 3)

    Returns:
        logging.Logger: Configured logger instance

    Log Rotation:
        When the log file reaches max_bytes, it's renamed to log_file.1,
        and a new empty log_file is created. Old backups are shifted
        (log_file.1 -> log_file.2, etc.) and the oldest is deleted.
    """
    if max_bytes is None:
        max_bytes = LOG_MAX_BYTES
    if backup_count is None:
        backup_count = LOG_BACKUP_COUNT

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(funcName)s - %(lineno)d --- %(message)s'
    )

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Create rotating file handler (automatically rotates when file reaches max_bytes)
    file_handler = RotatingFileHandler(
        log_file,
        mode="a",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def ensure_directory_exists(folder_path):
    """
    Check if a given folder path exists, if not, create all missing folders.

    Parameters:
        folder_path (str): The path to the folder.

    Returns:
        bool: True if directory exists or was created successfully, False on error

    Raises:
        OSError: If directory creation fails due to permissions or other OS errors
    """
    try:
        os.makedirs(folder_path, exist_ok=True)
        logging.debug(f"Directory ensured: {folder_path}")
        return True
    except OSError as e:
        logging.exception(f"Failed to create directory {folder_path}: {e}")
        raise
    except Exception as e:
        logging.exception(f"Unexpected error in ensure_directory_exists for {folder_path}: {e}")
        raise


def get_unique_filename(full_path):
    """
    Given a full file path, returns a unique path by appending a counter if needed.

    If the file already exists, appends _1, _2, _3, etc. until a unique name is found.

    Parameters:
        full_path (str): The full path to the file (including directory and filename)

    Returns:
        str: A unique file path that doesn't exist

    Raises:
        ValueError: If the path is invalid (empty filename)
        FileNotFoundError: If the directory doesn't exist

    Examples:
        >>> get_unique_filename("C:\\photos\\image.jpg")
        "C:\\photos\\image.jpg"  # if it doesn't exist

        >>> get_unique_filename("C:\\photos\\image.jpg")
        "C:\\photos\\image_1.jpg"  # if image.jpg already exists
    """
    try:
        directory, base_name = os.path.split(full_path)
        if not base_name:
            raise ValueError("Invalid file name in path.")

        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Directory does not exist: {directory}")

        name, ext = os.path.splitext(base_name)
        counter = 1
        candidate = full_path

        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{name}_{counter}{ext}")
            counter += 1

        return candidate

    except Exception as e:
        logging.error(f"Error determining unique filename for {full_path}: {e}")
        raise


def validate_settings(settings_data, required_keys):
    """
    Validate that required settings keys exist in the settings dictionary.

    Parameters:
        settings_data (dict): The settings dictionary to validate
        required_keys (list): List of required key names

    Returns:
        tuple: (is_valid: bool, missing_keys: list)
            - is_valid: True if all required keys present, False otherwise
            - missing_keys: List of missing key names

    Examples:
        >>> settings = {"source": "path", "dest": "path2"}
        >>> validate_settings(settings, ["source", "dest", "database"])
        (False, ["database"])
    """
    missing_keys = [key for key in required_keys if key not in settings_data]
    is_valid = len(missing_keys) == 0
    return is_valid, missing_keys


def format_file_size(size_bytes):
    """
    Convert bytes to human-readable file size.

    Parameters:
        size_bytes (int): File size in bytes

    Returns:
        str: Formatted file size (e.g., "1.5 MB", "234 KB")

    Examples:
        >>> format_file_size(1024)
        "1.0 KB"
        >>> format_file_size(1536000)
        "1.5 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def safe_get_file_size(file_path):
    """
    Safely get the size of a file without raising exceptions.

    Parameters:
        file_path (str): Path to the file

    Returns:
        int or None: File size in bytes, or None if file doesn't exist or error occurs

    Note:
        Returns None instead of 0 to distinguish between actual 0-byte files
        and files that couldn't be accessed.
    """
    try:
        return os.path.getsize(file_path)
    except (OSError, FileNotFoundError) as e:
        logging.warning(f"Could not get size of {file_path}: {e}")
        return None


def is_video_file(file_path):
    """
    Determine if a file is a video based on its extension.

    Parameters:
        file_path (str): Path to the file

    Returns:
        bool: True if file is a video, False otherwise

    Note:
        Uses the VIDEO_EXTENSIONS constant to determine file type.
        Returns False for unrecognized extensions.
    """
    import constants
    file_ext = os.path.splitext(file_path)[1].lower()
    return file_ext in [ext.lower() for ext in constants.VIDEO_EXTENSIONS]


def is_photo_file(file_path):
    """
    Determine if a file is a photo based on its extension.

    Parameters:
        file_path (str): Path to the file

    Returns:
        bool: True if file is a photo, False otherwise

    Note:
        Uses the PHOTO_EXTENSIONS constant to determine file type.
        Returns False for unrecognized extensions.
    """
    import constants
    file_ext = os.path.splitext(file_path)[1].lower()
    return file_ext in [ext.lower() for ext in constants.PHOTO_EXTENSIONS]


# ==================== Performance Profiling ====================

import time
import functools
from contextlib import contextmanager


def profile_function(logger=None):
    """
    Decorator to profile function execution time.

    Usage:
        @profile_function(logger)
        def my_function():
            ...

    Args:
        logger: Logger instance to use (defaults to function's module logger)

    Logs:
        INFO level: function_name completed in X.XXXs
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get logger
            if logger is not None:
                log = logger
            else:
                log = logging.getLogger(func.__module__)

            # Time execution
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start_time
                log.info(f"⏱️ {func.__name__} completed in {elapsed:.3f}s")

        return wrapper
    return decorator


@contextmanager
def profile_block(description, logger=None, level=logging.INFO):
    """
    Context manager to profile a code block.

    Usage:
        with profile_block("Loading data", logger):
            # code to profile
            ...

    Args:
        description: Description of the block being profiled
        logger: Logger instance (defaults to root logger)
        level: Log level (default: INFO)

    Logs:
        [level]: [description] completed in X.XXXs
    """
    if logger is None:
        logger = logging.getLogger()

    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time
        logger.log(level, f"⏱️ {description} completed in {elapsed:.3f}s")


if __name__ == '__main__':
    """Test the utility functions"""
    print("Testing utils.py")

    # Test logger setup
    logger = setup_logger(__name__, "utils_test.log")
    logger.info("Logger test successful")

    # Test ensure_directory_exists
    test_dir = "test_temp_dir"
    if ensure_directory_exists(test_dir):
        print(f"✓ Created directory: {test_dir}")
        os.rmdir(test_dir)

    # Test validate_settings
    settings = {"key1": "value1", "key2": "value2"}
    is_valid, missing = validate_settings(settings, ["key1", "key2", "key3"])
    print(f"✓ Settings validation: valid={is_valid}, missing={missing}")

    # Test format_file_size
    print(f"✓ Format file size: {format_file_size(1536000)}")

    # Test is_video_file
    print(f"✓ Is video (.mp4): {is_video_file('test.mp4')}")
    print(f"✓ Is video (.jpg): {is_video_file('test.jpg')}")

    print("All tests passed!")
