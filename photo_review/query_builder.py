"""
Photo Query Builder

Builds SQL queries for UniquePhotos table with various filters for the
Photo Review application.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


class PhotoQueryBuilder:
    """
    Builds SQL queries for UniquePhotos table with various filters.

    Supports:
    - Date range filters (creation, import via session join)
    - Status filters (unreliable dates, needs reorganization)
    - Filename pattern matching
    - Folder path filtering
    - Full-text search across filename and path
    """

    def __init__(self, db_path: str):
        """
        Initialize query builder.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

        # Get archive locations for version filtering
        from database_metadata import DatabaseMetadata
        db_metadata = DatabaseMetadata(db_path)
        self.archive_base = db_metadata.get_archive_location() or ''
        self.prior_archive_base = db_metadata.get_prior_revision_archive_location() or ''
        logger.debug(f"Archive base: {self.archive_base}")
        logger.debug(f"Prior archive base: {self.prior_archive_base}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with WAL mode."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def build_query(self, filters: Dict[str, Any]) -> Tuple[str, List]:
        """
        Build parameterized SQL query from filter dict.

        Args:
            filters: Dict with filter parameters:
                - creation_date_from: str (YYYY-MM-DD)
                - creation_date_to: str (YYYY-MM-DD)
                - import_date_from: str (YYYY-MM-DD)
                - import_date_to: str (YYYY-MM-DD)
                - correction_date_from: str (YYYY-MM-DD)
                - correction_date_to: str (YYYY-MM-DD)
                - has_unreliable_date: bool
                - has_corrected_date: bool
                - needs_reorganization: bool
                - has_revisions: bool
                - version_filter: str ('current', 'all', 'prior')
                - filename_pattern: str (substring match)
                - folder_path: str (exact folder match)
                - search_text: str (searches filename and path)

        Returns:
            tuple: (sql_query, params_list)
        """
        # Build base query joining UniquePhotos with UnreliableDates
        # Exclude files that have been deleted (in DeletedFiles with is_restored=0)
        base_query = """
            SELECT
                up.file_hash,
                up.file_name as archive_path,
                up.source_path,
                up.create_datetime,
                up.create_year,
                up.create_month,
                up.create_day,
                up.file_size,
                up.revised_photo,
                ud.corrected_date,
                ud.needs_reorganization,
                ud.flag_reason,
                ud.date_source,
                ud.original_date
            FROM UniquePhotos up
            LEFT JOIN UnreliableDates ud ON up.file_hash = ud.file_hash
            LEFT JOIN DeletedFiles df ON up.file_hash = df.file_hash AND df.is_restored = 0
            WHERE df.file_hash IS NULL
        """

        conditions = []
        params = []

        # -----------------------------------------------------------------
        # Creation date range (using indexed year/month/day columns)
        # -----------------------------------------------------------------
        if filters.get('creation_date_from'):
            try:
                date_from = filters['creation_date_from']
                year, month, day = date_from.split('-')
                # Build date comparison using string comparison (YYYY-MM-DD format)
                conditions.append("""
                    (up.create_year || '-' ||
                     CASE WHEN LENGTH(up.create_month) = 1 THEN '0' || up.create_month ELSE up.create_month END || '-' ||
                     CASE WHEN LENGTH(up.create_day) = 1 THEN '0' || up.create_day ELSE up.create_day END) >= ?
                """)
                params.append(date_from)
            except ValueError:
                logger.warning(f"Invalid creation_date_from: {filters['creation_date_from']}")

        if filters.get('creation_date_to'):
            try:
                date_to = filters['creation_date_to']
                year, month, day = date_to.split('-')
                conditions.append("""
                    (up.create_year || '-' ||
                     CASE WHEN LENGTH(up.create_month) = 1 THEN '0' || up.create_month ELSE up.create_month END || '-' ||
                     CASE WHEN LENGTH(up.create_day) = 1 THEN '0' || up.create_day ELSE up.create_day END) <= ?
                """)
                params.append(date_to)
            except ValueError:
                logger.warning(f"Invalid creation_date_to: {filters['creation_date_to']}")

        # -----------------------------------------------------------------
        # Correction date range
        # -----------------------------------------------------------------
        if filters.get('correction_date_from'):
            conditions.append("ud.corrected_date >= ?")
            params.append(filters['correction_date_from'])

        if filters.get('correction_date_to'):
            conditions.append("ud.corrected_date <= ?")
            params.append(filters['correction_date_to'])

        # -----------------------------------------------------------------
        # Status filters
        # -----------------------------------------------------------------
        if filters.get('has_unreliable_date'):
            conditions.append("ud.file_hash IS NOT NULL")

        if filters.get('has_corrected_date') is True:
            conditions.append("ud.corrected_date IS NOT NULL")
        elif filters.get('has_corrected_date') is False:
            conditions.append("(ud.corrected_date IS NULL OR ud.file_hash IS NULL)")

        if filters.get('needs_reorganization'):
            conditions.append("ud.needs_reorganization = 1")

        if filters.get('has_revisions'):
            conditions.append("up.revised_photo IS NOT NULL")

        # -----------------------------------------------------------------
        # Flag reason filter
        # -----------------------------------------------------------------
        if filters.get('flag_reasons'):
            flag_reasons = filters['flag_reasons']
            if isinstance(flag_reasons, list) and flag_reasons:
                placeholders = ','.join(['?' for _ in flag_reasons])
                conditions.append(f"ud.flag_reason IN ({placeholders})")
                params.extend(flag_reasons)

        # -----------------------------------------------------------------
        # Filename pattern (substring search)
        # -----------------------------------------------------------------
        if filters.get('filename_pattern'):
            pattern = filters['filename_pattern']
            conditions.append("up.file_name LIKE ?")
            params.append(f"%{pattern}%")

        # -----------------------------------------------------------------
        # Folder path filter (exact prefix match)
        # -----------------------------------------------------------------
        if filters.get('folder_path'):
            folder = filters['folder_path']
            # Ensure folder ends with separator for exact folder match
            if not folder.endswith('/') and not folder.endswith('\\'):
                folder = folder + '/'
            conditions.append("up.file_name LIKE ?")
            params.append(f"{folder}%")

        # -----------------------------------------------------------------
        # Full text search (searches filename and source path)
        # -----------------------------------------------------------------
        if filters.get('search_text'):
            search = filters['search_text']
            conditions.append("""
                (up.file_name LIKE ? OR up.source_path LIKE ? OR
                 ud.original_date LIKE ? OR ud.flag_reason LIKE ?)
            """)
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        # -----------------------------------------------------------------
        # Version filter (current/all/prior)
        # -----------------------------------------------------------------
        version_filter = filters.get('version_filter', 'current')
        if version_filter == 'current' and self.archive_base:
            # Only files in main archive (not prior revision archive)
            conditions.append("up.file_name LIKE ?")
            params.append(f"{self.archive_base}%")
            if self.prior_archive_base:
                # Explicitly exclude prior archive files
                conditions.append("up.file_name NOT LIKE ?")
                params.append(f"{self.prior_archive_base}%")
        elif version_filter == 'prior' and self.prior_archive_base:
            # Only files in prior revision archive
            conditions.append("up.file_name LIKE ?")
            params.append(f"{self.prior_archive_base}%")
        # 'all' = no version filtering, show everything

        # -----------------------------------------------------------------
        # Build WHERE clause (add to existing WHERE from deleted files filter)
        # -----------------------------------------------------------------
        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        # -----------------------------------------------------------------
        # Add ordering (most recent first)
        # -----------------------------------------------------------------
        base_query += " ORDER BY up.create_year DESC, up.create_month DESC, up.create_day DESC, up.file_name ASC"

        return (base_query, params)

    def execute_query(self, filters: Dict[str, Any], limit: int = 5000,
                      offset: int = 0) -> List[Dict[str, Any]]:
        """
        Execute query and return results.

        Args:
            filters: Filter dict
            limit: Max results (default 5000 for performance)
            offset: Offset for pagination

        Returns:
            List of record dicts
        """
        sql, params = self.build_query(filters)

        # Add limit and offset
        sql += f" LIMIT {limit}"
        if offset > 0:
            sql += f" OFFSET {offset}"

        logger.debug(f"Executing query with {len(params)} parameters, limit={limit}")

        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)

                for row in cursor.fetchall():
                    results.append(dict(row))

            logger.info(f"Query returned {len(results)} results")

        except Exception as e:
            logger.error(f"Query execution failed: {e}")

        return results

    def count_results(self, filters: Dict[str, Any]) -> int:
        """
        Count results without fetching data.

        Args:
            filters: Filter dict

        Returns:
            Number of matching records
        """
        sql, params = self.build_query(filters)

        # Wrap in COUNT query
        count_sql = f"SELECT COUNT(*) FROM ({sql})"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(count_sql, params)
                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Count query failed: {e}")
            return 0

    def get_photos_by_folder(self, folder_path: str, limit: int = 5000) -> List[Dict[str, Any]]:
        """
        Get photos from a specific archive folder.

        Args:
            folder_path: Archive folder path
            limit: Max results

        Returns:
            List of photo records
        """
        return self.execute_query({'folder_path': folder_path}, limit=limit)

    def get_photos_by_date(self, year: int, month: Optional[int] = None,
                           day: Optional[int] = None, limit: int = 5000) -> List[Dict[str, Any]]:
        """
        Get photos by creation date.

        Args:
            year: Year (required)
            month: Month (optional)
            day: Day (optional)
            limit: Max results

        Returns:
            List of photo records
        """
        # Build date range based on provided components
        if day and month:
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            filters = {
                'creation_date_from': date_str,
                'creation_date_to': date_str
            }
        elif month:
            from_date = f"{year:04d}-{month:02d}-01"
            # Calculate last day of month
            if month == 12:
                to_date = f"{year:04d}-12-31"
            else:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                to_date = f"{year:04d}-{month:02d}-{last_day:02d}"
            filters = {
                'creation_date_from': from_date,
                'creation_date_to': to_date
            }
        else:
            filters = {
                'creation_date_from': f"{year:04d}-01-01",
                'creation_date_to': f"{year:04d}-12-31"
            }

        return self.execute_query(filters, limit=limit)

    def get_unreliable_dates(self, pending_only: bool = False,
                              limit: int = 5000) -> List[Dict[str, Any]]:
        """
        Get photos with unreliable dates.

        Args:
            pending_only: If True, only return photos without corrected dates
            limit: Max results

        Returns:
            List of photo records
        """
        filters = {
            'has_unreliable_date': True
        }
        if pending_only:
            filters['has_corrected_date'] = False

        return self.execute_query(filters, limit=limit)

    def get_needs_reorganization(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """
        Get photos needing reorganization.

        Args:
            limit: Max results

        Returns:
            List of photo records
        """
        return self.execute_query({'needs_reorganization': True}, limit=limit)

    def search_photos(self, search_text: str, limit: int = 5000) -> List[Dict[str, Any]]:
        """
        Search photos by filename, path, or other text.

        Args:
            search_text: Text to search for
            limit: Max results

        Returns:
            List of photo records
        """
        return self.execute_query({'search_text': search_text}, limit=limit)

    def get_all_photos(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """
        Get all photos (up to limit).

        Args:
            limit: Max results

        Returns:
            List of photo records
        """
        return self.execute_query({}, limit=limit)

    def get_archive_folders(self) -> List[Dict[str, Any]]:
        """
        Get list of unique archive folders with photo counts.

        Returns:
            List of dicts with 'folder' and 'count' keys
        """
        # Get unique year folders
        sql = """
            SELECT create_year as year, COUNT(*) as count
            FROM UniquePhotos
            WHERE create_year IS NOT NULL
            GROUP BY create_year
            ORDER BY create_year DESC
        """

        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)

                for row in cursor.fetchall():
                    results.append({
                        'year': row['year'],
                        'count': row['count']
                    })

        except Exception as e:
            logger.error(f"Failed to get archive folders: {e}")

        return results

    def get_months_in_year(self, year: str) -> List[Dict[str, Any]]:
        """
        Get list of months with photos in a specific year.

        Args:
            year: Year string

        Returns:
            List of dicts with 'month' and 'count' keys
        """
        sql = """
            SELECT create_month as month, COUNT(*) as count
            FROM UniquePhotos
            WHERE create_year = ?
            GROUP BY create_month
            ORDER BY create_month ASC
        """

        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (year,))

                for row in cursor.fetchall():
                    results.append({
                        'month': row['month'],
                        'count': row['count']
                    })

        except Exception as e:
            logger.error(f"Failed to get months in year: {e}")

        return results

    def get_days_in_month(self, year: str, month: str) -> List[Dict[str, Any]]:
        """
        Get list of days with photos in a specific year/month.

        Args:
            year: Year string
            month: Month string

        Returns:
            List of dicts with 'day' and 'count' keys
        """
        sql = """
            SELECT create_day as day, COUNT(*) as count
            FROM UniquePhotos
            WHERE create_year = ? AND create_month = ?
            GROUP BY create_day
            ORDER BY create_day ASC
        """

        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (year, month))

                for row in cursor.fetchall():
                    results.append({
                        'day': row['day'],
                        'count': row['count']
                    })

        except Exception as e:
            logger.error(f"Failed to get days in month: {e}")

        return results
