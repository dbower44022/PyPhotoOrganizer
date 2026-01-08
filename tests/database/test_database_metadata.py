"""
Unit tests for DatabaseMetadata class.

Tests:
- Metadata initialization and retrieval
- Source directory management
- Unreliable dates management
- File rename settings
- Organization templates
- Database upgrades/migrations
"""

import os
import json
import pytest
from datetime import datetime

from database_metadata import DatabaseMetadata


class TestDatabaseMetadataInitialization:
    """Test metadata initialization and basic operations."""

    def test_initialize_metadata(self, empty_database, dest_dir):
        """Test initializing database metadata."""
        metadata = DatabaseMetadata(empty_database)

        metadata.initialize_metadata(
            database_name="Test Database",
            archive_location=dest_dir,
            description="Testing metadata"
        )

        md = metadata.get_metadata()

        assert md['database_name'] == "Test Database"
        assert md['archive_location'] == dest_dir
        assert md['description'] == "Testing metadata"
        assert md['total_photos'] == 0

    def test_get_metadata_empty(self, empty_database):
        """Test getting metadata from uninitialized database."""
        metadata = DatabaseMetadata(empty_database)
        md = metadata.get_metadata()

        # Should return default/empty metadata
        assert md is not None

    def test_update_metadata(self, empty_database, dest_dir):
        """Test updating existing metadata."""
        metadata = DatabaseMetadata(empty_database)

        metadata.initialize_metadata(
            database_name="Original Name",
            archive_location=dest_dir
        )

        # Update
        metadata.update_metadata(database_name="Updated Name")

        md = metadata.get_metadata()
        assert md['database_name'] == "Updated Name"


class TestSourceDirectoryManagement:
    """Test source directory CRUD operations."""

    def test_add_source_directory(self, empty_database):
        """Test adding a source directory."""
        metadata = DatabaseMetadata(empty_database)

        metadata.add_source_directory("/test/source1", enabled=True)
        metadata.add_source_directory("/test/source2", enabled=False)

        sources = metadata.get_all_source_directories()

        assert len(sources) == 2
        assert sources[0]['path'] == "/test/source1"
        assert sources[0]['enabled'] == 1
        assert sources[1]['path'] == "/test/source2"
        assert sources[1]['enabled'] == 0

    def test_remove_source_directory(self, empty_database):
        """Test removing a source directory."""
        metadata = DatabaseMetadata(empty_database)

        metadata.add_source_directory("/test/source1", enabled=True)
        metadata.add_source_directory("/test/source2", enabled=True)

        sources = metadata.get_all_source_directories()
        assert len(sources) == 2

        metadata.remove_source_directory("/test/source1")

        sources = metadata.get_all_source_directories()
        assert len(sources) == 1
        assert sources[0]['path'] == "/test/source2"

    def test_update_source_enabled(self, empty_database):
        """Test toggling source enabled status."""
        metadata = DatabaseMetadata(empty_database)

        metadata.add_source_directory("/test/source", enabled=True)
        sources = metadata.get_all_source_directories()
        assert sources[0]['enabled'] == 1

        metadata.update_source_enabled("/test/source", False)
        sources = metadata.get_all_source_directories()
        assert sources[0]['enabled'] == 0

    def test_update_source_last_scanned(self, empty_database):
        """Test updating source last scanned timestamp."""
        metadata = DatabaseMetadata(empty_database)

        metadata.add_source_directory("/test/source", enabled=True)

        timestamp = datetime.now().isoformat()
        metadata.update_source_last_scanned("/test/source", timestamp)

        sources = metadata.get_all_source_directories()
        assert sources[0]['last_scanned'] == timestamp

    def test_clear_all_source_directories(self, empty_database):
        """Test clearing all source directories."""
        metadata = DatabaseMetadata(empty_database)

        metadata.add_source_directory("/test/source1", enabled=True)
        metadata.add_source_directory("/test/source2", enabled=True)
        metadata.add_source_directory("/test/source3", enabled=True)

        sources = metadata.get_all_source_directories()
        assert len(sources) == 3

        metadata.clear_all_source_directories()

        sources = metadata.get_all_source_directories()
        assert len(sources) == 0


