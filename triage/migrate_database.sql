-- Database Migration Script for Photo Triage Application
-- Adds tables and indexes needed for high-performance photo triage features
--
-- Usage: Run this script on existing PyPhotoOrganizer databases
-- Safe to run multiple times (uses IF NOT EXISTS)

-- ============================================================================
-- TriageActions Table - Track all marking actions
-- ============================================================================
CREATE TABLE IF NOT EXISTS TriageActions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    action_type TEXT NOT NULL,  -- 'delete', 'favorite', 'date_correction'
    marked_timestamp TEXT NOT NULL,
    unmarked_timestamp TEXT,    -- NULL if still marked
    notes TEXT,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_triage_file_hash
    ON TriageActions(file_hash);

CREATE INDEX IF NOT EXISTS idx_triage_action_type
    ON TriageActions(action_type);

CREATE INDEX IF NOT EXISTS idx_triage_active
    ON TriageActions(unmarked_timestamp);  -- Fast query for active marks

-- ============================================================================
-- ThumbnailCache Table - Track disk-cached thumbnails
-- ============================================================================
CREATE TABLE IF NOT EXISTS ThumbnailCache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL UNIQUE,
    thumbnail_path TEXT NOT NULL,
    thumbnail_size INTEGER NOT NULL,  -- 256, 512, 1024
    created_timestamp TEXT NOT NULL,
    last_accessed_timestamp TEXT NOT NULL,
    file_modified_timestamp TEXT NOT NULL,  -- Detect if source changed
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
);

-- Index for LRU eviction
CREATE INDEX IF NOT EXISTS idx_thumb_last_accessed
    ON ThumbnailCache(last_accessed_timestamp);

-- ============================================================================
-- FavoritesArchive Table - Configuration for favorites
-- ============================================================================
CREATE TABLE IF NOT EXISTS FavoritesArchive (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    archive_location TEXT,
    auto_copy_enabled INTEGER DEFAULT 0
);

-- ============================================================================
-- Performance Index on Existing Table
-- ============================================================================
-- Fast folder queries: WHERE file_name LIKE '/archive/2025/02/%'
CREATE INDEX IF NOT EXISTS idx_file_name_prefix
    ON UniquePhotos(file_name);
