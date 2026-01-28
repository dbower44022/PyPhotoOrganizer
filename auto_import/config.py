"""
Configuration management for Auto-Import Service.

Supports YAML configuration files with validation and hot-reload.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default file patterns for photos and videos
DEFAULT_FILE_PATTERNS = [
    '*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.tiff', '*.tif',
    '*.heic', '*.heif', '*.webp', '*.raw', '*.cr2', '*.nef', '*.arw',
    '*.mov', '*.mp4', '*.avi', '*.mkv', '*.m4v', '*.wmv', '*.3gp'
]


@dataclass
class WatchConfig:
    """Configuration for a watched directory."""
    path: str
    enabled: bool = True
    recursive: bool = True
    file_patterns: List[str] = field(default_factory=lambda: DEFAULT_FILE_PATTERNS.copy())
    min_file_age_seconds: int = 60  # Wait for files to finish copying
    album_id: Optional[int] = None  # Auto-add to album
    name: Optional[str] = None  # Friendly name for reporting

    def __post_init__(self):
        # Expand user home directory
        self.path = os.path.expanduser(self.path)
        # Set default name from path
        if self.name is None:
            self.name = os.path.basename(self.path) or self.path

    def is_available(self) -> bool:
        """Check if the watched directory is accessible."""
        return os.path.isdir(self.path) and os.access(self.path, os.R_OK)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WatchConfig':
        """Create WatchConfig from dictionary."""
        return cls(
            path=data['path'],
            enabled=data.get('enabled', True),
            recursive=data.get('recursive', True),
            file_patterns=data.get('file_patterns', DEFAULT_FILE_PATTERNS.copy()),
            min_file_age_seconds=data.get('min_file_age_seconds', 60),
            album_id=data.get('album_id'),
            name=data.get('name'),
        )


@dataclass
class ScheduleConfig:
    """Scheduling configuration."""
    mode: str = 'interval'  # 'interval', 'cron', 'continuous'
    interval_minutes: int = 60
    cron_expression: str = '0 2 * * *'  # 2 AM daily (if mode='cron')
    quiet_hours_start: Optional[str] = None  # e.g., '23:00'
    quiet_hours_end: Optional[str] = None    # e.g., '06:00'
    run_on_startup: bool = True  # Run immediately when service starts

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduleConfig':
        """Create ScheduleConfig from dictionary."""
        quiet_hours = data.get('quiet_hours', {})
        return cls(
            mode=data.get('mode', 'interval'),
            interval_minutes=data.get('interval_minutes', 60),
            cron_expression=data.get('cron_expression', '0 2 * * *'),
            quiet_hours_start=quiet_hours.get('start'),
            quiet_hours_end=quiet_hours.get('end'),
            run_on_startup=data.get('run_on_startup', True),
        )

    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False

        from datetime import datetime

        try:
            now = datetime.now().time()
            start = datetime.strptime(self.quiet_hours_start, '%H:%M').time()
            end = datetime.strptime(self.quiet_hours_end, '%H:%M').time()

            # Handle overnight quiet hours (e.g., 23:00 to 06:00)
            if start <= end:
                return start <= now <= end
            else:
                return now >= start or now <= end

        except ValueError as e:
            logger.warning(f"Invalid quiet hours format: {e}")
            return False


@dataclass
class EmailConfig:
    """Email/SMTP configuration."""
    enabled: bool = True
    recipients: List[str] = field(default_factory=list)
    smtp_server: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''  # Can also use password_env
    smtp_password_env: str = ''  # Environment variable name for password
    smtp_use_tls: bool = True
    from_address: str = ''  # Defaults to smtp_username
    from_name: str = 'PyPhotoOrganizer'

    def __post_init__(self):
        # Load password from environment if specified
        if self.smtp_password_env and not self.smtp_password:
            self.smtp_password = os.environ.get(self.smtp_password_env, '')

        # Default from_address to username
        if not self.from_address and self.smtp_username:
            self.from_address = self.smtp_username

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailConfig':
        """Create EmailConfig from dictionary."""
        smtp = data.get('smtp', {})
        return cls(
            enabled=data.get('enabled', True),
            recipients=data.get('recipients', []),
            smtp_server=smtp.get('server', ''),
            smtp_port=smtp.get('port', 587),
            smtp_username=smtp.get('username', ''),
            smtp_password=smtp.get('password', ''),
            smtp_password_env=smtp.get('password_env', ''),
            smtp_use_tls=smtp.get('use_tls', True),
            from_address=smtp.get('from_address', ''),
            from_name=smtp.get('from_name', 'PyPhotoOrganizer'),
        )

    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        return bool(
            self.enabled and
            self.recipients and
            self.smtp_server and
            self.smtp_username and
            self.smtp_password
        )


@dataclass
class NotificationConfig:
    """Notification settings."""
    enabled: bool = True
    email: EmailConfig = field(default_factory=EmailConfig)

    # Report settings
    report_on_success: bool = True
    report_on_failure: bool = True
    report_on_no_changes: bool = False  # Don't spam when nothing happens
    include_file_list: bool = True
    max_files_in_report: int = 100

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NotificationConfig':
        """Create NotificationConfig from dictionary."""
        reports = data.get('reports', {})
        return cls(
            enabled=data.get('enabled', True),
            email=EmailConfig.from_dict(data.get('email', {})),
            report_on_success=reports.get('on_success', True),
            report_on_failure=reports.get('on_failure', True),
            report_on_no_changes=reports.get('on_no_changes', False),
            include_file_list=reports.get('include_file_list', True),
            max_files_in_report=reports.get('max_files_in_report', 100),
        )


@dataclass
class ProcessingConfig:
    """Processing options."""
    copy_mode: bool = True  # True=copy, False=move
    enable_cloud_sync: bool = False
    cloud_sync_after_import: bool = False
    max_files_per_run: int = 0  # 0 = unlimited
    max_bytes_per_run: int = 0  # 0 = unlimited

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingConfig':
        """Create ProcessingConfig from dictionary."""
        return cls(
            copy_mode=data.get('copy_mode', True),
            enable_cloud_sync=data.get('enable_cloud_sync', False),
            cloud_sync_after_import=data.get('cloud_sync_after_import', False),
            max_files_per_run=data.get('max_files_per_run', 0),
            max_bytes_per_run=data.get('max_bytes_per_run', 0),
        )


@dataclass
class ServiceConfig:
    """Complete service configuration."""
    # Required
    database_path: str

    # Components
    watch_directories: List[WatchConfig] = field(default_factory=list)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)

    # Service options
    pid_file: str = '/var/run/pyphoto-autoimport.pid'
    log_file: str = ''  # Empty = stdout
    log_level: str = 'INFO'
    state_file: str = ''  # Empty = use database

    def __post_init__(self):
        # Expand paths
        self.database_path = os.path.expanduser(self.database_path)
        if self.pid_file:
            self.pid_file = os.path.expanduser(self.pid_file)
        if self.log_file:
            self.log_file = os.path.expanduser(self.log_file)
        if self.state_file:
            self.state_file = os.path.expanduser(self.state_file)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServiceConfig':
        """Create ServiceConfig from dictionary."""
        service = data.get('service', {})

        # Parse watch directories
        watch_dirs = []
        for wd in data.get('watch_directories', []):
            watch_dirs.append(WatchConfig.from_dict(wd))

        return cls(
            database_path=service.get('database_path', ''),
            watch_directories=watch_dirs,
            schedule=ScheduleConfig.from_dict(data.get('schedule', {})),
            notifications=NotificationConfig.from_dict(data.get('notifications', {})),
            processing=ProcessingConfig.from_dict(data.get('processing', {})),
            pid_file=service.get('pid_file', '/var/run/pyphoto-autoimport.pid'),
            log_file=service.get('log_file', ''),
            log_level=service.get('log_level', 'INFO'),
            state_file=service.get('state_file', ''),
        )

    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Database path is required
        if not self.database_path:
            errors.append("database_path is required")
        elif not os.path.exists(self.database_path):
            errors.append(f"Database not found: {self.database_path}")

        # At least one watch directory
        if not self.watch_directories:
            errors.append("At least one watch_directory is required")

        # Validate watch directories
        for i, wd in enumerate(self.watch_directories):
            if not wd.path:
                errors.append(f"watch_directories[{i}]: path is required")

        # Validate schedule
        if self.schedule.mode not in ('interval', 'cron', 'continuous'):
            errors.append(f"Invalid schedule mode: {self.schedule.mode}")

        if self.schedule.mode == 'interval' and self.schedule.interval_minutes < 1:
            errors.append("interval_minutes must be at least 1")

        # Validate email if enabled
        if self.notifications.enabled and self.notifications.email.enabled:
            email = self.notifications.email
            if not email.recipients:
                errors.append("Email enabled but no recipients configured")
            if not email.smtp_server:
                errors.append("Email enabled but smtp_server not configured")

        return errors

    def get_enabled_watch_directories(self) -> List[WatchConfig]:
        """Get list of enabled watch directories."""
        return [wd for wd in self.watch_directories if wd.enabled]


class ConfigManager:
    """
    Manages configuration loading, validation, and hot-reload.
    """

    def __init__(self, config_path: str):
        """
        Initialize ConfigManager.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = os.path.expanduser(config_path)
        self.config: Optional[ServiceConfig] = None
        self._last_mtime: float = 0

    def load(self) -> ServiceConfig:
        """
        Load configuration from file.

        Returns:
            ServiceConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        import yaml

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        logger.info(f"Loading configuration from {self.config_path}")

        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)

        self.config = ServiceConfig.from_dict(data or {})
        self._last_mtime = os.path.getmtime(self.config_path)

        # Validate
        errors = self.config.validate()
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

        logger.info(f"Configuration loaded successfully: {len(self.config.watch_directories)} watch directories")
        return self.config

    def has_changed(self) -> bool:
        """Check if config file has been modified since last load."""
        try:
            current_mtime = os.path.getmtime(self.config_path)
            return current_mtime > self._last_mtime
        except OSError:
            return False

    def reload_if_changed(self) -> bool:
        """
        Reload configuration if file has changed.

        Returns:
            True if configuration was reloaded
        """
        if self.has_changed():
            logger.info("Configuration file changed, reloading...")
            try:
                self.load()
                return True
            except Exception as e:
                logger.error(f"Failed to reload configuration: {e}")
        return False

    @staticmethod
    def generate_default_config() -> str:
        """Generate default configuration YAML."""
        return '''# PyPhotoOrganizer Auto-Import Service Configuration
# See AUTO_IMPORT_SERVICE_PLAN.md for full documentation

service:
  # Path to PyPhotoOrganizer database (required)
  database_path: ~/Photos/PhotoDB.db

  # PID file for daemon mode
  pid_file: /var/run/pyphoto-autoimport.pid

  # Log file (empty for stdout)
  log_file: /var/log/pyphoto-autoimport.log
  log_level: INFO

schedule:
  # Mode: interval, cron, or continuous
  mode: interval
  interval_minutes: 60

  # Optional: Skip during these hours
  quiet_hours:
    start: "23:00"
    end: "06:00"

  # Run immediately when service starts
  run_on_startup: true

watch_directories:
  # Add directories to watch for new photos
  - path: ~/PhoneBackup/DCIM
    enabled: true
    recursive: true
    min_file_age_seconds: 120  # Wait for sync to complete
    # album_id: 1  # Optional: auto-add to album

  - path: ~/Downloads/Photos
    enabled: true
    recursive: false
    min_file_age_seconds: 60

processing:
  copy_mode: true  # true=copy, false=move source files
  enable_cloud_sync: false
  cloud_sync_after_import: false

notifications:
  enabled: true

  email:
    enabled: true
    recipients:
      - admin@example.com
    smtp:
      server: smtp.gmail.com
      port: 587
      username: your-email@gmail.com
      password_env: SMTP_PASSWORD  # Read from environment variable
      use_tls: true

  reports:
    on_success: true
    on_failure: true
    on_no_changes: false
    include_file_list: true
    max_files_in_report: 50
'''

    @classmethod
    def from_file(cls, config_path: str) -> 'ConfigManager':
        """Create ConfigManager and load configuration."""
        manager = cls(config_path)
        manager.load()
        return manager
