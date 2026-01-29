"""
Database Schema Definitions

Provides SQL schema definitions for all database tables used by PyPhotoOrganizer.
This module centralizes table definitions for:
- Easier maintenance and version control
- Documentation of schema structure
- Schema version tracking

Tables:
- UniquePhotos: Main file tracking table
- SourceDirectories: Import source configuration
- SourceDirectorySubAlbums: Sub-album mappings
- UnreliableDates: Files with questionable dates
- FileRenameHistory: Filename change tracking
- Albums / AlbumPhotos: Album system
- ImportSession / FileProcessingLog: Audit trail
- DeletedFiles: Soft-delete tracking
- ThumbnailCache: Thumbnail caching metadata
- MetadataUpgradeHistory: Archive upgrade tracking
- PendingOperations: Crash recovery
- QuickBackups: Backup tracking
- AuditQueue: Failed audit entries
- SavedQueries: User-saved filters

Current Schema Version: 7 (Metadata Quality Tracking)
"""

from typing import Dict, List, Optional
import constants

# Current schema version
SCHEMA_VERSION = 9

# Schema version history
SCHEMA_VERSION_HISTORY = {
    1: "Initial schema",
    2: "Added content_hash column",
    3: "Added revision tracking (revised_photo, revision_reason)",
    4: "Added metadata_upgrade_history table",
    5: "Unified schema - all hashes in UniquePhotos",
    6: "Relative paths for portable archives",
    7: "Metadata quality tracking (date_source, date_reliable, metadata_quality_score)",
    8: "Cloud storage support (CloudSyncStatus, storage backend tracking)",
    9: "Video content hashing (video_content_hash column)"
}


# ============================================================================
# Core Tables
# ============================================================================

UNIQUE_PHOTOS_TABLE = """
CREATE TABLE IF NOT EXISTS UniquePhotos (
    file_hash TEXT PRIMARY KEY,
    file_name TEXT,
    create_datetime TEXT,
    create_year TEXT,
    create_month TEXT,
    create_day TEXT,
    partial_hash TEXT,
    partial_hash_bytes INTEGER,
    content_hash TEXT,
    video_content_hash TEXT,
    file_size INTEGER,
    revised_photo TEXT,
    revision_reason TEXT,
    revision_timestamp TEXT,
    relative_path TEXT,
    storage_type TEXT DEFAULT 'archive',
    date_source TEXT DEFAULT 'os_metadata',
    date_reliable INTEGER DEFAULT 1,
    metadata_quality_score INTEGER DEFAULT 0,
    FOREIGN KEY (revised_photo) REFERENCES UniquePhotos(file_hash)
)
"""

