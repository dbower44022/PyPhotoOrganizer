
import datetime
import hashlib
import json
import logging
import os
import pillow_heif  # https://github.com/bigcat88/pillow_heif
import shutil
import sqlite3
import sys
import tempfile

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS
from tqdm import tqdm

import utils
from photo_filter import PhotoFilter

# from pillow_heif import register_heif_opener

# Configure logging using shared utility
logger = utils.setup_logger(__name__, "DuplicateFileDetection_app_error.log")


class PhotoDatabase:
    """
    Context manager for handling SQLite database connections for photo hash storage.

    Usage:
        with PhotoDatabase('PhotoDB.db') as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM UniquePhotos")
            results = cursor.fetchall()
    """

    def __init__(self, database_path='PhotoDB.db'):
        """
        Initialize the PhotoDatabase connection manager.

        Parameters:
            database_path (str): Path to the SQLite database file
        """
        self.database_path = database_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """
        Open database connection when entering context.

        Returns:
            PhotoDatabase: Self, allowing access to connection and cursor
        """
        try:
            self.conn = sqlite3.connect(self.database_path)
            self.cursor = self.conn.cursor()
            logger.debug(f"Database connection opened to {self.database_path}")
            return self
        except Exception as e:
            logger.exception(f"Failed to connect to database {self.database_path}: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close database connection when exiting context.
        Commits changes if no exception occurred, rolls back otherwise.

        Parameters:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        try:
            if exc_type is None:
                # No exception, commit changes
                if self.conn:
                    self.conn.commit()
                    logger.debug("Database changes committed")
            else:
                # Exception occurred, rollback
                if self.conn:
                    self.conn.rollback()
                    logger.warning(f"Database changes rolled back due to exception: {exc_val}")
        finally:
            # Always close the connection
            if self.conn:
                self.conn.close()
                logger.debug("Database connection closed")

        # Return False to propagate exceptions
        return False

    def connection(self):
        """Get the database connection object."""
        return self.conn

    def get_cursor(self):
        """Get a cursor for executing queries."""
        return self.cursor

    def initialize_database(self):
        """
        Create the UniquePhotos table if it doesn't exist.
        This should be called after entering the context.

        Schema includes:
        - file_hash: Full SHA-256 hash (PRIMARY KEY)
        - partial_hash: Hash of first N bytes (for quick lookup)
        - partial_hash_bytes: Number of bytes used for partial hash
        - file_size: File size in bytes
        - file_name: Full path to file
        - create_datetime, create_year, create_month, create_day: File metadata
        """
        try:
            # Create table with partial hash support
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS UniquePhotos (
                    file_hash TEXT PRIMARY KEY,
                    partial_hash TEXT,
                    partial_hash_bytes INTEGER,
                    file_size INTEGER,
                    file_name TEXT NOT NULL,
                    create_datetime TEXT,
                    create_year TEXT,
                    create_month TEXT,
                    create_day TEXT
                )
            ''')

            # Create index on partial_hash for fast lookups
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_partial_hash
                ON UniquePhotos(partial_hash)
            ''')

            # Create index on file_size for optimization decisions
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_file_size
                ON UniquePhotos(file_size)
            ''')

            # Create composite index on date fields for date-based queries
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_date
                ON UniquePhotos(create_year, create_month, create_day)
            ''')

            # Create index on file_name for path lookups
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_file_name
                ON UniquePhotos(file_name)
            ''')

            self.conn.commit()
            logger.info("Database table and indexes initialized successfully")
        except Exception as e:
            logger.exception(f"Failed to initialize database tables: {e}")
            raise

    def get_all_hashes(self):
        """
        Retrieve all file hashes from the UniquePhotos table.

        Returns:
            list: List of file hash strings
        """
        try:
            self.cursor.execute("SELECT file_hash FROM UniquePhotos")
            results = self.cursor.fetchall()
            # Extract just the hash values from the tuple results
            return [row[0] for row in results]
        except Exception as e:
            logger.exception(f"Failed to retrieve hashes from database: {e}")
            raise

    def insert_unique_photo(self, file_hash, file_path, create_datetime, create_year, create_month, create_day,
                           partial_hash=None, partial_hash_bytes=None, file_size=None):
        """
        Insert a new unique photo record into the database.

        Parameters:
            file_hash (str): SHA-256 hash of the full file
            file_path (str): Full path to the file
            create_datetime (str): Creation date in YYYY-MM-DD format
            create_year (str): Year as string
            create_month (str): Month as zero-padded string
            create_day (str): Day as zero-padded string
            partial_hash (str, optional): SHA-256 hash of first N bytes
            partial_hash_bytes (int, optional): Number of bytes used for partial hash
            file_size (int, optional): File size in bytes
        """
        try:
            self.cursor.execute(
                """INSERT INTO UniquePhotos
                   (file_hash, partial_hash, partial_hash_bytes, file_size, file_name,
                    create_datetime, create_year, create_month, create_day)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_hash, partial_hash, partial_hash_bytes, file_size, file_path,
                 create_datetime, create_year, create_month, create_day)
            )
            logger.debug(f"Inserted unique photo: {file_path} (partial_hash: {partial_hash is not None})")
        except sqlite3.IntegrityError:
            # Hash already exists (PRIMARY KEY constraint)
            logger.warning(f"Attempted to insert duplicate hash: {file_hash}")
            raise
        except Exception as e:
            logger.exception(f"Failed to insert photo record: {e}")
            raise

    def has_hash(self, file_hash):
        """
        Check if a file hash already exists in the database.
        This is useful for resume capability.

        Parameters:
            file_hash (str): SHA-256 hash to check

        Returns:
            bool: True if hash exists, False otherwise
        """
        try:
            self.cursor.execute("SELECT 1 FROM UniquePhotos WHERE file_hash = ? LIMIT 1", (file_hash,))
            result = self.cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.exception(f"Failed to check if hash exists: {e}")
            raise

    def has_partial_hash(self, partial_hash):
        """
        Check if a partial hash exists in the database.
        Returns list of full hashes that match this partial hash.

        Parameters:
            partial_hash (str): Partial SHA-256 hash to check

        Returns:
            list: List of full hashes that have matching partial hash
        """
        try:
            self.cursor.execute(
                "SELECT file_hash FROM UniquePhotos WHERE partial_hash = ?",
                (partial_hash,)
            )
            results = self.cursor.fetchall()
            return [row[0] for row in results]
        except Exception as e:
            logger.exception(f"Failed to check partial hash: {e}")
            raise

    def commit(self):
        """
        Manually commit pending changes to the database.
        Useful for periodic commits during long-running operations.
        """
        try:
            if self.conn:
                self.conn.commit()
                logger.debug("Manual commit executed")
        except Exception as e:
            logger.exception(f"Failed to commit changes: {e}")
            raise


def get_file_list(sources, recursive=False, file_endings=None):
    """
    Create a list all files in the source directory, and subdirectories if the recursive parameter is true.

    Parameters:
    source (list of strings that contain valid directory path): The source directory path.
    recursive (bool): If True, list files recursively. Default is False.
    file_endings (list): List of file endings/extensions to include. Default is None.

    Returns:
    file_list: A list of file paths contained in the source folder provided.

    """
    try:
        logger.info("Initializing get_file_list")
        file_list = []
        logger.info(f"The list of directories passed = {sources}")
        if not sources:
            logger.info(f"There were no sources passed!")
            return None

        # Progress bar for scanning directories
        with tqdm(total=len(sources), desc="Scanning directories", unit="dir") as pbar:
            for source in sources:
                pbar.set_postfix_str(os.path.basename(source)[:50])
                try:
                    logger.info(f"Processing the source = {source}")
                    if recursive:
                        logger.info(f"Recursively processing {source}")
                        for root, dirs, files in os.walk(source):
                            logger.info(f"Processing root = {root}, and Subdirectories = {dirs}.")
                            files_processed_count = 0
                            files_added_count = 0
                            for file in files:
                                logger.info(f"Processing file {file} in {root}/{dirs}")
                                files_processed_count = files_processed_count + 1
                                verified_filename = VerifyFileType(os.path.join(root, file))
                                if verified_filename:
                                    logger.info(f"Processing file {verified_filename}")
                                    if not file_endings or verified_filename.lower().endswith(tuple(file_endings)):
                                        file_list.append(os.path.join(root, verified_filename))
                                        files_added_count = files_added_count + 1
                                        logger.info(f"appended - {verified_filename} to file_list")
                                    else:
                                        logger.info("hmmmm")
                                else:
                                    logger.info(f"The verifyfiletype routine determined that the file is not a valid type!")

                            logger.debug(f"Processed {files_processed_count } and Added {files_added_count} files from {root}/{dirs} to the list to process.")
                    else:
                        logger.info(f"EXCLUSIVELY processing {source}")
                        with os.scandir(source) as entries:
                            for entry in entries:
                                if entry.is_file() and (
                                    not file_endings or entry.name.lower().endswith(tuple(file_endings))
                                ):
                                    file_list.append(entry.path)
                    logger.debug(f"Added {len(file_list)} files from {source} to the list to process.")
                    pbar.update(1)

                except Exception as e:
                    logger.exception(f"\n Processing the source = {source} Failed : {sys.exc_info()} - {e}")
                    pbar.update(1)

        logger.info("Completed processing all sources passed!")
        return file_list
    except Exception as e:
        logger.exception(f"\n list_files process Failed : { sys.exc_info()} - {e}")


def get_creation_date(file_path):
    """
    Get the creation date of a file and extract year, month, and day.

    Parameters:
    file_path (str): The full file name with path.

    Returns:
    tuple: A tuple containing the year, month, and day.
    """
    try:
        logger.info("Initializing get_creation_date")
        # init required variables
        im = None
        exts = Image.registered_extensions()
        supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}
        # logger.info(f"The supported extensions = {supported_extensions}.")

        # register the pillow heic opener.  Otherwise, pillow will throw an ioerror = cannot identify image file.
        #pillow_heif.register_heif_opener()

        if os.name == "nt":  # Windows
            # get the creation date/time from Windows - This is stored as a ???
            try:
                creation_time = os.path.getctime(file_path)
            except Exception as e:
                logger.exception(f"The getctime function failure {e} occurred for file {file_path}")

            mod_time = os.path.getmtime(file_path)  # usually the modification date is a better indicator of the actual creation date.
            creation_date = datetime.datetime.fromtimestamp(creation_time)
            creation_date = datetime.datetime.fromtimestamp(mod_time)
            extension = os.path.splitext(file_path)[1]
            logger.info(f"-- create_time = {creation_time}, creation_date = {creation_date}, extension = {extension}")
            # Now try to get a more accurate date from EXIF data.
            try:
                processed_photos = 0
                not_photos = 0

                # TAGS is defined in PIL as a list of items returned
                _TAGS_r = dict(((v, k) for k, v in TAGS.items()))

                # logger.info(f"TAGS.items() = {TAGS.items()}")
                #logger.info(f"The extension for file is {extension}, and the supported_extensions = {supported_extensions}")
                if extension in supported_extensions:
                    # verifying extension is valid saves time necessary for pillow to attempt open and fail, which can be considerable.
                    logger.info(f"We have a pillow supported file type - {extension}. So attempt to get exif data.")

                    with Image.open(file_path) as im:
                        try:
                            exif_data_PIL = im._getexif()
                            #logger.info(f"exif_data_PIL = {exif_data_PIL}")
                            '''
                            EXIF contains at least four dates:                    
                            DateTime - 
                            DateTimeDigitized - 
                            PreviewDateTime - 
                            DateTimeOriginal -

                            GPS Date time can be retrieved from the  GPSTAGS object if necessary.
                            GPSDateTime - 
                            '''
                            logger.info(f"____________________   List of Date Tags ____________________________________ ")
                            logger.info(f"_TAGS_r  for DateTimeOriginal = ")
                            logger.info(_TAGS_r["DateTimeOriginal"])
                            logger.info(_TAGS_r["Model"])
                            # logger.info(_TAGS_r["CreateDate"])
                            # logger.info(_TAGS_r["GPSDateTime"])
                            # logger.info(_TAGS_r["DateTimeCreated"])
                            logger.info(f"________________________________________________________ ")
                            if exif_data_PIL is not None:
                                if exif_data_PIL[_TAGS_r["DateTimeOriginal"]]:
                                    # if a value for DateTimeOriginal is included in EXIF data, then use that as the fileDate.
                                    fileDate = exif_data_PIL[_TAGS_r["DateTimeOriginal"]]
                                    logger.info(f"fileDate = {fileDate}")
                                    if fileDate != '' and len(fileDate) > 10 and fileDate != "0000:00:00 00:00:00":
                                        # we located a proper file date in the exif data, so use that instead of date from OS.
                                        logger.info("------------------  File Dates --------------------------")
                                        logger.info(f"Date from os {datetime.datetime.fromtimestamp(creation_time)}, date from EXIF {fileDate}")
                                        logger.info(f"Converted EXIF fileDate = {datetime.datetime.strptime(fileDate, '%Y:%m:%d %H:%M:%S')}")
                                        logger.info("--------------------------------------------")

                                        if creation_date != datetime.datetime.strptime(fileDate, '%Y:%m:%d %H:%M:%S'):
                                            logger.info("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                                            logger.info("The OS and EXIF dates do NOT match, so using the EXIF date!")
                                            logger.info("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                                            creation_date = datetime.datetime.strptime(fileDate, '%Y:%m:%d %H:%M:%S')
                                        else:
                                            logger.info("The OS and EXIF dates matched, so using them both :)")

                                        im.close()
                                        processed_photos += 1
                                        logger.info(f"\r{processed_photos} photos processed, {not_photos} not processed")
                                    else:
                                        logger.info("fileDate does not exist in EXIF data.")
                                else:
                                    logger.info(f" exif_data_PIL[_TAGS_r[DateTimeOriginal]] does not exist.")
                            else:
                                not_photos += 1
                                logger.info(f"No EXIF data was present.  \r{processed_photos} photos processed, {not_photos} not processed")
                        except Exception as e:
                            logger.exception(f"The failure {e} occurred for file {file_path}")
                    im.close()
                else:
                    logger.info(f"The file {file_path}, with an extension of {extension} cannot be opened by pillow to determine date information, so return the OS date created. Supported Extensions = {supported_extensions}")

            except IOError as io_err:
                not_photos += 1
                logger.error(f"IOError when processing file {file_path}- {io_err}.")
                logger.info(f"\r{processed_photos} photos processed, {not_photos} not processed")
                pass
            except OSError as os_err:
                not_photos += 1
                logger.error(f"OSError when processing file {file_path}- {os_err}.")
                logger.info(f"\r{processed_photos} photos processed, {not_photos} not processed")
                pass
            except KeyError as key_err:
                logger.error(f"KeyError when processing file {file_path} - {key_err}.")
                not_photos += 1
                pass
            except Exception as e:
                logger.exception(f"When processing file {file_path} this error occurred:  {e}")

        else:  # macOS or Linux
            stat = os.stat(file_path)
            try:
                creation_time = stat.st_birthtime
                creation_date = datetime.datetime.fromtimestamp(creation_time)
            except AttributeError:
                # Fallback to the last metadata change time (best approximation)
                creation_time = stat.st_mtime
                creation_date = datetime.datetime.fromtimestamp(creation_time)

        logger.info(f"Completed locating date for {file_path}, now convert it.... {creation_date}")

        # make sure to return month and day as two digit strings and year as a string!
        year = f"{creation_date:%Y}"
        month = f"{creation_date:%m}"
        day = f"{creation_date:%d}"

        logger.debug(f"File {file_path} creation date: {year}-{month}-{day}")
        return year, month, day

    except Exception as e:
        logger.exception(f"\n When processing file {file_path},  get_creation_date process Failed : {sys.exc_info()} == {e}")
        if im:
            im.close()
        year = "1000"
        month = "01"
        day = "01"
        return year, month, day

def hash_file(filename):
    """
    Calculates the SHA-256 hash of an entire file.

    Parameters:
        filename (str): Path to the file to hash

    Returns:
        str: Hexadecimal SHA-256 hash of the file
    """
    try:
        logger.info(f"Initiating full hash for {filename}")
        hasher = hashlib.sha256()
        with open(filename, 'rb') as file:
            while True:
                chunk = file.read(4096)  # Read file in chunks
                if not chunk:
                    break
                hasher.update(chunk)
        hash_result = hasher.hexdigest()
        logger.info(f"Full hash for {filename}: {hash_result}")
        return hash_result

    except Exception as duplicate_e:
        logger.exception(f"The hash_file routine failed - {duplicate_e}")
        raise


def hash_file_partial(filename, num_bytes=16384):
    """
    Calculates the SHA-256 hash of the first N bytes of a file.

    This is used as a quick preliminary check before hashing the entire file.
    If partial hashes don't match, files cannot be duplicates.
    If partial hashes match, must verify with full hash.

    Parameters:
        filename (str): Path to the file to hash
        num_bytes (int): Number of bytes from start of file to hash (default: 16KB)

    Returns:
        str: Hexadecimal SHA-256 hash of first num_bytes of the file
    """
    try:
        logger.debug(f"Calculating partial hash ({num_bytes} bytes) for {filename}")
        hasher = hashlib.sha256()
        with open(filename, 'rb') as file:
            # Read only the first num_bytes
            chunk = file.read(num_bytes)
            hasher.update(chunk)

        hash_result = hasher.hexdigest()
        logger.debug(f"Partial hash for {filename}: {hash_result}")
        return hash_result

    except Exception as e:
        logger.exception(f"The hash_file_partial routine failed - {e}")
        raise


def find_duplicates(files, hashes, database_path='PhotoDB.db', batch_size=100,
                   partial_hash_enabled=True, partial_hash_bytes=16384, partial_hash_min_file_size=1048576,
                   config=None):
    """ Looks through a list of files and returns a list of duplicate and original files using two-stage hashing.

        Two-Stage Hashing Strategy:
        1. For files >= partial_hash_min_file_size:
           - Calculate quick partial hash (first N bytes)
           - If partial hash not in DB: file is unique
           - If partial hash in DB: calculate full hash to confirm
        2. For files < partial_hash_min_file_size:
           - Skip partial hash, calculate full hash directly

        Photo Filtering:
        - Before hashing, files are checked to determine if they are real photographs
        - Filters out icons, web graphics, thumbnails based on size, dimensions, filename
        - Filtered files are tracked separately and not added to the database

        Parameters:
        files - a list of files to be processed including the directory path to access the file
        hashes - a list of all previously located file hashes.
        database_path - path to the SQLite database file (default: 'PhotoDB.db')
        batch_size - number of files to process before committing to database (default: 100)
                     Set to 0 to only commit at the end (not recommended for large batches)
        partial_hash_enabled - whether to use partial hashing optimization (default: True)
        partial_hash_bytes - number of bytes to hash for partial check (default: 16384 = 16KB)
        partial_hash_min_file_size - minimum file size to use partial hashing (default: 1048576 = 1MB)
        config - Config object with photo filter settings (optional, if None filtering is disabled)

        Returns:
            results - a dictionary containing:
                duplicate_files - list of files that already exist in the database
                original_files - list of new unique files that were added to database
                filtered_files - list of files that were filtered out (not real photos)
                status - "completed" if successful
                files_processed - total number of files processed
                files_skipped - number of files skipped (already in DB from previous run)
                filter_statistics - statistics about filtering (if enabled)

        Resume Capability:
            If processing is interrupted, you can re-run with the same file list.
            Files already in the database will be detected and skipped automatically.

        Periodic Commits:
            Database is committed every 'batch_size' files to preserve progress.
            If a crash occurs, all files up to the last commit are saved.

        TODO: Modify data base to contain a 512 byte filed containing the hash for the first 512 bytes in a file.  This will allow us to quickly locate new files by checking the first
              512 bytes.  If it is unique, we know the entire file is unique.  if it matches, we need to hash the entire file to determine if it is truly a duplicate.
              We may want to use a larger value for the number of bytes to process initially, but when we do that, we need to reset all of the values in the database.
              The primary objective of this function is to eliminate the time to process very large files when they are clearly not a duplicate.  This will decrease the time necessary to process new files dramatically.
    """
    try:
        # check existence of parameters
        if hashes:
            # logger.info(f"hashes was provided! - {hashes}")
            logger.info(f"hashes was successfully loaded with {len(hashes)} existing unique photos")
        else:
            logger.info("hashes was not provided")
            hashes = []

        duplicate_files = []
        original_files = []
        filtered_files = []
        files_processed = 0
        files_skipped = 0
        files_since_last_commit = 0

        # Initialize photo filter if config provided
        photo_filter = None
        if config:
            try:
                photo_filter = PhotoFilter(config)
                if photo_filter.enabled:
                    logger.info("Photo filtering ENABLED - non-photos will be filtered out")
                else:
                    logger.info("Photo filtering DISABLED in config")
            except Exception as e:
                logger.warning(f"Failed to initialize PhotoFilter: {e}. Continuing without filtering.")
                photo_filter = None

        logger.info(f"Starting to process {len(files)} files with batch_size={batch_size}")

        # Use the PhotoDatabase context manager
        with PhotoDatabase(database_path) as db:
            # Create progress bar for file processing
            with tqdm(total=len(files), desc="Processing files", unit="file",
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                for file_index, filename in enumerate(files, 1):
                    try:
                        # Update progress bar description with current file
                        pbar.set_postfix_str(os.path.basename(filename)[:40])

                        if not os.path.isfile(filename):
                            logger.warning(f"Skipping non-file entry: {filename}")
                            pbar.update(1)
                            continue

                        logger.info(f"Processing file {file_index}/{len(files)}: {filename}")

                        # PHOTO FILTERING: Check if file is a real photograph
                        if photo_filter and photo_filter.enabled:
                            if not photo_filter.is_photo(filename):
                                filter_reason = photo_filter.get_filter_reason(filename)
                                logger.info(f"FILTERED OUT (non-photo): {filename} - Reason: {filter_reason}")
                                filtered_file = {
                                    "file_path": filename,
                                    "filter_reason": filter_reason
                                }
                                filtered_files.append(filtered_file)
                                pbar.update(1)
                                continue

                        # Get file size to decide on hashing strategy
                        try:
                            file_size = os.path.getsize(filename)
                        except Exception as e:
                            logger.exception(f"Failed to get file size for {filename}: {e}")
                            pbar.update(1)
                            continue

                        # TWO-STAGE HASHING OPTIMIZATION
                        file_hash = None
                        partial_hash = None
                        use_partial_hash = (partial_hash_enabled and
                                           file_size >= partial_hash_min_file_size)

                        if use_partial_hash:
                            # STAGE 1: Quick partial hash check
                            try:
                                partial_hash = hash_file_partial(filename, partial_hash_bytes)
                                logger.info(f"Partial hash calculated for {filename} ({utils.format_file_size(file_size)})")
                            except Exception as e:
                                logger.exception(f"Partial hash failed for {filename}: {e}")
                                pbar.update(1)
                                continue

                            # Check if partial hash exists in database
                            matching_full_hashes = db.has_partial_hash(partial_hash)

                            if matching_full_hashes:
                                # Potential duplicate - STAGE 2: Verify with full hash
                                logger.info(f"Partial hash match found! Calculating full hash to confirm for {filename}")
                                try:
                                    file_hash = hash_file(filename)
                                except Exception as e:
                                    logger.exception(f"Full hash failed for {filename}: {e}")
                                    pbar.update(1)
                                    continue

                                # Check if full hash matches any of the candidates
                                if file_hash in matching_full_hashes:
                                    logger.info(f"DUPLICATE CONFIRMED: Full hash matches for {filename}")
                                    # This is a true duplicate
                                    files_skipped += 1
                                    duplicate_file = {
                                        "file_hash": file_hash,
                                        "file_path": filename,
                                        "file_create_datetime": "N/A"
                                    }
                                    duplicate_files.append(duplicate_file)
                                    files_processed += 1
                                    pbar.update(1)
                                    continue
                                else:
                                    # Partial hash collision - different files with same first N bytes
                                    logger.info(f"Partial hash collision (rare!) - files differ: {filename}")
                                    # Continue to save as unique file
                            else:
                                # No partial hash match - file is definitely unique
                                # Calculate full hash for storage
                                logger.info(f"No partial hash match - file is unique: {filename}")
                                try:
                                    file_hash = hash_file(filename)
                                except Exception as e:
                                    logger.exception(f"Full hash failed for {filename}: {e}")
                                    pbar.update(1)
                                    continue

                        else:
                            # Small file - skip partial hash, go straight to full hash
                            logger.debug(f"Small file ({utils.format_file_size(file_size)}) - using full hash only: {filename}")
                            try:
                                file_hash = hash_file(filename)
                            except Exception as e:
                                logger.exception(f"Hash failed for {filename}: {e}")
                                pbar.update(1)
                                continue

                            # Check if hash already exists in database
                            if db.has_hash(file_hash):
                                logger.info(f"File hash already in database: {filename}")
                                files_skipped += 1
                                duplicate_file = {
                                    "file_hash": file_hash,
                                    "file_path": filename,
                                    "file_create_datetime": "N/A"
                                }
                                duplicate_files.append(duplicate_file)
                                files_processed += 1
                                pbar.update(1)
                                continue

                        # Check against in-memory hash list (current batch)
                        if file_hash in hashes:
                            logger.info(f"Duplicate in current batch: {filename}")
                            duplicate_file = {
                                "file_hash": file_hash,
                                "file_path": filename,
                                "file_create_datetime": "N/A"
                            }
                            duplicate_files.append(duplicate_file)
                            files_processed += 1
                            pbar.update(1)
                        else:
                            # NEW UNIQUE FILE - Save to database
                            logger.info(f"Unique file - saving to database: {filename}")
                            hashes.append(file_hash)

                            # Get the create date
                            file_year, file_month, file_day = get_creation_date(filename)
                            file_create_date = f"{file_year}-{file_month}-{file_day}"

                            original_file = {
                                "file_hash": file_hash,
                                "file_path": filename,
                                "file_create_datetime": file_create_date,
                                "file_create_year": file_year,
                                "file_create_month": file_month,
                                "file_create_day": file_day
                            }
                            original_files.append(original_file)

                            # Add to database with partial hash info
                            db.insert_unique_photo(
                                file_hash,
                                filename,
                                file_create_date,
                                file_year,
                                file_month,
                                file_day,
                                partial_hash=partial_hash,  # Will be None for small files
                                partial_hash_bytes=partial_hash_bytes if partial_hash else None,
                                file_size=file_size
                            )

                            files_processed += 1
                            files_since_last_commit += 1

                            # Periodic commit to preserve progress
                            if batch_size > 0 and files_since_last_commit >= batch_size:
                                db.commit()
                                logger.info(f"*** CHECKPOINT: Committed {files_since_last_commit} files to database. Progress: {files_processed}/{len(files)} ***")
                                files_since_last_commit = 0

                            # Update progress bar after successful processing
                            pbar.update(1)

                    except Exception as e:
                        logger.exception(f"Error processing file {filename}: {e}")
                        logger.warning(f"Continuing with next file despite error in {filename}")
                        pbar.update(1)
                        # Continue processing other files even if one fails

            # Final commit for any remaining uncommitted changes
            if files_since_last_commit > 0:
                db.commit()
                logger.info(f"*** FINAL COMMIT: Committed final {files_since_last_commit} files to database ***")

            logger.info(f"=== PROCESSING COMPLETE ===")
            logger.info(f"Total files processed: {files_processed}/{len(files)}")
            logger.info(f"Unique files added: {len(original_files)}")
            logger.info(f"Duplicates found: {len(duplicate_files)}")
            logger.info(f"Files skipped (already in DB): {files_skipped}")
            if photo_filter and photo_filter.enabled:
                logger.info(f"Files filtered (non-photos): {len(filtered_files)}")
                photo_filter.print_statistics()

        # Return results
        results = {}
        results["duplicate_files"] = duplicate_files
        results["original_files"] = original_files
        results["filtered_files"] = filtered_files
        results["status"] = "completed"
        results["files_processed"] = files_processed
        results["files_skipped"] = files_skipped

        # Add filter statistics if filtering was enabled
        if photo_filter and photo_filter.enabled:
            results["filter_statistics"] = photo_filter.get_statistics()
        else:
            results["filter_statistics"] = None

        return results

    except Exception as duplicate_e:
        logger.exception(f"The find_duplicates routine failed - {duplicate_e}")


def load_photo_hashes(database_path='PhotoDB.db'):
    '''
    This routine will return a list of all unique photo hashes that can be used to locate existing photos.

    Parameters:
        database_path - path to the SQLite database file (default: 'PhotoDB.db')

    Returns:
        List of file hashes from the UniquePhotos table
    '''
    try:
        logger.info(f"Loading photo hashes from {database_path}")

        # Use the PhotoDatabase context manager
        with PhotoDatabase(database_path) as db:
            results = db.get_all_hashes()
            logger.info(f"Loaded {len(results)} unique photo hashes from database")
            return results

    except Exception as e:
        logger.exception(f"The error {e} occurred in load_photo_hashes")
        return []


def VerifyFileType(filename):
    """ This routine takes a filename, and then verifies that the file extension matches the file type.
    This is specifically used to assign a file extension to files that do not have an extension!

    This routine will return the passed 'filename' if it is a valid photo, or the 'newfilename' if the file had to be processed.
    """
    try:
        logger.info(f"About to process file '{filename}'!")

        valid_extensions = ['.jpg', '.png', '.gif', '.tif', '.bmp', '.webp', '.ico', '.ppm', '.eps', '.pdf']
        EXTENSIONS_MAP = {
            'JPEG': ['.jpg', '.jpeg'],
            'PNG': ['.png', '.png'],
            'GIF': ['.gif'],
            'TIFF': ['.tiff', '.tif'],
            'BMP': ['.bmp'],
            'WEBP': ['.webp'],
            'ICO': ['.ico'],
            'PPM': ['.ppm'],
            'EPS': ['.eps'],
            'PDF': ['.pdf'],
        }

        # Get the base filename, and extension (if one exists)
        base_filename, existing_file_extension = os.path.splitext(filename)
        logger.info(f"The existing_file_extension = '{existing_file_extension}'")

        # Try to open the file, and if it fails, try to verify if the extension is invalid.
        try:
            with Image.open(filename) as img:
                analyzed_file_format = img.format
                logger.info(f"The file - {filename} was successfully opened and the filetype returned by pillow is {analyzed_file_format}")

                # Now determine if the returned filetype contains a file extension that matches the file extension of the file being processed.  The format returned by pillow (correct_file_format) is a coded value, and likely does not match the extension. ex:  JPEG instead of .jpg
                matching_file_extension = None
                # for ext, extensions in EXTENSIONS_MAP.items():
                for file_type in EXTENSIONS_MAP:
                    if file_type.upper() == analyzed_file_format.upper():
                        logger.info(f"We found the matching file_type = {file_type}")
                        matching_file_type = file_type
                        for ext in EXTENSIONS_MAP[file_type]:
                            logger.info(f"Checking for match between the calculated file type extensions and the existing extension - existing_file_extension.upper() = '{existing_file_extension.upper()}',  ext.upper() = '{ext.upper()}'")
                            if existing_file_extension.upper() == ext.upper():
                                # If there is a matching file extension found, convert it to the STANDARD extension.
                                matching_file_extension = ext
                                logger.info(f"We located a valid file type -{analyzed_file_format}, and the existing file extension matched one of the valid extensions for that format - '{matching_file_extension}'")
                                # We found a file extension in the calculated type that matches the existing extension.  So the file is valid to process.
                                return filename
                            else:
                                logger.info(f"existing_file_extension.upper() - '{existing_file_extension.upper()}' does NOT MATCH ext.upper() = '{ext.upper()}', so checking other possible extensions for the file type = {file_type}.")
                    else:
                        logger.info(f"file_type.upper() = {file_type.upper()} does not match the calculated file format = {analyzed_file_format.upper()}, so checking next file type. ")

                logger.info("##################################################################################")
                logger.info(f"The file format returned by pillow '{analyzed_file_format}'is a valid pillow format, but the existing file extension '{existing_file_extension}' does not match any of the valid file extensions for the calculated file type.  So we need to continue processing to determine if it is a valid file!")
                logger.info("##################################################################################")

                # If the actual filetype does not match the extension of the file to be processed, write a valid file to the disk drive and return it to be processed instead of the incorrect file.
                if not existing_file_extension or existing_file_extension.lower() != matching_file_extension.lower():
                    # The valid file extensions from the analyzed_filetype does not match the existing file extension.  So create a new file with the first correct extensions from the analyzed_filetype
                    extension_list = EXTENSIONS_MAP[matching_file_type]
                    logger.info(f"The extension list = {extension_list}")
                    new_file_extension =  extension_list[0]  # Return the first extension in the list of valid extensions
                    logger.info(f"The new file extension = {new_file_extension}")
                    new_filepath = f"{os.path.splitext(filename)[0]}{new_file_extension}"
                    try:
                        safe_rename_or_copy(filename, new_filepath)
                    except Exception as e:
                        logger.error(f"The file {filename} could not be renamed - {e}")
                        return  None

                    logger.info(f"File extension corrected: {filename} -> {new_filepath}")
                    return new_filepath

                else:
                    logger.info("File extension is None, or matches!  How is this possible?????")
                    return

        except (FileNotFoundError, UnidentifiedImageError):
            logger.info(f"Pillow cannot open the file: {filename}. It might not be a valid image.")
            pass
        except Exception as e:
            logger.exception(f"The error {e} occurred in VerifyFileType")


        #TODO: Not sure if this use case can occur for a invalid file extension - IE pillow will open a file with an mis-matched extension or no extension at all... VERIFY!!!!
        logger.info("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        logger.info(f"Pillow could not open the file.  This could because of a file lock, or incorrect extension...THIS LOGIC IS NOT COMPLETE!!!!!")
        logger.info("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        # Verify that the file has a valid extension type
        logger.info(f"The existing_file_extension = {existing_file_extension}")
        if not os.path.exists(filename) :
            logger.info(f"The file to be processed - {filename}, does not exist. ")
            return None
        else:
            logger.info("The file exists, and will be checked for other format types!")

        if existing_file_extension:
            logger.info(f"The file extension = {existing_file_extension}")
        else:
            logger.info(f"The file does not contain an extension.  So we need to try adding an extension and seeing if the file can be opened in Pillow")
            # Read the original file content
            try:
                with open(filename, 'rb') as f:
                    content = f.read()
            except Exception:
                return None

            # Create a temporary directory to test file variants
            valid_extension_found = None
            with tempfile.TemporaryDirectory() as temp_dir:
                for ext in valid_extensions:
                    temp_path = os.path.join(temp_dir, 'temp' + ext)
                    logger.info(f"Processing {temp_path}")
                    try:
                        with open(temp_path, 'wb') as f:
                            f.write(content)
                        with Image.open(temp_path) as img:
                            img.verify()  # This confirms the image is valid
                            valid_extension_found = ext
                            logger.info(f"We found a valid format!!! - {img.format} with extension {ext}")
                            break
                    except (UnidentifiedImageError, OSError):
                        continue

            # Now outside the temp directory context, handle the file appropriately
            if valid_extension_found:
                # Create a new filepath with the correct extension
                new_filepath = f"{filename}{valid_extension_found}"
                try:
                    safe_rename_or_copy(filename, new_filepath)
                    logger.info(f"File extension added: {filename} -> {new_filepath}")
                    return new_filepath
                except Exception as e:
                    logger.error(f"Failed to rename file with new extension: {e}")
                    return None
            else:
                logger.info(f"We did not find a valid file format for {filename}")
                return filename

    except Exception as e:
        logger.exception(f"The error {e} occurred in VerifyFileType")


def safe_rename_or_copy(old_path, new_path):
    """Try to rename, or fall back to copying if the file is locked."""
    try:
        os.rename(old_path, new_path)
        logger.info(f"File renamed to: {new_path}")
    except (PermissionError, OSError) as e:
        logger.error(f"Rename failed: {e}")
        try:
            if os.path.exists(new_path):
                logger.info(f"Cannot copy. Target file already exists: {new_path}")
                return
            shutil.copy2(old_path, new_path)
            logger.info(f"File copied to: {new_path}")
        except Exception as copy_err:
            logger.error(f"Copy also failed: {copy_err}")

if __name__ == '__main__':
    try:
        '''
        This routine reads files in a directory and calculates the hash for each file.
        It then checks the database to determine if the file is a duplicate of a previous file.
        If the file is NOT a duplicate, it then adds the hash and filename/path  to the UniquePhotos database, and copies the file to the UniquePhotos Directory.
        If the file is a duplicate, it adds the hash and filename/path to the DuplicatePhotos database. 
        
        '''
        #logger.info("About to run sql_light")
        #sql_light()
        #logger.info("just finished!")

        directory_to_check = 'd:\\Test Files\\'
        #directory_to_check = "W:\\All Photographs\\2023 Photos\\To Be Filed"
        recursive = False
        file_endings =  [".jpg", ".png", ".heic"]

        try:
            logger.info("Initializing ensure_directory_exists")
            file_list = []
            if recursive:
                for root, dirs, files in os.walk(directory_to_check):
                    for file in files:
                        if not file_endings or file.lower().endswith(tuple(file_endings)):
                            file_list.append(os.path.join(root, file))
            else:
                with os.scandir(directory_to_check) as entries:
                    for entry in entries:
                        if entry.is_file() and (
                                not file_endings or entry.name.lower().endswith(tuple(file_endings))
                        ):
                            file_list.append(entry.path)
            logger.debug(f"Listed {len(file_list)} files from {directory_to_check}")

        except Exception as e:
            logger.exception(f"\n list_files process Failed : {sys.exc_info()} - {e}")

        try:
            database_path = "PhotoDB.db"  # Can be loaded from settings if needed
            batch_size = 100  # Commit every 100 files
            logger.info(f"About to run load_photo_hashes.")
            existing_hashes = load_photo_hashes(database_path)
        except Exception as e:
            logger.exception(f"The load_photo_hashes failed - {e}")

        results = find_duplicates(file_list, existing_hashes, database_path, batch_size)
        if results:
            logger.info("Files completed processing:")
            logger.info("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            if results["original_files"]:
                original_files = results["original_files"]
                logger.info(f"The original files found = {original_files}")
            else:
                logger.info("No new files located")

            if results["duplicate_files"]:
                duplicate_files = results["duplicate_files"]
                logger.info(f"The duplicate files found = {duplicate_files}")
            else:
                logger.info("No duplicate files located")

        else:
            print("No duplicate files found.")
    except Exception as duplicate_e:
        logger.exception(f"The __main__ routine failed - {duplicate_e}")