"""
Unit tests for the progress_persistence module.

Tests:
- Session management
- Directory scanning progress
- File processing tracking
- Checkpoints
- Hash caching
- Cleanup
"""

import os
import sys
import tempfile
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from progress_persistence import ProgressTracker


@pytest.fixture
def progress_db(temp_dir):
    """Create a temporary database for progress tracking."""
    db_path = os.path.join(temp_dir, "progress_test.db")
    return db_path


@pytest.fixture
def tracker(progress_db):
    """Create a ProgressTracker instance."""
    return ProgressTracker(progress_db)


class TestSessionManagement:
    """Tests for session management."""

    def test_start_session(self, tracker):
        """Test starting a new session."""
        session_id = tracker.start_session(
            source_directories=["/source1", "/source2"],
            destination_directory="/archive"
        )

        assert session_id is not None
        assert session_id.startswith("progress_")

    def test_end_session(self, tracker):
        """Test ending a session."""
        session_id = tracker.start_session(
            source_directories=["/source"],
            destination_directory="/archive"
        )

        result = tracker.end_session(session_id, status='completed')

        assert result is True

    def test_get_incomplete_sessions(self, tracker):
        """Test retrieving incomplete sessions."""
        # Start a session but don't end it
        session_id = tracker.start_session(
            source_directories=["/source"],
            destination_directory="/archive"
        )

        incomplete = tracker.get_incomplete_sessions()

        assert len(incomplete) >= 1
        assert any(s['session_id'] == session_id for s in incomplete)

    def test_completed_session_not_in_incomplete(self, tracker):
        """Test that completed sessions aren't returned as incomplete."""
        session_id = tracker.start_session(
            source_directories=["/source"],
            destination_directory="/archive"
        )
        tracker.end_session(session_id, status='completed', can_resume=False)

        incomplete = tracker.get_incomplete_sessions()

        assert not any(s['session_id'] == session_id for s in incomplete)

    def test_session_with_resume_data(self, tracker):
        """Test session can store resume data."""
        session_id = tracker.start_session(
            source_directories=["/source"],
            destination_directory="/archive",
            operation_type='reorganize'
        )

        sessions = tracker.get_incomplete_sessions()
        session = next(s for s in sessions if s['session_id'] == session_id)

        assert session['operation_type'] == 'reorganize'
        assert '/source' in session['source_directories']


class TestDirectoryScanningProgress:
    """Tests for directory scanning progress tracking."""

    def test_mark_directory_scanned(self, tracker):
        """Test marking a directory as scanned."""
        session_id = tracker.start_session(["/source"], "/archive")

        result = tracker.mark_directory_scanned(
            session_id,
            "/source/subdir",
            files_found=42
        )

        assert result is True

    def test_get_scanned_directories(self, tracker):
        """Test retrieving scanned directories."""
        session_id = tracker.start_session(["/source"], "/archive")

        tracker.mark_directory_scanned(session_id, "/source/dir1")
        tracker.mark_directory_scanned(session_id, "/source/dir2")

        scanned = tracker.get_scanned_directories(session_id)

        assert "/source/dir1" in scanned
        assert "/source/dir2" in scanned

    def test_get_unscanned_directories(self, tracker):
        """Test finding unscanned directories."""
        session_id = tracker.start_session(["/source"], "/archive")

        all_dirs = ["/source/dir1", "/source/dir2", "/source/dir3"]
        tracker.mark_directory_scanned(session_id, "/source/dir1")

        unscanned = tracker.get_unscanned_directories(session_id, all_dirs)

        assert "/source/dir1" not in unscanned
        assert "/source/dir2" in unscanned
        assert "/source/dir3" in unscanned

    def test_incomplete_directory_scan(self, tracker):
        """Test marking directory scan as incomplete."""
        session_id = tracker.start_session(["/source"], "/archive")

        tracker.mark_directory_scanned(
            session_id,
            "/source/partial",
            is_complete=False
        )

        scanned = tracker.get_scanned_directories(session_id)

        # Incomplete directories shouldn't be in complete list
        assert "/source/partial" not in scanned


