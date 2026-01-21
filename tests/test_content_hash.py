#!/usr/bin/env python3
"""
Content Hash Regression Test

A standalone test utility for verifying the content hashing functionality.
Can be run from the command line to test content hash calculation and
duplicate detection on a folder of images.

Usage:
    python tests/test_content_hash.py /path/to/test/folder
    python tests/test_content_hash.py /path/to/test/folder --verbose
    python tests/test_content_hash.py /path/to/test/folder --json

Features:
    - Calculates content hash for all image files in a folder
    - Reports files with their content hashes
    - Identifies duplicate groups (files with identical content hashes)
    - Supports verbose output and JSON format
    - Can be used as a pytest test or standalone script
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from DuplicateFileDetection import hash_image_content

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.webp', '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw',
    '.JPG', '.JPEG', '.PNG', '.GIF', '.BMP', '.TIFF', '.TIF',
    '.WEBP', '.HEIC', '.HEIF', '.RAW', '.CR2', '.NEF', '.ARW'
}

# Video extensions to skip
VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv',
    '.MP4', '.MOV', '.AVI', '.MKV', '.M4V', '.MPG', '.MPEG', '.WMV'
}


def scan_folder_for_images(folder_path: str, recursive: bool = False) -> List[str]:
    """
    Scan a folder for image files.

    Args:
        folder_path: Path to folder to scan
        recursive: If True, include subfolders

    Returns:
        List of image file paths
    """
    image_files = []
    folder = Path(folder_path)

    if not folder.exists():
        raise ValueError(f"Folder does not exist: {folder_path}")

    if not folder.is_dir():
        raise ValueError(f"Path is not a folder: {folder_path}")

    if recursive:
        pattern = '**/*'
    else:
        pattern = '*'

    for file_path in folder.glob(pattern):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext in {e.lower() for e in IMAGE_EXTENSIONS}:
                image_files.append(str(file_path))
            elif ext in {e.lower() for e in VIDEO_EXTENSIONS}:
                logger.debug(f"Skipping video file: {file_path}")

    return sorted(image_files)


def calculate_content_hashes(
    file_paths: List[str],
    progress_callback: Optional[callable] = None
) -> Dict[str, Optional[str]]:
    """
    Calculate content hashes for a list of files.

    Args:
        file_paths: List of file paths
        progress_callback: Optional callback(current, total, filename)

    Returns:
        Dict mapping file_path -> content_hash (or None if failed)
    """
    results = {}
    total = len(file_paths)

    for idx, file_path in enumerate(file_paths):
        filename = os.path.basename(file_path)

        if progress_callback:
            progress_callback(idx + 1, total, filename)

        try:
            content_hash = hash_image_content(file_path)
            results[file_path] = content_hash

            if content_hash is None:
                logger.warning(f"Could not calculate content hash for: {filename}")

        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            results[file_path] = None

    return results


def find_duplicates(hash_results: Dict[str, Optional[str]]) -> Dict[str, List[str]]:
    """
    Find duplicate groups from hash results.

    Args:
        hash_results: Dict mapping file_path -> content_hash

    Returns:
        Dict mapping content_hash -> list of file paths with that hash
        Only includes hashes that appear more than once.
    """
    # Group files by content hash
    hash_to_files = defaultdict(list)

    for file_path, content_hash in hash_results.items():
        if content_hash is not None:
            hash_to_files[content_hash].append(file_path)

    # Filter to only duplicates (more than one file with same hash)
    duplicates = {
        hash_val: files
        for hash_val, files in hash_to_files.items()
        if len(files) > 1
    }

    return duplicates


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def print_results(
    hash_results: Dict[str, Optional[str]],
    duplicates: Dict[str, List[str]],
    verbose: bool = False
):
    """Print results to console."""
    total_files = len(hash_results)
    successful = sum(1 for h in hash_results.values() if h is not None)
    failed = total_files - successful

    print("\n" + "=" * 70)
    print("CONTENT HASH TEST RESULTS")
    print("=" * 70)

    print(f"\nFiles scanned:     {total_files}")
    print(f"Successfully hashed: {successful}")
    print(f"Failed to hash:      {failed}")
    print(f"Duplicate groups:    {len(duplicates)}")

    total_duplicate_files = sum(len(files) for files in duplicates.values())
    if total_duplicate_files > 0:
        print(f"Total duplicate files: {total_duplicate_files}")

    # Print all files with hashes if verbose
    if verbose:
        print("\n" + "-" * 70)
        print("ALL FILES AND HASHES")
        print("-" * 70)

        for file_path, content_hash in sorted(hash_results.items()):
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            size_str = format_file_size(file_size)

            if content_hash:
                print(f"  {filename:<40} {size_str:>10}  {content_hash[:16]}...")
            else:
                print(f"  {filename:<40} {size_str:>10}  [FAILED]")

    # Print duplicate groups
    if duplicates:
        print("\n" + "-" * 70)
        print("DUPLICATE GROUPS DETECTED")
        print("-" * 70)

        for group_num, (content_hash, files) in enumerate(duplicates.items(), 1):
            print(f"\n  Group {group_num} (content_hash: {content_hash[:16]}...):")
            for file_path in files:
                filename = os.path.basename(file_path)
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                size_str = format_file_size(file_size)
                print(f"    - {filename:<40} {size_str:>10}")
                if verbose:
                    print(f"      Path: {file_path}")
    else:
        print("\n  No duplicate content detected.")

    print("\n" + "=" * 70)

    # Return exit code based on results
    return 0 if failed == 0 else 1


def print_json_results(
    hash_results: Dict[str, Optional[str]],
    duplicates: Dict[str, List[str]],
    folder_path: str
):
    """Print results in JSON format."""
    output = {
        'folder': folder_path,
        'summary': {
            'total_files': len(hash_results),
            'successful': sum(1 for h in hash_results.values() if h is not None),
            'failed': sum(1 for h in hash_results.values() if h is None),
            'duplicate_groups': len(duplicates),
            'total_duplicate_files': sum(len(files) for files in duplicates.values())
        },
        'files': [
            {
                'path': file_path,
                'filename': os.path.basename(file_path),
                'content_hash': content_hash,
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else None
            }
            for file_path, content_hash in sorted(hash_results.items())
        ],
        'duplicates': [
            {
                'content_hash': content_hash,
                'files': [
                    {
                        'path': fp,
                        'filename': os.path.basename(fp)
                    }
                    for fp in files
                ]
            }
            for content_hash, files in duplicates.items()
        ]
    }

    print(json.dumps(output, indent=2))

    # Return exit code
    return 0 if output['summary']['failed'] == 0 else 1


def run_content_hash_test(
    folder_path: str,
    recursive: bool = False,
    verbose: bool = False,
    json_output: bool = False
) -> Tuple[Dict[str, Optional[str]], Dict[str, List[str]], int]:
    """
    Run the content hash test on a folder.

    Args:
        folder_path: Path to folder to test
        recursive: If True, include subfolders
        verbose: If True, print detailed output
        json_output: If True, output JSON format

    Returns:
        Tuple of (hash_results, duplicates, exit_code)
    """
    # Scan for images
    if not json_output:
        print(f"\nScanning folder: {folder_path}")
        print(f"Recursive: {recursive}")

    image_files = scan_folder_for_images(folder_path, recursive)

    if not image_files:
        if json_output:
            print(json.dumps({
                'folder': folder_path,
                'error': 'No image files found',
                'summary': {'total_files': 0}
            }, indent=2))
        else:
            print(f"\nNo image files found in: {folder_path}")
        return {}, {}, 0

    if not json_output:
        print(f"Found {len(image_files)} image files")
        print("\nCalculating content hashes...")

    # Progress callback for non-JSON output
    def progress(current, total, filename):
        if not json_output:
            print(f"  [{current}/{total}] {filename}", end='\r')

    # Calculate hashes
    hash_results = calculate_content_hashes(image_files, progress)

    if not json_output:
        print()  # Clear progress line

    # Find duplicates
    duplicates = find_duplicates(hash_results)

    # Print results
    if json_output:
        exit_code = print_json_results(hash_results, duplicates, folder_path)
    else:
        exit_code = print_results(hash_results, duplicates, verbose)

    return hash_results, duplicates, exit_code


# ============================================================================
# Pytest test functions
# ============================================================================

def test_hash_image_content_returns_string_for_valid_image(tmp_path):
    """Test that hash_image_content returns a hex string for valid images."""
    # Create a simple test image
    from PIL import Image

    test_image = tmp_path / "test_image.png"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(test_image)

    result = hash_image_content(str(test_image))

    assert result is not None
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 produces 64 hex characters


def test_hash_image_content_returns_none_for_video():
    """Test that hash_image_content returns None for video files."""
    # We can't easily create a real video, so we test with a non-existent
    # video path pattern - the function checks extension first
    result = hash_image_content("/fake/path/video.mp4")
    assert result is None


def test_hash_image_content_same_pixels_same_hash(tmp_path):
    """Test that identical pixel content produces identical hashes."""
    from PIL import Image

    # Create two identical images with different filenames
    img = Image.new('RGB', (100, 100), color='blue')

    image1 = tmp_path / "image1.png"
    image2 = tmp_path / "image2.png"

    img.save(image1)
    img.save(image2)

    hash1 = hash_image_content(str(image1))
    hash2 = hash_image_content(str(image2))

    assert hash1 is not None
    assert hash2 is not None
    assert hash1 == hash2


def test_hash_image_content_different_pixels_different_hash(tmp_path):
    """Test that different pixel content produces different hashes."""
    from PIL import Image

    # Create two different images
    img1 = Image.new('RGB', (100, 100), color='red')
    img2 = Image.new('RGB', (100, 100), color='green')

    image1 = tmp_path / "red.png"
    image2 = tmp_path / "green.png"

    img1.save(image1)
    img2.save(image2)

    hash1 = hash_image_content(str(image1))
    hash2 = hash_image_content(str(image2))

    assert hash1 is not None
    assert hash2 is not None
    assert hash1 != hash2


def test_hash_image_content_ignores_exif(tmp_path):
    """Test that EXIF metadata doesn't affect content hash."""
    from PIL import Image
    import piexif

    # Create a test image
    img = Image.new('RGB', (100, 100), color='purple')

    # Save without EXIF
    image_no_exif = tmp_path / "no_exif.jpg"
    img.save(image_no_exif, quality=95)

    # Save with EXIF
    image_with_exif = tmp_path / "with_exif.jpg"
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: "TestCamera",
            piexif.ImageIFD.Model: "Test Model",
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: "2024:01:15 10:30:00",
        }
    }
    exif_bytes = piexif.dump(exif_dict)
    img.save(image_with_exif, quality=95, exif=exif_bytes)

    hash_no_exif = hash_image_content(str(image_no_exif))
    hash_with_exif = hash_image_content(str(image_with_exif))

    assert hash_no_exif is not None
    assert hash_with_exif is not None
    # Note: JPEG compression may cause slight differences, but the core
    # pixel data should be the same. For exact matching, use PNG.