class TestUnreliableDatesManagement:
    """Test unreliable dates tracking."""

    def test_insert_unreliable_date(self, empty_database):
        """Test inserting unreliable date record."""
        metadata = DatabaseMetadata(empty_database)

        metadata.insert_unreliable_date(
            file_hash="test_hash",
            source_path="/source/photo.jpg",
            archive_path="/archive/2024/01/01/photo.jpg",
            original_date="2024-01-01",
            date_source="os_metadata",
            flag_reason="no_exif"
        )

        records = metadata.get_unreliable_dates()
        assert len(records) == 1
        assert records[0]['file_hash'] == "test_hash"
        assert records[0]['flag_reason'] == "no_exif"

    def test_get_unreliable_dates_with_filter(self, empty_database):
        """Test filtering unreliable dates by reason."""
        metadata = DatabaseMetadata(empty_database)

        # Insert various flag reasons
        metadata.insert_unreliable_date(
            file_hash="hash1",
            source_path="/source/1.jpg",
            archive_path="/archive/1.jpg",
            original_date="2024-01-01",
            date_source="os_metadata",
            flag_reason="no_exif"
        )

        metadata.insert_unreliable_date(
            file_hash="hash2",
            source_path="/source/2.jpg",
            archive_path="/archive/2.jpg",
            original_date="1970-01-01",
            date_source="fallback",
            flag_reason="year_1000"
        )

        metadata.insert_unreliable_date(
            file_hash="hash3",
            source_path="/source/3.jpg",
            archive_path="/archive/3.jpg",
            original_date="1985-01-01",
            date_source="exif",
            flag_reason="suspicious"
        )

        # Filter by specific reason
        no_exif = metadata.get_unreliable_dates(filter_reason="no_exif")
        assert len(no_exif) == 1
        assert no_exif[0]['flag_reason'] == "no_exif"

        # Get all
        all_records = metadata.get_unreliable_dates()
        assert len(all_records) == 3

    def test_update_corrected_date(self, empty_database):
        """Test updating corrected date."""
        metadata = DatabaseMetadata(empty_database)

        metadata.insert_unreliable_date(
            file_hash="test_hash",
            source_path="/source/photo.jpg",
            archive_path="/archive/photo.jpg",
            original_date="1970-01-01",
            date_source="os_metadata",
            flag_reason="suspicious"
        )

        # Correct the date
        metadata.update_corrected_date(
            file_hash="test_hash",
            corrected_date="2020-06-15",
            needs_reorganization=True
        )

        records = metadata.get_unreliable_dates()
        assert records[0]['corrected_date'] == "2020-06-15"
        assert records[0]['needs_reorganization'] == 1

    def test_get_files_needing_reorganization(self, empty_database):
        """Test retrieving files marked for reorganization."""
        metadata = DatabaseMetadata(empty_database)

        # Insert records with different reorganization status
        metadata.insert_unreliable_date(
            file_hash="hash1",
            source_path="/source/1.jpg",
            archive_path="/archive/1.jpg",
            original_date="2024-01-01",
            date_source="os_metadata",
            flag_reason="no_exif"
        )

        metadata.update_corrected_date("hash1", "2020-06-15", needs_reorganization=True)

        metadata.insert_unreliable_date(
            file_hash="hash2",
            source_path="/source/2.jpg",
            archive_path="/archive/2.jpg",
            original_date="2024-01-02",
            date_source="os_metadata",
            flag_reason="no_exif"
        )

        # Only hash1 needs reorganization
        to_reorganize = metadata.get_files_needing_reorganization()
        assert len(to_reorganize) == 1
        assert to_reorganize[0]['file_hash'] == "hash1"

    def test_mark_reorganized(self, empty_database):
        """Test marking file as reorganized."""
        metadata = DatabaseMetadata(empty_database)

        metadata.insert_unreliable_date(
            file_hash="test_hash",
            source_path="/source/photo.jpg",
            archive_path="/archive/old_location.jpg",
            original_date="2024-01-01",
            date_source="os_metadata",
            flag_reason="no_exif"
        )

        metadata.update_corrected_date("test_hash", "2020-06-15", needs_reorganization=True)
        metadata.mark_reorganized("test_hash", new_archive_path="/archive/new_location.jpg")

        records = metadata.get_unreliable_dates()
        assert records[0]['needs_reorganization'] == 0
        assert records[0]['archive_path'] == "/archive/new_location.jpg"


