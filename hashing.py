"""
Hashing Module

Provides file hashing functionality for duplicate detection.
Includes full file hashing, partial hashing for large files,
and content-based image hashing.

Functions:
    hash_file: Calculate SHA-256 hash of entire file
    hash_file_partial: Calculate hash of first N bytes (for quick comparison)
    hash_image_content: Calculate hash of image pixel data (ignores metadata)
    verify_copy_integrity: Verify copied file matches expected hash
"""

import hashlib
import logging
import os
from typing import Optional, Tuple

from PIL import Image, ImageOps
import pillow_heif

import constants
import utils

# Configure logging
logger = utils.setup_logger(__name__, "hashing.log")


def hash_file(filename: str) -> str:
    """
    Calculate SHA-256 hash of the entire file.

    This is the primary method for generating unique file identifiers
    for duplicate detection. The hash is calculated over the raw file
    bytes, so any metadata changes will result in a different hash.

    Parameters:
        filename (str): Path to the file to hash

    Returns:
        str: SHA-256 hex digest of the file contents

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
        Exception: For other read errors
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(filename, "rb") as f:
            for byte_block in iter(lambda: f.read(constants.FILE_READ_CHUNK_SIZE), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    except Exception as e:
        logger.exception(f"hash_file failed for {filename}: {e}")
        raise


def hash_file_partial(
    filename: str,
    num_bytes: int = constants.PARTIAL_HASH_BYTES
) -> str:
    """
    Calculate SHA-256 hash of the first N bytes of a file.

    This is an optimization for large files - if the partial hashes
    of two files don't match, they can't be duplicates, so we can
    skip the full hash. If partial hashes match, a full hash is needed.

    Parameters:
        filename (str): Path to the file to hash
        num_bytes (int): Number of bytes to hash (default: 16KB)

    Returns:
        str: SHA-256 hex digest of the first num_bytes

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
        Exception: For other read errors
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(filename, "rb") as f:
            # Read only the first num_bytes
            data = f.read(num_bytes)
            sha256_hash.update(data)
        return sha256_hash.hexdigest()

    except Exception as e:
        logger.exception(f"hash_file_partial failed for {filename}: {e}")
        raise


def verify_copy_integrity(
    dest_path: str,
    expected_hash: str,
    retry_count: int = 1
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verify that a copied file matches the expected hash.

    This function is used after copying a file to ensure no corruption
    occurred during the copy operation. Supports retries for transient
    errors.

    Parameters:
        dest_path (str): Path to the destination file to verify
        expected_hash (str): Expected SHA-256 hash of the file
        retry_count (int): Number of times to retry on failure (default: 1)

    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            - verified: True if hash matches, False otherwise
            - actual_hash: The actual hash of the destination file (or None on error)
            - error_message: Error description if verification failed, None on success
    """
    for attempt in range(retry_count + 1):
        try:
            if not os.path.exists(dest_path):
                error_msg = f"Destination file does not exist: {dest_path}"
                logger.warning(error_msg)
                return (False, None, error_msg)

            actual_hash = hash_file(dest_path)

            if actual_hash == expected_hash:
                logger.debug(f"Copy verified: {dest_path}")
                return (True, actual_hash, None)
            else:
                error_msg = (
                    f"Hash mismatch after copy: expected {expected_hash[:16]}..., "
                    f"got {actual_hash[:16]}..."
                )
                if attempt < retry_count:
                    logger.warning(f"{error_msg} - Retrying (attempt {attempt + 1}/{retry_count})")
                    continue
                else:
                    logger.error(error_msg)
                    return (False, actual_hash, error_msg)

        except Exception as e:
            error_msg = f"Verification error: {str(e)}"
            if attempt < retry_count:
                logger.warning(f"{error_msg} - Retrying (attempt {attempt + 1}/{retry_count})")
                continue
            else:
                logger.exception(f"Copy verification failed for {dest_path}")
                return (False, None, error_msg)

    # Should not reach here, but safety fallback
    return (False, None, "Verification failed after all retries")


def hash_image_content(file_path: str) -> Optional[str]:
    """
    Calculate SHA-256 hash of the normalized pixel content of an image.

    This hash is based purely on the visual content (RGB pixel data), ignoring
    all metadata including EXIF. Two images that look identical will produce
    the same content hash even if their metadata differs.

    The image is normalized by:
    1. Applying EXIF rotation via ImageOps.exif_transpose()
    2. Converting to RGB mode (strips alpha channel, handles grayscale)
    3. Hashing the raw pixel bytes

    Parameters:
        file_path (str): Path to the image file

    Returns:
        str or None: SHA-256 hex digest of pixel content, or None for:
            - Video files (cannot be processed by PIL)
            - Files that fail to load
            - Any other processing errors
    """
    # Check if file is a video (cannot process with PIL)
    video_extensions = set(ext.lower() for ext in constants.VIDEO_EXTENSIONS)
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in video_extensions:
        logger.debug(f"Skipping content hash for video file: {file_path}")
        return None

    try:
        # Register HEIF opener if needed
        pillow_heif.register_heif_opener()

        # Open and load the image
        with Image.open(file_path) as img:
            # Apply EXIF rotation to normalize orientation
            img = ImageOps.exif_transpose(img)

            # Convert to RGB mode for consistent hashing
            # This handles:
            # - RGBA images (strips alpha)
            # - Grayscale/L mode images
            # - Palette images
            # - CMYK images
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get raw pixel data and hash it
            pixel_data = img.tobytes()
            content_hash = hashlib.sha256(pixel_data).hexdigest()

            logger.debug(f"Content hash for {file_path}: {content_hash[:16]}...")
            return content_hash

    except Exception as e:
        logger.warning(f"Failed to compute content hash for {file_path}: {e}")
        return None


def should_use_partial_hash(file_size: int) -> bool:
    """
    Determine if partial hashing should be used for a file.

    Partial hashing is an optimization for large files. Files smaller
    than the threshold are hashed fully in one pass.

    Parameters:
        file_size (int): Size of the file in bytes

    Returns:
        bool: True if partial hashing should be used
    """
    return file_size >= constants.PARTIAL_HASH_MIN_FILE_SIZE


def get_file_size_and_hash(
    file_path: str,
    use_partial: bool = True,
    partial_hash_bytes: int = constants.PARTIAL_HASH_BYTES
) -> Tuple[int, str, Optional[str], Optional[int]]:
    """
    Get file size and appropriate hash(es) for a file.

    This is a convenience function that handles the two-stage hashing
    logic for large files.

    Parameters:
        file_path (str): Path to the file
        use_partial (bool): Whether to use partial hashing for large files
        partial_hash_bytes (int): Number of bytes for partial hash

    Returns:
        Tuple[int, str, Optional[str], Optional[int]]:
            - file_size: Size in bytes
            - full_hash: Full file hash
            - partial_hash: Partial hash (or None if not applicable)
            - partial_bytes: Number of bytes used for partial (or None)
    """
    file_size = os.path.getsize(file_path)

    # Determine if we should use partial hashing
    if use_partial and should_use_partial_hash(file_size):
        partial_hash = hash_file_partial(file_path, partial_hash_bytes)
        full_hash = hash_file(file_path)
        return (file_size, full_hash, partial_hash, partial_hash_bytes)
    else:
        full_hash = hash_file(file_path)
        return (file_size, full_hash, None, None)
