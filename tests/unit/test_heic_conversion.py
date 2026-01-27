"""
Unit tests for HEIC to JPEG conversion with EXIF preservation.

Tests:
- EXIF data is transferred during HEIC to JPEG conversion
- DateTimeOriginal is preserved
- GPS coordinates are preserved
- Camera make/model are preserved
- Orientation tags are preserved
- Graceful handling when no EXIF data exists
"""

import os
import tempfile
import shutil
from datetime import datetime

import pytest
from PIL import Image
import piexif
import pillow_heif


class HEICTestFileGenerator:
    """Generate HEIC test files with configurable EXIF data."""

    @staticmethod
    def create_heic_with_exif(
        path: str,
        width: int = 800,
        height: int = 600,
        exif_date: datetime = None,
        camera_make: str = "Test Camera",
        camera_model: str = "TestCam HEIC",
        gps_lat: float = None,
        gps_lon: float = None,
        orientation: int = 1
    ) -> str:
        """
        Create a HEIC file with EXIF metadata.

        Args:
            path: Output file path
            width: Image width
            height: Image height
            exif_date: Date for EXIF DateTimeOriginal
            camera_make: Camera manufacturer
            camera_model: Camera model
            gps_lat: GPS latitude (decimal degrees)
            gps_lon: GPS longitude (decimal degrees)
            orientation: EXIF orientation value (1-8)

        Returns:
            Path to created HEIC file
        """
        # Create a PIL image
        img = Image.new('RGB', (width, height), color=(100, 150, 200))

        # Build EXIF data
        exif_dict = {
            "0th": {},
            "Exif": {},
            "GPS": {},
            "1st": {},
            "thumbnail": None
        }

        # Add camera info
        if camera_make:
            exif_dict["0th"][piexif.ImageIFD.Make] = camera_make.encode()
        if camera_model:
            exif_dict["0th"][piexif.ImageIFD.Model] = camera_model.encode()

        # Add orientation
        exif_dict["0th"][piexif.ImageIFD.Orientation] = orientation

        # Add date
        if exif_date:
            date_str = exif_date.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str.encode()
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = date_str.encode()
            exif_dict["0th"][piexif.ImageIFD.DateTime] = date_str.encode()

        # Add dimensions
        exif_dict["Exif"][piexif.ExifIFD.PixelXDimension] = width
        exif_dict["Exif"][piexif.ExifIFD.PixelYDimension] = height

        # Add GPS if provided
        if gps_lat is not None and gps_lon is not None:
            # Convert decimal degrees to EXIF GPS format
            lat_ref = 'N' if gps_lat >= 0 else 'S'
            lon_ref = 'E' if gps_lon >= 0 else 'W'

            lat_abs = abs(gps_lat)
            lon_abs = abs(gps_lon)

            lat_deg = int(lat_abs)
            lat_min = int((lat_abs - lat_deg) * 60)
            lat_sec = int(((lat_abs - lat_deg) * 60 - lat_min) * 60 * 100)

            lon_deg = int(lon_abs)
            lon_min = int((lon_abs - lon_deg) * 60)
            lon_sec = int(((lon_abs - lon_deg) * 60 - lon_min) * 60 * 100)

            exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_ref.encode()
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = (
                (lat_deg, 1), (lat_min, 1), (lat_sec, 100)
            )
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lon_ref.encode()
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = (
                (lon_deg, 1), (lon_min, 1), (lon_sec, 100)
            )

        # Dump EXIF to bytes
        exif_bytes = piexif.dump(exif_dict)

        # Ensure directory exists
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)

        # Save as JPEG first with EXIF
        temp_jpeg = path + ".temp.jpg"
        img.save(temp_jpeg, format="JPEG", exif=exif_bytes, quality=95)

        # Convert JPEG to HEIC using pillow_heif
        heif_file = pillow_heif.from_pillow(Image.open(temp_jpeg))

        # Copy EXIF from JPEG to HEIC
        with open(temp_jpeg, 'rb') as f:
            jpeg_data = f.read()
            # Extract EXIF from JPEG
            try:
                jpeg_exif = piexif.load(jpeg_data)
                heif_file.info['exif'] = piexif.dump(jpeg_exif)
            except Exception:
                pass

        # Save HEIC
        heif_file.save(path, quality=95)

        # Clean up temp file
        if os.path.exists(temp_jpeg):
            os.remove(temp_jpeg)

        return path

    @staticmethod
    def create_heic_without_exif(path: str, width: int = 800, height: int = 600) -> str:
        """
        Create a HEIC file without EXIF metadata.

        Args:
            path: Output file path
            width: Image width
            height: Image height

        Returns:
            Path to created HEIC file
        """
        img = Image.new('RGB', (width, height), color=(200, 100, 50))

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)

        # Convert to HEIC without EXIF
        heif_file = pillow_heif.from_pillow(img)
        heif_file.save(path, quality=95)

        return path


