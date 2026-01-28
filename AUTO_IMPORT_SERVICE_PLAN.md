# Auto-Import Background Service Plan

## Executive Summary

Design a background service that automatically monitors source directories for new photos/videos, imports them to the archive, and sends reports to administrators. This enables "set and forget" photo organization for devices that sync photos to watched folders (e.g., phone backup apps, cloud sync folders).

**Use Cases:**
- Automatic import from phone backup folders (Google Photos sync, iCloud, etc.)
- NAS watch folders for family photo drops
- Camera SD card auto-import stations
- Scheduled overnight batch processing

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Auto-Import Service                           │
├─────────────────────────────────────────────────────────────────┤
│  ServiceManager          │  ConfigManager    │  ReportManager   │
│  (lifecycle, scheduling) │  (settings)       │  (notifications) │
├─────────────────────────────────────────────────────────────────┤
│                      DirectoryWatcher                            │
│              (monitor directories for changes)                   │
├─────────────────────────────────────────────────────────────────┤
│                      ImportProcessor                             │
│              (reuse existing import logic)                       │
├─────────────────────────────────────────────────────────────────┤
│  PhotoDatabase  │  AuditManager  │  CloudSyncManager (optional) │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. ServiceManager

Main service lifecycle and scheduling manager.

```python
class ServiceManager:
    """
    Manages the auto-import service lifecycle.

    Responsibilities:
    - Start/stop service
    - Schedule periodic scans
    - Handle signals (SIGTERM, SIGHUP)
    - Manage worker threads
    - Coordinate between components
    """

    def __init__(self, config_path: str):
        self.config = ConfigManager(config_path)
        self.watcher = DirectoryWatcher(self.config)
        self.processor = ImportProcessor(self.config)
        self.reporter = ReportManager(self.config)

    def start(self):
        """Start the service."""
        pass

    def stop(self):
        """Graceful shutdown."""
        pass

    def run_once(self):
        """Run a single import cycle (for testing/manual runs)."""
        pass
```

### 2. ConfigManager

Configuration management with hot-reload support.

```python
@dataclass
class WatchConfig:
    """Configuration for a watched directory."""
    path: str
    enabled: bool = True
    recursive: bool = True
    file_patterns: List[str] = field(default_factory=lambda: ['*.jpg', '*.jpeg', '*.png', '*.heic', '*.mov', '*.mp4'])
    min_file_age_seconds: int = 60  # Wait for files to finish copying
    album_id: Optional[int] = None  # Auto-add to album

@dataclass
class ScheduleConfig:
    """Scheduling configuration."""
    mode: str = 'interval'  # 'interval', 'cron', 'continuous'
    interval_minutes: int = 60
    cron_expression: str = '0 2 * * *'  # 2 AM daily
    quiet_hours_start: Optional[str] = None  # e.g., '23:00'
    quiet_hours_end: Optional[str] = None    # e.g., '06:00'

@dataclass
class NotificationConfig:
    """Notification settings."""
    enabled: bool = True
    email_enabled: bool = True
    email_recipients: List[str] = field(default_factory=list)
    smtp_server: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''  # Or use keyring
    smtp_use_tls: bool = True

    # Report settings
    report_on_success: bool = True
    report_on_failure: bool = True
    report_on_no_changes: bool = False
    include_file_list: bool = True
    max_files_in_report: int = 100

@dataclass
class ServiceConfig:
    """Complete service configuration."""
    database_path: str
    watch_directories: List[WatchConfig]
    schedule: ScheduleConfig
    notifications: NotificationConfig

    # Processing options
    copy_mode: bool = True  # True=copy, False=move
    enable_cloud_sync: bool = False
    cloud_sync_after_import: bool = False

    # Service options
    pid_file: str = '/var/run/pyphoto-autoimport.pid'
    log_file: str = '/var/log/pyphoto-autoimport.log'
    log_level: str = 'INFO'
```

### 3. DirectoryWatcher

Monitors directories for new files.

```python
class DirectoryWatcher:
    """
    Watches directories for new files.

    Two modes:
    1. Polling: Scan directories at intervals (cross-platform)
    2. Event-based: Use inotify/FSEvents (Linux/macOS only)
    """

    def __init__(self, config: ServiceConfig):
        self.config = config
        self._known_files: Dict[str, Set[str]] = {}  # path -> set of known files

    def scan_for_new_files(self) -> List[NewFile]:
        """
        Scan all watched directories for new files.

        Returns list of new files that:
        - Match file patterns
        - Are older than min_file_age (finished copying)
        - Haven't been processed before
        """
        pass

    def mark_as_processed(self, file_path: str):
        """Mark file as processed to avoid re-processing."""
        pass

    def get_watch_status(self) -> Dict[str, WatchStatus]:
        """Get status of all watched directories."""
        pass
```

