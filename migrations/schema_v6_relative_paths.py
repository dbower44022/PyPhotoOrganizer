"""
Schema v6 Migration: Relative Path Storage

This migration populates the relative_path and storage_type columns in UniquePhotos
and related tables from existing absolute paths.

The schema columns are automatically created via ALTER TABLE when the database is opened
(handled by DuplicateFileDetection.initialize_database() and database_metadata._ensure_*_table()).

This script handles populating those columns with data derived from existing absolute paths.

Usage:
    from migrations.schema_v6_relative_paths import migrate_to_relative_paths

    # Migrate existing database
    success, message = migrate_to_relative_paths(
        database_path='/path/to/PhotoDB.db',
        dry_run=False  # Set True to preview without changes
    )

Storage Type Detection Priority:
    1. prior_revision_archive (check first - may be subdirectory)
    2. video_archive
    3. archive (default)
    4. 'unknown' (fallback if no base matches)
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def migrate_to_relative_paths(
    database_path: str,
    dry_run: bool = False,
    batch_size: int = 1000,
    progress_callback: callable = None
) -> Tuple[bool, str]:
    """
    Migrate existing absolute paths to relative paths in the database.

    This function:
    1. Creates a pre-migration backup
    2. Reads archive locations from DatabaseMetadata
    3. Iterates through UniquePhotos and converts absolute paths to relative
    4. Updates related tables (UnreliableDates, AlbumPhotos, DeletedFiles)
    5. Reports statistics on migrated records

    Args:
        database_path: Path to the SQLite database file
        dry_run: If True, analyze but don't make changes
        batch_size: Number of records to process per batch
        progress_callback: Optional callback(current, total, message) for progress updates

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        if not os.path.exists(database_path):
            return False, f"Database not found: {database_path}"

        # Connect to database
        conn = sqlite3.connect(database_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        cursor = conn.cursor()

        # Get archive locations from DatabaseMetadata
        cursor.execute("""
            SELECT archive_location, video_archive_location, prior_revision_archive_location
            FROM DatabaseMetadata WHERE id = 1
        """)
        metadata_row = cursor.fetchone()

        if not metadata_row:
            conn.close()
            return False, "No metadata found in database. Cannot determine archive locations."

        archive_location = metadata_row[0]
        video_archive_location = metadata_row[1]
        prior_revision_location = metadata_row[2]

        if not archive_location:
            conn.close()
            return False, "Archive location not configured. Cannot compute relative paths."

        logger.info(f"Migration starting with locations:")
        logger.info(f"  Archive: {archive_location}")
        logger.info(f"  Video Archive: {video_archive_location}")
        logger.info(f"  Prior Revision: {prior_revision_location}")

        # Create backup before migration (unless dry run)
        if not dry_run:
            backup_result = _create_backup(conn, cursor)
            if not backup_result[0]:
                logger.warning(f"Could not create backup: {backup_result[1]}")
                # Continue anyway - backup is not strictly required

        # Check how many records need migration
        # Use storage_type IS NULL as the indicator (not relative_path)
        # because relative_path can legitimately be NULL for 'unknown' storage types
        cursor.execute("""
            SELECT COUNT(*) FROM UniquePhotos
            WHERE storage_type IS NULL AND file_name IS NOT NULL
        """)
        total_unique = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM UnreliableDates
            WHERE relative_archive_path IS NULL AND archive_path IS NOT NULL
        """)
        total_unreliable = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM AlbumPhotos
            WHERE relative_album_path IS NULL AND album_file_path IS NOT NULL
        """)
        total_album = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM DeletedFiles
            WHERE relative_archive_path IS NULL AND original_archive_path IS NOT NULL
        """)
        total_deleted = cursor.fetchone()[0]

        total_records = total_unique + total_unreliable + total_album + total_deleted

        logger.info(f"Records to migrate:")
        logger.info(f"  UniquePhotos: {total_unique}")
        logger.info(f"  UnreliableDates: {total_unreliable}")
        logger.info(f"  AlbumPhotos: {total_album}")
        logger.info(f"  DeletedFiles: {total_deleted}")
        logger.info(f"  Total: {total_records}")

        if dry_run:
            # Just report what would be done
            stats = _analyze_paths(
                cursor, archive_location, video_archive_location, prior_revision_location
            )
            conn.close()
            return True, _format_dry_run_report(stats, total_records)

        # Migrate UniquePhotos
        migrated = 0
        errors = 0
        unknown_count = 0
        skipped = 0

        processed = 0
        while True:
            # Use storage_type IS NULL to track processed records
            # This prevents infinite loop when relative_path computation returns None
            cursor.execute("""
                SELECT file_hash, file_name FROM UniquePhotos
                WHERE storage_type IS NULL AND file_name IS NOT NULL
                LIMIT ?
            """, (batch_size,))
            rows = cursor.fetchall()

            if not rows:
                break

            for file_hash, file_name in rows:
                relative_path, storage_type = _compute_relative_path(
                    file_name, archive_location, video_archive_location, prior_revision_location
                )

                if storage_type == 'unknown':
                    unknown_count += 1
                    logger.debug(f"Unknown storage type for: {file_name}")

                # Always set storage_type (even if 'unknown') to mark as processed
                # relative_path may be None for unknown paths, that's OK
                try:
                    cursor.execute("""
                        UPDATE UniquePhotos
                        SET relative_path = ?, storage_type = ?
                        WHERE file_hash = ?
                    """, (relative_path, storage_type, file_hash))
                    migrated += 1
                except Exception as e:
                    logger.error(f"Failed to update {file_hash}: {e}")
                    errors += 1

                processed += 1
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, total_records, "Migrating UniquePhotos...")

            conn.commit()

        # Migrate UnreliableDates
        while True:
            cursor.execute("""
                SELECT id, archive_path FROM UnreliableDates
                WHERE relative_archive_path IS NULL AND archive_path IS NOT NULL
                LIMIT ?
            """, (batch_size,))
            rows = cursor.fetchall()

            if not rows:
                break

            for record_id, archive_path in rows:
                relative_path, _ = _compute_relative_path(
                    archive_path, archive_location, video_archive_location, prior_revision_location
                )

                try:
                    cursor.execute("""
                        UPDATE UnreliableDates
                        SET relative_archive_path = ?
                        WHERE id = ?
                    """, (relative_path, record_id))
                    migrated += 1
                except Exception as e:
                    logger.error(f"Failed to update UnreliableDates {record_id}: {e}")
                    errors += 1

                processed += 1
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, total_records, "Migrating UnreliableDates...")

            conn.commit()

        # Migrate AlbumPhotos - need album storage location for each
        cursor.execute("""
            SELECT ap.id, ap.album_file_path, a.storage_location
            FROM AlbumPhotos ap
            JOIN Albums a ON ap.album_id = a.id
            WHERE ap.relative_album_path IS NULL AND ap.album_file_path IS NOT NULL
        """)
        album_rows = cursor.fetchall()

        for record_id, album_file_path, album_storage in album_rows:
            if album_storage and album_file_path:
                try:
                    rel_path = os.path.relpath(album_file_path, album_storage)
                    rel_path = rel_path.replace(os.sep, '/')

                    cursor.execute("""
                        UPDATE AlbumPhotos
                        SET relative_album_path = ?
                        WHERE id = ?
                    """, (rel_path, record_id))
                    migrated += 1
                except ValueError:
                    # Different drives on Windows
                    errors += 1
                except Exception as e:
                    logger.error(f"Failed to update AlbumPhotos {record_id}: {e}")
                    errors += 1

            processed += 1
            if progress_callback and processed % 100 == 0:
                progress_callback(processed, total_records, "Migrating AlbumPhotos...")

        conn.commit()

        # Migrate DeletedFiles
        cursor.execute("""
            SELECT id, original_archive_path, delete_vault_path
            FROM DeletedFiles
            WHERE relative_archive_path IS NULL AND original_archive_path IS NOT NULL
        """)
        deleted_rows = cursor.fetchall()

        # Get delete vault location
        cursor.execute("SELECT delete_vault_location FROM DatabaseMetadata WHERE id = 1")
        vault_row = cursor.fetchone()
        delete_vault = vault_row[0] if vault_row else None

        for record_id, original_archive_path, delete_vault_path in deleted_rows:
            rel_archive_path, storage_type = _compute_relative_path(
                original_archive_path, archive_location, video_archive_location, prior_revision_location
            )

            rel_vault_path = None
            if delete_vault and delete_vault_path:
                try:
                    rel_vault_path = os.path.relpath(delete_vault_path, delete_vault)
                    rel_vault_path = rel_vault_path.replace(os.sep, '/')
                except ValueError:
                    pass  # Different drives

            try:
                cursor.execute("""
                    UPDATE DeletedFiles
                    SET relative_archive_path = ?, relative_vault_path = ?, archive_storage_type = ?
                    WHERE id = ?
                """, (rel_archive_path, rel_vault_path, storage_type, record_id))
                migrated += 1
            except Exception as e:
                logger.error(f"Failed to update DeletedFiles {record_id}: {e}")
                errors += 1

            processed += 1
            if progress_callback and processed % 100 == 0:
                progress_callback(processed, total_records, "Migrating DeletedFiles...")

        conn.commit()
        conn.close()

        # Final report
        message = (
            f"Migration completed successfully.\n"
            f"  Records migrated: {migrated}\n"
            f"  Unknown storage type: {unknown_count}\n"
            f"  Errors: {errors}"
        )

        logger.info(message)
        return True, message

    except Exception as e:
        logger.exception(f"Migration failed: {e}")
        return False, f"Migration failed: {e}"


def _compute_relative_path(
    absolute_path: str,
    archive_location: str,
    video_archive_location: str,
    prior_revision_location: str
) -> Tuple[Optional[str], str]:
    """
    Compute relative path and storage type from absolute path.

    Priority order for detection:
    1. prior_revision (may be subdirectory of archive)
    2. video_archive
    3. archive
    4. unknown

    Args:
        absolute_path: Full path to file
        archive_location: Main archive base path
        video_archive_location: Video archive base path (may be None)
        prior_revision_location: Prior revision archive base path (may be None)

    Returns:
        Tuple of (relative_path, storage_type)
    """
    if not absolute_path:
        return None, 'unknown'

    norm_path = os.path.normpath(absolute_path)

    # Check prior_revision first (may be subdirectory of archive)
    if prior_revision_location:
        norm_prior = os.path.normpath(prior_revision_location)
        if norm_path.startswith(norm_prior + os.sep) or norm_path == norm_prior:
            try:
                rel = os.path.relpath(norm_path, norm_prior)
                return rel.replace(os.sep, '/'), 'prior_revision'
            except ValueError:
                pass

    # Check video_archive
    if video_archive_location:
        norm_video = os.path.normpath(video_archive_location)
        if norm_path.startswith(norm_video + os.sep) or norm_path == norm_video:
            try:
                rel = os.path.relpath(norm_path, norm_video)
                return rel.replace(os.sep, '/'), 'video_archive'
            except ValueError:
                pass

    # Check archive
    if archive_location:
        norm_archive = os.path.normpath(archive_location)
        if norm_path.startswith(norm_archive + os.sep) or norm_path == norm_archive:
            try:
                rel = os.path.relpath(norm_path, norm_archive)
                return rel.replace(os.sep, '/'), 'archive'
            except ValueError:
                pass

    # No match found
    return None, 'unknown'


def _create_backup(conn: sqlite3.Connection, cursor: sqlite3.Cursor) -> Tuple[bool, str]:
    """
    Create a backup before migration using the quick backup system.

    Args:
        conn: Database connection
        cursor: Database cursor

    Returns:
        Tuple of (success, message)
    """
    try:
        import shutil
        from pathlib import Path

        # Get database path
        cursor.execute("PRAGMA database_list")
        db_info = cursor.fetchone()
        if not db_info:
            return False, "Could not determine database path"

        db_path = db_info[2]
        db_dir = Path(db_path).parent
        snapshots_dir = db_dir / "db_snapshots"
        snapshots_dir.mkdir(exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import uuid
        backup_name = f"db_snapshot_{timestamp}_pre_v6_migration_{uuid.uuid4().hex[:8]}.db"
        backup_path = snapshots_dir / backup_name

        # Checkpoint WAL before backup
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        # Copy database file
        shutil.copy2(db_path, backup_path)

        # Record in QuickBackups table
        db_size = os.path.getsize(db_path)
        cursor.execute("""
            INSERT INTO QuickBackups (backup_path, backup_reason, created_timestamp, database_size_bytes)
            VALUES (?, ?, ?, ?)
        """, (str(backup_path), "pre_v6_migration", datetime.now().isoformat(), db_size))
        conn.commit()

        logger.info(f"Created pre-migration backup: {backup_path}")
        return True, str(backup_path)

    except Exception as e:
        return False, str(e)


def _analyze_paths(
    cursor: sqlite3.Cursor,
    archive_location: str,
    video_archive_location: str,
    prior_revision_location: str
) -> Dict[str, int]:
    """
    Analyze paths to determine storage type distribution (for dry run).

    Returns:
        Dict with storage type counts
    """
    stats = {
        'archive': 0,
        'video_archive': 0,
        'prior_revision': 0,
        'unknown': 0
    }

    # Only analyze records that haven't been migrated yet
    cursor.execute("""
        SELECT file_name FROM UniquePhotos
        WHERE storage_type IS NULL AND file_name IS NOT NULL
        LIMIT 10000
    """)
    for row in cursor.fetchall():
        _, storage_type = _compute_relative_path(
            row[0], archive_location, video_archive_location, prior_revision_location
        )
        stats[storage_type] = stats.get(storage_type, 0) + 1

    return stats


def _format_dry_run_report(stats: Dict[str, int], total_records: int) -> str:
    """Format the dry run analysis report."""
    return (
        f"Dry run analysis (no changes made):\n"
        f"  Total records to migrate: {total_records}\n"
        f"  Storage type distribution (sample of first 10000):\n"
        f"    Archive: {stats.get('archive', 0)}\n"
        f"    Video Archive: {stats.get('video_archive', 0)}\n"
        f"    Prior Revision: {stats.get('prior_revision', 0)}\n"
        f"    Unknown: {stats.get('unknown', 0)}"
    )


# CLI interface for running migration standalone
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Migrate database to Schema v6 relative paths")
    parser.add_argument("database", help="Path to the database file")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without making changes")
    parser.add_argument("--batch-size", type=int, default=1000, help="Records per batch")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    def progress(current, total, message):
        print(f"\r{message} {current}/{total} ({100*current//total}%)", end="", flush=True)

    success, message = migrate_to_relative_paths(
        args.database,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        progress_callback=progress if not args.verbose else None
    )

    print()  # Newline after progress
    print(message)
    sys.exit(0 if success else 1)