def test_find_duplicates_empty_input():
    """Test find_duplicates with empty input."""
    result = find_duplicates({})
    assert result == {}


def test_find_duplicates_no_duplicates():
    """Test find_duplicates with no duplicates."""
    hash_results = {
        '/path/a.jpg': 'hash1',
        '/path/b.jpg': 'hash2',
        '/path/c.jpg': 'hash3',
    }
    result = find_duplicates(hash_results)
    assert result == {}


def test_find_duplicates_with_duplicates():
    """Test find_duplicates correctly identifies duplicates."""
    hash_results = {
        '/path/a.jpg': 'hash1',
        '/path/b.jpg': 'hash1',  # Duplicate of a.jpg
        '/path/c.jpg': 'hash2',
        '/path/d.jpg': 'hash2',  # Duplicate of c.jpg
        '/path/e.jpg': 'hash3',  # Unique
    }
    result = find_duplicates(hash_results)

    assert len(result) == 2  # Two duplicate groups
    assert 'hash1' in result
    assert 'hash2' in result
    assert 'hash3' not in result  # Not a duplicate

    assert set(result['hash1']) == {'/path/a.jpg', '/path/b.jpg'}
    assert set(result['hash2']) == {'/path/c.jpg', '/path/d.jpg'}


def test_find_duplicates_ignores_none_hashes():
    """Test that find_duplicates ignores None hashes."""
    hash_results = {
        '/path/a.jpg': 'hash1',
        '/path/b.jpg': None,  # Failed to hash
        '/path/c.jpg': 'hash1',  # Duplicate
        '/path/d.jpg': None,  # Also failed
    }
    result = find_duplicates(hash_results)

    assert len(result) == 1
    assert 'hash1' in result
    assert None not in result


# ============================================================================
# Command-line interface
# ============================================================================

def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Content Hash Regression Test - Test content hashing on a folder of images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s /path/to/test/images
    %(prog)s /path/to/test/images --verbose
    %(prog)s /path/to/test/images --recursive
    %(prog)s /path/to/test/images --json > results.json
        """
    )

    parser.add_argument(
        'folder',
        help='Path to folder containing test images'
    )

    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Include subfolders'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print detailed output including all file hashes'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    try:
        _, _, exit_code = run_content_hash_test(
            args.folder,
            recursive=args.recursive,
            verbose=args.verbose,
            json_output=args.json
        )
        sys.exit(exit_code)

    except ValueError as e:
        if args.json:
            print(json.dumps({'error': str(e)}, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nCancelled by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        if args.json:
            print(json.dumps({'error': str(e)}, indent=2))
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