### 4. ImportProcessor

Handles the actual import using existing PyPhotoOrganizer logic.

```python
class ImportProcessor:
    """
    Processes new files using existing import infrastructure.

    Reuses:
    - PhotoDatabase for duplicate detection
    - organize_files() for file organization
    - AuditManager for session tracking
    - CloudSyncManager for cloud uploads (optional)
    """

    def __init__(self, config: ServiceConfig):
        self.config = config
        self.db = PhotoDatabase(config.database_path)
        self.audit = AuditManager(config.database_path)

    def process_files(self, files: List[NewFile],
                     progress_callback: Callable = None) -> ImportResult:
        """
        Process a batch of new files.

        Returns:
            ImportResult with statistics and any errors
        """
        pass

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get cumulative processing statistics."""
        pass
```

### 5. ReportManager

Generates and sends reports.

```python
@dataclass
class ImportResult:
    """Result of an import operation."""
    start_time: datetime
    end_time: datetime
    files_scanned: int
    files_imported: int
    files_duplicate: int
    files_filtered: int
    files_failed: int
    bytes_processed: int
    errors: List[str]
    imported_files: List[str]  # Paths of imported files

class ReportManager:
    """
    Generates and sends import reports.

    Supports:
    - Email (SMTP)
    - File output (JSON, HTML)
    - Webhooks (future)
    - System notifications (future)
    """

    def __init__(self, config: ServiceConfig):
        self.config = config

    def generate_report(self, result: ImportResult) -> str:
        """Generate HTML report from import result."""
        pass

    def send_email_report(self, result: ImportResult):
        """Send report via email."""
        pass

    def should_send_report(self, result: ImportResult) -> bool:
        """Determine if report should be sent based on config."""
        pass
```

---

## Configuration File Format

```yaml
# /etc/pyphoto-autoimport/config.yaml
# or ~/.config/pyphoto-autoimport/config.yaml

service:
  database_path: /home/user/Photos/PhotoDB.db
  pid_file: /var/run/pyphoto-autoimport.pid
  log_file: /var/log/pyphoto-autoimport.log
  log_level: INFO

schedule:
  mode: interval  # interval, cron, continuous
  interval_minutes: 60
  # cron_expression: "0 2 * * *"  # Alternative: run at 2 AM
  quiet_hours:
    start: "23:00"
    end: "06:00"

watch_directories:
  - path: /home/user/PhoneBackup/DCIM
    enabled: true
    recursive: true
    file_patterns:
      - "*.jpg"
      - "*.jpeg"
      - "*.heic"
      - "*.mov"
      - "*.mp4"
    min_file_age_seconds: 120  # Wait 2 min for sync to complete
    album_id: 5  # Auto-add to "Phone Photos" album

  - path: /mnt/nas/FamilyDropbox
    enabled: true
    recursive: true
    min_file_age_seconds: 300  # Wait 5 min for large files

  - path: /home/user/Downloads/Photos
    enabled: true
    recursive: false

processing:
  copy_mode: true  # true=copy, false=move
  enable_cloud_sync: false
  cloud_sync_after_import: false

notifications:
  enabled: true

  email:
    enabled: true
    recipients:
      - admin@example.com
      - backup@example.com
    smtp:
      server: smtp.gmail.com
      port: 587
      username: notifications@example.com
      password_env: SMTP_PASSWORD  # Read from environment
      use_tls: true

  reports:
    on_success: true
    on_failure: true
    on_no_changes: false  # Don't spam when nothing happens
    include_file_list: true
    max_files_in_report: 50
```

---

## Implementation Phases

### Phase 1: Core Service Infrastructure

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Create ServiceConfig dataclasses | `auto_import/config.py` |
| 1.2 | Create ConfigManager with YAML loading | `auto_import/config.py` |
| 1.3 | Create ServiceManager skeleton | `auto_import/service.py` |
| 1.4 | Add signal handling (SIGTERM, SIGHUP) | `auto_import/service.py` |
| 1.5 | Create daemon/service wrapper | `auto_import/daemon.py` |
| 1.6 | Add logging configuration | `auto_import/logging_config.py` |

**Deliverable:** Service can start, stop, and respond to signals.

### Phase 2: Directory Watching

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Create DirectoryWatcher class | `auto_import/watcher.py` |
| 2.2 | Implement polling-based file detection | `auto_import/watcher.py` |
| 2.3 | Add file age checking (wait for copy complete) | `auto_import/watcher.py` |
| 2.4 | Add pattern matching for file types | `auto_import/watcher.py` |
| 2.5 | Create state persistence (track processed files) | `auto_import/state.py` |
| 2.6 | Add directory availability checking | `auto_import/watcher.py` |

