"""
Unit tests for PhotoDatabase class.

Tests:
- Database initialization
- Insert/query operations
- Context manager behavior
- Transaction handling
- Hash lookups (full and partial)
- Error handling
"""

import os
import sqlite3
import pytest
from datetime import datetime

from DuplicateFileDetection import PhotoDatabase
from database_metadata import DatabaseMetadata


class TestPhotoDatabaseInitialization:
    """Test database initialization and schema creation."""

    def test_create_new_database(self, test_db_path):
        """Test creating a new database file."""
        assert not os.path.exists(test_db_path)

        DatabaseMetadata.create_database(test_db_path)

        assert os.path.exists(test_db_path)

    def test_database_has_required_tables(self, empty_database):
        """Test that all required tables are created."""
        conn = sqlite3.connect(empty_database)
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = [
            'UniquePhotos',
            'DatabaseMetadata',
            'SourceDirectories',
            'UnreliableDates',
            'FileHashHistory',
            'FileRenameHistory',
            'ImportSession',
            'FileProcessingLog',
            'DuplicateMapping',
            'AuditRetentionSettings'
        ]

        for table in required_tables:
            assert table in tables, f"Table {table} should exist"

        conn.close()

    def test_initialize_metadata(self, empty_database, dest_dir):
        """Test metadata initialization."""
        metadata = DatabaseMetadata(empty_database)

        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir,
            description="Test database"
        )

        # Verify metadata was stored
        md = metadata.get_metadata()
        assert md['database_name'] == "Test DB"
        assert md['archive_location'] == dest_dir


class TestPhotoDatabaseContextManager:
    """Test PhotoDatabase context manager behavior."""

    def test_context_manager_basic(self, empty_database):
        """Test basic context manager usage."""
        with PhotoDatabase(empty_database) as db:
            assert db.conn is not None
            assert db.cursor is not None

    def test_context_manager_commit(self, empty_database):
        """Test that changes are committed on successful exit."""
        with PhotoDatabase(empty_database) as db:
            db.insert_unique_photo(
                file_hash="test_hash_123",
                file_path="/test/photo.jpg",
                year="2024",
                month="06",
                day="15",
                creation_date="2024-06-15 10:00:00",
                date_source="exif",
                partial_hash=None,
                file_size=1024000
            )

        # Verify data was committed
        with PhotoDatabase(empty_database) as db:
            hashes = db.get_all_hashes()
            assert "test_hash_123" in hashes

    def test_context_manager_rollback_on_error(self, empty_database):
        """Test that changes are rolled back on error."""
        try:
            with PhotoDatabase(empty_database) as db:
                db.insert_unique_photo(
                    file_hash="hash_1",
                    file_path="/test/photo1.jpg",
                    year="2024",
                    month="01",
                    day="01",
                    creation_date="2024-01-01 10:00:00",
                    date_source="exif",
                    partial_hash=None,
                    file_size=1024000
                )

                # Raise an error to trigger rollback
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify data was NOT committed
        with PhotoDatabase(empty_database) as db:
            hashes = db.get_all_hashes()
            assert "hash_1" not in hashes


class TestPhotoDatabaseInsertOperations:
    """Test database insert operations."""

    def test_insert_unique_photo(self, empty_database):
        """Test inserting a unique photo record."""
        with PhotoDatabase(empty_database) as db:
            db.insert_unique_photo(
                file_hash="abc123def456",
                file_path="/archive/2024/06/15/vacation.jpg",
                year="2024",
                month="06",
                day="15",
                creation_date="2024-06-15 14:30:00",
                date_source="exif",
                partial_hash="abc123",
                file_size=2048000
            )

        # Verify insertion
        with PhotoDatabase(empty_database) as db:
            hashes = db.get_all_hashes()
            assert "abc123def456" in hashes

    def test_insert_multiple_photos(self, empty_database):
        """Test inserting multiple photo records."""
        test_data = [
            ("hash1", "/path/1.jpg", "2024", "01", "01", "2024-01-01 10:00:00", "exif", None, 1000000),
            ("hash2", "/path/2.jpg", "2024", "01", "02", "2024-01-02 11:00:00", "exif", None, 2000000),
            ("hash3", "/path/3.jpg", "2024", "01", "03", "2024-01-03 12:00:00", "os_metadata", None, 3000000),
        ]

        with PhotoDatabase(empty_database) as db:
            for data in test_data:
                db.insert_unique_photo(*data)

        # Verify all were inserted
        with PhotoDatabase(empty_database) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == 3
            assert "hash1" in hashes
            assert "hash2" in hashes
            assert "hash3" in hashes

    def test_insert_duplicate_hash_constraint(self, empty_database):
        """Test that duplicate hashes are prevented by unique constraint."""
        with PhotoDatabase(empty_database) as db:
            db.insert_unique_photo(
                file_hash="duplicate_hash",
                file_path="/path/original.jpg",
                year="2024",
                month="01",
                day="01",
                creation_date="2024-01-01 10:00:00",
                date_source="exif",
                partial_hash=None,
                file_size=1000000
            )

        # Try to insert same hash again
        with pytest.raises(sqlite3.IntegrityError):
            with PhotoDatabase(empty_database) as db:
                db.insert_unique_photo(
                    file_hash="duplicate_hash",  # Same hash
                    file_path="/path/duplicate.jpg",
                    year="2024",
                    month="01",
                    day="02",
                    creation_date="2024-01-02 11:00:00",
                    date_source="exif",
                    partial_hash=None,
                    file_size=1000000
                )


