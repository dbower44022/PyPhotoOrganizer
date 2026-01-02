"""
Database Metadata Management

Manages database metadata including archive location, creation date, and statistics.
Each database is tied to a specific archive location.
"""

import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


logger = logging.getLogger(__name__)


class DatabaseMetadata:
    """Manages database metadata and archive location binding."""

    METADATA_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS DatabaseMetadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            database_name TEXT NOT NULL,
            description TEXT,
            archive_location TEXT NOT NULL,
            video_archive_location TEXT,
            separate_video_archive INTEGER DEFAULT 0,
            created_date TEXT NOT NULL,
            last_used_date TEXT,
            schema_version INTEGER DEFAULT 1,
            total_photos INTEGER DEFAULT 0
        );
    """

    def __init__(self, database_path: str):
        """
        Initialize database metadata manager.

        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path
        self._ensure_metadata_table()

    def _ensure_metadata_table(self):
        """Ensure the metadata table exists in the database with all columns."""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.METADATA_TABLE_SCHEMA)

                # Check if new columns exist (for upgrading old databases)
                cursor.execute("PRAGMA table_info(DatabaseMetadata)")
                columns = [row[1] for row in cursor.fetchall()]

                # Add video_archive_location column if missing
                if 'video_archive_location' not in columns:
                    logger.info("Upgrading database: adding video_archive_location column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN video_archive_location TEXT")

                # Add separate_video_archive column if missing
                if 'separate_video_archive' not in columns:
                    logger.info("Upgrading database: adding separate_video_archive column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN separate_video_archive INTEGER DEFAULT 0")

                conn.commit()
                logger.debug(f"Metadata table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create/upgrade metadata table: {e}")
            raise

    def ensure_all_tables(self):
        """
        Ensure all required tables exist in the database.
        This includes both DatabaseMetadata and UniquePhotos tables.
        Useful for upgrading old databases.
        """
        try:
            # Ensure metadata table exists
            self._ensure_metadata_table()

            # Ensure UniquePhotos table exists
            import DuplicateFileDetection
            with DuplicateFileDetection.PhotoDatabase(self.database_path) as db:
                db.initialize_database()

            logger.info(f"All required tables ensured in {self.database_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to ensure all tables: {e}")
            return False

    def initialize_metadata(self, database_name: str, archive_location: str,
                          description: str = "") -> bool:
        """
        Initialize metadata for a new database.

        Args:
            database_name: User-friendly name for the database
            archive_location: Absolute path to the archive (destination) folder
            description: Optional description

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate archive location
            if not os.path.isabs(archive_location):
                raise ValueError("Archive location must be an absolute path")

            created_date = datetime.now().isoformat()

            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()

                # Check if metadata already exists
                cursor.execute("SELECT COUNT(*) FROM DatabaseMetadata")
                count = cursor.fetchone()[0]

                if count > 0:
                    logger.warning(f"Metadata already exists for {self.database_path}")
                    return False

                # Insert metadata
                cursor.execute("""
                    INSERT INTO DatabaseMetadata
                    (id, database_name, description, archive_location, created_date, last_used_date, total_photos)
                    VALUES (1, ?, ?, ?, ?, ?, 0)
                """, (database_name, description, archive_location, created_date, created_date))

                conn.commit()
                logger.info(f"Initialized metadata for database: {database_name}")
                return True

        except Exception as e:
            logger.error(f"Failed to initialize metadata: {e}")
            raise

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get database metadata.

        Returns:
            Dictionary with metadata or None if not found
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT database_name, description, archive_location, video_archive_location,
                           separate_video_archive, created_date, last_used_date, schema_version, total_photos
                    FROM DatabaseMetadata WHERE id = 1
                """)

                row = cursor.fetchone()
                if row:
                    return {
                        'database_name': row[0],
                        'description': row[1],
                        'archive_location': row[2],
                        'video_archive_location': row[3],
                        'separate_video_archive': bool(row[4]),
                        'created_date': row[5],
                        'last_used_date': row[6],
                        'schema_version': row[7],
                        'total_photos': row[8]
                    }
                return None

        except sqlite3.OperationalError:
            # Metadata table doesn't exist (old database)
            logger.warning(f"No metadata table in {self.database_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return None

    def get_archive_location(self) -> Optional[str]:
        """
        Get the archive location for this database.

        Returns:
            Archive location path or None if not found
        """
        metadata = self.get_metadata()
        return metadata['archive_location'] if metadata else None

    def get_video_archive_location(self) -> Optional[str]:
        """
        Get the video archive location for this database.

        Returns:
            Video archive location path or None if not set
        """
        metadata = self.get_metadata()
        return metadata.get('video_archive_location') if metadata else None

    def is_separate_video_archive_enabled(self) -> bool:
        """
        Check if separate video archive is enabled.

        Returns:
            True if separate video archive is enabled, False otherwise
        """
        metadata = self.get_metadata()
        return metadata.get('separate_video_archive', False) if metadata else False

    def set_video_archive(self, video_archive_location: str, enabled: bool = True) -> bool:
        """
        Set or update the video archive location.

        Args:
            video_archive_location: Path to video archive folder
            enabled: Whether to enable separate video archive

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate path if enabling
            if enabled and video_archive_location:
                if not os.path.isabs(video_archive_location):
                    raise ValueError("Video archive location must be an absolute path")

            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET video_archive_location = ?,
                        separate_video_archive = ?
                    WHERE id = 1
                """, (video_archive_location if enabled else None, 1 if enabled else 0))
                conn.commit()

                logger.info(f"Video archive {'enabled' if enabled else 'disabled'}: {video_archive_location if enabled else 'N/A'}")
                return True

        except Exception as e:
            logger.error(f"Failed to set video archive: {e}")
            return False

    def update_last_used(self):
        """Update the last used timestamp."""
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET last_used_date = ?
                    WHERE id = 1
                """, (datetime.now().isoformat(),))
                conn.commit()
                logger.debug("Updated last_used_date")
        except Exception as e:
            logger.error(f"Failed to update last_used_date: {e}")

    def update_total_photos(self, count: int):
        """
        Update the total photos count.

        Args:
            count: New total photos count
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET total_photos = ?
                    WHERE id = 1
                """, (count,))
                conn.commit()
                logger.debug(f"Updated total_photos to {count}")
        except Exception as e:
            logger.error(f"Failed to update total_photos: {e}")

    def refresh_total_photos(self):
        """
        Refresh the total photos count by querying the UniquePhotos table.
        This should be called after processing files to update the count.
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()

                # Count rows in UniquePhotos table
                cursor.execute("SELECT COUNT(*) FROM UniquePhotos")
                count = cursor.fetchone()[0]

                # Update the metadata
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET total_photos = ?
                    WHERE id = 1
                """, (count,))
                conn.commit()

                logger.info(f"Refreshed total_photos to {count} from UniquePhotos table")
                return count
        except Exception as e:
            logger.error(f"Failed to refresh total_photos: {e}")
            return 0

    def update_archive_location(self, new_location: str) -> bool:
        """
        Update the archive location (for future migration feature).

        Args:
            new_location: New archive location path

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.isabs(new_location):
                raise ValueError("Archive location must be an absolute path")

            with sqlite3.connect(self.database_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET archive_location = ?
                    WHERE id = 1
                """, (new_location,))
                conn.commit()
                logger.info(f"Updated archive location to: {new_location}")
                return True

        except Exception as e:
            logger.error(f"Failed to update archive location: {e}")
            return False

    @staticmethod
    def find_databases(search_path: str = ".") -> List[Dict[str, Any]]:
        """
        Find all PyPhotoOrganizer databases in a directory.

        Args:
            search_path: Directory to search for databases

        Returns:
            List of dictionaries with database info
        """
        databases = []

        try:
            search_dir = Path(search_path)
            for db_file in search_dir.glob("*.db"):
                try:
                    db_meta = DatabaseMetadata(str(db_file))
                    metadata = db_meta.get_metadata()

                    if metadata:
                        databases.append({
                            'path': str(db_file.absolute()),
                            'filename': db_file.name,
                            **metadata
                        })
                except Exception as e:
                    logger.debug(f"Skipping {db_file}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to search for databases: {e}")

        return databases

    @staticmethod
    def create_database(database_path: str, database_name: str,
                       archive_location: str, description: str = "") -> bool:
        """
        Create a new database with metadata and UniquePhotos table.

        Args:
            database_path: Path for the new database file
            database_name: User-friendly name
            archive_location: Archive (destination) location
            description: Optional description

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create database file if it doesn't exist
            if os.path.exists(database_path):
                raise FileExistsError(f"Database already exists: {database_path}")

            # Create parent directory if needed
            parent_dir = os.path.dirname(database_path)
            if parent_dir:  # Only create if there's a parent directory
                os.makedirs(parent_dir, exist_ok=True)

            # Create database with metadata
            db_meta = DatabaseMetadata(database_path)
            success = db_meta.initialize_metadata(database_name, archive_location, description)

            if not success:
                return False

            # Initialize UniquePhotos table
            # Import here to avoid circular dependency
            import DuplicateFileDetection
            with DuplicateFileDetection.PhotoDatabase(database_path) as db:
                db.initialize_database()

            logger.info(f"Created new database with all tables: {database_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            raise