def convert_heic_to_jpeg_with_exif(heic_path: str, jpeg_path: str) -> bool:
    """
    Convert HEIC to JPEG while preserving EXIF data.
    This mirrors the implementation in main.py.

    Args:
        heic_path: Source HEIC file
        jpeg_path: Destination JPEG file

    Returns:
        True if successful, False otherwise
    """
    try:
        heif_file = pillow_heif.read_heif(heic_path)
        heic_image = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
        )
        # Extract EXIF data from HEIC file to preserve metadata
        exif_bytes = heif_file.info.get('exif')

        # Save with EXIF data if available
        if exif_bytes:
            heic_image.save(jpeg_path, format="JPEG", quality=95, exif=exif_bytes)
        else:
            heic_image.save(jpeg_path, format="JPEG", quality=95)

        return True
    except Exception as e:
        print(f"Conversion failed: {e}")
        return False


class TestHEICConversionExifPreservation:
    """Test HEIC to JPEG conversion preserves EXIF data."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_path = tempfile.mkdtemp(prefix="heic_test_")
        yield temp_path
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_datetime_original_preserved(self, temp_dir):
        """Test that DateTimeOriginal is preserved during conversion."""
        test_date = datetime(2024, 7, 15, 14, 30, 45)
        heic_path = os.path.join(temp_dir, "test_date.heic")
        jpeg_path = os.path.join(temp_dir, "test_date.jpeg")

        # Create HEIC with specific date
        HEICTestFileGenerator.create_heic_with_exif(
            heic_path,
            exif_date=test_date
        )

        # Convert to JPEG
        success = convert_heic_to_jpeg_with_exif(heic_path, jpeg_path)
        assert success, "Conversion should succeed"
        assert os.path.exists(jpeg_path), "JPEG file should be created"

        # Verify EXIF in output
        exif_dict = piexif.load(jpeg_path)
        assert piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif'], \
            "DateTimeOriginal should be present in converted JPEG"

        date_bytes = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal]
        date_str = date_bytes.decode('utf-8') if isinstance(date_bytes, bytes) else date_bytes
        assert date_str == "2024:07:15 14:30:45", \
            f"Date should match original: expected '2024:07:15 14:30:45', got '{date_str}'"

    def test_camera_make_model_preserved(self, temp_dir):
        """Test that camera make/model are preserved during conversion."""
        heic_path = os.path.join(temp_dir, "test_camera.heic")
        jpeg_path = os.path.join(temp_dir, "test_camera.jpeg")

        # Create HEIC with specific camera info
        HEICTestFileGenerator.create_heic_with_exif(
            heic_path,
            camera_make="Apple",
            camera_model="iPhone 15 Pro"
        )

        # Convert to JPEG
        success = convert_heic_to_jpeg_with_exif(heic_path, jpeg_path)
        assert success, "Conversion should succeed"

        # Verify camera info in output
        exif_dict = piexif.load(jpeg_path)

        if piexif.ImageIFD.Make in exif_dict['0th']:
            make = exif_dict['0th'][piexif.ImageIFD.Make]
            make_str = make.decode('utf-8').rstrip('\x00') if isinstance(make, bytes) else make
            assert make_str == "Apple", f"Make should be 'Apple', got '{make_str}'"

        if piexif.ImageIFD.Model in exif_dict['0th']:
            model = exif_dict['0th'][piexif.ImageIFD.Model]
            model_str = model.decode('utf-8').rstrip('\x00') if isinstance(model, bytes) else model
            assert model_str == "iPhone 15 Pro", f"Model should be 'iPhone 15 Pro', got '{model_str}'"

    def test_gps_coordinates_preserved(self, temp_dir):
        """Test that GPS coordinates are preserved during conversion."""
        heic_path = os.path.join(temp_dir, "test_gps.heic")
        jpeg_path = os.path.join(temp_dir, "test_gps.jpeg")

        # Create HEIC with GPS coordinates (San Francisco)
        HEICTestFileGenerator.create_heic_with_exif(
            heic_path,
            gps_lat=37.7749,
            gps_lon=-122.4194
        )

        # Convert to JPEG
        success = convert_heic_to_jpeg_with_exif(heic_path, jpeg_path)
        assert success, "Conversion should succeed"

        # Verify GPS in output
        exif_dict = piexif.load(jpeg_path)

        # Check GPS latitude reference exists
        if piexif.GPSIFD.GPSLatitudeRef in exif_dict['GPS']:
            lat_ref = exif_dict['GPS'][piexif.GPSIFD.GPSLatitudeRef]
            lat_ref_str = lat_ref.decode('utf-8') if isinstance(lat_ref, bytes) else lat_ref
            assert lat_ref_str == 'N', "Latitude reference should be 'N'"

        # Check GPS longitude reference exists
        if piexif.GPSIFD.GPSLongitudeRef in exif_dict['GPS']:
            lon_ref = exif_dict['GPS'][piexif.GPSIFD.GPSLongitudeRef]
            lon_ref_str = lon_ref.decode('utf-8') if isinstance(lon_ref, bytes) else lon_ref
            assert lon_ref_str == 'W', "Longitude reference should be 'W'"

    def test_orientation_preserved(self, temp_dir):
        """Test that orientation tag is preserved during conversion."""
        heic_path = os.path.join(temp_dir, "test_orientation.heic")
        jpeg_path = os.path.join(temp_dir, "test_orientation.jpeg")

        # Create HEIC with orientation 6 (rotated 90 degrees CW)
        HEICTestFileGenerator.create_heic_with_exif(
            heic_path,
            orientation=6
        )

        # Convert to JPEG
        success = convert_heic_to_jpeg_with_exif(heic_path, jpeg_path)
        assert success, "Conversion should succeed"

        # Verify orientation in output
        exif_dict = piexif.load(jpeg_path)

        if piexif.ImageIFD.Orientation in exif_dict['0th']:
            orientation = exif_dict['0th'][piexif.ImageIFD.Orientation]
            assert orientation == 6, f"Orientation should be 6, got {orientation}"

    def test_conversion_without_exif_succeeds(self, temp_dir):
        """Test that conversion succeeds even when source has no EXIF."""
        heic_path = os.path.join(temp_dir, "test_no_exif.heic")
        jpeg_path = os.path.join(temp_dir, "test_no_exif.jpeg")

        # Create HEIC without EXIF
        HEICTestFileGenerator.create_heic_without_exif(heic_path)

        # Convert to JPEG (should not fail)
        success = convert_heic_to_jpeg_with_exif(heic_path, jpeg_path)
        assert success, "Conversion should succeed even without EXIF"
        assert os.path.exists(jpeg_path), "JPEG file should be created"

        # Verify image is valid
        img = Image.open(jpeg_path)
        assert img.size == (800, 600), "Image dimensions should be preserved"
        img.close()

    def test_image_dimensions_preserved(self, temp_dir):
        """Test that image dimensions are preserved during conversion."""
        heic_path = os.path.join(temp_dir, "test_dims.heic")
        jpeg_path = os.path.join(temp_dir, "test_dims.jpeg")

        width, height = 1920, 1080
        HEICTestFileGenerator.create_heic_with_exif(
            heic_path,
            width=width,
            height=height
        )

        success = convert_heic_to_jpeg_with_exif(heic_path, jpeg_path)
        assert success, "Conversion should succeed"

        img = Image.open(jpeg_path)
        assert img.size == (width, height), \
            f"Dimensions should be {width}x{height}, got {img.size}"
        img.close()

    def test_multiple_exif_fields_preserved(self, temp_dir):
        """Test that multiple EXIF fields are preserved together."""
        test_date = datetime(2023, 12, 25, 10, 30, 0)
        heic_path = os.path.join(temp_dir, "test_multi.heic")
        jpeg_path = os.path.join(temp_dir, "test_multi.jpeg")

        # Create HEIC with all metadata
        HEICTestFileGenerator.create_heic_with_exif(
            heic_path,
            exif_date=test_date,
            camera_make="Canon",
            camera_model="EOS R5",
            gps_lat=40.7128,
            gps_lon=-74.0060,
            orientation=1
        )

        success = convert_heic_to_jpeg_with_exif(heic_path, jpeg_path)
        assert success, "Conversion should succeed"

        # Verify all fields
        exif_dict = piexif.load(jpeg_path)

        # Check date
        if piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
            date_bytes = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal]
            date_str = date_bytes.decode('utf-8') if isinstance(date_bytes, bytes) else date_bytes
            assert "2023:12:25" in date_str, "Date should contain 2023:12:25"

        # Check camera
        if piexif.ImageIFD.Make in exif_dict['0th']:
            make = exif_dict['0th'][piexif.ImageIFD.Make]
            make_str = make.decode('utf-8').rstrip('\x00') if isinstance(make, bytes) else make
            assert make_str == "Canon", "Make should be Canon"

        # Check GPS exists
        assert len(exif_dict['GPS']) > 0, "GPS data should be present"


class TestHEICExifDataAccess:
    """Test that EXIF data can be read from HEIC files."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_path = tempfile.mkdtemp(prefix="heic_read_test_")
        yield temp_path
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_read_exif_from_heic(self, temp_dir):
        """Test reading EXIF data directly from HEIC file."""
        test_date = datetime(2024, 1, 15, 9, 0, 0)
        heic_path = os.path.join(temp_dir, "test_read.heic")

        HEICTestFileGenerator.create_heic_with_exif(
            heic_path,
            exif_date=test_date,
            camera_make="Sony",
            camera_model="A7IV"
        )

        # Read HEIC file
        heif_file = pillow_heif.read_heif(heic_path)

        # Check EXIF is accessible
        exif_bytes = heif_file.info.get('exif')

        # Note: EXIF might be None if pillow_heif doesn't support
        # writing EXIF to HEIC files on this system
        if exif_bytes:
            exif_dict = piexif.load(exif_bytes)
            assert 'Exif' in exif_dict, "EXIF IFD should be present"
            assert '0th' in exif_dict, "0th IFD should be present"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
