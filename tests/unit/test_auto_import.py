"""
Unit tests for Auto-Import Service.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from auto_import.config import (
    WatchConfig,
    ScheduleConfig,
    EmailConfig,
    NotificationConfig,
    ProcessingConfig,
    ServiceConfig,
    ConfigManager,
    DEFAULT_FILE_PATTERNS,
)
from auto_import.scheduler import Scheduler
from auto_import.processor import ImportResult, ImportedFile


class TestWatchConfig(unittest.TestCase):
    """Tests for WatchConfig dataclass."""

    def test_default_values(self):
        """Test default values are applied."""
        config = WatchConfig(path='/test/path')
        self.assertTrue(config.enabled)
        self.assertTrue(config.recursive)
        self.assertEqual(config.min_file_age_seconds, 60)
        self.assertIsNone(config.album_id)
        self.assertEqual(config.name, 'path')  # Basename of path

    def test_path_expansion(self):
        """Test home directory expansion."""
        config = WatchConfig(path='~/Photos')
        self.assertTrue(config.path.startswith('/'))
        self.assertNotIn('~', config.path)

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'path': '/test/photos',
            'enabled': False,
            'recursive': False,
            'min_file_age_seconds': 120,
            'album_id': 5,
            'name': 'My Photos',
        }
        config = WatchConfig.from_dict(data)
        self.assertEqual(config.path, '/test/photos')
        self.assertFalse(config.enabled)
        self.assertFalse(config.recursive)
        self.assertEqual(config.min_file_age_seconds, 120)
        self.assertEqual(config.album_id, 5)
        self.assertEqual(config.name, 'My Photos')

    def test_is_available_nonexistent(self):
        """Test is_available returns False for nonexistent path."""
        config = WatchConfig(path='/nonexistent/path/that/does/not/exist')
        self.assertFalse(config.is_available())


class TestScheduleConfig(unittest.TestCase):
    """Tests for ScheduleConfig dataclass."""

    def test_default_values(self):
        """Test default values."""
        config = ScheduleConfig()
        self.assertEqual(config.mode, 'interval')
        self.assertEqual(config.interval_minutes, 60)
        self.assertTrue(config.run_on_startup)

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'mode': 'cron',
            'interval_minutes': 30,
            'cron_expression': '0 3 * * *',
            'quiet_hours': {
                'start': '22:00',
                'end': '07:00',
            },
            'run_on_startup': False,
        }
        config = ScheduleConfig.from_dict(data)
        self.assertEqual(config.mode, 'cron')
        self.assertEqual(config.interval_minutes, 30)
        self.assertEqual(config.cron_expression, '0 3 * * *')
        self.assertEqual(config.quiet_hours_start, '22:00')
        self.assertEqual(config.quiet_hours_end, '07:00')
        self.assertFalse(config.run_on_startup)


class TestEmailConfig(unittest.TestCase):
    """Tests for EmailConfig dataclass."""

    def test_default_values(self):
        """Test default values."""
        config = EmailConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.smtp_port, 587)
        self.assertTrue(config.smtp_use_tls)

    def test_is_configured_false_when_incomplete(self):
        """Test is_configured returns False when not fully configured."""
        config = EmailConfig()
        self.assertFalse(config.is_configured())

    def test_is_configured_true_when_complete(self):
        """Test is_configured returns True when fully configured."""
        config = EmailConfig(
            enabled=True,
            recipients=['test@example.com'],
            smtp_server='smtp.example.com',
            smtp_username='user',
            smtp_password='pass',
        )
        self.assertTrue(config.is_configured())

    @patch.dict(os.environ, {'TEST_SMTP_PASS': 'secret123'})
    def test_password_from_env(self):
        """Test loading password from environment variable."""
        config = EmailConfig(smtp_password_env='TEST_SMTP_PASS')
        self.assertEqual(config.smtp_password, 'secret123')


class TestServiceConfig(unittest.TestCase):
    """Tests for ServiceConfig dataclass."""

    def test_validate_missing_database(self):
        """Test validation fails without database path."""
        config = ServiceConfig(
            database_path='',
            watch_directories=[WatchConfig(path='/test')],
        )
        errors = config.validate()
        self.assertTrue(any('database_path' in e for e in errors))

    def test_validate_missing_watch_directories(self):
        """Test validation fails without watch directories."""
        config = ServiceConfig(
            database_path='/test.db',
            watch_directories=[],
        )
        errors = config.validate()
        self.assertTrue(any('watch_directory' in e for e in errors))

    def test_validate_invalid_schedule_mode(self):
        """Test validation fails with invalid schedule mode."""
        config = ServiceConfig(
            database_path='/test.db',
            watch_directories=[WatchConfig(path='/test')],
            schedule=ScheduleConfig(mode='invalid'),
        )
        errors = config.validate()
        self.assertTrue(any('schedule mode' in e.lower() for e in errors))

    def test_get_enabled_watch_directories(self):
        """Test filtering enabled watch directories."""
        config = ServiceConfig(
            database_path='/test.db',
            watch_directories=[
                WatchConfig(path='/enabled1', enabled=True),
                WatchConfig(path='/disabled', enabled=False),
                WatchConfig(path='/enabled2', enabled=True),
            ],
        )
        enabled = config.get_enabled_watch_directories()
        self.assertEqual(len(enabled), 2)
        self.assertEqual(enabled[0].path, '/enabled1')
        self.assertEqual(enabled[1].path, '/enabled2')


class TestScheduler(unittest.TestCase):
    """Tests for Scheduler class."""

    def test_continuous_mode(self):
        """Test continuous mode returns current time."""
        config = ScheduleConfig(mode='continuous')
        scheduler = Scheduler(config)
        now = datetime.now()
        next_run = scheduler.get_next_run_time(now)
        self.assertEqual(next_run, now)

    def test_interval_mode_first_run(self):
        """Test interval mode returns current time on first run."""
        config = ScheduleConfig(mode='interval', interval_minutes=60)
        scheduler = Scheduler(config)
        now = datetime.now()
        next_run = scheduler.get_next_run_time(now)
        self.assertEqual(next_run, now)

    def test_interval_mode_after_run(self):
        """Test interval mode calculates next time after run."""
        config = ScheduleConfig(mode='interval', interval_minutes=60)
        scheduler = Scheduler(config)
        scheduler.mark_run_completed()

        now = datetime.now()
        next_run = scheduler.get_next_run_time(now)

        # Should be approximately 60 minutes from now
        expected = now + timedelta(minutes=60)
        self.assertAlmostEqual(
            (next_run - expected).total_seconds(),
            0,
            delta=5  # Allow 5 seconds tolerance
        )

    def test_should_run_now_continuous(self):
        """Test should_run_now returns True for continuous mode."""
        config = ScheduleConfig(mode='continuous')
        scheduler = Scheduler(config)
        self.assertTrue(scheduler.should_run_now())

    def test_get_schedule_description_interval(self):
        """Test schedule description for interval mode."""
        config = ScheduleConfig(mode='interval', interval_minutes=60)
        scheduler = Scheduler(config)
        desc = scheduler.get_schedule_description()
        self.assertIn('hour', desc.lower())

    def test_get_schedule_description_continuous(self):
        """Test schedule description for continuous mode."""
        config = ScheduleConfig(mode='continuous')
        scheduler = Scheduler(config)
        desc = scheduler.get_schedule_description()
        self.assertIn('continuous', desc.lower())

    def test_cron_field_wildcard(self):
        """Test cron field matching with wildcard."""
        config = ScheduleConfig(mode='cron')
        scheduler = Scheduler(config)
        self.assertTrue(scheduler._matches_cron_field('*', 5))
        self.assertTrue(scheduler._matches_cron_field('*', 0))
        self.assertTrue(scheduler._matches_cron_field('*', 59))

    def test_cron_field_specific_value(self):
        """Test cron field matching with specific value."""
        config = ScheduleConfig(mode='cron')
        scheduler = Scheduler(config)
        self.assertTrue(scheduler._matches_cron_field('5', 5))
        self.assertFalse(scheduler._matches_cron_field('5', 6))

    def test_cron_field_range(self):
        """Test cron field matching with range."""
        config = ScheduleConfig(mode='cron')
        scheduler = Scheduler(config)
        self.assertTrue(scheduler._matches_cron_field('1-5', 3))
        self.assertTrue(scheduler._matches_cron_field('1-5', 1))
        self.assertTrue(scheduler._matches_cron_field('1-5', 5))
        self.assertFalse(scheduler._matches_cron_field('1-5', 0))
        self.assertFalse(scheduler._matches_cron_field('1-5', 6))

    def test_cron_field_list(self):
        """Test cron field matching with list."""
        config = ScheduleConfig(mode='cron')
        scheduler = Scheduler(config)
        self.assertTrue(scheduler._matches_cron_field('1,3,5', 3))
        self.assertTrue(scheduler._matches_cron_field('1,3,5', 1))
        self.assertFalse(scheduler._matches_cron_field('1,3,5', 2))

    def test_cron_field_interval(self):
        """Test cron field matching with interval."""
        config = ScheduleConfig(mode='cron')
        scheduler = Scheduler(config)
        self.assertTrue(scheduler._matches_cron_field('*/15', 0))
        self.assertTrue(scheduler._matches_cron_field('*/15', 15))
        self.assertTrue(scheduler._matches_cron_field('*/15', 30))
        self.assertFalse(scheduler._matches_cron_field('*/15', 10))


class TestImportResult(unittest.TestCase):
    """Tests for ImportResult dataclass."""

    def test_duration_seconds(self):
        """Test duration calculation."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 10, 5, 30)
        result = ImportResult(
            start_time=start,
            end_time=end,
            files_scanned=0,
            files_imported=0,
            files_duplicate=0,
            files_filtered=0,
            files_failed=0,
            bytes_processed=0,
        )
        self.assertEqual(result.duration_seconds, 330.0)

    def test_success_rate_all_success(self):
        """Test success rate with all successful imports."""
        result = ImportResult(
            start_time=datetime.now(),
            end_time=datetime.now(),
            files_scanned=10,
            files_imported=10,
            files_duplicate=0,
            files_filtered=0,
            files_failed=0,
            bytes_processed=1000,
        )
        self.assertEqual(result.success_rate, 100.0)

    def test_success_rate_partial(self):
        """Test success rate with partial success."""
        result = ImportResult(
            start_time=datetime.now(),
            end_time=datetime.now(),
            files_scanned=10,
            files_imported=7,
            files_duplicate=0,
            files_filtered=0,
            files_failed=3,
            bytes_processed=700,
        )
        self.assertEqual(result.success_rate, 70.0)

    def test_success_rate_no_files(self):
        """Test success rate with no files processed."""
        result = ImportResult(
            start_time=datetime.now(),
            end_time=datetime.now(),
            files_scanned=0,
            files_imported=0,
            files_duplicate=0,
            files_filtered=0,
            files_failed=0,
            bytes_processed=0,
        )
        self.assertEqual(result.success_rate, 100.0)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 10, 5, 0)
        result = ImportResult(
            start_time=start,
            end_time=end,
            files_scanned=10,
            files_imported=8,
            files_duplicate=1,
            files_filtered=0,
            files_failed=1,
            bytes_processed=1024000,
            errors=['Test error'],
            imported_files=[
                ImportedFile(
                    source_path='/source/file.jpg',
                    dest_path='/dest/file.jpg',
                    file_hash='abc123',
                    file_size=1024,
                ),
            ],
        )

        data = result.to_dict()
        self.assertEqual(data['files_scanned'], 10)
        self.assertEqual(data['files_imported'], 8)
        self.assertEqual(data['duration_seconds'], 300.0)
        self.assertEqual(len(data['errors']), 1)
        self.assertEqual(len(data['imported_files']), 1)


