"""
Image Modification and Version Control Module

Provides:
1. ImageModifier: PIL-based image manipulation operations
2. VersionManager: File version tracking and storage

All operations preserve EXIF metadata where possible and enforce
the critical architectural principle: SOURCE FILES ARE NEVER MODIFIED.
All operations work exclusively on archive files.
"""

import os
import shutil
import sqlite3
import logging
import hashlib
import json
from datetime import datetime
from typing import Tuple, List, Dict, Optional
from PIL import Image, ImageEnhance, ExifTags
import piexif

logger = logging.getLogger(__name__)


class ImageModifier:
    """
    PIL-based image modification operations.

    All methods:
    - Preserve EXIF metadata where possible
    - Return tuple: (success, output_path_or_error, error_message)
    - Work on temporary files, caller responsible for final file management
    """

    @staticmethod
    def rotate_image(input_path: str, angle: int, expand: bool = True) -> Tuple[bool, str, str]:
        """
        Rotate image by specified angle.

        Args:
            input_path: Path to input image
            angle: Rotation angle in degrees (90, 180, 270, or custom)
            expand: If True, expand output to fit entire rotated image

        Returns:
            tuple: (success, output_path, error_message)
                  output_path is a temporary file if successful
        """
        try:
            logger.info(f"Rotating image: {input_path}")
            logger.info(f"  Angle: {angle}°, Expand: {expand}")

            # Open image
            img = Image.open(input_path)
            original_format = img.format
            logger.info(f"  Original size: {img.size}, Format: {original_format}")

            # Extract and preserve EXIF data
            exif_dict = None
            try:
                exif_data = img.info.get('exif')
                if exif_data:
                    exif_dict = piexif.load(exif_data)
                    logger.info("  ✓ EXIF data extracted for preservation")
            except Exception as e:
                logger.warning(f"  Could not extract EXIF data: {e}")

            # Rotate image
            # Note: PIL rotates counter-clockwise, so we negate the angle
            rotated = img.rotate(-angle, expand=expand, resample=Image.BICUBIC)
            logger.info(f"  Rotated size: {rotated.size}")

            # Update EXIF orientation tag if present
            if exif_dict and 'Exif' in exif_dict:
                # Reset orientation to normal (1) since we've physically rotated the image
                exif_dict['0th'][piexif.ImageIFD.Orientation] = 1
                logger.info("  ✓ Updated EXIF orientation tag")

            # Create temporary output file
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_rotated{ext}"

            # Save with EXIF data
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                rotated.save(output_path, format=original_format or 'JPEG',
                           exif=exif_bytes, quality=95)
            else:
                rotated.save(output_path, format=original_format or 'JPEG', quality=95)

            logger.info(f"  ✓ Image rotated successfully")
            logger.info(f"  Output: {output_path}")

            return True, output_path, ""

        except Exception as e:
            error_msg = f"Failed to rotate image: {str(e)}"
            logger.error(f"  ✗ {error_msg}", exc_info=True)
            return False, "", error_msg

    @staticmethod
    def crop_image(input_path: str, box: Tuple[int, int, int, int]) -> Tuple[bool, str, str]:
        """
        Crop image to specified bounding box.

        Args:
            input_path: Path to input image
            box: Crop box as (left, upper, right, lower) in pixels

        Returns:
            tuple: (success, output_path, error_message)
        """
        try:
            logger.info(f"Cropping image: {input_path}")
            logger.info(f"  Crop box: {box}")

            # Open image
            img = Image.open(input_path)
            original_format = img.format
            logger.info(f"  Original size: {img.size}, Format: {original_format}")

            # Validate crop box
            left, upper, right, lower = box
            width, height = img.size

            if left < 0 or upper < 0 or right > width or lower > height:
                raise ValueError(f"Crop box {box} exceeds image bounds {img.size}")
            if right <= left or lower <= upper:
                raise ValueError(f"Invalid crop box {box} - negative area")

            # Extract EXIF data
            exif_dict = None
            try:
                exif_data = img.info.get('exif')
                if exif_data:
                    exif_dict = piexif.load(exif_data)
                    logger.info("  ✓ EXIF data extracted for preservation")
            except Exception as e:
                logger.warning(f"  Could not extract EXIF data: {e}")

            # Crop image
            cropped = img.crop(box)
            logger.info(f"  Cropped size: {cropped.size}")

            # Create temporary output file
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_cropped{ext}"

            # Save with EXIF data
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                cropped.save(output_path, format=original_format or 'JPEG',
                           exif=exif_bytes, quality=95)
            else:
                cropped.save(output_path, format=original_format or 'JPEG', quality=95)

            logger.info(f"  ✓ Image cropped successfully")
            logger.info(f"  Output: {output_path}")

            return True, output_path, ""

        except Exception as e:
            error_msg = f"Failed to crop image: {str(e)}"
            logger.error(f"  ✗ {error_msg}", exc_info=True)
            return False, "", error_msg

    @staticmethod
    def resize_image(input_path: str, width: int, height: int,
                    maintain_aspect: bool = True) -> Tuple[bool, str, str]:
        """
        Resize image to specified dimensions.

        Args:
            input_path: Path to input image
            width: Target width in pixels
            height: Target height in pixels
            maintain_aspect: If True, maintain aspect ratio (use width/height as max dimensions)

        Returns:
            tuple: (success, output_path, error_message)
        """
        try:
            logger.info(f"Resizing image: {input_path}")
            logger.info(f"  Target size: {width}x{height}, Maintain aspect: {maintain_aspect}")

            # Open image
            img = Image.open(input_path)
            original_format = img.format
            logger.info(f"  Original size: {img.size}, Format: {original_format}")

            # Extract EXIF data
            exif_dict = None
            try:
                exif_data = img.info.get('exif')
                if exif_data:
                    exif_dict = piexif.load(exif_data)
                    logger.info("  ✓ EXIF data extracted for preservation")
            except Exception as e:
                logger.warning(f"  Could not extract EXIF data: {e}")

            # Calculate target size
            if maintain_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                resized = img
                logger.info(f"  Resized with aspect ratio: {resized.size}")
            else:
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                logger.info(f"  Resized to exact size: {resized.size}")

            # Create temporary output file
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_resized{ext}"

            # Save with EXIF data
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                resized.save(output_path, format=original_format or 'JPEG',
                           exif=exif_bytes, quality=95)
            else:
                resized.save(output_path, format=original_format or 'JPEG', quality=95)

            logger.info(f"  ✓ Image resized successfully")
            logger.info(f"  Output: {output_path}")

            return True, output_path, ""

        except Exception as e:
            error_msg = f"Failed to resize image: {str(e)}"
            logger.error(f"  ✗ {error_msg}", exc_info=True)
            return False, "", error_msg

    @staticmethod
    def adjust_color(input_path: str, brightness: float = 0,
                    contrast: float = 0, saturation: float = 0) -> Tuple[bool, str, str]:
        """
        Adjust image color properties.

        Args:
            input_path: Path to input image
            brightness: Brightness adjustment (-100 to +100, 0 = no change)
            contrast: Contrast adjustment (-100 to +100, 0 = no change)
            saturation: Saturation adjustment (-100 to +100, 0 = no change)

        Returns:
            tuple: (success, output_path, error_message)
        """
        try:
            logger.info(f"Adjusting colors: {input_path}")
            logger.info(f"  Brightness: {brightness:+.1f}, Contrast: {contrast:+.1f}, Saturation: {saturation:+.1f}")

            # Open image
            img = Image.open(input_path)
            original_format = img.format
            logger.info(f"  Original size: {img.size}, Format: {original_format}")

            # Extract EXIF data
            exif_dict = None
            try:
                exif_data = img.info.get('exif')
                if exif_data:
                    exif_dict = piexif.load(exif_data)
                    logger.info("  ✓ EXIF data extracted for preservation")
            except Exception as e:
                logger.warning(f"  Could not extract EXIF data: {e}")

            # Apply adjustments
            adjusted = img

            # Brightness: -100 to +100 → factor 0.0 to 2.0
            if brightness != 0:
                factor = 1.0 + (brightness / 100.0)
                enhancer = ImageEnhance.Brightness(adjusted)
                adjusted = enhancer.enhance(factor)
                logger.info(f"  Applied brightness factor: {factor:.2f}")

            # Contrast: -100 to +100 → factor 0.0 to 2.0
            if contrast != 0:
                factor = 1.0 + (contrast / 100.0)
                enhancer = ImageEnhance.Contrast(adjusted)
                adjusted = enhancer.enhance(factor)
                logger.info(f"  Applied contrast factor: {factor:.2f}")

            # Saturation: -100 to +100 → factor 0.0 to 2.0
            if saturation != 0:
                factor = 1.0 + (saturation / 100.0)
                enhancer = ImageEnhance.Color(adjusted)
                adjusted = enhancer.enhance(factor)
                logger.info(f"  Applied saturation factor: {factor:.2f}")

            # Create temporary output file
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_adjusted{ext}"

            # Save with EXIF data
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                adjusted.save(output_path, format=original_format or 'JPEG',
                            exif=exif_bytes, quality=95)
            else:
                adjusted.save(output_path, format=original_format or 'JPEG', quality=95)

            logger.info(f"  ✓ Color adjustments applied successfully")
            logger.info(f"  Output: {output_path}")

            return True, output_path, ""

        except Exception as e:
            error_msg = f"Failed to adjust colors: {str(e)}"
            logger.error(f"  ✗ {error_msg}", exc_info=True)
            return False, "", error_msg

    @staticmethod
    def auto_enhance(input_path: str) -> Tuple[bool, dict, str]:
        """
        Analyze image histogram and return optimal adjustment values.

        Uses statistical analysis of brightness, contrast, and saturation
        to calculate adjustment values that would improve the image.

        Args:
            input_path: Path to input image

        Returns:
            tuple: (success, adjustments_dict, error_message)
                   adjustments_dict contains: brightness, contrast, saturation (-100 to +100)
        """
        try:
            logger.info(f"Auto-enhance analysis: {input_path}")

            # Open image
            img = Image.open(input_path)

            # Convert to RGB if necessary for analysis
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Calculate image statistics
            from PIL import ImageStat
            stat = ImageStat.Stat(img)

            # Brightness analysis: Target mean ~128 (middle gray)
            # stat.mean gives mean for each channel (R, G, B)
            mean_brightness = sum(stat.mean[:3]) / 3 if img.mode == 'RGB' else stat.mean[0]
            logger.info(f"  Mean brightness: {mean_brightness:.1f}")

            # Calculate brightness adjustment
            # Target is 128 (middle gray), scale factor 1.28 for -100 to +100 range
            brightness_adjust = int((128 - mean_brightness) / 1.28)
            # Clamp to reasonable range
            brightness_adjust = max(-50, min(50, brightness_adjust))
            logger.info(f"  Brightness adjustment: {brightness_adjust:+d}")

            # Contrast analysis: Target stddev ~64 (good tonal range)
            # stat.stddev gives standard deviation for each channel
            mean_stddev = sum(stat.stddev[:3]) / 3 if img.mode == 'RGB' else stat.stddev[0]
            logger.info(f"  Mean stddev: {mean_stddev:.1f}")

            # Calculate contrast adjustment
            if mean_stddev < 40:  # Low contrast - needs boost
                contrast_adjust = int((64 - mean_stddev) * 1.5)
            elif mean_stddev > 80:  # High contrast - might need reduction
                contrast_adjust = int((64 - mean_stddev) * 0.5)
            else:
                contrast_adjust = 0
            # Clamp to reasonable range
            contrast_adjust = max(-40, min(60, contrast_adjust))
            logger.info(f"  Contrast adjustment: {contrast_adjust:+d}")

            # Saturation analysis: Analyze using HSV colorspace
            saturation_adjust = 0
            if img.mode == 'RGB':
                hsv_img = img.convert('HSV')
                hsv_stat = ImageStat.Stat(hsv_img)
                # Saturation is the second channel in HSV
                hsv_saturation = hsv_stat.mean[1]
                logger.info(f"  HSV saturation mean: {hsv_saturation:.1f}")

                # Calculate saturation adjustment
                # Target ~128 for good color vibrancy
                if hsv_saturation < 80:  # Undersaturated
                    saturation_adjust = int((100 - hsv_saturation) / 2)
                elif hsv_saturation > 180:  # Oversaturated
                    saturation_adjust = int((128 - hsv_saturation) / 3)
                else:
                    saturation_adjust = 0
                # Clamp to reasonable range
                saturation_adjust = max(-30, min(40, saturation_adjust))
                logger.info(f"  Saturation adjustment: {saturation_adjust:+d}")

            adjustments = {
                'brightness': brightness_adjust,
                'contrast': contrast_adjust,
                'saturation': saturation_adjust
            }

            logger.info(f"  ✓ Auto-enhance analysis complete")
            logger.info(f"  Recommended adjustments: {adjustments}")

            return True, adjustments, ""

        except Exception as e:
            error_msg = f"Failed to analyze image for auto-enhance: {str(e)}"
            logger.error(f"  ✗ {error_msg}", exc_info=True)
            return False, {}, error_msg

    @staticmethod
    def apply_edits(input_path: str, brightness: float = 0, contrast: float = 0,
                   saturation: float = 0, crop_box: Tuple[int, int, int, int] = None) -> Tuple[bool, str, str]:
        """
        Apply combined edits (crop and/or color adjustments) to an image.

        This method applies crop first (if specified), then color adjustments.
        It's more efficient than separate calls when both operations are needed.

        Args:
            input_path: Path to input image
            brightness: Brightness adjustment (-100 to +100, 0 = no change)
            contrast: Contrast adjustment (-100 to +100, 0 = no change)
            saturation: Saturation adjustment (-100 to +100, 0 = no change)
            crop_box: Optional crop box as (left, upper, right, lower) in pixels

        Returns:
            tuple: (success, output_path, error_message)
        """
        try:
            logger.info(f"Applying combined edits: {input_path}")
            logger.info(f"  Brightness: {brightness:+.1f}, Contrast: {contrast:+.1f}, Saturation: {saturation:+.1f}")
            if crop_box:
                logger.info(f"  Crop box: {crop_box}")

            # Open image
            img = Image.open(input_path)
            original_format = img.format
            logger.info(f"  Original size: {img.size}, Format: {original_format}")

            # Extract EXIF data
            exif_dict = None
            try:
                exif_data = img.info.get('exif')
                if exif_data:
                    exif_dict = piexif.load(exif_data)
                    logger.info("  ✓ EXIF data extracted for preservation")
            except Exception as e:
                logger.warning(f"  Could not extract EXIF data: {e}")

            # Apply crop first if specified
            if crop_box:
                left, upper, right, lower = crop_box
                width, height = img.size

                # Validate crop box
                if left < 0 or upper < 0 or right > width or lower > height:
                    raise ValueError(f"Crop box {crop_box} exceeds image bounds {img.size}")
                if right <= left or lower <= upper:
                    raise ValueError(f"Invalid crop box {crop_box} - negative area")

                img = img.crop(crop_box)
                logger.info(f"  ✓ Cropped to: {img.size}")

            # Apply color adjustments
            adjusted = img

            # Brightness: -100 to +100 → factor 0.0 to 2.0
            if brightness != 0:
                factor = 1.0 + (brightness / 100.0)
                enhancer = ImageEnhance.Brightness(adjusted)
                adjusted = enhancer.enhance(factor)
                logger.info(f"  Applied brightness factor: {factor:.2f}")

            # Contrast: -100 to +100 → factor 0.0 to 2.0
            if contrast != 0:
                factor = 1.0 + (contrast / 100.0)
                enhancer = ImageEnhance.Contrast(adjusted)
                adjusted = enhancer.enhance(factor)
                logger.info(f"  Applied contrast factor: {factor:.2f}")

            # Saturation: -100 to +100 → factor 0.0 to 2.0
            if saturation != 0:
                factor = 1.0 + (saturation / 100.0)
                enhancer = ImageEnhance.Color(adjusted)
                adjusted = enhancer.enhance(factor)
                logger.info(f"  Applied saturation factor: {factor:.2f}")

            # Create temporary output file
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_edited{ext}"

            # Save with EXIF data
            if exif_dict:
                exif_bytes = piexif.dump(exif_dict)
                adjusted.save(output_path, format=original_format or 'JPEG',
                            exif=exif_bytes, quality=95)
            else:
                adjusted.save(output_path, format=original_format or 'JPEG', quality=95)

            logger.info(f"  ✓ Edits applied successfully")
            logger.info(f"  Output: {output_path}")

            return True, output_path, ""

        except Exception as e:
            error_msg = f"Failed to apply edits: {str(e)}"
            logger.error(f"  ✗ {error_msg}", exc_info=True)
            return False, "", error_msg

    @staticmethod
    def convert_format(input_path: str, target_format: str,
                      quality: int = 95) -> Tuple[bool, str, str]:
        """
        Convert image to different format.

        Args:
            input_path: Path to input image
            target_format: Target format ('JPEG', 'PNG', 'TIFF', etc.)
            quality: JPEG quality (1-100, only used for JPEG)

        Returns:
            tuple: (success, output_path, error_message)
        """
        try:
            logger.info(f"Converting format: {input_path}")
            logger.info(f"  Target format: {target_format}, Quality: {quality}")

            # Open image
            img = Image.open(input_path)
            original_format = img.format
            logger.info(f"  Original format: {original_format}")

            # Handle format-specific requirements
            if target_format.upper() == 'JPEG':
                # JPEG doesn't support transparency, convert RGBA to RGB
                if img.mode in ('RGBA', 'LA', 'P'):
                    logger.info(f"  Converting {img.mode} to RGB for JPEG")
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

            # Extract EXIF data (JPEG and TIFF support EXIF)
            exif_dict = None
            if target_format.upper() in ('JPEG', 'TIFF'):
                try:
                    exif_data = img.info.get('exif')
                    if exif_data:
                        exif_dict = piexif.load(exif_data)
                        logger.info("  ✓ EXIF data extracted for preservation")
                except Exception as e:
                    logger.warning(f"  Could not extract EXIF data: {e}")

            # Determine output extension
            ext_map = {
                'JPEG': '.jpg',
                'PNG': '.png',
                'TIFF': '.tif',
                'BMP': '.bmp',
                'GIF': '.gif'
            }
            ext = ext_map.get(target_format.upper(), f'.{target_format.lower()}')

            # Create output path
            base, _ = os.path.splitext(input_path)
            output_path = f"{base}_converted{ext}"

            # Save with appropriate parameters
            save_kwargs = {'format': target_format.upper()}

            if target_format.upper() == 'JPEG':
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True

            if exif_dict and target_format.upper() in ('JPEG', 'TIFF'):
                save_kwargs['exif'] = piexif.dump(exif_dict)

            img.save(output_path, **save_kwargs)

            logger.info(f"  ✓ Format converted successfully")
            logger.info(f"  Output: {output_path}")

            return True, output_path, ""

        except Exception as e:
            error_msg = f"Failed to convert format: {str(e)}"
            logger.error(f"  ✗ {error_msg}", exc_info=True)
            return False, "", error_msg


