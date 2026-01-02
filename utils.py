"""
Shared utility functions for the PhotoOrganizer application.

This module contains common functions used across multiple modules to reduce
code duplication and maintain consistency.
"""

import logging
import os
import sys


def setup_logger(name, log_file, level=logging.DEBUG):
    """
    Configure and return a logger with both console and file handlers.

    Parameters:
        name (str): Name of the logger (typically __name__ from calling module)
        log_file (str): Path to the log file
        level (int): Logging level (default: logging.DEBUG)

    Returns:
        logging.Logger: Configured logger instance
    """
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

    # Create file handler
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
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
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logging.info(f"Created missing directories for path: {folder_path}")
            return True
        else:
            logging.debug(f"Directory already exists: {folder_path}")
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

    print("All tests passed!")
