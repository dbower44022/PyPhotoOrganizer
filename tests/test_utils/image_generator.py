"""
Image Generator for Test Data

Creates synthetic images with various properties for testing:
- Different formats (JPEG, PNG, TIFF)
- Different sizes and dimensions
- EXIF data with customizable dates
- Corrupted/invalid files for error testing
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
import piexif


class ImageGenerator:
    """Generate synthetic test images with configurable properties."""

    @staticmethod
    def create_test_image(
        path: str,
        width: int = 800,
        height: int = 600,
        format: str = "JPEG",
        color: Tuple[int, int, int] = (100, 150, 200),
        text: Optional[str] = None,
        exif_date: Optional[datetime] = None,
        camera_make: str = "Test Camera",
        camera_model: str = "TestCam 1000"
    ) -> str:
        """
        Create a synthetic test image with optional EXIF data.

        Args:
            path: File path for the generated image
            width: Image width in pixels
            height: Image height in pixels
            format: Image format (JPEG, PNG, TIFF)
            color: RGB color tuple for image background
            text: Optional text to draw on image
            exif_date: Date to embed in EXIF data
            camera_make: Camera manufacturer for EXIF
            camera_model: Camera model for EXIF

        Returns:
            Path to created image file
        """
        # Create image with solid color background
        img = Image.new('RGB', (width, height), color)

        # Draw text if provided
        if text:
            draw = ImageDraw.Draw(img)
            try:
                # Try to use a better font if available
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except:
                # Fallback to default font
                font = ImageFont.load_default()

            # Calculate text position (center)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((width - text_width) // 2, (height - text_height) // 2)

            draw.text(position, text, fill=(255, 255, 255), font=font)

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)

        # Add EXIF data if date provided and format supports it
        if exif_date and format.upper() in ['JPEG', 'TIFF']:
            exif_dict = ImageGenerator._create_exif_data(
                exif_date, camera_make, camera_model, width, height
            )
            exif_bytes = piexif.dump(exif_dict)
            img.save(path, format=format, exif=exif_bytes, quality=95)
        else:
            img.save(path, format=format)

        return path

    @staticmethod
    def _create_exif_data(
        date: datetime,
        camera_make: str,
        camera_model: str,
        width: int,
        height: int
    ) -> dict:
        """
        Create EXIF data dictionary for image.

        Args:
            date: DateTime for EXIF DateTimeOriginal
            camera_make: Camera manufacturer
            camera_model: Camera model
            width: Image width
            height: Image height

        Returns:
            EXIF dictionary compatible with piexif
        """
        # Format date as required by EXIF (YYYY:MM:DD HH:MM:SS)
        date_str = date.strftime("%Y:%m:%d %H:%M:%S")

        exif_ifd = {
            piexif.ExifIFD.DateTimeOriginal: date_str.encode(),
            piexif.ExifIFD.DateTimeDigitized: date_str.encode(),
            piexif.ExifIFD.PixelXDimension: width,
            piexif.ExifIFD.PixelYDimension: height,
            piexif.ExifIFD.FNumber: (28, 10),  # f/2.8
            piexif.ExifIFD.ExposureTime: (1, 100),  # 1/100 second
            piexif.ExifIFD.ISOSpeedRatings: 400,
            piexif.ExifIFD.FocalLength: (50, 1),  # 50mm
        }

        zeroth_ifd = {
            piexif.ImageIFD.Make: camera_make.encode(),
            piexif.ImageIFD.Model: camera_model.encode(),
            piexif.ImageIFD.DateTime: date_str.encode(),
            piexif.ImageIFD.Orientation: 1,
        }

        gps_ifd = {}

        exif_dict = {
            "0th": zeroth_ifd,
            "Exif": exif_ifd,
            "GPS": gps_ifd,
            "1st": {},
            "thumbnail": None
        }

        return exif_dict

    @staticmethod
    def create_icon(path: str, size: int = 64) -> str:
        """
        Create a small square icon (should be filtered by PhotoFilter).

        Args:
            path: File path for icon
            size: Icon size in pixels (square)

        Returns:
            Path to created icon file
        """
        return ImageGenerator.create_test_image(
            path=path,
            width=size,
            height=size,
            format="PNG",
            color=(255, 0, 0),
            text=None
        )

    @staticmethod
    def create_thumbnail(path: str) -> str:
        """
        Create a thumbnail-sized image (should be filtered).

        Args:
            path: File path for thumbnail

        Returns:
            Path to created thumbnail file
        """
        return ImageGenerator.create_test_image(
            path=path,
            width=150,
            height=150,
            format="JPEG",
            color=(128, 128, 128),
            text="Thumb"
        )

    @staticmethod
    def create_photo_without_exif(path: str) -> str:
        """
        Create a photo without EXIF data (should be flagged as unreliable).

        Args:
            path: File path for image

        Returns:
            Path to created image file
        """
        return ImageGenerator.create_test_image(
            path=path,
            width=1920,
            height=1080,
            format="JPEG",
            color=(50, 100, 150),
            text="No EXIF",
            exif_date=None  # Explicitly no EXIF
        )

    @staticmethod
    def create_photo_with_suspicious_date(path: str) -> str:
        """
        Create a photo with suspicious date (year 1970).

        Args:
            path: File path for image

        Returns:
            Path to created image file
        """
        suspicious_date = datetime(1970, 1, 1, 0, 0, 0)
        return ImageGenerator.create_test_image(
            path=path,
            width=1920,
            height=1080,
            format="JPEG",
            color=(200, 50, 50),
            text="1970",
            exif_date=suspicious_date
        )

    @staticmethod
    def create_photo_series(
        base_path: str,
        count: int,
        start_date: datetime,
        prefix: str = "IMG"
    ) -> list:
        """
        Create a series of photos with sequential dates.

        Args:
            base_path: Directory to create images in
            count: Number of images to create
            start_date: Starting date for sequence
            prefix: Filename prefix

        Returns:
            List of created file paths
        """
        os.makedirs(base_path, exist_ok=True)
        created_files = []

        for i in range(count):
            filename = f"{prefix}_{i+1:04d}.jpg"
            filepath = os.path.join(base_path, filename)
            date = start_date + timedelta(days=i)

            ImageGenerator.create_test_image(
                path=filepath,
                width=1920,
                height=1080,
                format="JPEG",
                color=(100 + i*5, 150, 200),
                text=f"Photo {i+1}",
                exif_date=date
            )
            created_files.append(filepath)

        return created_files

    @staticmethod
    def create_corrupted_file(path: str) -> str:
        """
        Create a corrupted image file for error testing.

        Args:
            path: File path for corrupted file

        Returns:
            Path to created file
        """
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)

        # Write random bytes that look like an image header but are corrupted
        with open(path, 'wb') as f:
            f.write(b'\xff\xd8\xff\xe0' + b'\x00' * 100)  # JPEG header + garbage

        return path

    @staticmethod
    def create_duplicate(source_path: str, dest_path: str) -> str:
        """
        Create an exact duplicate of an existing image.

        Args:
            source_path: Path to source image
            dest_path: Path for duplicate

        Returns:
            Path to created duplicate
        """
        import shutil
        os.makedirs(os.path.dirname(dest_path) if os.path.dirname(dest_path) else '.', exist_ok=True)
        shutil.copy2(source_path, dest_path)
        return dest_path
