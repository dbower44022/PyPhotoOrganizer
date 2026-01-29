"""
Video Thumbnail Module

Provides ffmpeg/ffprobe integration for video processing:
- Thumbnail extraction from video frames
- Video duration retrieval
- Video metadata extraction (resolution, codec, bitrate)

Requirements:
- ffmpeg and ffprobe must be installed and in PATH
- Falls back to placeholder if ffmpeg is not available

Usage:
    from video_thumbnail import VideoThumbnailExtractor

    extractor = VideoThumbnailExtractor()

    # Check if ffmpeg is available
    if extractor.is_available():
        # Extract thumbnail
        success = extractor.extract_thumbnail(
            video_path="/path/to/video.mp4",
            output_path="/path/to/thumbnail.jpg",
            size=256
        )

        # Get video metadata
        metadata = extractor.get_video_metadata("/path/to/video.mp4")
        print(f"Duration: {metadata['duration_formatted']}")
        print(f"Resolution: {metadata['width']}x{metadata['height']}")
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from PIL import Image

import constants
import utils

logger = utils.setup_logger(__name__, "video_thumbnail.log")


@dataclass
class VideoMetadata:
    """Video metadata container."""
    duration: float  # Duration in seconds
    duration_formatted: str  # Formatted as HH:MM:SS or MM:SS
    width: int
    height: int
    codec: str
    bitrate: Optional[int]  # Bits per second
    fps: Optional[float]
    creation_time: Optional[str]  # ISO format timestamp
    has_audio: bool
    audio_codec: Optional[str]
    file_size: int


class VideoThumbnailExtractor:
    """
    Extracts thumbnails from video files using ffmpeg.

    This class provides methods for:
    - Checking ffmpeg availability
    - Extracting video thumbnails at specific timestamps
    - Getting video metadata (duration, resolution, codec)
    - Formatting duration for display

    Attributes:
        ffmpeg_path: Path to ffmpeg executable (auto-detected)
        ffprobe_path: Path to ffprobe executable (auto-detected)
        available: Whether ffmpeg/ffprobe are available
    """

    # Class-level cache for availability check
    _availability_checked = False
    _ffmpeg_available = False
    _ffmpeg_path = None
    _ffprobe_path = None

    def __init__(self):
        """Initialize the video thumbnail extractor."""
        self._check_availability()

    @classmethod
    def _check_availability(cls):
        """Check if ffmpeg and ffprobe are available (cached)."""
        if cls._availability_checked:
            return

        cls._ffmpeg_path = shutil.which('ffmpeg')
        cls._ffprobe_path = shutil.which('ffprobe')
        cls._ffmpeg_available = cls._ffmpeg_path is not None and cls._ffprobe_path is not None
        cls._availability_checked = True

        if cls._ffmpeg_available:
            logger.info(f"ffmpeg found at: {cls._ffmpeg_path}")
            logger.info(f"ffprobe found at: {cls._ffprobe_path}")
        else:
            logger.warning("ffmpeg/ffprobe not found - video thumbnails will use placeholders")

    def is_available(self) -> bool:
        """
        Check if ffmpeg is available for video processing.

        Returns:
            True if ffmpeg and ffprobe are installed and accessible
        """
        return self._ffmpeg_available

    @property
    def ffmpeg_path(self) -> Optional[str]:
        """Get path to ffmpeg executable."""
        return self._ffmpeg_path

    @property
    def ffprobe_path(self) -> Optional[str]:
        """Get path to ffprobe executable."""
        return self._ffprobe_path

    def get_video_metadata(self, video_path: str) -> Optional[VideoMetadata]:
        """
        Get metadata from a video file using ffprobe.

        Parameters:
            video_path: Path to the video file

        Returns:
            VideoMetadata object with video information, or None on error
        """
        if not self._ffmpeg_available:
            logger.warning("ffprobe not available - cannot get video metadata")
            return None

        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None

        try:
            # Run ffprobe to get JSON metadata
            result = subprocess.run(
                [
                    self._ffprobe_path,
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    '-show_streams',
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"ffprobe failed for {video_path}: {result.stderr}")
                return None

            data = json.loads(result.stdout)

            # Extract format info
            format_info = data.get('format', {})

            # Find video and audio streams
            video_stream = None
            audio_stream = None

            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video' and video_stream is None:
                    video_stream = stream
                elif stream.get('codec_type') == 'audio' and audio_stream is None:
                    audio_stream = stream

            if video_stream is None:
                logger.warning(f"No video stream found in {video_path}")
                return None

            # Parse duration
            duration = float(format_info.get('duration', 0))

            # Parse resolution
            width = video_stream.get('width', 0)
            height = video_stream.get('height', 0)

            # Parse codec
            codec = video_stream.get('codec_name', 'unknown')

            # Parse bitrate
            bitrate = None
            if 'bit_rate' in format_info:
                try:
                    bitrate = int(format_info['bit_rate'])
                except (ValueError, TypeError):
                    pass

            # Parse FPS
            fps = None
            fps_str = video_stream.get('avg_frame_rate', '0/1')
            if '/' in fps_str:
                num, denom = fps_str.split('/')
                try:
                    if int(denom) != 0:
                        fps = float(num) / float(denom)
                except (ValueError, ZeroDivisionError):
                    pass

            # Parse creation time
            creation_time = None
            tags = format_info.get('tags', {})
            creation_time = tags.get('creation_time') or tags.get('Creation_Time')

            # Audio info
            has_audio = audio_stream is not None
            audio_codec = audio_stream.get('codec_name') if audio_stream else None

            # File size
            file_size = int(format_info.get('size', 0))

            return VideoMetadata(
                duration=duration,
                duration_formatted=self.format_duration(duration),
                width=width,
                height=height,
                codec=codec,
                bitrate=bitrate,
                fps=fps,
                creation_time=creation_time,
                has_audio=has_audio,
                audio_codec=audio_codec,
                file_size=file_size
            )

        except subprocess.TimeoutExpired:
            logger.error(f"ffprobe timeout for {video_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ffprobe output for {video_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting video metadata for {video_path}: {e}")
            return None

    def extract_thumbnail(
        self,
        video_path: str,
        output_path: str,
        size: int = 256,
        timestamp: Optional[float] = None,
        quality: int = 85
    ) -> bool:
        """
        Extract a thumbnail from a video file.

        Parameters:
            video_path: Path to the video file
            output_path: Path to save the thumbnail (JPEG)
            size: Thumbnail size in pixels (square, maintains aspect ratio)
            timestamp: Specific timestamp in seconds to extract (default: auto-select)
            quality: JPEG quality (1-100, default: 85)

        Returns:
            True if thumbnail was successfully extracted
        """
        if not self._ffmpeg_available:
            logger.warning("ffmpeg not available - cannot extract thumbnail")
            return False

        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return False

        try:
            # Get video duration if timestamp not specified
            if timestamp is None:
                metadata = self.get_video_metadata(video_path)
                if metadata and metadata.duration > 0:
                    # Extract frame at 10% into the video (avoids black intro frames)
                    timestamp = min(metadata.duration * 0.1, 5.0)  # Max 5 seconds in
                else:
                    timestamp = 0.0

            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Use a temp file first to avoid partial writes
            temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(temp_fd)

            try:
                # Build ffmpeg command
                # -ss before -i for fast seeking
                # -vf scale for resizing with aspect ratio preservation
                # -vframes 1 for single frame
                # -pix_fmt yuvj420p for full-range YUV (required by mjpeg encoder)
                cmd = [
                    self._ffmpeg_path,
                    '-ss', str(timestamp),
                    '-i', video_path,
                    '-vf', f'scale={size}:{size}:force_original_aspect_ratio=decrease',
                    '-vframes', '1',
                    '-pix_fmt', 'yuvj420p',  # Full-range YUV for JPEG compatibility
                    '-q:v', str(max(1, min(31, 31 - int(quality * 0.3)))),  # ffmpeg quality (1=best, 31=worst)
                    '-y',  # Overwrite output
                    temp_path
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    logger.error(f"ffmpeg thumbnail extraction failed: {result.stderr}")
                    return False

                # Verify output file exists and has content
                if not os.path.exists(temp_path):
                    logger.error(f"Thumbnail file was not created: {temp_path}")
                    return False

                if os.path.getsize(temp_path) == 0:
                    logger.error(f"Thumbnail file is empty: {temp_path}")
                    os.remove(temp_path)
                    return False

                # Move temp file to final location
                shutil.move(temp_path, output_path)

                logger.debug(f"Extracted thumbnail from {video_path} at {timestamp}s -> {output_path}")
                return True

            finally:
                # Clean up temp file if it still exists
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

        except subprocess.TimeoutExpired:
            logger.error(f"ffmpeg timeout extracting thumbnail from {video_path}")
            return False
        except Exception as e:
            logger.error(f"Error extracting thumbnail from {video_path}: {e}")
            return False

    def extract_thumbnail_pil(
        self,
        video_path: str,
        size: int = 256,
        timestamp: Optional[float] = None
    ) -> Optional[Image.Image]:
        """
        Extract a thumbnail from a video file and return as PIL Image.

        This method extracts to a temp file and loads it as a PIL Image,
        which can then be processed further or converted to other formats.

        Parameters:
            video_path: Path to the video file
            size: Thumbnail size in pixels
            timestamp: Specific timestamp in seconds (default: auto-select)

        Returns:
            PIL Image object, or None on error
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg')
        os.close(temp_fd)

        try:
            if self.extract_thumbnail(video_path, temp_path, size, timestamp):
                img = Image.open(temp_path)
                # Copy the image data so we can close the file
                img = img.copy()
                return img
            return None
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

    def get_duration(self, video_path: str) -> Optional[float]:
        """
        Get the duration of a video file in seconds.

        Parameters:
            video_path: Path to the video file

        Returns:
            Duration in seconds, or None on error
        """
        metadata = self.get_video_metadata(video_path)
        if metadata:
            return metadata.duration
        return None

    def get_duration_formatted(self, video_path: str) -> Optional[str]:
        """
        Get the duration of a video file as formatted string.

        Parameters:
            video_path: Path to the video file

        Returns:
            Duration formatted as "HH:MM:SS" or "MM:SS", or None on error
        """
        metadata = self.get_video_metadata(video_path)
        if metadata:
            return metadata.duration_formatted
        return None

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds to human-readable string.

        Parameters:
            seconds: Duration in seconds

        Returns:
            Formatted string like "1:23:45" or "12:34"
        """
        if seconds <= 0:
            return "0:00"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    @staticmethod
    def format_bitrate(bitrate: int) -> str:
        """
        Format bitrate to human-readable string.

        Parameters:
            bitrate: Bitrate in bits per second

        Returns:
            Formatted string like "5.2 Mbps" or "320 kbps"
        """
        if bitrate >= 1_000_000:
            return f"{bitrate / 1_000_000:.1f} Mbps"
        elif bitrate >= 1000:
            return f"{bitrate / 1000:.0f} kbps"
        else:
            return f"{bitrate} bps"

    @staticmethod
    def format_resolution(width: int, height: int) -> str:
        """
        Format resolution to common name if applicable.

        Parameters:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Resolution string like "1080p" or "1920×1080"
        """
        # Common resolution names
        common_resolutions = {
            (3840, 2160): "4K UHD",
            (2560, 1440): "1440p",
            (1920, 1080): "1080p",
            (1280, 720): "720p",
            (854, 480): "480p",
            (640, 360): "360p",
        }

        # Check for exact match
        if (width, height) in common_resolutions:
            return common_resolutions[(width, height)]

        # Check for height-based match (some videos have different widths)
        height_names = {
            2160: "4K",
            1440: "1440p",
            1080: "1080p",
            720: "720p",
            480: "480p",
            360: "360p",
        }

        if height in height_names:
            return height_names[height]

        return f"{width}×{height}"


def is_video_file(file_path: str) -> bool:
    """
    Check if a file is a video based on extension.

    Parameters:
        file_path: Path to the file

    Returns:
        True if file has a video extension
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in [e.lower() for e in constants.VIDEO_EXTENSIONS]