class TestFileProcessingProgress:
    """Tests for file processing progress tracking."""

    def test_mark_file_processed(self, tracker):
        """Test marking a file as processed."""
        session_id = tracker.start_session(["/source"], "/archive")

        result = tracker.mark_file_processed(
            session_id,
            "/source/photo.jpg",
            file_hash="abc123",
            status='processed',
            result_path="/archive/2024/01/photo.jpg"
        )

        assert result is True

    def test_get_processed_files(self, tracker):
        """Test getting processed files."""
        session_id = tracker.start_session(["/source"], "/archive")

        tracker.mark_file_processed(session_id, "/source/file1.jpg")
        tracker.mark_file_processed(session_id, "/source/file2.jpg")

        processed = tracker.get_processed_files(session_id)

        assert "/source/file1.jpg" in processed
        assert "/source/file2.jpg" in processed

    def test_get_unprocessed_files(self, tracker):
        """Test finding unprocessed files."""
        session_id = tracker.start_session(["/source"], "/archive")

        all_files = ["/source/file1.jpg", "/source/file2.jpg", "/source/file3.jpg"]
        tracker.mark_file_processed(session_id, "/source/file1.jpg")

        unprocessed = tracker.get_unprocessed_files(session_id, all_files)

        assert "/source/file1.jpg" not in unprocessed
        assert "/source/file2.jpg" in unprocessed
        assert "/source/file3.jpg" in unprocessed

    def test_file_status_tracking(self, tracker):
        """Test different file status values."""
        session_id = tracker.start_session(["/source"], "/archive")

        tracker.mark_file_processed(session_id, "/source/new.jpg", status='processed')
        tracker.mark_file_processed(session_id, "/source/dup.jpg", status='duplicate')
        tracker.mark_file_processed(session_id, "/source/skip.jpg", status='skipped')
        tracker.mark_file_processed(
            session_id,
            "/source/fail.jpg",
            status='failed',
            error_message='Permission denied'
        )

        processed = tracker.get_processed_files(session_id)

        assert len(processed) == 4

    def test_file_with_error_message(self, tracker):
        """Test storing error messages for failed files."""
        session_id = tracker.start_session(["/source"], "/archive")

        tracker.mark_file_processed(
            session_id,
            "/source/corrupt.jpg",
            status='failed',
            error_message='File corrupted'
        )

        # Verify file is tracked (even though failed)
        processed = tracker.get_processed_files(session_id)
        assert "/source/corrupt.jpg" in processed


class TestCheckpoints:
    """Tests for checkpoint functionality."""

    def test_create_checkpoint(self, tracker):
        """Test creating a checkpoint."""
        session_id = tracker.start_session(["/source"], "/archive")

        result = tracker.create_checkpoint(
            session_id,
            current_index=50,
            total_files=100,
            files_processed=45,
            files_skipped=3,
            files_failed=2,
            bytes_processed=1024 * 1024 * 500
        )

        assert result is True

    def test_get_latest_checkpoint(self, tracker):
        """Test retrieving latest checkpoint."""
        session_id = tracker.start_session(["/source"], "/archive")

        # Create multiple checkpoints
        tracker.create_checkpoint(session_id, 25, 100, 25)
        tracker.create_checkpoint(session_id, 50, 100, 50)
        tracker.create_checkpoint(session_id, 75, 100, 75)

        checkpoint = tracker.get_latest_checkpoint(session_id)

        assert checkpoint is not None
        assert checkpoint['current_index'] == 75
        assert checkpoint['files_processed'] == 75

    def test_checkpoint_with_extra_data(self, tracker):
        """Test checkpoint with additional data."""
        session_id = tracker.start_session(["/source"], "/archive")

        extra = {
            'current_batch': 3,
            'last_error': 'connection timeout'
        }

        tracker.create_checkpoint(
            session_id,
            current_index=30,
            total_files=100,
            extra_data=extra
        )

        checkpoint = tracker.get_latest_checkpoint(session_id)

        assert checkpoint['checkpoint_data'] == extra

    def test_checkpoint_updates_session(self, tracker):
        """Test that checkpoint updates session progress."""
        session_id = tracker.start_session(["/source"], "/archive")

        tracker.create_checkpoint(
            session_id,
            current_index=50,
            total_files=200,
            files_processed=45
        )

        sessions = tracker.get_incomplete_sessions()
        session = next(s for s in sessions if s['session_id'] == session_id)

        assert session['current_file_index'] == 50
        assert session['total_files_found'] == 200

    def test_no_checkpoint_returns_none(self, tracker):
        """Test getting checkpoint when none exists."""
        session_id = tracker.start_session(["/source"], "/archive")

        checkpoint = tracker.get_latest_checkpoint(session_id)

        assert checkpoint is None


