"""
Mock Data Factory

Creates mock data for testing:
- Settings configurations
- Database records
- File metadata
"""

import json
from datetime import datetime
from typing import Dict, List, Optional


class MockDataFactory:
    """Factory for creating mock data structures."""

    @staticmethod
    def create_settings(
        source_directories: Optional[List[str]] = None,
        destination_directory: str = "/tmp/test_archive",
        database_path: str = ":memory:",
        **overrides
    ) -> Dict:
        """
        Create mock settings dictionary.

        Args:
            source_directories: List of source paths
            destination_directory: Archive destination
            database_path: Database file path
            **overrides: Additional settings to override defaults

        Returns:
            Settings dictionary
        """
        if source_directories is None:
            source_directories = ["/tmp/test_source"]

        settings = {
            "source_directory": source_directories,
            "destination_directory": destination_directory,
            "database_path": database_path,
            "batch_size": 100,
            "include_subdirectories": True,
            "file_endings": [".jpg", ".png", ".heic", ".jpeg", ".tif", ".mov", ".mp4"],
            "group_by_year": True,
            "group_by_day": True,
            "copy_files": True,
            "move_files": False,
            "partial_hash_enabled": True,
            "partial_hash_bytes": 16384,
            "partial_hash_min_file_size": 1048576,
            "photo_filter_enabled": True,
            "min_file_size": 51200,
            "min_width": 800,
            "min_height": 600,
            "max_width": 50000,
            "max_height": 50000,
            "exclude_square_smaller_than": 400,
            "require_exif": False,
            "excluded_filename_patterns": ["favicon", "icon", "logo", "thumb", "button"],
            "move_filtered_files": False,
            "filtered_files_folder": "filtered_non_photos",
            "organization_template": "{year}/{month}/{day}",
            "enable_file_rename": False,
            "filename_template": "{original_name}"
        }

        # Apply overrides
        settings.update(overrides)
        return settings

    @staticmethod
    def create_database_metadata(
        database_name: str = "Test Database",
        archive_location: str = "/tmp/test_archive",
        **overrides
    ) -> Dict:
        """
        Create mock database metadata record.

        Args:
            database_name: Name of database
            archive_location: Archive path
            **overrides: Additional metadata fields

        Returns:
            Metadata dictionary
        """
        metadata = {
            "database_name": database_name,
            "description": "Test database for automated tests",
            "archive_location": archive_location,
            "video_archive_location": None,
            "created_date": datetime.now().isoformat(),
            "last_used_date": datetime.now().isoformat(),
            "total_photos": 0,
            "organization_template": "{year}/{month}/{day}",
            "enable_file_rename": 0,
            "filename_template": "{original_name}",
            "user_specified_unreliable_paths": "[]",
            "schema_version": 1
        }

        metadata.update(overrides)
        return metadata

    @staticmethod
    def create_file_record(
        file_hash: str = "abc123...",
        file_path: str = "/tmp/test.jpg",
        creation_date: Optional[datetime] = None,
        **overrides
    ) -> Dict:
        """
        Create mock file record for UniquePhotos table.

        Args:
            file_hash: SHA-256 hash
            file_path: File path
            creation_date: File creation date
            **overrides: Additional fields

        Returns:
            File record dictionary
        """
        if creation_date is None:
            creation_date = datetime.now()

        record = {
            "file_hash": file_hash,
            "file_path": file_path,
            "year": creation_date.year,
            "month": f"{creation_date.month:02d}",
            "day": f"{creation_date.day:02d}",
            "creation_date": creation_date.strftime("%Y-%m-%d %H:%M:%S"),
            "date_source": "exif",
            "partial_hash": file_hash[:32] if len(file_hash) > 32 else None,
            "file_size": 1024000,
            "import_timestamp": datetime.now().isoformat()
        }

        record.update(overrides)
        return record

    @staticmethod
    def create_unreliable_date_record(
        file_hash: str = "abc123...",
        source_path: str = "/tmp/source/test.jpg",
        archive_path: str = "/tmp/archive/2024/01/01/test.jpg",
        flag_reason: str = "no_exif",
        **overrides
    ) -> Dict:
        """
        Create mock unreliable date record.

        Args:
            file_hash: SHA-256 hash
            source_path: Original source path
            archive_path: Archive location
            flag_reason: Reason for flagging
            **overrides: Additional fields

        Returns:
            Unreliable date record dictionary
        """
        record = {
            "file_hash": file_hash,
            "source_path": source_path,
            "archive_path": archive_path,
            "original_date": "2024-01-01",
            "date_source": "os_metadata",
            "flag_reason": flag_reason,
            "flag_timestamp": datetime.now().isoformat(),
            "corrected_date": None,
            "correction_timestamp": None,
            "needs_reorganization": 0,
            "original_archive_path": None
        }

        record.update(overrides)
        return record

    @staticmethod
    def create_audit_session(
        session_id: Optional[str] = None,
        status: str = "completed",
        **overrides
    ) -> Dict:
        """
        Create mock audit session record.

        Args:
            session_id: Session ID (auto-generated if None)
            status: Session status
            **overrides: Additional fields

        Returns:
            Audit session dictionary
        """
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S_000000")

        session = {
            "session_id": session_id,
            "start_timestamp": datetime.now().isoformat(),
            "end_timestamp": datetime.now().isoformat() if status != "running" else None,
            "status": status,
            "source_directories": json.dumps(["/tmp/test_source"]),
            "destination_directory": "/tmp/test_archive",
            "operation_mode": "copy",
            "total_files_scanned": 0,
            "total_files_processed": 0,
            "total_unique_files": 0,
            "total_duplicates": 0,
            "total_filtered": 0,
            "total_errors": 0,
            "error_summary": "{}"
        }

        session.update(overrides)
        return session

    @staticmethod
    def create_file_operation_log(
        session_id: str,
        source_path: str,
        operation: str = "copy",
        status: str = "success",
        **overrides
    ) -> Dict:
        """
        Create mock file operation log record.

        Args:
            session_id: Parent session ID
            source_path: Source file path
            operation: Operation type
            status: Operation status
            **overrides: Additional fields

        Returns:
            File operation log dictionary
        """
        log = {
            "session_id": session_id,
            "source_path": source_path,
            "destination_path": None if operation.startswith("skip") else f"/tmp/archive/{source_path.split('/')[-1]}",
            "file_hash": "abc123..." if operation not in ["error", "skip_filtered"] else None,
            "operation": operation,
            "status": status,
            "file_size": 1024000,
            "creation_date": "2024-01-01",
            "date_source": "exif",
            "hash_verification_status": "passed" if status == "success" else None,
            "process_timestamp": datetime.now().isoformat(),
            "duration_ms": 150,
            "error_code": None if status == "success" else "IO_ERROR",
            "error_message": None if status == "success" else "Test error",
            "duplicate_of_hash": None if operation != "skip_duplicate" else "def456...",
            "filter_reason": None if operation != "skip_filtered" else "too_small"
        }

        log.update(overrides)
        return log

    @staticmethod
    def save_settings_to_file(settings: Dict, path: str):
        """
        Save settings dictionary to JSON file.

        Args:
            settings: Settings dictionary
            path: File path to save to
        """
        with open(path, 'w') as f:
            json.dump(settings, f, indent=2)