UNIQUE_PHOTOS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_year ON UniquePhotos(create_year)",
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_month ON UniquePhotos(create_month)",
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_day ON UniquePhotos(create_day)",
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_content ON UniquePhotos(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_video_content ON UniquePhotos(video_content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_revised ON UniquePhotos(revised_photo)",
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_storage ON UniquePhotos(storage_type)",
    "CREATE INDEX IF NOT EXISTS idx_unique_photos_date_source ON UniquePhotos(date_source)",
]


# ============================================================================
# Metadata Table
# ============================================================================

ARCHIVE_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS ArchiveMetadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    database_name TEXT,
    archive_location TEXT,
    video_archive_location TEXT,
    video_archive_enabled INTEGER DEFAULT 0,
    prior_revision_archive_location TEXT,
    delete_vault_location TEXT,
    total_photos INTEGER DEFAULT 0,
    last_used TEXT,
    created_date TEXT,
    schema_version INTEGER DEFAULT 9,
    organization_template TEXT DEFAULT '{year}/{month}/{day}',
    file_type_organization TEXT DEFAULT 'combined',
    enable_file_rename INTEGER DEFAULT 0,
    filename_template TEXT DEFAULT '{original_name}',
    user_specified_unreliable_paths TEXT,
    thumbnail_size INTEGER DEFAULT 200,
    cache_memory_mb INTEGER DEFAULT 256,
    cache_worker_threads INTEGER DEFAULT 4,
    scroll_speed_percent INTEGER DEFAULT 67,
    preview_window_geometry TEXT,
    preview_window_visible INTEGER DEFAULT 0,
    ignored_directories TEXT DEFAULT '[]',
    -- Schema v8: Cloud storage configuration
    storage_config TEXT,
    cloud_sync_enabled INTEGER DEFAULT 0,
    cloud_last_sync TEXT
)
"""


# ============================================================================
# Source Directory Tables
# ============================================================================

SOURCE_DIRECTORIES_TABLE = """
CREATE TABLE IF NOT EXISTS SourceDirectories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    enabled INTEGER DEFAULT 1,
    last_scanned TEXT,
    display_order INTEGER DEFAULT 0,
    associated_album_id INTEGER,
    create_sub_albums INTEGER DEFAULT 0,
    FOREIGN KEY (associated_album_id) REFERENCES Albums(id) ON DELETE SET NULL
)
"""

SOURCE_DIRECTORY_SUB_ALBUMS_TABLE = """
CREATE TABLE IF NOT EXISTS SourceDirectorySubAlbums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_directory_id INTEGER NOT NULL,
    parent_album_id INTEGER NOT NULL,
    subfolder_path TEXT NOT NULL,
    album_id INTEGER NOT NULL,
    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_directory_id) REFERENCES SourceDirectories(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_album_id) REFERENCES Albums(id) ON DELETE CASCADE,
    FOREIGN KEY (album_id) REFERENCES Albums(id) ON DELETE CASCADE,
    UNIQUE (source_directory_id, subfolder_path)
)
"""


# ============================================================================
# Album Tables
# ============================================================================

ALBUMS_TABLE = """
CREATE TABLE IF NOT EXISTS Albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    storage_location TEXT,
    sync_deletions INTEGER DEFAULT 0,
    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_date TEXT DEFAULT CURRENT_TIMESTAMP,
    parent_id INTEGER,
    is_sub_album INTEGER DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES Albums(id) ON DELETE CASCADE
)
"""

ALBUM_PHOTOS_TABLE = """
CREATE TABLE IF NOT EXISTS AlbumPhotos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    album_file_path TEXT,
    added_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (album_id) REFERENCES Albums(id) ON DELETE CASCADE,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash) ON DELETE CASCADE,
    UNIQUE (album_id, file_hash)
)
"""

ALBUM_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_album_photos_album ON AlbumPhotos(album_id)",
    "CREATE INDEX IF NOT EXISTS idx_album_photos_hash ON AlbumPhotos(file_hash)",
]


# ============================================================================
# Audit Tables
# ============================================================================

IMPORT_SESSION_TABLE = """
CREATE TABLE IF NOT EXISTS ImportSession (
    session_id TEXT PRIMARY KEY,
    start_time TEXT,
    end_time TEXT,
    status TEXT,
    operation_mode TEXT,
    source_directories TEXT,
    destination_directory TEXT,
    total_files_scanned INTEGER DEFAULT 0,
    total_files_processed INTEGER DEFAULT 0,
    total_unique_files INTEGER DEFAULT 0,
    total_duplicates_found INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    total_bytes_processed INTEGER DEFAULT 0,
    filters_applied TEXT,
    notes TEXT
)
"""

FILE_PROCESSING_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS FileProcessingLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    timestamp TEXT,
    source_path TEXT,
    destination_path TEXT,
    file_hash TEXT,
    file_size INTEGER,
    operation TEXT,
    status TEXT,
    error_message TEXT,
    duplicate_of TEXT,
    processing_time_ms INTEGER,
    metadata_source TEXT,
    date_reliable INTEGER,
    FOREIGN KEY (session_id) REFERENCES ImportSession(session_id)
)
"""