**Deliverable:** Can detect new files in watched directories.

### Phase 3: Import Processing

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Create ImportProcessor class | `auto_import/processor.py` |
| 3.2 | Integrate with existing organize_files() | `auto_import/processor.py` |
| 3.3 | Add headless AuditManager integration | `auto_import/processor.py` |
| 3.4 | Handle album auto-add | `auto_import/processor.py` |
| 3.5 | Add error handling and recovery | `auto_import/processor.py` |
| 3.6 | Optional: Cloud sync after import | `auto_import/processor.py` |

**Deliverable:** Can import files using existing PyPhotoOrganizer logic.

### Phase 4: Reporting and Notifications

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Create ReportManager class | `auto_import/reporter.py` |
| 4.2 | Generate HTML email reports | `auto_import/reporter.py` |
| 4.3 | Implement SMTP email sending | `auto_import/email_sender.py` |
| 4.4 | Add report templates | `auto_import/templates/` |
| 4.5 | Add JSON report output | `auto_import/reporter.py` |
| 4.6 | Secure credential handling | `auto_import/credentials.py` |

**Deliverable:** Sends email reports after import.

### Phase 5: Scheduling

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Implement interval-based scheduling | `auto_import/scheduler.py` |
| 5.2 | Implement cron-style scheduling | `auto_import/scheduler.py` |
| 5.3 | Add quiet hours support | `auto_import/scheduler.py` |
| 5.4 | Add continuous/watch mode (optional) | `auto_import/scheduler.py` |
| 5.5 | Handle missed schedules (service was down) | `auto_import/scheduler.py` |

**Deliverable:** Runs on configured schedule.

### Phase 6: CLI and Management

| Task | Description | Files |
|------|-------------|-------|
| 6.1 | Create CLI entry point | `auto_import/__main__.py` |
| 6.2 | Add start/stop/status commands | `auto_import/cli.py` |
| 6.3 | Add run-once command (manual trigger) | `auto_import/cli.py` |
| 6.4 | Add config validation command | `auto_import/cli.py` |
| 6.5 | Create systemd service file | `auto_import/systemd/` |
| 6.6 | Create Windows service wrapper (optional) | `auto_import/windows/` |

**Deliverable:** Full CLI management and system service integration.

---

## CLI Interface

```bash
# Service management
pyphoto-autoimport start [--config /path/to/config.yaml]
pyphoto-autoimport stop
pyphoto-autoimport restart
pyphoto-autoimport status

# Manual operations
pyphoto-autoimport run-once [--config /path/to/config.yaml]
pyphoto-autoimport scan [--directory /path/to/dir]

# Configuration
pyphoto-autoimport validate-config /path/to/config.yaml
pyphoto-autoimport generate-config > config.yaml

# Reporting
pyphoto-autoimport last-report
pyphoto-autoimport send-test-email

# Debugging
pyphoto-autoimport --foreground  # Run in foreground for debugging
pyphoto-autoimport --verbose     # Extra logging
```

---

