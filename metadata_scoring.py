"""
Metadata Quality Scoring Module

Provides functions for calculating and comparing metadata quality scores.
Used to determine when an incoming file should replace an existing archive
file based on superior metadata (e.g., better EXIF data).

The scoring system assigns points based on:
- Date source type (EXIF DateTimeOriginal is highest, OS metadata is lowest)
- Reliability of the date (bonus points for reliable dates)

Functions:
    calculate_metadata_quality_score: Calculate score for a file's metadata
    should_upgrade_archive_file: Determine if incoming file should replace archive
    is_file_manually_corrected: Check if file has user corrections (protected)
"""

import logging
from typing import Dict, Any, Tuple, Optional

import constants

logger = logging.getLogger(__name__)


# Score values for different date sources (higher = better)
METADATA_SOURCE_SCORES: Dict[str, int] = {
    'exif': constants.METADATA_SCORE_EXIF,
    'exif_digitized': constants.METADATA_SCORE_EXIF_DIGITIZED,
    'exif_gps': constants.METADATA_SCORE_EXIF_GPS,
    'exif_datetime': constants.METADATA_SCORE_EXIF_DATETIME,
    'exif_preview': constants.METADATA_SCORE_EXIF_PREVIEW,
    'iptc': constants.METADATA_SCORE_IPTC,
    'xmp': constants.METADATA_SCORE_XMP,
    'video_metadata': constants.METADATA_SCORE_VIDEO_METADATA,
    'video_quicktime': constants.METADATA_SCORE_VIDEO_QUICKTIME,
    'os_metadata': constants.METADATA_SCORE_OS_METADATA,
    'fallback': constants.METADATA_SCORE_FALLBACK
}


def calculate_metadata_quality_score(
    date_source: Optional[str],
    is_reliable: bool
) -> int:
    """
    Calculate a numerical metadata quality score (0-100).

    Higher scores indicate better/more reliable metadata. This score is used
    to compare incoming files with archive files to determine if the incoming
    file has superior metadata worth upgrading to.

    Score components:
    - Base score (0-80): From date source type
    - Reliability bonus (0-20): Added if date is considered reliable

    Parameters:
        date_source (str): Source of the date ('exif', 'os_metadata', etc.)
        is_reliable (bool): Whether the date is considered reliable

    Returns:
        int: Quality score from 0 to 100
    """
    if date_source is None:
        date_source = 'fallback'

    base_score = METADATA_SOURCE_SCORES.get(date_source, 0)
    reliability_bonus = constants.METADATA_RELIABILITY_BONUS if is_reliable else 0

    return base_score + reliability_bonus


def should_upgrade_archive_file(
    archive_metadata: Dict[str, Any],
    incoming_date_source: str,
    incoming_is_reliable: bool,
    incoming_date: Optional[str] = None
) -> Tuple[bool, str, int]:
    """
    Determine if an archive file should be upgraded with an incoming duplicate.

    An upgrade is recommended when:
    1. Incoming file has a higher metadata quality score, OR
    2. Same score AND incoming is reliable AND archive is not

    Note: Files that have been manually corrected by the user are never upgraded.
    This function does NOT check for manual corrections - that must be done separately
    using is_file_manually_corrected().

    Parameters:
        archive_metadata (dict): Metadata from the archive file containing:
            - date_source (str): Source of the archive file's date
            - date_reliable (bool): Whether archive date is reliable
            - metadata_quality_score (int): Pre-computed score for archive file
            - create_datetime (str): Archive file's creation date
        incoming_date_source (str): Date source of incoming file
        incoming_is_reliable (bool): Whether incoming file's date is reliable
        incoming_date (str, optional): Creation date of incoming file

    Returns:
        Tuple[bool, str, int]:
            - should_upgrade: True if incoming file should replace archive file
            - reason: Explanation of the decision
            - incoming_score: Calculated quality score for incoming file
    """
    # Calculate incoming file's quality score
    incoming_score = calculate_metadata_quality_score(incoming_date_source, incoming_is_reliable)

    # Get archive file's quality score (use pre-computed if available)
    archive_score = archive_metadata.get('metadata_quality_score')
    if archive_score is None:
        # Fall back to computing from components
        archive_date_source = archive_metadata.get('date_source')
        archive_is_reliable = archive_metadata.get('date_reliable', True)
        archive_score = calculate_metadata_quality_score(archive_date_source, archive_is_reliable)

    # Compare scores
    if incoming_score > archive_score:
        # Incoming has better metadata
        score_diff = incoming_score - archive_score
        return (True,
                f"Incoming has better metadata (score {incoming_score} vs {archive_score}, +{score_diff})",
                incoming_score)

    elif incoming_score == archive_score:
        # Same score - check reliability as tiebreaker
        archive_is_reliable = archive_metadata.get('date_reliable', True)
        if incoming_is_reliable and not archive_is_reliable:
            return (True,
                    f"Same score ({incoming_score}) but incoming is reliable, archive is not",
                    incoming_score)

        # Check if dates differ - might be useful info but don't upgrade just for that
        archive_date = archive_metadata.get('create_datetime')
        if incoming_date and archive_date and incoming_date != archive_date:
            return (False,
                    f"Same quality ({incoming_score}), different dates ({incoming_date} vs {archive_date}) - no upgrade",
                    incoming_score)

        return (False,
                f"Same quality ({incoming_score}), no improvement",
                incoming_score)

    else:
        # Archive has better metadata
        score_diff = archive_score - incoming_score
        return (False,
                f"Archive has better metadata (score {archive_score} vs {incoming_score}, archive is +{score_diff})",
                incoming_score)