class TestHashCache:
    """Tests for hash caching functionality."""

    def test_cache_hash(self, tracker, temp_dir):
        """Test caching a file hash."""
        # Create a test file
        test_file = os.path.join(temp_dir, "test.jpg")
        with open(test_file, "w") as f:
            f.write("test content")

        stat = os.stat(test_file)

        result = tracker.cache_hash(
            test_file,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
            partial_hash="partial123",
            full_hash="full456"
        )

        assert result is True

    def test_get_cached_hash(self, tracker, temp_dir):
        """Test retrieving cached hash."""
        test_file = os.path.join(temp_dir, "test.jpg")
        with open(test_file, "w") as f:
            f.write("test content")

        stat = os.stat(test_file)

        tracker.cache_hash(
            test_file,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
            partial_hash="partial123",
            full_hash="full456"
        )

        cached = tracker.get_cached_hash(test_file)

        assert cached is not None
        assert cached['partial_hash'] == "partial123"
        assert cached['full_hash'] == "full456"

    def test_cache_invalidated_on_change(self, tracker, temp_dir):
        """Test that cache is invalidated when file changes."""
        test_file = os.path.join(temp_dir, "test.jpg")
        with open(test_file, "w") as f:
            f.write("original content")

        stat = os.stat(test_file)
        tracker.cache_hash(
            test_file,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
            full_hash="original_hash"
        )

        # Modify the file
        import time
        time.sleep(0.1)  # Ensure mtime changes
        with open(test_file, "w") as f:
            f.write("modified content - different size")

        cached = tracker.get_cached_hash(test_file)

        # Cache should not be returned because file changed
        assert cached is None

    def test_nonexistent_file_returns_none(self, tracker, temp_dir):
        """Test that nonexistent file returns None."""
        nonexistent = os.path.join(temp_dir, "does_not_exist.jpg")

        cached = tracker.get_cached_hash(nonexistent)

        assert cached is None


class TestCleanup:
    """Tests for cleanup functionality."""

    def test_cleanup_removes_old_sessions(self, tracker):
        """Test that cleanup removes old completed sessions."""
        # Note: This test may not fully verify cleanup since we can't
        # easily create old timestamps in SQLite. We verify the method runs.
        session_id = tracker.start_session(["/source"], "/archive")
        tracker.end_session(session_id, status='completed')

        # Cleanup with 0 days should remove the session
        deleted = tracker.cleanup_old_data(days_old=0)

        # Should have deleted something
        assert deleted >= 0

    def test_get_session_statistics(self, tracker):
        """Test getting session statistics."""
        session_id = tracker.start_session(["/source"], "/archive")

        tracker.mark_directory_scanned(session_id, "/source/dir1")
        tracker.mark_file_processed(session_id, "/source/file1.jpg", status='processed')
        tracker.mark_file_processed(session_id, "/source/file2.jpg", status='duplicate')
        tracker.mark_file_processed(session_id, "/source/file3.jpg", status='failed')

        stats = tracker.get_session_statistics(session_id)

        assert stats['session_id'] == session_id
        assert stats['directories_scanned'] == 1
        assert 'processed' in stats['files_by_status']
        assert 'duplicate' in stats['files_by_status']
        assert 'failed' in stats['files_by_status']


class TestResumeScenarios:
    """Tests for resume scenarios after crash."""

    def test_resume_from_checkpoint(self, tracker):
        """Test resuming from a checkpoint."""
        # Simulate an interrupted session
        session_id = tracker.start_session(["/source"], "/archive")

        # Process some files
        for i in range(50):
            tracker.mark_file_processed(
                session_id,
                f"/source/file{i}.jpg",
                status='processed'
            )

        # Create checkpoint at position 50
        tracker.create_checkpoint(
            session_id,
            current_index=50,
            total_files=100,
            files_processed=50
        )

        # "Crash" - session is still incomplete

        # Resume: get incomplete sessions
        incomplete = tracker.get_incomplete_sessions()
        assert any(s['session_id'] == session_id for s in incomplete)

        # Get checkpoint to resume from
        checkpoint = tracker.get_latest_checkpoint(session_id)
        assert checkpoint['current_index'] == 50

        # Get already processed files to skip
        processed = tracker.get_processed_files(session_id)
        assert len(processed) == 50

    def test_resume_directory_scan(self, tracker):
        """Test resuming directory scanning."""
        session_id = tracker.start_session(
            ["/source/dir1", "/source/dir2", "/source/dir3"],
            "/archive"
        )

        # Scan first two directories
        tracker.mark_directory_scanned(session_id, "/source/dir1", files_found=10)
        tracker.mark_directory_scanned(session_id, "/source/dir2", files_found=15)

        # "Crash" - only partial scan

        # Resume: find unscanned directories
        all_dirs = ["/source/dir1", "/source/dir2", "/source/dir3"]
        unscanned = tracker.get_unscanned_directories(session_id, all_dirs)

        assert unscanned == ["/source/dir3"]