class TestFileRenameSettings:
    """Test file rename configuration."""

    def test_is_file_rename_enabled_default(self, empty_database, dest_dir):
        """Test default file rename setting."""
        metadata = DatabaseMetadata(empty_database)
        metadata.initialize_metadata(
            database_name="Test",
            archive_location=dest_dir
        )

        # Should be disabled by default
        assert metadata.is_file_rename_enabled() is False

    def test_set_file_rename_enabled(self, empty_database, dest_dir):
        """Test enabling/disabling file rename."""
        metadata = DatabaseMetadata(empty_database)
        metadata.initialize_metadata(
            database_name="Test",
            archive_location=dest_dir
        )

        metadata.set_file_rename_enabled(True)
        assert metadata.is_file_rename_enabled() is True

        metadata.set_file_rename_enabled(False)
        assert metadata.is_file_rename_enabled() is False

    def test_get_filename_template_default(self, empty_database, dest_dir):
        """Test default filename template."""
        metadata = DatabaseMetadata(empty_database)
        metadata.initialize_metadata(
            database_name="Test",
            archive_location=dest_dir
        )

        template = metadata.get_filename_template()
        assert template == "{original_name}"

    def test_set_filename_template(self, empty_database, dest_dir):
        """Test setting custom filename template."""
        metadata = DatabaseMetadata(empty_database)
        metadata.initialize_metadata(
            database_name="Test",
            archive_location=dest_dir
        )

        custom_template = "{year}{month}{day}_{counter:04d}"
        metadata.set_filename_template(custom_template)

        template = metadata.get_filename_template()
        assert template == custom_template

    def test_insert_rename_history(self, empty_database):
        """Test recording file rename history."""
        metadata = DatabaseMetadata(empty_database)

        metadata.insert_rename_history(
            file_hash="test_hash",
            original_filename="IMG_001.jpg",
            renamed_filename="20240615_0001.jpg"
        )

        # Verify it was recorded (query directly)
        conn = metadata._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM FileRenameHistory WHERE file_hash = ?", ("test_hash",))
        record = cursor.fetchone()
        conn.close()

        assert record is not None
        assert record[2] == "IMG_001.jpg"  # original_filename
        assert record[3] == "20240615_0001.jpg"  # renamed_filename


class TestUserSpecifiedPaths:
    """Test user-specified unreliable paths management."""

    def test_get_user_specified_paths_default(self, empty_database, dest_dir):
        """Test default user-specified paths (empty)."""
        metadata = DatabaseMetadata(empty_database)
        metadata.initialize_metadata(
            database_name="Test",
            archive_location=dest_dir
        )

        paths = metadata.get_user_specified_paths()
        assert paths == []

    def test_set_user_specified_paths(self, empty_database, dest_dir):
        """Test setting user-specified paths."""
        metadata = DatabaseMetadata(empty_database)
        metadata.initialize_metadata(
            database_name="Test",
            archive_location=dest_dir
        )

        test_paths = ["/old/scanned_photos", "/legacy/phone_backup"]
        metadata.set_user_specified_paths(test_paths)

        paths = metadata.get_user_specified_paths()
        assert paths == test_paths

    def test_set_user_specified_paths_json_storage(self, empty_database, dest_dir):
        """Test that paths are stored as JSON."""
        metadata = DatabaseMetadata(empty_database)
        metadata.initialize_metadata(
            database_name="Test",
            archive_location=dest_dir
        )

        test_paths = ["/path1", "/path2", "/path3"]
        metadata.set_user_specified_paths(test_paths)

        # Query raw value
        conn = metadata._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_specified_unreliable_paths FROM DatabaseMetadata")
        raw_value = cursor.fetchone()[0]
        conn.close()

        # Should be valid JSON
        parsed = json.loads(raw_value)
        assert parsed == test_paths


class TestDatabaseFind:
    """Test database discovery functionality."""

    def test_find_databases_in_directory(self, temp_dir):
        """Test finding PyPhotoOrganizer databases."""
        # Create multiple databases
        db1_path = os.path.join(temp_dir, "photos1.db")
        db2_path = os.path.join(temp_dir, "photos2.db")
        db3_path = os.path.join(temp_dir, "subdir", "photos3.db")

        os.makedirs(os.path.dirname(db3_path), exist_ok=True)

        for db_path in [db1_path, db2_path, db3_path]:
            DatabaseMetadata.create_database(db_path)
            metadata = DatabaseMetadata(db_path)
            metadata.initialize_metadata(
                database_name=f"DB {os.path.basename(db_path)}",
                archive_location=temp_dir
            )

        # Find databases
        found = DatabaseMetadata.find_databases(temp_dir)

        # Should find all 3
        assert len(found) >= 3


class TestDatabaseUpgrades:
    """Test database schema upgrades."""

    def test_ensure_all_tables(self, empty_database):
        """Test that ensure_all_tables adds missing tables."""
        metadata = DatabaseMetadata(empty_database)

        # ensure_all_tables should be called during initialization
        metadata.ensure_all_tables()

        # Verify all tables exist
        conn = metadata._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        required_tables = [
            'UniquePhotos',
            'DatabaseMetadata',
            'SourceDirectories',
            'UnreliableDates',
            'FileHashHistory'
        ]

        for table in required_tables:
            assert table in tables