class TestPhotoDatabaseQueryOperations:
    """Test database query operations."""

    def test_get_all_hashes(self, populated_database):
        """Test retrieving all hashes."""
        with PhotoDatabase(populated_database) as db:
            hashes = db.get_all_hashes()

            assert len(hashes) >= 3  # From fixture
            assert all(isinstance(h, str) for h in hashes)

    def test_get_all_hashes_empty_database(self, empty_database):
        """Test get_all_hashes on empty database."""
        with PhotoDatabase(empty_database) as db:
            hashes = db.get_all_hashes()

            assert hashes == []

    def test_get_partial_hashes(self, empty_database):
        """Test retrieving partial hashes."""
        # Insert records with partial hashes
        test_data = [
            ("hash1", "/path/1.jpg", "2024", "01", "01", "2024-01-01 10:00:00", "exif", "partial1", 1000000),
            ("hash2", "/path/2.jpg", "2024", "01", "02", "2024-01-02 11:00:00", "exif", "partial2", 2000000),
        ]

        with PhotoDatabase(empty_database) as db:
            for data in test_data:
                db.insert_unique_photo(*data)

            # Query partial hashes
            conn = db.conn
            cursor = conn.cursor()
            cursor.execute("SELECT partial_hash FROM UniquePhotos WHERE partial_hash IS NOT NULL")
            partial_hashes = [row[0] for row in cursor.fetchall()]

            assert len(partial_hashes) == 2
            assert "partial1" in partial_hashes
            assert "partial2" in partial_hashes


class TestHashHistoryOperations:
    """Test hash history tracking."""

    def test_add_hash_to_history(self, empty_database):
        """Test adding hash history record."""
        # First insert a photo
        with PhotoDatabase(empty_database) as db:
            db.insert_unique_photo(
                file_hash="original_hash",
                file_path="/archive/photo.jpg",
                year="2024",
                month="06",
                day="15",
                creation_date="2024-06-15 10:00:00",
                date_source="exif",
                partial_hash=None,
                file_size=1024000
            )

            # Add to hash history
            db.add_hash_to_history(
                old_hash="original_hash",
                new_hash="modified_hash",
                reason="date_correction"
            )

        # Verify history was recorded
        with PhotoDatabase(empty_database) as db:
            historical = db.get_all_historical_hashes()
            assert "original_hash" in historical
            assert "modified_hash" in historical

    def test_is_duplicate_hash_in_history(self, empty_database):
        """Test checking for historical hash matches."""
        with PhotoDatabase(empty_database) as db:
            # Insert photo
            db.insert_unique_photo(
                file_hash="current_hash",
                file_path="/archive/photo.jpg",
                year="2024",
                month="01",
                day="01",
                creation_date="2024-01-01 10:00:00",
                date_source="exif",
                partial_hash=None,
                file_size=1024000
            )

            # Add history
            db.add_hash_to_history("old_hash", "current_hash", "exif_edit")

            # Check for historical match
            assert db.is_duplicate_hash_in_history("old_hash") is True
            assert db.is_duplicate_hash_in_history("nonexistent_hash") is False


class TestDatabasePerformance:
    """Test database performance with larger datasets."""

    @pytest.mark.slow
    def test_batch_insert_performance(self, empty_database):
        """Test inserting many records."""
        import time

        num_records = 1000

        start = time.time()
        with PhotoDatabase(empty_database) as db:
            for i in range(num_records):
                db.insert_unique_photo(
                    file_hash=f"hash_{i:06d}",
                    file_path=f"/archive/2024/01/{i%31+1:02d}/photo_{i}.jpg",
                    year="2024",
                    month="01",
                    day=f"{i%31+1:02d}",
                    creation_date=f"2024-01-{i%31+1:02d} 10:00:00",
                    date_source="exif",
                    partial_hash=None,
                    file_size=1024000 + i*1000
                )
        duration = time.time() - start

        # Verify all were inserted
        with PhotoDatabase(empty_database) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == num_records

        # Should complete in reasonable time (< 10 seconds for 1000 records)
        assert duration < 10, f"Batch insert took {duration:.2f}s, should be < 10s"

    @pytest.mark.slow
    def test_query_performance_large_dataset(self, empty_database):
        """Test query performance with many records."""
        import time

        # Insert 1000 records
        with PhotoDatabase(empty_database) as db:
            for i in range(1000):
                db.insert_unique_photo(
                    file_hash=f"hash_{i:06d}",
                    file_path=f"/archive/photo_{i}.jpg",
                    year="2024",
                    month="01",
                    day="01",
                    creation_date="2024-01-01 10:00:00",
                    date_source="exif",
                    partial_hash=f"partial_{i:06d}",
                    file_size=1024000
                )

        # Time hash retrieval
        start = time.time()
        with PhotoDatabase(empty_database) as db:
            hashes = db.get_all_hashes()
        query_duration = time.time() - start

        assert len(hashes) == 1000
        # Should be very fast (< 1 second)
        assert query_duration < 1, f"Query took {query_duration:.2f}s, should be < 1s"
