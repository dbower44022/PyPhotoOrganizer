# photo_organizer/main.py

"""
This routine is designed to look through multiple sources of photo and video files, and determine if there are duplicates.

Flow diagram:  https://lucid.app/lucidchart/d52adf95-4275-4107-ad41-20c4cfd5c72c/edit?invitationId=inv_70bff327-b21c-4508-9ae6-03f07b9bdefe&page=4wTk8nA8b3At#

Assumptions:
1 - Most users will have multiple locations where they store original files (Phone, Ipad, multiple PC's, multiple places on a single PC, NAS, etc)
2 - Most users will end up with a large number of duplicates due to their manual attempts to organize / secure / archive their important photos.  They will backup devices multiple times to a PC or File service creating tons of duplicates!
3 - Storage space is cheap, but it should not be wasted with multiple identical files.
4 - Of all possible archiving schemes, organization by date created makes the most sense. Other software can be used to create albums, by person, or event .
5 - There are a wide variety of tools to help organize photos, but none of them are good at assuring their is a single, highly reliable location where all photos exist.
6 - It is impossible for users to review all files and determine which should be archived long term or deleted immediately.
7 - It is difficult to assure that all photos are backed up for long term availability in a central place.  Having multiple places is common because of attempts to secure and organize files over the years.
8 - There are various applications that can copy photos from mobile devices to a long term storage device, but most of them do not do a good job of preventing duplicates from being created.
9 - Many users create duplicates when downloading from a mobile device because they are not sure if the mobile files were previously copied.


TODO:
* 1 - <COMPLETE> Integrate duplicate file detection into the main processing app.
*1.1 - Verify that the copy function does not modify the hash value of the file.
*1.2 - Create a way to determine that two hash values are the same file, so when we convert a HEIC to JPEG we know it is the same file.
*1.3 - Create a mechanism where we can establish a parent photo, so that low resolution photos created from that image can be tracked and not seen as separate original files. (There may be ways to do this automatically with some of the photo compare algorithms)
*1.4 - Compute the hash of the file written to the vault to assure that there were no file write errors!!!

2 - Figure out how to ignore small icon files, or super low resolution thumbnails or "optimized" files.
3 - Add logic to hash only a small portion of a file and then determine if it is a duplicate.  Then hash larger amounts to assure it is a duplicate.  If the first 10 bytes are not a duplicate, then it is not a duplicate!!!
3.1 - Add a separate hash table for small file portion hashes.  If there is a duplicate, then hash full file.
4 - Add logic to create a database of the duplicate files, so we know which are duplicates.
5 - Add logic to copy and rename all non-duplicate files into a vault!  This will be used to drive Mylio!
6 - Add a routine that will add EXIF data to files that do not have them, so we can say 'All these files are from 1945' and the system will override the operating system date.
7 - Figure out how to utilize some of the folder structure/contents to re-organize photos.
8 - Add logic to better process video files!
9 - Add logic to add exif data to files if there is a setting to add the information in the settings file.  The most common would be to add the create date to old files.
10 - <COMPLETE> Add the ability to enter multiple input folders so we can process a number of folders repeatedly, or schedule a large import without repeatedly entering directories.
11 - Add ability to process paths that contain an apostrophy - Currently it fails.
12 - <COMPLETE> Add routine that determines the filetype using pillow, and verifies the file extension.  If it is incorrect, it automatically corrects the source and destination files.
13 - Modify the filetype verification routine to write the file as a new file if the rename fails due to a file open conflict.
14 - Add some analytics to be presented at the end.
15 - Add a delete file routine that can be used to quickly delete files that are determined not to be included in the database.  Ex -Thumbnails or just ugly photos that the user wants removed.

Possible TODO:
1 - Save the destination file with the hash value as the filename.  To assure uniqueness, and make it easier to find the file that matches the DB.
2 - Should we add the original filename to the end of the hash value of destination filename?


base example code repository = https://github.com/Supporterino/photo-organizer/tree/main
get exif data repository = https://github.com/ozgecinko/image-metadata-extractor
Second EXIF Library - https://pypi.org/project/ExifRead/
detect duplicate file repository =


"""