def is_file_manually_corrected(
    database_path: str,
    file_hash: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if a file has been manually corrected by the user.

    A file is protected from replacement if ANY of these are true:
    1. Has revision_reason of 'date_correction' or 'exif_edit' (explicit EXIF edit)
    2. Has a corrected_date in UnreliableDates table
    3. Is a revision of a file that was user-edited (walks revision chain)

    Parameters:
        database_path (str): Path to the database
        file_hash (str): Hash of the file to check

    Returns:
        Tuple[bool, Optional[str]]:
            - is_protected: True if file should not be replaced
            - protection_reason: Explanation if protected, None otherwise
    """
    # Import here to avoid circular imports
    from DuplicateFileDetection import PhotoDatabase
    from database_metadata import DatabaseMetadata

    try:
        with PhotoDatabase(database_path) as db:
            # Check 1: Direct revision reason check
            db.cursor.execute("""
                SELECT revision_reason, revised_photo FROM UniquePhotos WHERE file_hash = ?
            """, (file_hash,))
            result = db.cursor.fetchone()

            if result:
                revision_reason, revised_photo = result

                # Check for explicit user edits
                if revision_reason in ('date_correction', 'exif_edit', 'manual_correction'):
                    return (True, f"File has user correction: {revision_reason}")

                # Check 3: Walk revision chain to check ancestors
                if revised_photo:
                    # This file is a revision - check if the original was user-edited
                    chain_protected, chain_reason = _check_revision_chain(db, revised_photo, set())
                    if chain_protected:
                        return (True, f"Ancestor in revision chain was edited: {chain_reason}")

        # Check 2: Corrected date in UnreliableDates table
        db_meta = DatabaseMetadata(database_path)
        try:
            with db_meta._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT corrected_date FROM UnreliableDates
                    WHERE file_hash = ? AND corrected_date IS NOT NULL
                """, (file_hash,))
                result = cursor.fetchone()

                if result and result[0]:
                    return (True, "File has corrected date in UnreliableDates")
        except Exception as e:
            logger.warning(f"Could not check UnreliableDates for {file_hash}: {e}")

        return (False, None)

    except Exception as e:
        logger.error(f"Error checking if file is manually corrected: {e}")
        # On error, err on the side of caution and don't protect
        return (False, None)


def _check_revision_chain(
    db,
    file_hash: str,
    visited: set
) -> Tuple[bool, Optional[str]]:
    """
    Recursively check revision chain for user corrections.

    Parameters:
        db: PhotoDatabase instance
        file_hash (str): Hash to check
        visited (set): Set of already-visited hashes to prevent cycles

    Returns:
        Tuple[bool, Optional[str]]:
            - is_protected: True if chain contains user edits
            - protection_reason: Explanation if protected, None otherwise
    """
    if file_hash in visited:
        return (False, None)  # Cycle detected, stop

    visited.add(file_hash)

    try:
        db.cursor.execute("""
            SELECT revision_reason, revised_photo FROM UniquePhotos WHERE file_hash = ?
        """, (file_hash,))
        result = db.cursor.fetchone()

        if not result:
            return (False, None)

        revision_reason, revised_photo = result

        # Check for user edits at this level
        if revision_reason in ('date_correction', 'exif_edit', 'manual_correction'):
            return (True, f"Ancestor {file_hash[:8]}... has {revision_reason}")

        # Continue up the chain
        if revised_photo:
            return _check_revision_chain(db, revised_photo, visited)

        return (False, None)

    except Exception as e:
        logger.warning(f"Error checking revision chain for {file_hash}: {e}")
        return (False, None)


def get_date_source_description(date_source: str) -> str:
    """
    Get a human-readable description of a date source.

    Parameters:
        date_source (str): The date source identifier

    Returns:
        str: Human-readable description
    """
    descriptions = {
        'exif': 'EXIF DateTimeOriginal (camera capture time)',
        'exif_digitized': 'EXIF DateTimeDigitized (when digitized)',
        'exif_gps': 'EXIF GPS timestamp',
        'exif_datetime': 'EXIF DateTime (file modification)',
        'exif_preview': 'EXIF PreviewDateTime',
        'iptc': 'IPTC Date Created',
        'xmp': 'XMP CreateDate',
        'video_metadata': 'Video creation_time (ffprobe)',
        'video_quicktime': 'QuickTime atom creation time',
        'os_metadata': 'Operating system file timestamp',
        'fallback': 'Default fallback date'
    }
    return descriptions.get(date_source, f'Unknown source: {date_source}')


def compare_metadata_scores(score1: int, score2: int) -> str:
    """
    Get a human-readable comparison of two metadata scores.

    Parameters:
        score1 (int): First score
        score2 (int): Second score

    Returns:
        str: Description of comparison
    """
    if score1 > score2:
        return f"First is better ({score1} vs {score2}, +{score1 - score2})"
    elif score2 > score1:
        return f"Second is better ({score2} vs {score1}, +{score2 - score1})"
    else:
        return f"Equal quality ({score1})"
