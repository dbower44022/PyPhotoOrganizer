# API Documentation

> Code reference and API documentation for developers

**Last Updated:** 2026-01-02

---

## Table of Contents

- [Module Overview](#module-overview)
- [constants.py](#constantspy)
- [config.py](#configpy)
- [utils.py](#utilspy)
- [DuplicateFileDetection.py](#duplicatefiledetectionpy)
- [photo_filter.py](#photo_filterpy)
- [main.py](#mainpy)
- [Usage Examples](#usage-examples)

---

## Module Overview

```
PyPhotoOrganizer/
├── constants.py          # Application constants
├── config.py            # Configuration management
├── utils.py             # Shared utilities
├── DuplicateFileDetection.py  # Core duplicate detection
├── photo_filter.py      # Photo filtering logic
└── main.py              # Main orchestration
```

---

## constants.py

Application-wide constants. All values are read-only.

### File I/O Constants

```python
FILE_READ_CHUNK_SIZE = 4096  # Bytes to read per iteration
```

**Usage:**
```python
with open(file, 'rb') as f:
    while chunk := f.read(constants.FILE_READ_CHUNK_SIZE):
        process(chunk)
```

---

### Hashing Constants

```python
PARTIAL_HASH_BYTES = 16384          # 16KB for partial hash
PARTIAL_HASH_MIN_FILE_SIZE = 1048576  # 1MB threshold
```

**Usage:**
```python
if file_size >= constants.PARTIAL_HASH_MIN_FILE_SIZE:
    partial_hash = hash_file_partial(file, constants.PARTIAL_HASH_BYTES)
```

---

### Database Constants

```python
DEFAULT_BATCH_SIZE = 100           # Files per commit
DEFAULT_DATABASE_NAME = 'PhotoDB.db'
```

---

### Photo Filtering Constants

```python
MIN_PHOTO_FILE_SIZE = 51200  # 50KB
MIN_PHOTO_WIDTH = 800        # pixels
MIN_PHOTO_HEIGHT = 600       # pixels
MAX_PHOTO_WIDTH = 50000
MAX_PHOTO_HEIGHT = 50000
MIN_SQUARE_SIZE = 400        # pixels
```

---

### Display Constants

```python
MAX_FILENAME_DISPLAY_LENGTH = 40       # Progress bar display
MAX_FILENAME_DISPLAY_LENGTH_SCAN = 50  # Directory scan display
```

---

### File Extension Constants

```python
VALID_IMAGE_EXTENSIONS = [
    '.jpg', '.png', '.gif', '.tif', '.bmp',
    '.webp', '.ico', '.ppm', '.eps', '.pdf'
]

DEFAULT_FILE_ENDINGS = [
    '.jpg', '.jpeg', '.png', '.heic', '.tif', '.mov', '.mp4'
]

HEIC_EXTENSIONS = ('.heic', '.heif', '.HEIC', '.HEIF')
```

---

### Error Constants

```python
INVALID_DATE_YEAR = "1000"
INVALID_DATE_MONTH = "01"
INVALID_DATE_DAY = "01"
```

**Usage:** Returned when date extraction fails

---

### Security Constants

```python
DANGEROUS_PATH_PATTERNS = ['..']
```

---

## config.py

### Class: `Config`

Configuration loader and manager.

#### Constructor

```python
Config(config_file: str = 'settings.json')
```

**Parameters:**
- `config_file` (str): Path to JSON configuration file

**Raises:**
- `FileNotFoundError`: If config file doesn't exist
- `json.JSONDecodeError`: If config file is invalid JSON
- `ValueError`: If required settings missing or invalid

**Example:**
```python
from config import Config

config = Config('settings.json')
print(config.batch_size)  # 100
```

---

#### Properties

```python
@property
config.source_directory -> List[str]
config.destination_directory -> str
config.database_path -> str
config.batch_size -> int
config.include_subdirectories -> bool
config.file_endings -> List[str]
config.group_by_year -> bool
config.group_by_day -> bool
config.copy_files -> bool
config.move_files -> bool
config.partial_hash_enabled -> bool
config.partial_hash_bytes -> int
config.partial_hash_min_file_size -> int
```

**Example:**
```python
for source_dir in config.source_directory:
    print(f"Processing: {source_dir}")
```

---

#### Methods

##### `get(key: str, default: Any = None) -> Any`

Get configuration value with optional default.

```python
value = config.get('custom_setting', default='fallback')
```

---

##### `set(key: str, value: Any) -> None`

Set configuration value (in-memory only).

```python
config.set('batch_size', 200)
```

---

##### `save() -> None`

Save current configuration to file.

```python
config.set('batch_size', 200)
config.save()  # Persists to settings.json
```

---

##### `to_dict() -> Dict[str, Any]`

Get all settings as dictionary.

```python
all_settings = config.to_dict()
```

---

#### Dictionary-Style Access

```python
config['batch_size']  # Get
config['batch_size'] = 200  # Set
'batch_size' in config  # Check existence
```

---

## utils.py

### Function: `setup_logger`

```python
setup_logger(name: str, log_file: str, level=logging.DEBUG) -> logging.Logger
```

Configure logger with console and file handlers.

**Parameters:**
- `name` (str): Logger name (usually `__name__`)
- `log_file` (str): Log file path
- `level` (int): Logging level (default: DEBUG)

**Returns:**
- `logging.Logger`: Configured logger instance

**Example:**
```python
import utils

logger = utils.setup_logger(__name__, "app.log")
logger.info("Application started")
```

---

### Function: `ensure_directory_exists`

```python
ensure_directory_exists(folder_path: str) -> bool
```

Create directory if it doesn't exist.

**Parameters:**
- `folder_path` (str): Directory path

**Returns:**
- `bool`: True if directory exists or was created

**Raises:**
- `OSError`: If directory creation fails

**Example:**
```python
utils.ensure_directory_exists("/path/to/output")
```

---

### Function: `get_unique_filename`

```python
get_unique_filename(full_path: str) -> str
```

Generate unique filename by appending counter.

**Parameters:**
- `full_path` (str): Desired file path

**Returns:**
- `str`: Unique file path (may have _1, _2, etc.)

**Example:**
```python
# If photo.jpg exists
unique = utils.get_unique_filename("/dest/photo.jpg")
# Returns: "/dest/photo_1.jpg"
```

---

### Function: `validate_settings`

```python
validate_settings(settings_data: dict, required_keys: list) -> Tuple[bool, list]
```

Validate required settings present.

**Parameters:**
- `settings_data` (dict): Settings dictionary
- `required_keys` (list): Required key names

**Returns:**
- `tuple`: `(is_valid: bool, missing_keys: list)`

**Example:**
```python
is_valid, missing = utils.validate_settings(
    settings,
    ['source_directory', 'destination_directory']
)
if not is_valid:
    print(f"Missing: {missing}")
```

---

### Function: `format_file_size`

```python
format_file_size(size_bytes: int) -> str
```

Convert bytes to human-readable format.

**Parameters:**
- `size_bytes` (int): Size in bytes

**Returns:**
- `str`: Formatted size (e.g., "1.5 MB")

**Example:**
```python
size_str = utils.format_file_size(1536000)
# Returns: "1.5 MB"
```

---

### Function: `safe_get_file_size`

```python
safe_get_file_size(file_path: str) -> Optional[int]
```

Get file size without raising exceptions.

**Parameters:**
- `file_path` (str): File path

**Returns:**
- `int | None`: File size in bytes, or None if error

**Example:**
```python
size = utils.safe_get_file_size("/path/to/file.jpg")
if size is not None:
    print(f"Size: {size} bytes")
```

---

## DuplicateFileDetection.py

### Class: `PhotoDatabase`

Context manager for SQLite database operations.

#### Constructor

```python
PhotoDatabase(database_path: str = constants.DEFAULT_DATABASE_NAME)
```

**Example:**
```python
with PhotoDatabase('PhotoDB.db') as db:
    db.initialize_database()
    hashes = db.get_all_hashes()
```

---

#### Methods

##### `initialize_database() -> None`

Create tables and indexes.

**Raises:**
- `Exception`: If database initialization fails

---

##### `get_all_hashes() -> List[str]`

Retrieve all file hashes.

**Returns:**
- `list`: List of SHA-256 hash strings

---

##### `insert_unique_photo(...) -> None`

Insert new unique photo record.

**Parameters:**
```python
insert_unique_photo(
    file_hash: str,
    partial_hash: str,
    partial_hash_bytes: int,
    file_size: int,
    file_path: str,
    create_datetime: str,
    create_year: str,
    create_month: str,
    create_day: str
)
```

---

### Function: `get_file_list`

```python
get_file_list(
    sources: List[str],
    recursive: bool = True,
    endings: List[str] = None
) -> List[str]
```

Scan directories for matching files.

**Parameters:**
- `sources` (list): Directory paths to scan
- `recursive` (bool): Include subdirectories
- `endings` (list): File extensions to match

**Returns:**
- `list`: File paths

**Example:**
```python
files = DuplicateFileDetection.get_file_list(
    sources=["/photos"],
    recursive=True,
    endings=['.jpg', '.png']
)
```

---

### Function: `hash_file`

```python
hash_file(filename: str) -> str
```

Calculate SHA-256 hash of entire file.

**Parameters:**
- `filename` (str): File path

**Returns:**
- `str`: SHA-256 hash (64 hex characters)

**Raises:**
- `Exception`: If file cannot be read

**Example:**
```python
file_hash = DuplicateFileDetection.hash_file("/path/photo.jpg")
# Returns: "a1b2c3d4..."
```

---

### Function: `hash_file_partial`

```python
hash_file_partial(
    filename: str,
    num_bytes: int = constants.PARTIAL_HASH_BYTES
) -> str
```

Calculate SHA-256 hash of first N bytes.

**Parameters:**
- `filename` (str): File path
- `num_bytes` (int): Bytes to hash (default: 16384)

**Returns:**
- `str`: SHA-256 hash of first N bytes

**Example:**
```python
partial = DuplicateFileDetection.hash_file_partial(
    "/path/video.mp4",
    num_bytes=16384
)
```

---

### Function: `find_duplicates`

```python
find_duplicates(
    files: List[str],
    hashes: List[str],
    database_path: str = constants.DEFAULT_DATABASE_NAME,
    batch_size: int = constants.DEFAULT_BATCH_SIZE,
    partial_hash_enabled: bool = True,
    partial_hash_bytes: int = constants.PARTIAL_HASH_BYTES,
    partial_hash_min_file_size: int = constants.PARTIAL_HASH_MIN_FILE_SIZE,
    config: Config = None
) -> Dict
```

Main duplicate detection function.

**Parameters:**
- `files` (list): File paths to process
- `hashes` (list): Existing hashes from database
- `database_path` (str): Database file path
- `batch_size` (int): Files per commit
- `partial_hash_enabled` (bool): Enable two-stage hashing
- `partial_hash_bytes` (int): Bytes for partial hash
- `partial_hash_min_file_size` (int): Minimum size for partial hashing
- `config` (Config): Configuration for photo filtering

**Returns:**
```python
{
    'duplicate_files': [...],      # List of duplicates
    'original_files': [...],       # List of unique files
    'filtered_files': [...],       # List of filtered files
    'status': 'completed',
    'files_processed': int,
    'files_skipped': int,
    'filter_statistics': {...}     # Filter stats dict
}
```

**Example:**
```python
results = DuplicateFileDetection.find_duplicates(
    files=file_list,
    hashes=existing_hashes,
    database_path='PhotoDB.db',
    batch_size=100,
    config=config
)

print(f"Found {len(results['duplicate_files'])} duplicates")
print(f"Found {len(results['original_files'])} unique files")
```

---

### Function: `get_creation_date`

```python
get_creation_date(file_path: str) -> Tuple[str, str, str]
```

Extract creation date from EXIF or file system.

**Parameters:**
- `file_path` (str): Image file path

**Returns:**
- `tuple`: `(year, month, day)` as zero-padded strings

**Example:**
```python
year, month, day = DuplicateFileDetection.get_creation_date("/photo.jpg")
# Returns: ("2024", "11", "25")
```

**Priority:**
1. EXIF DateTimeOriginal
2. EXIF DateTime
3. File system creation time
4. File system modification time
5. Default: ("1000", "01", "01")

---

### Function: `load_photo_hashes`

```python
load_photo_hashes(database_path: str) -> List[str]
```

Load all hashes from database.

**Parameters:**
- `database_path` (str): Database file path

**Returns:**
- `list`: List of hash strings

**Example:**
```python
existing_hashes = DuplicateFileDetection.load_photo_hashes('PhotoDB.db')
```

---

### Function: `VerifyFileType`

```python
VerifyFileType(filename: str) -> Optional[str]
```

Verify file extension matches actual type.

**Parameters:**
- `filename` (str): File path

**Returns:**
- `str | None`: Corrected filename, or None if invalid

**Example:**
```python
corrected = DuplicateFileDetection.VerifyFileType("/path/image.png")
# If PNG labeled as JPG, renames and returns new path
```

---

## photo_filter.py

### Class: `PhotoFilter`

Photo validation and filtering.

#### Constructor

```python
PhotoFilter(config: Config)
```

**Parameters:**
- `config` (Config): Configuration object with filter settings

**Example:**
```python
from photo_filter import PhotoFilter
from config import Config

config = Config('settings.json')
photo_filter = PhotoFilter(config)
```

---

#### Method: `is_photo`

```python
is_photo(file_path: str) -> bool
```

Determine if file is a real photograph.

**Parameters:**
- `file_path` (str): File to check

**Returns:**
- `bool`: True if photo, False if should be filtered

**Example:**
```python
if photo_filter.is_photo("/path/image.jpg"):
    process_photo()
else:
    print("Filtered: not a photo")
```

---

#### Method: `get_filter_reason`

```python
get_filter_reason(file_path: str) -> Optional[str]
```

Get reason why file was filtered.

**Parameters:**
- `file_path` (str): File path

**Returns:**
- `str | None`: Filter reason or None if not filtered

**Example:**
```python
reason = photo_filter.get_filter_reason("/icon.png")
# Returns: "File size too small (5 KB < 50 KB)"
```

---

#### Method: `get_statistics`

```python
get_statistics() -> Dict[str, int]
```

Get filtering statistics.

**Returns:**
```python
{
    'total_checked': int,
    'total_filtered': int,
    'filtered_by_size': int,
    'filtered_by_dimensions': int,
    'filtered_by_square': int,
    'filtered_by_filename': int,
    'filtered_by_exif': int,
    'filtered_by_read_error': int
}
```

**Example:**
```python
stats = photo_filter.get_statistics()
print(f"Filtered {stats['total_filtered']} files")
print(f"  By size: {stats['filtered_by_size']}")
```

---

## main.py

### Function: `organize_files`

```python
organize_files(
    config: Config,
    files: List[str],
    database_path: str = constants.DEFAULT_DATABASE_NAME,
    batch_size: int = constants.DEFAULT_BATCH_SIZE
) -> Dict[str, int]
```

Main file organization function.

**Parameters:**
- `config` (Config): Configuration object
- `files` (list): File paths to organize
- `database_path` (str): Database file path
- `batch_size` (int): Files per commit

**Returns:**
```python
{
    'total_files_processed': int,
    'total_new_original_files': int
}
```

**Example:**
```python
from config import Config
import main

config = Config('settings.json')
files = ['/photo1.jpg', '/photo2.jpg']

results = main.organize_files(
    config=config,
    files=files,
    database_path='PhotoDB.db',
    batch_size=100
)

print(f"Processed: {results['total_files_processed']}")
print(f"New files: {results['total_new_original_files']}")
```

---

### Function: `main`

```python
main() -> None
```

Application entry point.

**Example:**
```python
if __name__ == '__main__':
    main()
```

---

## Usage Examples

### Complete Workflow Example

```python
from config import Config
import DuplicateFileDetection
import main

# 1. Load configuration
config = Config('settings.json')

# 2. Get file list
files = DuplicateFileDetection.get_file_list(
    sources=config.source_directory,
    recursive=config.include_subdirectories,
    endings=config.file_endings
)

# 3. Process and organize
results = main.organize_files(
    config=config,
    files=files,
    database_path=config.database_path,
    batch_size=config.batch_size
)

# 4. Display results
print(f"Total processed: {results['total_files_processed']}")
print(f"New unique files: {results['total_new_original_files']}")
```

---

### Custom Duplicate Detection

```python
import DuplicateFileDetection
from config import Config

config = Config('settings.json')

# Load existing hashes
existing_hashes = DuplicateFileDetection.load_photo_hashes('PhotoDB.db')

# Find duplicates with custom settings
results = DuplicateFileDetection.find_duplicates(
    files=file_list,
    hashes=existing_hashes,
    database_path='PhotoDB.db',
    batch_size=500,  # Custom batch size
    partial_hash_enabled=True,
    partial_hash_bytes=32768,  # 32KB instead of 16KB
    config=config
)

# Process results
for dup in results['duplicate_files']:
    print(f"Duplicate: {dup}")

for original in results['original_files']:
    print(f"Unique: {original['file_path']}")
```

---

### Photo Filtering Example

```python
from photo_filter import PhotoFilter
from config import Config

config = Config('settings.json')
photo_filter = PhotoFilter(config)

files = ['/icon.png', '/photo.jpg', '/thumbnail.jpg']

for file in files:
    if photo_filter.is_photo(file):
        print(f"✓ Photo: {file}")
    else:
        reason = photo_filter.get_filter_reason(file)
        print(f"✗ Filtered: {file} - {reason}")

# Get statistics
stats = photo_filter.get_statistics()
print(f"\nTotal filtered: {stats['total_filtered']}")
```

---

### Database Direct Access

```python
from DuplicateFileDetection import PhotoDatabase

with PhotoDatabase('PhotoDB.db') as db:
    # Initialize
    db.initialize_database()

    # Get all hashes
    hashes = db.get_all_hashes()
    print(f"Database contains {len(hashes)} photos")

    # Insert new photo
    db.insert_unique_photo(
        file_hash="abc123...",
        partial_hash="def456...",
        partial_hash_bytes=16384,
        file_size=1048576,
        file_path="/path/photo.jpg",
        create_datetime="2024-11-25 14:30:00",
        create_year="2024",
        create_month="11",
        create_day="25"
    )
    # Auto-commits on successful exit
```

---

## Error Handling

All functions use standard Python exception handling:

```python
try:
    results = DuplicateFileDetection.find_duplicates(...)
except FileNotFoundError as e:
    print(f"File not found: {e}")
except PermissionError as e:
    print(f"Permission denied: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Type Hints

Code uses Python type hints for better IDE support:

```python
from typing import List, Dict, Optional, Tuple

def get_file_list(
    sources: List[str],
    recursive: bool = True,
    endings: List[str] = None
) -> List[str]:
    ...
```

---

**See Also:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [CONFIGURATION.md](CONFIGURATION.md) - Settings reference
- [DEVELOPMENT.md](DEVELOPMENT.md) - Developer guide

---

*Last updated: 2026-01-02*