import argparse
import datetime
import filecmp
import json
import logging
import os
import sqlite3

from PIL import Image
from PIL.ExifTags import TAGS
import pillow_heif  # https://github.com/bigcat88/pillow_heif
# from pillow_heif import register_heif_opener

from PIL.ExifTags import GPSTAGS
import shutil
import sys
from tqdm import tqdm

import DuplicateFileDetection
import utils
from config import Config
import constants
from organization_template import OrganizationTemplate
from filename_template import FilenameTemplate
from database_metadata import DatabaseMetadata
from datetime import datetime as dt_datetime

# Configure logging using shared utility
logger = utils.setup_logger(__name__, "main_app_error.log")


def configure_logging(verbose):
    """
    Configure logging settings.

    Parameters:
    verbose (bool): If True, enable verbose logging.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def parse_arguments():
    """
    Parse command line arguments.

    Returns:
    Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Sort photos from source to Destination directory."
    )
    parser.add_argument("-source", type=str, help="The source directory")
    parser.add_argument("-destination", type=str, help="The Destination directory")
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Sort photos recursively"
    )
    parser.add_argument(
        "-d",
        "--daily",
        action="store_true",
        default=False,
        help="Folder structure with daily folders",
    )
    parser.add_argument(
        "-e",
        "--endings",
        type=str,
        nargs="*",
        help="File endings/extensions to copy (e.g., .jpg .png)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "-c", "--copy", action="store_true", help="Copy files instead of moving them"
    )
    parser.add_argument(
        "--no-year",
        action="store_true",
        help="Do not place month folders inside a year folder",
    )

    return parser.parse_args()