class VersionManager:
    """
    Manages file version control and storage.

    Version Storage Location:
        <archive_base>/.pyphotoorg_versions/by_hash/<hash_prefix>/<full_hash>_v<N>.<ext>

    Version Tracking:
        - FileVersions table tracks all versions
        - Parent-child relationships form version tree
        - is_active flag indicates current version
    """

    def __init__(self, database_path: str, archive_base: str):
        """
        Initialize version manager.

        Args:
            database_path: Path to SQLite database
            archive_base: Base path for archive storage
        """
        self.database_path = database_path
        self.archive_base = archive_base
        self.version_storage = os.path.join(archive_base, '.pyphotoorg_versions', 'by_hash')

        # Ensure version storage directory exists
        os.makedirs(self.version_storage, exist_ok=True)

        # Ensure database is migrated to support version tracking
        self._ensure_migration()

        logger.info(f"VersionManager initialized")
        logger.info(f"  Database: {database_path}")
        logger.info(f"  Archive base: {archive_base}")
        logger.info(f"  Version storage: {self.version_storage}")

    def _ensure_migration(self):
        """Ensure database schema supports version tracking."""
        try:
            from migrations.add_modifications_support import migrate_database

            migrate_database(self.database_path)
            logger.info("Database migration verified")
        except Exception as e:
            logger.error(f"Database migration check failed: {e}")
            raise RuntimeError(f"Database must be migrated to schema version 3. "
                              f"Run migrations/add_modifications_support.py first.")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper settings."""
        conn = sqlite3.connect(self.database_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.row_factory = sqlite3.Row
        return conn

    def _hash_file(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_version_path(self, file_hash: str, version_number: int, extension: str) -> str:
        """
        Generate version storage path.

        Args:
            file_hash: Full SHA-256 hash
            version_number: Version number (0, 1, 2, ...)
            extension: File extension (with dot)

        Returns:
            Full path to version file
        """
        # Use first 2 characters of hash for sharding
        hash_prefix = file_hash[:2]
        shard_dir = os.path.join(self.version_storage, hash_prefix)
        os.makedirs(shard_dir, exist_ok=True)

        filename = f"{file_hash}_v{version_number}{extension}"
        return os.path.join(shard_dir, filename)

    def save_original_version(self, file_path: str, file_hash: str) -> Optional[str]:
        """
        Save original version (v0) of a file before first modification.

        Args:
            file_path: Path to current archive file
            file_hash: SHA-256 hash of file

        Returns:
            version_id if successful, None otherwise
        """
        try:
            logger.info(f"Saving original version: {file_path}")
            logger.info(f"  File hash: {file_hash[:16]}...")

            # Check if version already exists
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT version_id FROM FileVersions
                WHERE file_hash = ? AND version_number = 0
            """, (file_hash,))

            existing = cursor.fetchone()
            if existing:
                logger.info(f"  Original version already exists: {existing['version_id']}")
                conn.close()
                return existing['version_id']

            # Get file metadata
            file_size = os.path.getsize(file_path)
            _, ext = os.path.splitext(file_path)

            # Try to get image dimensions
            image_width, image_height, image_format = None, None, None
            try:
                img = Image.open(file_path)
                image_width, image_height = img.size
                image_format = img.format
            except Exception as e:
                logger.warning(f"  Could not read image metadata: {e}")

            # Generate version path
            version_path = self._get_version_path(file_hash, 0, ext)
            version_id = f"{file_hash}_v0"

            logger.info(f"  Version ID: {version_id}")
            logger.info(f"  Storage path: {version_path}")

            # Copy file to version storage
            shutil.copy2(file_path, version_path)
            logger.info(f"  ✓ File copied to version storage")

            # Create database record
            cursor.execute("""
                INSERT INTO FileVersions (
                    version_id, file_hash, parent_version_id, original_hash,
                    version_number, storage_path, is_active,
                    modification_session_id, modification_type, modification_params,
                    file_size, image_width, image_height, image_format,
                    created_timestamp
                ) VALUES (?, ?, NULL, ?, 0, ?, 0, NULL, 'original', NULL, ?, ?, ?, ?, ?)
            """, (
                version_id, file_hash, file_hash, version_path,
                file_size, image_width, image_height, image_format,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            # Add original version (v0) hash to FileHashHistory
            try:
                from DuplicateFileDetection import PhotoDatabase

                with PhotoDatabase(self.database_path) as db:
                    db.add_version_hash_to_history(
                        original_hash=file_hash,
                        version_hash=file_hash,
                        reason='version_original'
                    )

                logger.info(f"  ✓ Original version hash added to FileHashHistory")
            except Exception as e:
                logger.warning(f"  ⚠ Failed to add version hash: {e}")

            logger.info(f"  ✓ Original version saved successfully")
            return version_id

        except Exception as e:
            logger.error(f"  ✗ Failed to save original version: {e}", exc_info=True)
            try:
                conn.close()
            except:
                pass
            return None

    def create_new_version(self, parent_version_id: str, modified_file_path: str,
                          modification_type: str, params: Dict,
                          session_id: str) -> Optional[str]:
        """
        Create new version after modification.

        Args:
            parent_version_id: ID of parent version
            modified_file_path: Path to modified file (temporary)
            modification_type: Type of modification ('rotation', 'crop', etc.)
            params: Modification parameters as dict
            session_id: ModificationSession ID

        Returns:
            new_version_id if successful, None otherwise
        """
        try:
            logger.info(f"Creating new version from parent: {parent_version_id}")
            logger.info(f"  Modification type: {modification_type}")
            logger.info(f"  Modified file: {modified_file_path}")

            conn = self._get_connection()
            cursor = conn.cursor()

            # Get parent version info
            cursor.execute("""
                SELECT original_hash, version_number
                FROM FileVersions
                WHERE version_id = ?
            """, (parent_version_id,))

            parent = cursor.fetchone()
            if not parent:
                raise ValueError(f"Parent version not found: {parent_version_id}")

            original_hash = parent['original_hash']
            new_version_number = parent['version_number'] + 1

            logger.info(f"  Original hash: {original_hash[:16]}...")
            logger.info(f"  New version number: {new_version_number}")

            # Calculate hash of modified file
            new_hash = self._hash_file(modified_file_path)
            logger.info(f"  New file hash: {new_hash[:16]}...")

            # Get file metadata
            file_size = os.path.getsize(modified_file_path)
            _, ext = os.path.splitext(modified_file_path)

            image_width, image_height, image_format = None, None, None
            try:
                img = Image.open(modified_file_path)
                image_width, image_height = img.size
                image_format = img.format
            except Exception as e:
                logger.warning(f"  Could not read image metadata: {e}")

            # Generate new version ID and path
            version_id = f"{new_hash}_v{new_version_number}"
            version_path = self._get_version_path(new_hash, new_version_number, ext)

            logger.info(f"  Version ID: {version_id}")
            logger.info(f"  Storage path: {version_path}")

            # Copy modified file to version storage
            shutil.copy2(modified_file_path, version_path)
            logger.info(f"  ✓ File copied to version storage")

            # Mark previous version as inactive
            cursor.execute("""
                UPDATE FileVersions
                SET is_active = 0
                WHERE original_hash = ?
            """, (original_hash,))
            logger.info(f"  ✓ Previous versions marked as inactive")

            # Create new version record (active)
            cursor.execute("""
                INSERT INTO FileVersions (
                    version_id, file_hash, parent_version_id, original_hash,
                    version_number, storage_path, is_active,
                    modification_session_id, modification_type, modification_params,
                    file_size, image_width, image_height, image_format,
                    created_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version_id, new_hash, parent_version_id, original_hash,
                new_version_number, version_path, session_id,
                modification_type, json.dumps(params),
                file_size, image_width, image_height, image_format,
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            # Add new version hash to FileHashHistory for duplicate detection
            try:
                from DuplicateFileDetection import PhotoDatabase

                with PhotoDatabase(self.database_path) as db:
                    # Link version hash to original for duplicate detection
                    db.add_version_hash_to_history(
                        original_hash=original_hash,
                        version_hash=new_hash,
                        reason=f'version_{modification_type}'
                    )

                logger.info(f"  ✓ Version hash added to FileHashHistory")
            except Exception as e:
                logger.warning(f"  ⚠ Failed to add version hash to history: {e}")
                # Non-fatal - version still usable, just not in duplicate detection

            logger.info(f"  ✓ New version created successfully")
            return version_id

        except Exception as e:
            logger.error(f"  ✗ Failed to create new version: {e}", exc_info=True)
            try:
                conn.close()
            except:
                pass
            return None

    def get_version_history(self, original_hash: str) -> List[Dict]:
        """
        Get complete version history for a file.

        Args:
            original_hash: Original hash when file was first imported

        Returns:
            List of version records, ordered by version_number
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM FileVersions
                WHERE original_hash = ?
                ORDER BY version_number ASC
            """, (original_hash,))

            versions = [dict(row) for row in cursor.fetchall()]
            conn.close()

            logger.info(f"Retrieved {len(versions)} versions for hash {original_hash[:16]}...")
            return versions

        except Exception as e:
            logger.error(f"Failed to get version history: {e}", exc_info=True)
            return []

    def restore_version(self, version_id: str, target_path: str) -> bool:
        """
        Restore a specific version to target path.

        Args:
            version_id: Version ID to restore
            target_path: Destination path for restored file

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Restoring version: {version_id}")
            logger.info(f"  Target path: {target_path}")

            conn = self._get_connection()
            cursor = conn.cursor()

            # Get version info
            cursor.execute("""
                SELECT storage_path
                FROM FileVersions
                WHERE version_id = ?
            """, (version_id,))

            version = cursor.fetchone()
            conn.close()

            if not version:
                raise ValueError(f"Version not found: {version_id}")

            storage_path = version['storage_path']
            logger.info(f"  Storage path: {storage_path}")

            if not os.path.exists(storage_path):
                raise FileNotFoundError(f"Version file not found: {storage_path}")

            # Copy version file to target
            shutil.copy2(storage_path, target_path)
            logger.info(f"  ✓ Version restored successfully")

            return True

        except Exception as e:
            logger.error(f"  ✗ Failed to restore version: {e}", exc_info=True)
            return False
