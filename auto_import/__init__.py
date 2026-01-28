"""
PyPhotoOrganizer Auto-Import Service.

A background service that monitors directories for new photos/videos,
automatically imports them to the archive, and sends reports.

Usage:
    # As a module
    python -m auto_import start --config /path/to/config.yaml

    # Or import directly
    from auto_import import ServiceManager, ConfigManager

    config = ConfigManager.load('config.yaml')
    service = ServiceManager(config)
    service.start()
"""

from auto_import.config import (
    ServiceConfig,
    WatchConfig,
    ScheduleConfig,
    NotificationConfig,
    EmailConfig,
    ProcessingConfig,
    ConfigManager,
)
from auto_import.service import ServiceManager
from auto_import.processor import ImportProcessor, ImportResult, ImportedFile
from auto_import.watcher import DirectoryWatcher, NewFile
from auto_import.reporter import ReportManager
from auto_import.scheduler import Scheduler

__version__ = '1.0.0'
__all__ = [
    # Service
    'ServiceManager',
    # Config
    'ConfigManager',
    'ServiceConfig',
    'WatchConfig',
    'ScheduleConfig',
    'NotificationConfig',
    'EmailConfig',
    'ProcessingConfig',
    # Processing
    'ImportProcessor',
    'ImportResult',
    'ImportedFile',
    # Watcher
    'DirectoryWatcher',
    'NewFile',
    # Reporter
    'ReportManager',
    # Scheduler
    'Scheduler',
]