def organize_files(config, files, database_path=constants.DEFAULT_DATABASE_NAME, batch_size=constants.DEFAULT_BATCH_SIZE, progress_callback=None, audit_manager=None, session_id=None, should_stop=None, album_manager=None, source_album_mapping=None):
    """
    Organize files by moving or copying them to the Destination directory.

    Parameters:
    config (Config): Configuration object containing all settings
    files (list): List of file paths to organize.
    database_path (str): Path to the SQLite database file
    batch_size (int): Number of files to process before committing to database
    progress_callback (callable): Optional callback function(organized, total, current_file, bytes_copied, total_bytes) for progress updates
        Returns True if processing should stop, False to continue.
    audit_manager (AuditManager): Optional audit manager for logging file operations
    session_id (str): Optional session ID for audit logging
    should_stop (callable): Optional callable that returns True if processing should be cancelled.
        Used for graceful shutdown - when True is returned, commits partial progress and exits cleanly.
    album_manager (AlbumManager): Optional album manager for adding files to albums during import
    source_album_mapping (dict): Optional mapping of source paths to album associations
        Format: {source_path: {'album_id': int, 'enable_sub_albums': bool}}

    Returns:
    dict: Dictionary containing:
        total_files_processed - Integer containing the total number of files in all the provided directories.
        total_new_original_files - Integer containing the total number of NEW photos detected.
        was_cancelled - Boolean indicating if processing was stopped before completion.
        total_album_additions - Integer containing the number of files added to albums.

    """
    try:
        logger.info(f"Initializing organize_files")

        # Get settings from config object (already validated with defaults)
        total_files_processed = 0
        total_new_original_files = 0
        total_errors = 0  # Track errors for audit
        total_album_additions = 0  # Track files added to albums
        current_file_being_processed = 0
        file_counter = 0  # Sequential counter for filename templates
        was_cancelled = False  # Track if processing was cancelled by user

        # Prepare album mapping for quick source lookup
        album_source_lookup = {}  # Maps source directory path to album config
        if source_album_mapping:
            for source_path, album_config in source_album_mapping.items():
                album_source_lookup[source_path] = album_config
            logger.info(f"Album integration: {len(album_source_lookup)} source directories have album associations")

        # Extract settings from config
        source_directory = config.source_directory
        destination_directory = config.destination_directory
        organization_template = config.get('organization_template', '{YYYY}/{MM}/{DD}')
        copy_files = config.copy_files
        move_files = config.move_files

        # Initialize database metadata for filename template support
        logger.info(f"=" * 80)
        logger.info(f"MAIN.PY: Creating DatabaseMetadata with database_path: '{database_path}'")
        logger.info(f"=" * 80)
        db_metadata = DatabaseMetadata(database_path)

        try:
            # Check for cancellation before starting duplicate detection
            if should_stop and should_stop():
                logger.info("Processing cancelled before duplicate detection")
                return {
                    "total_files_processed": 0,
                    "total_new_original_files": 0,
                    "total_duplicates": 0,
                    "total_filtered": 0,
                    "total_unreliable_dates": 0,
                    "total_errors": 0,
                    "total_album_additions": 0,
                    "filter_statistics": {},
                    "filtered_files": [],
                    "was_cancelled": True
                }

            hashes = DuplicateFileDetection.load_photo_hashes(database_path)
            logger.info("The load_photo_hashes completed and returned 'hashes' ")
            results = DuplicateFileDetection.find_duplicates(
                files,
                hashes,
                database_path,
                batch_size,
                partial_hash_enabled=config.partial_hash_enabled,
                partial_hash_bytes=config.partial_hash_bytes,
                partial_hash_min_file_size=config.partial_hash_min_file_size,
                config=config,  # Pass config for photo filtering
                audit_manager=audit_manager,
                session_id=session_id,
                should_stop=should_stop  # Pass stop check callable
            )
            logger.info(f"The DuplicateFileDetection.find_duplicates returned = {results}")

            # verify status of return
            if results.get("status") == "completed":
                logger.info("The DuplicateFileDetection routine completed.")
            elif results.get("status") == "cancelled":
                logger.info("The DuplicateFileDetection routine was cancelled by user.")
                # Return partial results with cancellation flag
                return {
                    "total_files_processed": results.get('files_processed', 0),
                    "total_new_original_files": len(results.get('original_files', [])),
                    "total_duplicates": len(results.get('duplicate_files', [])),
                    "total_filtered": len(results.get('filtered_files', [])),
                    "total_unreliable_dates": results.get('unreliable_dates_count', 0),
                    "total_errors": 0,
                    "total_album_additions": 0,
                    "filter_statistics": results.get('filter_statistics', {}),
                    "filtered_files": results.get('filtered_files', []),
                    "was_cancelled": True
                }
            else:
                logger.info(f"The DuplicateFileDetection routine failed with a status returned = {results.get('status')}.")

            duplicate_files = results['duplicate_files']
            # The files that are NOT duplicates, will be returned in original_files.  These need to be processed to be copied/moved
            original_files = results.get('original_files')
            filtered_files = results.get('filtered_files', [])
            filter_stats = results.get('filter_statistics')
            unreliable_dates_count = results.get('unreliable_dates_count', 0)

            # Log filter statistics if filtering was enabled
            if filter_stats and filter_stats['total_filtered'] > 0:
                logger.info("=" * 70)
                logger.info(f"Photo filtering removed {filter_stats['total_filtered']} non-photo files")
                logger.info(f"  - By file size: {filter_stats['filtered_by_size']}")
                logger.info(f"  - By dimensions: {filter_stats['filtered_by_dimensions']}")
                logger.info(f"  - By square icon: {filter_stats['filtered_by_square']}")
                logger.info(f"  - By filename pattern: {filter_stats['filtered_by_filename']}")
                logger.info("=" * 70)

            logger.info("Completed locating files to be moved/copied.")

        except Exception as e:
            logger.exception(f"The get duplicates routine failed - {e}")

        if original_files:
            # process the list of original files passed to this routine in the 'files' list.
            total_files_processed = len(original_files) + len(duplicate_files) + len(filtered_files)
            total_new_original_files = len(original_files)
            logger.info(f"Total files examined: {total_files_processed}")
            logger.info(f"  - New original photos: {len(original_files)}")
            logger.info(f"  - Duplicates: {len(duplicate_files)}")
            logger.info(f"  - Filtered (non-photos): {len(filtered_files)}")
            logger.info(f"original_files contains {total_new_original_files} NEW photos to be processed.")

            # Calculate total bytes for progress tracking (used by GUI)
            total_bytes = 0
            if progress_callback:
                try:
                    for f in original_files:
                        fp = f["file_path"]
                        if os.path.exists(fp):
                            total_bytes += os.path.getsize(fp)
                except Exception as e:
                    logger.warning(f"Failed to calculate total bytes: {e}")
                    total_bytes = 0  # If calculation fails, just use 0

            # Progress bar for copying/moving files
            bytes_copied = 0
            was_cancelled = False
            with tqdm(total=len(original_files), desc="Organizing files", unit="file",
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                for original_file in original_files:
                    # Check for cancellation at the start of each file
                    if should_stop and should_stop():
                        logger.info(f"Processing cancelled after {current_file_being_processed} files")
                        was_cancelled = True
                        break

                    current_file_being_processed = current_file_being_processed + 1
                    file_path = original_file["file_path"]
                    pbar.set_postfix_str(os.path.basename(file_path)[:constants.MAX_FILENAME_DISPLAY_LENGTH])

                    # Progress callback for GUI - also checks for stop signal
                    if progress_callback:
                        callback_result = progress_callback(current_file_being_processed, len(original_files),
                                        file_path, bytes_copied, total_bytes)
                        # If callback returns True, it means stop was requested
                        if callback_result:
                            logger.info(f"Processing cancelled via callback after {current_file_being_processed} files")
                            was_cancelled = True
                            break

                    # Track bytes for next iteration
                    if progress_callback and os.path.exists(file_path):
                        try:
                            bytes_copied += os.path.getsize(file_path)
                        except Exception as e:
                            logger.warning(f"Failed to get file size for progress tracking: {e}")

                    logger.info(f"file_path = {file_path}")
                    year, month, day, date_source, is_reliable = DuplicateFileDetection.get_creation_date(file_path)
                    # The year, month and day will be returned as strings.
                    # date_source and is_reliable are tracked but not used here

                    # Convert year, month, day strings to datetime object for template parsing
                    try:
                        file_date = dt_datetime(int(year), int(month), int(day))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid date for file {file_path}: {year}/{month}/{day}. Using current date. Error: {e}")
                        file_date = dt_datetime.now()

                    # Determine base destination directory (photo archive or video archive)
                    # Check if file is a video and if separate video archive is enabled
                    is_video = utils.is_video_file(file_path)
                    video_archive_enabled = db_metadata.is_separate_video_archive_enabled()
                    video_archive_location = db_metadata.get_video_archive_location()

                    if is_video and video_archive_enabled and video_archive_location:
                        # Route video to video archive
                        base_destination = video_archive_location
                        logger.info(f"Routing video file to video archive: {base_destination}")
                    else:
                        # Route to photo archive (default)
                        base_destination = destination_directory
                        logger.debug(f"Routing file to photo archive: {base_destination}")

                    # Use organization template to generate folder structure
                    folder_path = OrganizationTemplate.parse(organization_template, file_date)
                    destination_folder = os.path.join(base_destination, folder_path)

                    logger.info(f"The destination directory was set to: {destination_folder}")

                    # now verify if the destination folder exists, and if not, create it.
                    utils.ensure_directory_exists(destination_folder)

                    # Increment file counter for each unique file
                    file_counter += 1

                    # Apply filename template if enabled, otherwise use original filename
                    rename_enabled = db_metadata.is_file_rename_enabled()
                    logger.info(f"File rename enabled: {rename_enabled}")
                    if rename_enabled:
                        try:
                            filename_template = db_metadata.get_filename_template()
                            logger.info(f"Filename template from database: '{filename_template}'")

                            # Parse template to generate new filename
                            # Pass full file_path so template can extract folder names
                            new_filename = FilenameTemplate.parse(
                                filename_template,
                                file_date,
                                file_path,  # Full path for folder name extraction
                                counter=file_counter
                            )

                            original_filename = os.path.basename(file_path)

                            logger.info(f"Filename template applied: {original_filename} → {new_filename}")
                        except Exception as e:
                            logger.error(f"Failed to parse filename template, falling back to original filename: {e}")
                            new_filename = os.path.basename(file_path)
                    else:
                        # Use original filename (default behavior)
                        new_filename = os.path.basename(file_path)

                    # join the destination folder with the (possibly renamed) file
                    target_path = os.path.join(destination_folder, new_filename)

                    # now determine if the new file already exists in directory, and if so, verify if it is identical.  There could be two files with same name but different images.
                    if os.path.exists(target_path):
                        # do a full file comparison of the two files
                        logger.info(f"About to compare '{file_path}' with '{target_path}'.")
                        if filecmp.cmp(file_path, target_path, shallow=False):
                            logger.warning(f"File {target_path} already exists and is identical. Skipping file and continuing with next file.")
                            pbar.update(1)
                            continue
                        else:
                            ####
                            # A file already exists in the Sorted file with the same name, but is not identical.  So store both of them so a human can figure out if they are different.
                            ####
                            new_target_path = utils.get_unique_filename(target_path)
                            logger.info(f"File {target_path} already exists and is different. We will write a second file with the name {new_target_path}.")
                            target_path = new_target_path
                    else:
                        logger.info("The original file has an original name that is not in the Stored files.  So write the file and continue.")

                    try:
                        import time as time_module
                        operation_start = time_module.time()
                        operation_type = 'copy' if copy_files else 'move'
                        operation_success = False

                        # Initialize album tracking variables (will be populated if file is added to album)
                        audit_album_name = None
                        audit_album_path = None
                        audit_sub_album_name = None

                        if copy_files and not move_files:
                            # use the copyfile not copy or copy2 in order to maintain the existing hash code of the original file!
                            shutil.copyfile(file_path, target_path)
                            logger.info(f"Copied {file_path} to {target_path}")
                            operation_success = True
                        elif move_files and not copy_files:
                            shutil.move(file_path, target_path)
                            logger.info(f"Moved {file_path} to {target_path}")
                            operation_success = True
                        else:
                            logger.info("ERROR - Move and Copy files are not supported simultaneously")

                        # Update database with archive path after successful organization
                        try:
                            file_hash = original_file.get("file_hash")
                            logger.debug(f"Updating database with archive path for file_hash: {file_hash}")

                            if file_hash:
                                with sqlite3.connect(database_path) as conn:
                                    cursor = conn.cursor()

                                    # Update UniquePhotos table with archive path
                                    cursor.execute("""
                                        UPDATE UniquePhotos
                                        SET file_name = ?
                                        WHERE file_hash = ?
                                    """, (target_path, file_hash))

                                    if cursor.rowcount > 0:
                                        logger.debug(f"✓ Updated UniquePhotos.file_name: {file_hash[:16]}... -> {target_path}")
                                    else:
                                        logger.warning(f"File not found in UniquePhotos: {file_hash[:16]}...")

                                    # Record rename history if file renaming is enabled
                                    # NOTE: Using existing cursor to avoid "database is locked" error
                                    # (db_metadata.insert_rename_history opens a new connection)
                                    if db_metadata.is_file_rename_enabled():
                                        original_filename = os.path.basename(file_path)
                                        renamed_filename = os.path.basename(target_path)

                                        # Only record if filename actually changed
                                        if original_filename != renamed_filename:
                                            cursor.execute("""
                                                INSERT INTO FileRenameHistory
                                                (file_hash, original_filename, renamed_filename, rename_timestamp)
                                                VALUES (?, ?, ?, datetime('now'))
                                            """, (file_hash, original_filename, renamed_filename))
                                            logger.debug(f"✓ Recorded rename history: {original_filename} → {renamed_filename}")

                                    # Update archive_path in UnreliableDates (if this file has unreliable date)
                                    cursor.execute("""
                                        SELECT file_hash, archive_path
                                        FROM UnreliableDates
                                        WHERE file_hash = ?
                                    """, (file_hash,))
                                    unreliable_record = cursor.fetchone()

                                    if unreliable_record:
                                        logger.info(f"Found file in UnreliableDates: hash={file_hash[:16]}..., current archive_path={unreliable_record[1]}")

                                        cursor.execute("""
                                            UPDATE UnreliableDates
                                            SET archive_path = ?
                                            WHERE file_hash = ?
                                        """, (target_path, file_hash))

                                        if cursor.rowcount > 0:
                                            logger.info(f"✓ Updated UnreliableDates.archive_path: {file_hash[:16]}... -> {target_path}")

                                    conn.commit()
                            else:
                                logger.warning(f"No file_hash found in original_file dict for: {file_path}")

                        except Exception as e:
                            logger.error(f"Failed to update database with archive path: {e}", exc_info=True)

                        # Add file to album if source has album association
                        if album_manager and album_source_lookup and file_hash:
                            try:
                                # Find matching source directory
                                matching_source = None
                                relative_subdir = ""
                                for source_path in album_source_lookup:
                                    if file_path.startswith(source_path):
                                        matching_source = source_path
                                        # Calculate relative subdirectory path
                                        rel_path = os.path.relpath(file_path, source_path)
                                        rel_dir = os.path.dirname(rel_path)
                                        if rel_dir and rel_dir != '.':
                                            relative_subdir = rel_dir
                                        break

                                if matching_source:
                                    album_config = album_source_lookup[matching_source]
                                    album_id = album_config['album_id']
                                    enable_sub_albums = album_config.get('enable_sub_albums', False)

                                    target_album_id = album_id
                                    current_sub_album_name = None  # Track sub-album name for audit

                                    # Handle sub-albums if enabled and file is in a subdirectory
                                    if enable_sub_albums and relative_subdir:
                                        # Get parent album info for sub-album naming
                                        parent_album = album_manager.get_album(album_id)
                                        if parent_album:
                                            # Generate sub-album name: "Parent Album - Subdir1 - Subdir2"
                                            subdir_parts = relative_subdir.replace(os.sep, ' - ')
                                            sub_album_name = f"{parent_album['album_name']} - {subdir_parts}"
                                            current_sub_album_name = sub_album_name  # Track for audit

                                            # Check if sub-album exists, create if not
                                            existing_sub_album = album_manager.get_album_by_name(sub_album_name)
                                            if existing_sub_album:
                                                target_album_id = existing_sub_album['id']
                                            else:
                                                # Create sub-album with storage in subfolder of parent
                                                parent_storage = parent_album['storage_location']
                                                sub_storage = os.path.join(parent_storage, relative_subdir.replace(os.sep, os.sep))
                                                try:
                                                    new_album_id = album_manager.create_album(
                                                        name=sub_album_name,
                                                        storage_location=sub_storage,
                                                        description=f"Auto-created sub-album for {relative_subdir}",
                                                        sync_deletions=parent_album.get('sync_deletions', True)
                                                    )
                                                    if new_album_id:
                                                        target_album_id = new_album_id
                                                        logger.info(f"Created sub-album: {sub_album_name}")

                                                        # Record sub-album mapping in database
                                                        source_dir = db_metadata.get_source_directory_by_path(matching_source)
                                                        if source_dir:
                                                            db_metadata.get_or_create_sub_album(
                                                                source_directory_id=source_dir['id'],
                                                                parent_album_id=album_id,
                                                                sub_album_id=new_album_id,
                                                                relative_subdir_path=relative_subdir
                                                            )
                                                except Exception as sub_err:
                                                    logger.warning(f"Failed to create sub-album '{sub_album_name}': {sub_err}")
                                                    # Fall back to parent album
                                                    target_album_id = album_id
                                                    current_sub_album_name = None  # Clear sub-album name on failure

                                    # Add file to album (copies to album storage)
                                    album_file_path = album_manager.add_photo_to_album(
                                        album_id=target_album_id,
                                        file_hash=file_hash,
                                        archive_path=target_path
                                    )
                                    if album_file_path:
                                        total_album_additions += 1
                                        logger.debug(f"Added to album: {os.path.basename(target_path)}")

                                        # Track album info for audit logging
                                        target_album = album_manager.get_album(target_album_id)
                                        if target_album:
                                            audit_album_name = target_album['album_name']
                                            audit_album_path = album_file_path
                                            # If this is a sub-album, track the sub-album name
                                            if current_sub_album_name:
                                                audit_sub_album_name = current_sub_album_name

                            except Exception as album_err:
                                # Album errors are non-fatal - log and continue
                                logger.warning(f"Failed to add file to album: {album_err}")

                        # Log successful operation to audit (after album addition so we have album info)
                        if operation_success and audit_manager and session_id:
                            try:
                                operation_duration = int((time_module.time() - operation_start) * 1000)
                                file_size = os.path.getsize(target_path) if os.path.exists(target_path) else 0
                                file_hash = original_file.get("file_hash")

                                audit_manager.log_file_operation(
                                    session_id=session_id,
                                    source_path=file_path,
                                    operation=operation_type,
                                    status='success',
                                    destination_path=target_path,
                                    file_hash=file_hash,
                                    file_size=file_size,
                                    creation_date=f"{year}-{month}-{day}",
                                    date_source=date_source if 'date_source' in dir() else None,
                                    date_reliable=is_reliable if 'is_reliable' in dir() else None,
                                    duration_ms=operation_duration,
                                    album_name=audit_album_name,
                                    album_path=audit_album_path,
                                    sub_album_name=audit_sub_album_name
                                )
                            except Exception as audit_err:
                                logger.debug(f"Failed to log audit: {audit_err}")

                        # if file = heic convert to jpeg
                        try:
                            if file_path.endswith(constants.HEIC_EXTENSIONS):
                                try:
                                    heif_file = pillow_heif.read_heif(file_path)
                                    heic_image = Image.frombytes(
                                        heif_file.mode,
                                        heif_file.size,
                                        heif_file.data,
                                        "raw",
                                    )
                                except Exception as e:
                                    logger.error(f"The open file for {file_path} failed with error = {e}")

                                jpeg_file_path = f"{target_path[:-5]}.jpeg"
                                logger.info(f"The new jpeg_file_path = '{jpeg_file_path}'")
                                heic_image.save(jpeg_file_path, format="JPEG")
                            else:
                                logger.info("The file is NOT a HEIC format.")
                        except Exception as e:
                            logger.exception(f"Exception in HEIC conversion = {e}")

                        # image.save("./picture_name.png", format("png"))

                    except Exception as e:
                        total_errors += 1
                        logger.exception(f"Failed to {'copy' if copy_files else 'move'} '{file_path}' to '{target_path}': {e}")

                        # Log error to audit
                        if audit_manager and session_id:
                            try:
                                import traceback as tb_module
                                audit_manager.log_file_operation(
                                    session_id=session_id,
                                    source_path=file_path,
                                    operation=operation_type if 'operation_type' in dir() else ('copy' if copy_files else 'move'),
                                    status='failed',
                                    destination_path=target_path,
                                    file_hash=original_file.get("file_hash"),
                                    error_code=type(e).__name__,
                                    error_message=str(e),
                                    error_traceback=tb_module.format_exc()
                                )
                            except Exception as audit_err:
                                logger.debug(f"Failed to log audit error: {audit_err}")
                    finally:
                        # Update progress bar after each file (success or failure)
                        pbar.update(1)
            logger.info(f"Processed {total_files_processed} original files, and located {total_new_original_files} that are not duplicates.")
        else:
            total_files_processed = len(duplicate_files) + len(filtered_files)
            total_new_original_files = 0
            logger.info("****************************************************************")
            logger.info(f"Of the {total_files_processed} files examined, there were ZERO original files located!")
            logger.info(f"  - All {len(duplicate_files)} files were duplicates")
            if filtered_files:
                logger.info(f"  - {len(filtered_files)} files were filtered out as non-photos")
            logger.info("****************************************************************")

        # Check if processing was cancelled mid-way through file organization
        # The was_cancelled variable is set in the file processing loop above
        files_actually_organized = current_file_being_processed - 1 if was_cancelled else total_new_original_files

        # Log album additions summary
        if total_album_additions > 0:
            logger.info(f"Album additions: {total_album_additions} files added to albums")

        organize_files_return = {
            "total_files_processed": total_files_processed,
            "total_new_original_files": files_actually_organized,
            "total_duplicates": len(duplicate_files),
            "total_filtered": len(filtered_files),
            "total_unreliable_dates": unreliable_dates_count,
            "total_errors": total_errors,
            "total_album_additions": total_album_additions,
            "filter_statistics": filter_stats or {},
            "filtered_files": filtered_files,
            "was_cancelled": was_cancelled if 'was_cancelled' in dir() else False
        }
        return organize_files_return

    except Exception as e_organize_files:
        logger.exception(f"\n organize_files Failed : {sys.exc_info()} - {e_organize_files}")
        organize_files_return = {
            "total_files_processed": total_files_processed,
            "total_new_original_files": total_new_original_files,
            "total_duplicates": len(duplicate_files) if 'duplicate_files' in dir() else 0,
            "total_filtered": len(filtered_files) if 'filtered_files' in dir() else 0,
            "total_unreliable_dates": unreliable_dates_count if 'unreliable_dates_count' in dir() else 0,
            "total_errors": total_errors,
            "total_album_additions": total_album_additions if 'total_album_additions' in dir() else 0,
            "filter_statistics": filter_stats if 'filter_stats' in dir() else {},
            "filtered_files": filtered_files if 'filtered_files' in dir() else [],
            "was_cancelled": was_cancelled if 'was_cancelled' in dir() else False
        }
        return organize_files_return


def write_settings(existing_settings):
    try:
        settings = {}
        if "source_directory" in existing_settings:
            settings["source_directory"] = existing_settings["source_directory"]
        else:
            settings["source_directory"] = 'W:\\All Photographs\\2003 - Photos'
            settings["source_directory"] = "W:\\Mylio_Vault\\Mylio_83eacc_131074\\Apple Photos"

        if "destination_directory" in existing_settings:
            settings["destination_directory"] = existing_settings["destination_directory"]
        else:
            settings["destination_directory"] = "W:\\SortedPhotos"

        if "include_subdirectories" in existing_settings:
            settings["include_subdirectories"] = existing_settings["include_subdirectories"]
        else:
            settings["include_subdirectories"] = True

        if "file_endings" in existing_settings:
            logger.info(f"The file_endings setting = {settings['file_endings']}")
        else:
            logger.info(f"file_endings not in settings so creating default!")
            settings['file_endings'] = [".jpg", ".png", ".heic", ".mov", ".mp4"]

        # Now write all the settings to the exe directory
        with open("settings.json", mode="w", encoding="utf-8") as write_file:
            json.dump(settings, write_file)

    except Exception as e:
        logger.exception("The write_settings function failed - {e}")

def main():
    # Parse the arguments
    # args = parse_arguments()
    logger.info(f"Starting file sorting process")

    # write settings:
    # write_settings("x")

    # Load configuration using Config class
    try:
        config = Config("settings.json")
        logger.info("Configuration loaded successfully")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        logger.exception(f"Failed to load configuration: {e}")
        return

    # Ensure the Destination directory exists
    utils.ensure_directory_exists(config.destination_directory)

    # List all files in the source directory
    files = DuplicateFileDetection.get_file_list(
        config.source_directory,
        config.include_subdirectories,
        config.file_endings
    )
    logger.info("#############################################################################")
    logger.info(f"The get_file_list function returned {len(files)} files for processing.")
    logger.info("#############################################################################")
    logger.info(f"The get_file_list function returned =  {files}")

    # Organize files by moving or copying them to the destination directory
    organize_files_return = organize_files(
        config,
        files,
        config.database_path,
        config.batch_size
    )


    logger.info("Completed Processing")


if __name__ == '__main__':
    try:
        logger.info("Starting __main__")
        main()
    except Exception as e:
        logger.exception(f"Process Failed : {sys.exc_info()} - {e}")