def get_video_info_dict(video_path: str) -> Optional[Dict[str, Any]]:
    """
    Get video metadata as a dictionary (convenience function).

    Parameters:
        video_path: Path to the video file

    Returns:
        Dictionary with video info, or None on error
    """
    extractor = VideoThumbnailExtractor()
    metadata = extractor.get_video_metadata(video_path)

    if metadata is None:
        return None

    return {
        'duration': metadata.duration,
        'duration_formatted': metadata.duration_formatted,
        'width': metadata.width,
        'height': metadata.height,
        'resolution': VideoThumbnailExtractor.format_resolution(metadata.width, metadata.height),
        'codec': metadata.codec,
        'bitrate': metadata.bitrate,
        'bitrate_formatted': VideoThumbnailExtractor.format_bitrate(metadata.bitrate) if metadata.bitrate else None,
        'fps': metadata.fps,
        'creation_time': metadata.creation_time,
        'has_audio': metadata.has_audio,
        'audio_codec': metadata.audio_codec,
        'file_size': metadata.file_size,
    }


# Singleton instance for easy access
_extractor_instance: Optional[VideoThumbnailExtractor] = None


def get_extractor() -> VideoThumbnailExtractor:
    """Get the singleton VideoThumbnailExtractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = VideoThumbnailExtractor()
    return _extractor_instance


if __name__ == '__main__':
    # Test video thumbnail extraction
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print("Usage: python video_thumbnail.py <video_file> [output.jpg]")
        sys.exit(1)

    video_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "test_thumbnail.jpg"

    extractor = VideoThumbnailExtractor()

    print(f"ffmpeg available: {extractor.is_available()}")

    if not extractor.is_available():
        print("ffmpeg not found - install ffmpeg to extract video thumbnails")
        sys.exit(1)

    # Get metadata
    print(f"\nGetting metadata for: {video_path}")
    metadata = extractor.get_video_metadata(video_path)

    if metadata:
        print(f"  Duration: {metadata.duration_formatted}")
        print(f"  Resolution: {extractor.format_resolution(metadata.width, metadata.height)}")
        print(f"  Codec: {metadata.codec}")
        if metadata.bitrate:
            print(f"  Bitrate: {extractor.format_bitrate(metadata.bitrate)}")
        if metadata.fps:
            print(f"  FPS: {metadata.fps:.2f}")
        print(f"  Has Audio: {metadata.has_audio}")
        if metadata.audio_codec:
            print(f"  Audio Codec: {metadata.audio_codec}")
        if metadata.creation_time:
            print(f"  Creation Time: {metadata.creation_time}")
    else:
        print("  Failed to get metadata")

    # Extract thumbnail
    print(f"\nExtracting thumbnail to: {output_path}")
    if extractor.extract_thumbnail(video_path, output_path, size=256):
        print(f"  ✓ Thumbnail saved: {output_path}")
        print(f"  Size: {os.path.getsize(output_path)} bytes")
    else:
        print("  ✗ Thumbnail extraction failed")