## Email Report Template

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .header { background: #4a90d9; color: white; padding: 20px; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-box { background: #f5f5f5; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-number { font-size: 24px; font-weight: bold; color: #333; }
        .stat-label { color: #666; }
        .success { color: #28a745; }
        .warning { color: #ffc107; }
        .error { color: #dc3545; }
        .file-list { max-height: 300px; overflow-y: auto; }
        .file-item { padding: 5px; border-bottom: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📸 Photo Import Report</h1>
        <p>{{ timestamp }}</p>
    </div>

    <div class="stats">
        <div class="stat-box">
            <div class="stat-number success">{{ files_imported }}</div>
            <div class="stat-label">Imported</div>
        </div>
        <div class="stat-box">
            <div class="stat-number">{{ files_duplicate }}</div>
            <div class="stat-label">Duplicates</div>
        </div>
        <div class="stat-box">
            <div class="stat-number warning">{{ files_filtered }}</div>
            <div class="stat-label">Filtered</div>
        </div>
        <div class="stat-box">
            <div class="stat-number error">{{ files_failed }}</div>
            <div class="stat-label">Failed</div>
        </div>
    </div>

    <h2>Summary</h2>
    <ul>
        <li>Duration: {{ duration }}</li>
        <li>Data processed: {{ bytes_processed | filesizeformat }}</li>
        <li>Directories scanned: {{ directories_scanned }}</li>
    </ul>

    {% if imported_files %}
    <h2>Imported Files</h2>
    <div class="file-list">
        {% for file in imported_files[:max_files] %}
        <div class="file-item">{{ file }}</div>
        {% endfor %}
        {% if imported_files|length > max_files %}
        <div class="file-item"><em>... and {{ imported_files|length - max_files }} more</em></div>
        {% endif %}
    </div>
    {% endif %}

    {% if errors %}
    <h2 class="error">Errors</h2>
    <ul>
        {% for error in errors %}
        <li>{{ error }}</li>
        {% endfor %}
    </ul>
    {% endif %}

    <hr>
    <p style="color: #666; font-size: 12px;">
        PyPhotoOrganizer Auto-Import Service<br>
        Database: {{ database_path }}
    </p>
</body>
</html>
```

---

## State Persistence

Track processed files to avoid re-importing:

```python
# State stored in SQLite (same DB or separate)

CREATE TABLE AutoImportState (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_size INTEGER,
    file_mtime REAL,
    first_seen TEXT,
    processed_at TEXT,
    status TEXT,  -- 'pending', 'imported', 'duplicate', 'filtered', 'failed'
    result_hash TEXT,  -- Hash if imported
    error_message TEXT
);

CREATE TABLE AutoImportRuns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE,
    start_time TEXT,
    end_time TEXT,
    files_scanned INTEGER,
    files_imported INTEGER,
    files_duplicate INTEGER,
    files_filtered INTEGER,
    files_failed INTEGER,
    report_sent INTEGER DEFAULT 0,
    config_hash TEXT  -- Detect config changes
);
```

---

## Security Considerations

1. **Credential Storage**
   - SMTP passwords via environment variables or system keyring
   - Never store plaintext passwords in config files
   - Support for OAuth2 for Gmail/Outlook (future)

2. **File Permissions**
   - Service runs as dedicated user (not root)
   - Watched directories need read access
   - Archive directory needs write access
   - Config file should be readable only by service user

3. **Input Validation**
   - Validate file paths to prevent directory traversal
   - Sanitize filenames before processing
   - Limit file sizes to prevent DoS

4. **Rate Limiting**
   - Configurable max files per run
   - Configurable max bytes per run
   - Backoff on repeated failures

---

## Systemd Service File

```ini
# /etc/systemd/system/pyphoto-autoimport.service

[Unit]
Description=PyPhotoOrganizer Auto-Import Service
After=network.target

[Service]
Type=simple
User=photoservice
Group=photoservice
ExecStart=/usr/local/bin/pyphoto-autoimport start --foreground
ExecStop=/usr/local/bin/pyphoto-autoimport stop
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=30

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/lib/pyphoto /path/to/archive
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pyphoto-autoimport

[Install]
WantedBy=multi-user.target
```

---

## Testing Strategy

### Unit Tests
- ConfigManager parsing
- DirectoryWatcher file detection
- ReportManager template rendering
- Scheduler interval calculations

### Integration Tests
- End-to-end import with test files
- Email sending (with mock SMTP)
- State persistence and recovery

### Manual Testing
- Long-running stability test
- Network interruption recovery
- Large batch processing

---

## Dependencies

**Required:**
```
PyYAML           # Config file parsing
schedule         # Cron-like scheduling (or APScheduler)
Jinja2           # Email template rendering
```

**Optional:**
```
watchdog         # Filesystem events (alternative to polling)
keyring          # Secure credential storage
python-daemon    # Unix daemon support
pywin32          # Windows service support
```

---

## Future Enhancements

1. **Web Dashboard**
   - Real-time status monitoring
   - Manual trigger button
   - View recent reports

2. **Mobile Push Notifications**
   - Pushover, Pushbullet integration
   - iOS/Android native notifications

3. **Webhooks**
   - POST import results to URL
   - Integration with home automation (Home Assistant)

4. **Multi-Database Support**
   - Route files to different databases based on rules
   - Support for family member separation

5. **Smart Scheduling**
   - Detect high-activity periods
   - Adaptive interval based on new file rate

---

## Estimated Effort

| Phase | Scope | Complexity |
|-------|-------|------------|
| Phase 1 | Core Service | Medium |
| Phase 2 | Directory Watching | Low |
| Phase 3 | Import Processing | Medium |
| Phase 4 | Reporting | Medium |
| Phase 5 | Scheduling | Low |
| Phase 6 | CLI/System Integration | Medium |

**Total:** 4-6 focused development sessions

---

## Success Criteria

- [ ] Service starts and runs without crashing for 24+ hours
- [ ] Correctly detects and imports new files
- [ ] Handles unavailable directories gracefully
- [ ] Sends email reports successfully
- [ ] Recovers from restart without re-processing files
- [ ] Respects quiet hours configuration
- [ ] Logs comprehensively for debugging

---

*Document created: 2026-01-28*
