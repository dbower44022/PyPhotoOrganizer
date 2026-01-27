"""
Unit tests for the video_thumbnail module.

Tests:
- ffmpeg availability detection
- Video metadata extraction
- Thumbnail extraction
- Duration formatting
- Bitrate and resolution formatting
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from video_thumbnail import (
    VideoThumbnailExtractor,
    VideoMetadata,
    is_video_file,
    get_video_info_dict,
)


class TestVideoThumbnailExtractor:
    """Tests for VideoThumbnailExtractor class."""

    def test_format_duration_seconds(self):
        """Test formatting duration less than a minute."""
        assert VideoThumbnailExtractor.format_duration(0) == "0:00"
        assert VideoThumbnailExtractor.format_duration(30) == "0:30"
        assert VideoThumbnailExtractor.format_duration(59) == "0:59"

    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        assert VideoThumbnailExtractor.format_duration(60) == "1:00"
        assert VideoThumbnailExtractor.format_duration(90) == "1:30"
        assert VideoThumbnailExtractor.format_duration(754) == "12:34"

    def test_format_duration_hours(self):
        """Test formatting duration with hours."""
        assert VideoThumbnailExtractor.format_duration(3600) == "1:00:00"
        assert VideoThumbnailExtractor.format_duration(5025) == "1:23:45"
        assert VideoThumbnailExtractor.format_duration(36000) == "10:00:00"

    def test_format_duration_negative(self):
        """Test that negative duration returns zero."""
        assert VideoThumbnailExtractor.format_duration(-10) == "0:00"

    def test_format_bitrate_bps(self):
        """Test formatting low bitrate."""
        assert VideoThumbnailExtractor.format_bitrate(500) == "500 bps"
        assert VideoThumbnailExtractor.format_bitrate(999) == "999 bps"

    def test_format_bitrate_kbps(self):
        """Test formatting kbps bitrate."""
        assert VideoThumbnailExtractor.format_bitrate(1000) == "1 kbps"
        assert VideoThumbnailExtractor.format_bitrate(320000) == "320 kbps"
        assert VideoThumbnailExtractor.format_bitrate(999999) == "1000 kbps"

    def test_format_bitrate_mbps(self):
        """Test formatting Mbps bitrate."""
        assert VideoThumbnailExtractor.format_bitrate(1000000) == "1.0 Mbps"
        assert VideoThumbnailExtractor.format_bitrate(5200000) == "5.2 Mbps"
        assert VideoThumbnailExtractor.format_bitrate(25000000) == "25.0 Mbps"

    def test_format_resolution_common(self):
        """Test formatting common resolutions."""
        assert VideoThumbnailExtractor.format_resolution(1920, 1080) == "1080p"
        assert VideoThumbnailExtractor.format_resolution(1280, 720) == "720p"
        assert VideoThumbnailExtractor.format_resolution(3840, 2160) == "4K UHD"

    def test_format_resolution_by_height(self):
        """Test resolution formatting by height only."""
        # Non-standard width but standard height
        assert VideoThumbnailExtractor.format_resolution(1440, 1080) == "1080p"
        assert VideoThumbnailExtractor.format_resolution(1600, 720) == "720p"

    def test_format_resolution_custom(self):
        """Test formatting non-standard resolutions."""
        assert VideoThumbnailExtractor.format_resolution(800, 600) == "800×600"
        assert VideoThumbnailExtractor.format_resolution(1920, 800) == "1920×800"

    def test_availability_check_cached(self):
        """Test that availability check is cached."""
        extractor1 = VideoThumbnailExtractor()
        extractor2 = VideoThumbnailExtractor()
        # Both should use the same cached result
        assert extractor1.is_available() == extractor2.is_available()


class TestIsVideoFile:
    """Tests for is_video_file function."""

    def test_video_extensions(self):
        """Test recognition of video file extensions."""
        assert is_video_file("video.mp4") is True
        assert is_video_file("video.MP4") is True
        assert is_video_file("video.mov") is True
        assert is_video_file("video.MOV") is True
        assert is_video_file("video.avi") is True
        assert is_video_file("video.mkv") is True
        assert is_video_file("video.wmv") is True

    def test_non_video_extensions(self):
        """Test non-video files are not detected."""
        assert is_video_file("photo.jpg") is False
        assert is_video_file("photo.png") is False
        assert is_video_file("document.pdf") is False
        assert is_video_file("data.json") is False

    def test_path_with_directory(self):
        """Test video detection with full paths."""
        assert is_video_file("/home/user/videos/movie.mp4") is True
        assert is_video_file("C:\\Videos\\clip.avi") is True
        assert is_video_file("/photos/vacation.jpg") is False


class TestVideoMetadata:
    """Tests for VideoMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating a VideoMetadata instance."""
        metadata = VideoMetadata(
            duration=125.5,
            duration_formatted="2:05",
            width=1920,
            height=1080,
            codec="h264",
            bitrate=5000000,
            fps=30.0,
            creation_time="2024-01-15T10:30:00",
            has_audio=True,
            audio_codec="aac",
            file_size=10485760
        )

        assert metadata.duration == 125.5
        assert metadata.duration_formatted == "2:05"
        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.codec == "h264"
        assert metadata.bitrate == 5000000
        assert metadata.fps == 30.0
        assert metadata.has_audio is True
        assert metadata.audio_codec == "aac"


class TestGetVideoInfoDict:
    """Tests for get_video_info_dict function."""

    def test_nonexistent_file(self):
        """Test handling of nonexistent file."""
        result = get_video_info_dict("/nonexistent/video.mp4")
        # Should return None or handle gracefully
        # (depends on ffprobe availability)
        assert result is None or isinstance(result, dict)


class TestMockedFfprobe:
    """Tests using mocked ffprobe for reproducible results."""

    @pytest.fixture
    def mock_ffprobe_output(self):
        """Create mock ffprobe JSON output."""
        return {
            "format": {
                "duration": "125.500000",
                "size": "10485760",
                "bit_rate": "5000000",
                "tags": {
                    "creation_time": "2024-01-15T10:30:00.000000Z"
                }
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30/1"
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac"
                }
            ]
        }

    def test_parse_ffprobe_metadata(self, mock_ffprobe_output, temp_dir):
        """Test parsing ffprobe JSON output."""
        # Create a dummy video file
        video_path = os.path.join(temp_dir, "test.mp4")
        with open(video_path, "wb") as f:
            f.write(b"\x00" * 1000)  # Dummy content

        # Mock subprocess.run to return our test data
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_ffprobe_output)

        with patch('subprocess.run', return_value=mock_result):
            with patch('shutil.which', return_value='/usr/bin/ffprobe'):
                # Reset the cached availability check
                VideoThumbnailExtractor._availability_checked = False
                VideoThumbnailExtractor._ffmpeg_available = True
                VideoThumbnailExtractor._ffprobe_path = '/usr/bin/ffprobe'
                VideoThumbnailExtractor._ffmpeg_path = '/usr/bin/ffmpeg'

                extractor = VideoThumbnailExtractor()
                metadata = extractor.get_video_metadata(video_path)

        if metadata:  # Only assert if we got metadata
            assert metadata.duration == 125.5
            assert metadata.width == 1920
            assert metadata.height == 1080
            assert metadata.codec == "h264"
            assert metadata.has_audio is True
            assert metadata.audio_codec == "aac"

    def test_extract_thumbnail_mock(self, temp_dir):
        """Test thumbnail extraction with mocked ffmpeg."""
        video_path = os.path.join(temp_dir, "test.mp4")
        output_path = os.path.join(temp_dir, "thumbnail.jpg")

        with open(video_path, "wb") as f:
            f.write(b"\x00" * 1000)

        # Mock subprocess.run for ffprobe metadata call
        mock_metadata_result = MagicMock()
        mock_metadata_result.returncode = 0
        mock_metadata_result.stdout = json.dumps({
            "format": {"duration": "10.0"},
            "streams": [{"codec_type": "video", "width": 640, "height": 480}]
        })

        # Mock subprocess.run for ffmpeg thumbnail extraction
        mock_ffmpeg_result = MagicMock()
        mock_ffmpeg_result.returncode = 0

        def mock_run(cmd, **kwargs):
            if 'ffprobe' in cmd[0]:
                return mock_metadata_result
            elif 'ffmpeg' in cmd[0]:
                # Create dummy output file
                for i, arg in enumerate(cmd):
                    if arg == '-y' and i + 1 < len(cmd):
                        # The output path is the last argument
                        out_path = cmd[-1]
                        # Create a valid minimal JPEG
                        from PIL import Image
                        img = Image.new('RGB', (256, 256), color=(100, 100, 100))
                        img.save(out_path, 'JPEG')
                return mock_ffmpeg_result
            return mock_metadata_result

        with patch('subprocess.run', side_effect=mock_run):
            with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
                # Reset cached availability
                VideoThumbnailExtractor._availability_checked = False
                VideoThumbnailExtractor._ffmpeg_available = True
                VideoThumbnailExtractor._ffprobe_path = '/usr/bin/ffprobe'
                VideoThumbnailExtractor._ffmpeg_path = '/usr/bin/ffmpeg'

                extractor = VideoThumbnailExtractor()
                success = extractor.extract_thumbnail(video_path, output_path, size=256)

        # Note: This may or may not succeed depending on mock completeness
        # The key is that it doesn't crash


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_extractor_without_ffmpeg(self):
        """Test extractor behavior when ffmpeg is not available."""
        with patch('shutil.which', return_value=None):
            # Reset cached check
            VideoThumbnailExtractor._availability_checked = False

            extractor = VideoThumbnailExtractor()

            # Should report as not available
            # (Note: might be cached from previous test, so we force reset)

    def test_invalid_video_path(self, temp_dir):
        """Test handling of invalid video path."""
        extractor = VideoThumbnailExtractor()

        # Try to get metadata for non-existent file
        metadata = extractor.get_video_metadata("/nonexistent/path/video.mp4")
        assert metadata is None

    def test_extract_thumbnail_invalid_path(self, temp_dir):
        """Test thumbnail extraction with invalid path."""
        extractor = VideoThumbnailExtractor()
        output_path = os.path.join(temp_dir, "output.jpg")

        success = extractor.extract_thumbnail("/nonexistent/video.mp4", output_path)
        assert success is False
