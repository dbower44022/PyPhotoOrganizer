"""
Unit tests for CloudSync module.

Tests the high-level sync orchestration without requiring cloud services.
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from cloud_sync import (
    CloudSync,
    ConflictResolution,
    SyncStats,
    FileConflict,
)


class TestSyncStats(unittest.TestCase):
    """Tests for SyncStats dataclass."""

    def test_default_values(self):
        """Test SyncStats default values."""
        stats = SyncStats()
        self.assertEqual(stats.total_files, 0)
        self.assertEqual(stats.files_uploaded, 0)
        self.assertEqual(stats.files_downloaded, 0)
        self.assertEqual(stats.files_skipped, 0)
        self.assertEqual(stats.files_failed, 0)
        self.assertEqual(stats.bytes_transferred, 0)
        self.assertEqual(stats.errors, [])

    def test_str_representation(self):
        """Test SyncStats string representation."""
        stats = SyncStats(
            files_uploaded=10,
            files_downloaded=5,
            files_skipped=2,
            files_failed=1,
            bytes_transferred=1024 * 1024 * 100  # 100 MB
        )
        s = str(stats)
        self.assertIn("10 uploaded", s)
        self.assertIn("5 downloaded", s)
        self.assertIn("2 skipped", s)
        self.assertIn("1 failed", s)
        self.assertIn("100.0 MB", s)


class TestConflictResolution(unittest.TestCase):
    """Tests for ConflictResolution enum."""

    def test_resolution_values(self):
        """Test all resolution values exist."""
        self.assertEqual(ConflictResolution.KEEP_LOCAL.value, 'keep_local')
        self.assertEqual(ConflictResolution.KEEP_CLOUD.value, 'keep_cloud')
        self.assertEqual(ConflictResolution.KEEP_BOTH.value, 'keep_both')
        self.assertEqual(ConflictResolution.SKIP.value, 'skip')
        self.assertEqual(ConflictResolution.ASK.value, 'ask')


class TestFileConflict(unittest.TestCase):
    """Tests for FileConflict dataclass."""

    def test_create_conflict(self):
        """Test creating a FileConflict."""
        conflict = FileConflict(
            file_hash='abc123',
            relative_path='2024/01/photo.jpg',
            local_size=1000,
            cloud_size=1001,
            local_modified=datetime.now(),
            cloud_modified=None,
            local_exists=True,
            cloud_exists=True,
            conflict_type='size_mismatch'
        )
        self.assertEqual(conflict.file_hash, 'abc123')
        self.assertEqual(conflict.conflict_type, 'size_mismatch')
        self.assertTrue(conflict.local_exists)
        self.assertTrue(conflict.cloud_exists)


class TestCloudSyncWithMocks(unittest.TestCase):
    """Tests for CloudSync with mocked dependencies."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')

        # Create database schema
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()

        # Create required tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UniquePhotos (
                file_hash TEXT PRIMARY KEY,
                file_name TEXT,
                file_size INTEGER,
                relative_path TEXT,
                storage_type TEXT DEFAULT 'archive'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS CloudSyncStatus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                storage_location TEXT NOT NULL,
                cloud_provider TEXT,
                cloud_path TEXT,
                upload_status TEXT DEFAULT 'pending',
                UNIQUE (file_hash, storage_location, cloud_provider)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS CloudUploadQueue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                local_path TEXT NOT NULL,
                target_storage TEXT NOT NULL,
                target_path TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                queued_at TEXT,
                attempts INTEGER DEFAULT 0,
                last_attempt TEXT,
                last_error TEXT,
                status TEXT DEFAULT 'queued'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FileLocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                location_type TEXT NOT NULL,
                storage_backend TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                verified_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DatabaseMetadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                archive_location TEXT
            )
        """)
        cursor.execute("INSERT INTO DatabaseMetadata (id, archive_location) VALUES (1, ?)",
                      (self.temp_dir,))

        conn.commit()
        conn.close()

        # Create mock storage manager
        self.mock_storage_manager = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_sync_status_summary_empty(self):
        """Test get_sync_status_summary with empty database."""
        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        # Mock backend returns local storage
        mock_backend = MagicMock()
        mock_backend.storage_type = 'local'
        self.mock_storage_manager.get_backend.return_value = mock_backend

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)
        summary = cloud_sync.get_sync_status_summary('archive')

        self.assertEqual(summary['total_files'], 0)
        self.assertEqual(summary['synced_files'], 0)
        self.assertEqual(summary['sync_percentage'], 0)

    def test_get_sync_status_summary_with_files(self):
        """Test get_sync_status_summary with files in database."""
        # Add test files
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Add files to UniquePhotos
        for i in range(10):
            cursor.execute("""
                INSERT INTO UniquePhotos (file_hash, file_name, file_size, relative_path, storage_type)
                VALUES (?, ?, ?, ?, 'archive')
            """, (f'hash{i}', f'photo{i}.jpg', 1000 * i, f'2024/01/photo{i}.jpg'))

        # Mark some as synced
        for i in range(5):
            cursor.execute("""
                INSERT INTO CloudSyncStatus (file_hash, storage_location, upload_status)
                VALUES (?, 'archive', 'completed')
            """, (f'hash{i}',))

        conn.commit()
        conn.close()

        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        # Mock backend returns s3 storage
        mock_backend = MagicMock()
        mock_backend.storage_type = 's3'
        self.mock_storage_manager.get_backend.return_value = mock_backend

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)
        summary = cloud_sync.get_sync_status_summary('archive')

        self.assertEqual(summary['total_files'], 10)
        self.assertEqual(summary['synced_files'], 5)
        self.assertEqual(summary['sync_percentage'], 50.0)
        self.assertEqual(summary['needs_sync'], 5)

    def test_find_files_needing_upload_local_vault(self):
        """Test that local vaults return no files for upload."""
        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        # Mock backend returns local storage
        mock_backend = MagicMock()
        mock_backend.storage_type = 'local'
        self.mock_storage_manager.get_backend.return_value = mock_backend

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)
        files = list(cloud_sync.find_files_needing_upload('archive'))

        self.assertEqual(len(files), 0)

    def test_find_files_needing_upload_cloud_vault(self):
        """Test finding files that need upload to cloud."""
        # Add test files
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Add files to UniquePhotos (unsynced)
        for i in range(5):
            cursor.execute("""
                INSERT INTO UniquePhotos (file_hash, file_name, file_size, relative_path, storage_type)
                VALUES (?, ?, ?, ?, 'archive')
            """, (f'hash{i}', f'photo{i}.jpg', 1000 * i, f'2024/01/photo{i}.jpg'))

        conn.commit()
        conn.close()

        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        # Mock backend returns s3 storage
        mock_backend = MagicMock()
        mock_backend.storage_type = 's3'
        self.mock_storage_manager.get_backend.return_value = mock_backend

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)
        files = list(cloud_sync.find_files_needing_upload('archive'))

        self.assertEqual(len(files), 5)
        self.assertEqual(files[0]['file_hash'], 'hash0')

    def test_queue_all_for_sync(self):
        """Test queuing all files for sync."""
        # Add test files
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create a test file
        test_file_path = os.path.join(self.temp_dir, '2024', '01', 'photo.jpg')
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, 'w') as f:
            f.write('test content')

        cursor.execute("""
            INSERT INTO UniquePhotos (file_hash, file_name, file_size, relative_path, storage_type)
            VALUES ('hash1', 'photo.jpg', 1000, '2024/01/photo.jpg', 'archive')
        """)
        conn.commit()
        conn.close()

        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        # Mock backend for cloud
        mock_backend = MagicMock()
        mock_backend.storage_type = 's3'
        self.mock_storage_manager.get_backend.return_value = mock_backend

        # Mock local backend
        mock_local_backend = MagicMock()
        mock_local_backend.resolve_path.return_value = test_file_path

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)

        # Patch the _get_local_backend_for_vault method
        with patch.object(cloud_sync, '_get_local_backend_for_vault', return_value=mock_local_backend):
            count = cloud_sync.queue_all_for_sync('archive')

        self.assertEqual(count, 1)
        mock_sync_manager.queue_upload.assert_called_once()

    def test_clear_failed_uploads_delete(self):
        """Test clearing failed uploads."""
        # Add failed upload
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO CloudUploadQueue (file_hash, local_path, target_storage, target_path, status)
            VALUES ('hash1', '/path/to/file', 'archive', '2024/01/photo.jpg', 'failed')
        """)
        conn.commit()
        conn.close()

        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)
        affected = cloud_sync.clear_failed_uploads('archive', retry=False)

        self.assertEqual(affected, 1)

        # Verify deleted
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM CloudUploadQueue WHERE status = 'failed'")
        count = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(count, 0)

    def test_clear_failed_uploads_retry(self):
        """Test retrying failed uploads."""
        # Add failed upload
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO CloudUploadQueue (file_hash, local_path, target_storage, target_path, status, attempts)
            VALUES ('hash1', '/path/to/file', 'archive', '2024/01/photo.jpg', 'failed', 3)
        """)
        conn.commit()
        conn.close()

        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)
        affected = cloud_sync.clear_failed_uploads('archive', retry=True)

        self.assertEqual(affected, 1)

        # Verify reset to queued
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, attempts FROM CloudUploadQueue")
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row[0], 'queued')
        self.assertEqual(row[1], 0)


class TestResolveConflict(unittest.TestCase):
    """Tests for conflict resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')

        # Create minimal database
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DatabaseMetadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                archive_location TEXT
            )
        """)
        cursor.execute("INSERT INTO DatabaseMetadata (id, archive_location) VALUES (1, ?)",
                      (self.temp_dir,))
        conn.commit()
        conn.close()

        self.mock_storage_manager = MagicMock()

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_resolve_skip(self):
        """Test SKIP resolution always returns True."""
        mock_sync_manager = MagicMock()
        mock_sync_manager.storage_manager = self.mock_storage_manager

        cloud_sync = CloudSync(self.db_path, mock_sync_manager)

        conflict = FileConflict(
            file_hash='abc123',
            relative_path='2024/01/photo.jpg',
            local_size=1000,
            cloud_size=1001,
            local_modified=None,
            cloud_modified=None,
            local_exists=True,
            cloud_exists=True,
            conflict_type='size_mismatch'
        )

        result = cloud_sync.resolve_conflict(conflict, ConflictResolution.SKIP)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