AUDIT_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS AuditQueue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    last_retry_timestamp TEXT
)
"""

AUDIT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_file_log_session ON FileProcessingLog(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_file_log_hash ON FileProcessingLog(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_file_log_status ON FileProcessingLog(status)",
]


# ============================================================================
# Date Correction Tables
# ============================================================================

UNRELIABLE_DATES_TABLE = """
CREATE TABLE IF NOT EXISTS UnreliableDates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL UNIQUE,
    source_path TEXT,
    archive_path TEXT,
    detected_date TEXT,
    detection_reason TEXT,
    corrected_date TEXT,
    correction_timestamp TEXT,
    correction_applied INTEGER DEFAULT 0,
    reorganize_needed INTEGER DEFAULT 0,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
)
"""

UNRELIABLE_DATES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_unreliable_hash ON UnreliableDates(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_unreliable_reason ON UnreliableDates(detection_reason)",
    "CREATE INDEX IF NOT EXISTS idx_unreliable_reorganize ON UnreliableDates(reorganize_needed)",
]


# ============================================================================
# File Tracking Tables
# ============================================================================

FILE_RENAME_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS FileRenameHistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    new_filename TEXT NOT NULL,
    renamed_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
)
"""

DELETED_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS DeletedFiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    original_path TEXT NOT NULL,
    vault_path TEXT,
    deleted_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    deletion_reason TEXT,
    file_size INTEGER,
    can_restore INTEGER DEFAULT 1,
    restored_timestamp TEXT,
    restored_path TEXT,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
)
"""

DELETED_FILES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_deleted_hash ON DeletedFiles(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_deleted_timestamp ON DeletedFiles(deleted_timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_deleted_can_restore ON DeletedFiles(can_restore)",
]


# ============================================================================
# Cache Tables
# ============================================================================

THUMBNAIL_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS ThumbnailCache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    thumbnail_size INTEGER NOT NULL,
    thumbnail_path TEXT NOT NULL,
    created_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    last_accessed TEXT DEFAULT CURRENT_TIMESTAMP,
    file_mtime REAL,
    UNIQUE (file_hash, thumbnail_size)
)
"""

THUMBNAIL_CACHE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_thumb_hash ON ThumbnailCache(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_thumb_accessed ON ThumbnailCache(last_accessed)",
]


# ============================================================================
# Recovery Tables
# ============================================================================

PENDING_OPERATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS PendingOperations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,
    source_path TEXT,
    destination_path TEXT,
    file_hash TEXT,
    status TEXT DEFAULT 'pending',
    created_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_timestamp TEXT,
    error_message TEXT,
    metadata TEXT
)
"""

PENDING_OPERATIONS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pending_status ON PendingOperations(status)",
    "CREATE INDEX IF NOT EXISTS idx_pending_hash ON PendingOperations(file_hash)",
]


# ============================================================================
# Backup Tables
# ============================================================================

QUICK_BACKUPS_TABLE = """
CREATE TABLE IF NOT EXISTS QuickBackups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_path TEXT NOT NULL,
    backup_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    backup_type TEXT DEFAULT 'quick',
    file_size INTEGER,
    notes TEXT
)
"""

METADATA_UPGRADE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS MetadataUpgradeHistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    old_path TEXT,
    new_source_path TEXT,
    upgrade_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    old_date_source TEXT,
    new_date_source TEXT,
    old_quality_score INTEGER,
    new_quality_score INTEGER,
    upgrade_reason TEXT,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
)
"""


# ============================================================================
# Cloud Storage Tables (Schema v8)
# ============================================================================

CLOUD_SYNC_STATUS_TABLE = """
CREATE TABLE IF NOT EXISTS CloudSyncStatus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    storage_location TEXT NOT NULL,
    cloud_provider TEXT,
    cloud_path TEXT,
    upload_status TEXT DEFAULT 'pending',
    upload_started TEXT,
    upload_completed TEXT,
    cloud_etag TEXT,
    cloud_storage_class TEXT,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    verified_at TEXT,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash),
    UNIQUE (file_hash, storage_location, cloud_provider)
)
"""

CLOUD_SYNC_STATUS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cloud_sync_status ON CloudSyncStatus(upload_status, storage_location)",
    "CREATE INDEX IF NOT EXISTS idx_cloud_sync_hash ON CloudSyncStatus(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_cloud_sync_provider ON CloudSyncStatus(cloud_provider)",
]