class TestConfigManager(unittest.TestCase):
    """Tests for ConfigManager class."""

    def test_generate_default_config(self):
        """Test default config generation."""
        config_content = ConfigManager.generate_default_config()
        self.assertIn('database_path', config_content)
        self.assertIn('watch_directories', config_content)
        self.assertIn('schedule', config_content)
        self.assertIn('notifications', config_content)

    def test_load_nonexistent_file(self):
        """Test loading nonexistent config file raises error."""
        manager = ConfigManager('/nonexistent/config.yaml')
        with self.assertRaises(FileNotFoundError):
            manager.load()

    def test_load_valid_config(self):
        """Test loading a valid config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
service:
  database_path: /tmp/test.db
watch_directories:
  - path: /tmp/watch
    enabled: true
schedule:
  mode: interval
  interval_minutes: 30
notifications:
  enabled: false
""")
            f.flush()
            config_path = f.name

        try:
            # Create a dummy database file for validation
            with open('/tmp/test.db', 'w') as db:
                db.write('')

            manager = ConfigManager(config_path)
            config = manager.load()

            self.assertEqual(config.database_path, '/tmp/test.db')
            self.assertEqual(len(config.watch_directories), 1)
            self.assertEqual(config.schedule.interval_minutes, 30)

        finally:
            os.unlink(config_path)
            if os.path.exists('/tmp/test.db'):
                os.unlink('/tmp/test.db')


class TestDefaultFilePatterns(unittest.TestCase):
    """Tests for default file patterns."""

    def test_includes_common_image_formats(self):
        """Test that common image formats are included."""
        patterns = [p.lower() for p in DEFAULT_FILE_PATTERNS]
        self.assertIn('*.jpg', patterns)
        self.assertIn('*.jpeg', patterns)
        self.assertIn('*.png', patterns)
        self.assertIn('*.heic', patterns)

    def test_includes_raw_formats(self):
        """Test that RAW formats are included."""
        patterns = [p.lower() for p in DEFAULT_FILE_PATTERNS]
        self.assertIn('*.raw', patterns)
        self.assertIn('*.cr2', patterns)
        self.assertIn('*.nef', patterns)

    def test_includes_video_formats(self):
        """Test that video formats are included."""
        patterns = [p.lower() for p in DEFAULT_FILE_PATTERNS]
        self.assertIn('*.mov', patterns)
        self.assertIn('*.mp4', patterns)
        self.assertIn('*.avi', patterns)


if __name__ == '__main__':
    unittest.main()