# Track files that exist in multiple locations (local + cloud)
FILE_LOCATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS FileLocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    location_type TEXT NOT NULL,
    storage_backend TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    cloud_provider TEXT,
    cloud_bucket TEXT,
    verified_at TEXT,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash),
    UNIQUE (file_hash, location_type, storage_backend)
)
"""

FILE_LOCATIONS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_file_locations_hash ON FileLocations(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_file_locations_type ON FileLocations(location_type, storage_backend)",
]

# Queue for pending cloud uploads (for offline support)
CLOUD_UPLOAD_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS CloudUploadQueue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    local_path TEXT NOT NULL,
    target_storage TEXT NOT NULL,
    target_path TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    queued_at TEXT DEFAULT CURRENT_TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    last_attempt TEXT,
    last_error TEXT,
    status TEXT DEFAULT 'queued',
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
)
"""

CLOUD_UPLOAD_QUEUE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_upload_queue_status ON CloudUploadQueue(status, priority)",
    "CREATE INDEX IF NOT EXISTS idx_upload_queue_hash ON CloudUploadQueue(file_hash)",
]


# ============================================================================
# Query Tables
# ============================================================================

SAVED_QUERIES_TABLE = """
CREATE TABLE IF NOT EXISTS SavedQueries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    query_json TEXT NOT NULL,
    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used TEXT
)
"""


# ============================================================================
# Helper Functions
# ============================================================================

def get_all_table_definitions() -> Dict[str, str]:
    """
    Get all table creation SQL statements.

    Returns:
        Dict mapping table name to CREATE TABLE SQL
    """
    return {
        'UniquePhotos': UNIQUE_PHOTOS_TABLE,
        'ArchiveMetadata': ARCHIVE_METADATA_TABLE,
        'SourceDirectories': SOURCE_DIRECTORIES_TABLE,
        'SourceDirectorySubAlbums': SOURCE_DIRECTORY_SUB_ALBUMS_TABLE,
        'Albums': ALBUMS_TABLE,
        'AlbumPhotos': ALBUM_PHOTOS_TABLE,
        'ImportSession': IMPORT_SESSION_TABLE,
        'FileProcessingLog': FILE_PROCESSING_LOG_TABLE,
        'AuditQueue': AUDIT_QUEUE_TABLE,
        'UnreliableDates': UNRELIABLE_DATES_TABLE,
        'FileRenameHistory': FILE_RENAME_HISTORY_TABLE,
        'DeletedFiles': DELETED_FILES_TABLE,
        'ThumbnailCache': THUMBNAIL_CACHE_TABLE,
        'PendingOperations': PENDING_OPERATIONS_TABLE,
        'QuickBackups': QUICK_BACKUPS_TABLE,
        'MetadataUpgradeHistory': METADATA_UPGRADE_HISTORY_TABLE,
        'SavedQueries': SAVED_QUERIES_TABLE,
        # Schema v8: Cloud storage tables
        'CloudSyncStatus': CLOUD_SYNC_STATUS_TABLE,
        'FileLocations': FILE_LOCATIONS_TABLE,
        'CloudUploadQueue': CLOUD_UPLOAD_QUEUE_TABLE,
    }


def get_all_indexes() -> List[str]:
    """
    Get all index creation SQL statements.

    Returns:
        List of CREATE INDEX SQL statements
    """
    indexes = []
    indexes.extend(UNIQUE_PHOTOS_INDEXES)
    indexes.extend(ALBUM_INDEXES)
    indexes.extend(AUDIT_INDEXES)
    indexes.extend(UNRELIABLE_DATES_INDEXES)
    indexes.extend(DELETED_FILES_INDEXES)
    indexes.extend(THUMBNAIL_CACHE_INDEXES)
    indexes.extend(PENDING_OPERATIONS_INDEXES)
    # Schema v8: Cloud storage indexes
    indexes.extend(CLOUD_SYNC_STATUS_INDEXES)
    indexes.extend(FILE_LOCATIONS_INDEXES)
    indexes.extend(CLOUD_UPLOAD_QUEUE_INDEXES)
    return indexes


def get_schema_version_description(version: int) -> str:
    """
    Get description of a schema version.

    Parameters:
        version: Schema version number

    Returns:
        Description string or "Unknown" if not found
    """
    return SCHEMA_VERSION_HISTORY.get(version, "Unknown version")
