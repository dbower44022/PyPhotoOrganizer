# Configuration Guide

> Complete reference for all PyPhotoOrganizer settings

**Last Updated:** 2026-01-02

---

## Table of Contents

- [Configuration File](#configuration-file)
- [Required Settings](#required-settings)
- [Optional Settings](#optional-settings)
- [Setting Categories](#setting-categories)
- [Configuration Examples](#configuration-examples)
- [Validation Rules](#validation-rules)
- [Default Values](#default-values)
- [Advanced Configuration](#advanced-configuration)
- [Migration Guide](#migration-guide)

---

## Configuration File

PyPhotoOrganizer uses a JSON configuration file (`settings.json`) located in the project root directory.

### Basic Structure

```json
{
  "source_directory": ["path/to/photos"],
  "destination_directory": "path/to/organized",
  "copy_files": true,
  "move_files": false
}
```

### File Location

- **Default:** `settings.json` in project root
- **Custom:** Pass path to `Config()` constructor (advanced)

### Loading Process

```python
# Application loads and validates on startup
config = Config('settings.json')
# Automatic validation, default application, type checking
```

---

## Required Settings

These settings **must** be provided in `settings.json`:

### `source_directory`

**Type:** `string` or `array of strings`

**Description:** Directory(ies) containing photos to process

**Examples:**
```json
// Single directory
"source_directory": "D:\\Photos\\iPhone Backup"

// Multiple directories
"source_directory": [
  "D:\\Photos\\iPhone Backup",
  "D:\\Photos\\Android Backup",
  "E:\\Old PC Photos"
]
```

**Validation:**
- Will be converted to array if string
- No `..` patterns allowed (security)
- Paths are not required to exist (will be checked at runtime)

---

### `destination_directory`

**Type:** `string`

**Description:** Where organized photos will be copied/moved

**Example:**
```json
"destination_directory": "E:\\Master Photo Archive"
```

**Validation:**
- Must be a string (not array)
- No `..` patterns allowed (security)
- Will be created if doesn't exist

---

## Optional Settings

All optional settings have sensible defaults.

### Directory Settings

#### `include_subdirectories`

**Type:** `boolean`
**Default:** `true`

**Description:** Recursively process subdirectories

**Example:**
```json
"include_subdirectories": true
```

**Impact:**
- `true`: Scans all subdirectories
- `false`: Only scans top-level directory

---

#### `group_by_year`

**Type:** `boolean`
**Default:** `true`

**Description:** Create year folders in destination

**Example:**
```json
"group_by_year": true
```

**Folder Structure:**
```
true:  destination/2024/11/25/photo.jpg
false: destination/2024-11/25/photo.jpg
```

---

#### `group_by_day`

**Type:** `boolean`
**Default:** `true`

**Description:** Create day folders in destination

**Example:**
```json
"group_by_day": true
```

**Folder Structure:**
```
true:  destination/2024/11/25/photo.jpg
false: destination/2024/11/photo.jpg
```

**Combined Examples:**

| group_by_year | group_by_day | Result Path |
|---------------|--------------|-------------|
| true | true | `2024/11/25/photo.jpg` |
| true | false | `2024/11/photo.jpg` |
| false | true | `2024-11/25/photo.jpg` |
| false | false | `2024-11/photo.jpg` |

---

### File Operation Settings

#### `copy_files`

**Type:** `boolean`
**Default:** `true`

**Description:** Copy files to destination (preserves originals)

**Example:**
```json
"copy_files": true,
"move_files": false
```

**Notes:**
- Cannot be `true` if `move_files` is `true`
- At least one of `copy_files` or `move_files` must be `true`

---

#### `move_files`

**Type:** `boolean`
**Default:** `false`

**Description:** Move files to destination (removes from source)

**Example:**
```json
"copy_files": false,
"move_files": true
```

**⚠️ Warning:** Moving files is destructive! Ensure backups exist.

---

### File Type Settings

#### `file_endings`

**Type:** `array of strings`
**Default:** `[".jpg", ".jpeg", ".png", ".heic", ".tif", ".mov", ".mp4"]`

**Description:** File extensions to process

**Example:**
```json
"file_endings": [".jpg", ".jpeg", ".png", ".heic", ".tif", ".mov", ".mp4"]
```

**Notes:**
- Extensions are case-insensitive
- Leading dot (`.`) is auto-added if missing
- Common formats: `.jpg`, `.png`, `.heic`, `.mov`, `.mp4`, `.avi`, `.tif`

---

### Database Settings

#### `database_path`

**Type:** `string`
**Default:** `"PhotoDB.db"`

**Description:** Path to SQLite database file

**Example:**
```json
"database_path": "PhotoDB.db"
```

**Notes:**
- Relative paths are relative to project root
- Database auto-created if doesn't exist
- Can use different databases for different projects

---

#### `batch_size`

**Type:** `integer`
**Default:** `100`

**Description:** Number of files to process before database commit

**Example:**
```json
"batch_size": 100
```

**Tuning Guide:**

| Batch Size | Use Case | Trade-off |
|------------|----------|-----------|
| 50-100 | Default, balanced | Frequent checkpoints |
| 500-1000 | Fast processing, reliable system | Less frequent checkpoints |
| 1-10 | Testing, debugging | Maximum safety, slower |

**Impact:**
- Higher = Faster processing, less frequent progress saves
- Lower = More frequent progress saves, slightly slower
- Crash recovery: Lost work = at most `batch_size` files

---

### Partial Hashing Settings

#### `partial_hash_enabled`

**Type:** `boolean`
**Default:** `true`

**Description:** Enable two-stage hashing optimization

**Example:**
```json
"partial_hash_enabled": true
```

**Impact:**
- `true`: 100x faster for large files
- `false`: Always hash entire file (slower but simpler)

**Recommended:** Leave `true` unless debugging

---

#### `partial_hash_bytes`

**Type:** `integer`
**Default:** `16384` (16KB)

**Description:** Number of bytes to hash in stage 1

**Example:**
```json
"partial_hash_bytes": 16384
```

**Tuning:**
- Smaller (4KB-8KB): Faster but more collisions
- Larger (32KB-64KB): Fewer collisions but slower
- **Recommended:** 16KB (good balance)

---

#### `partial_hash_min_file_size`

**Type:** `integer`
**Default:** `1048576` (1MB)

**Description:** Minimum file size to use partial hashing

**Example:**
```json
"partial_hash_min_file_size": 1048576
```

**Tuning:**
- Photos: 1MB threshold works well
- Only videos: Can increase to 10MB
- **Recommended:** 1MB

---

### Photo Filtering Settings

#### `photo_filter_enabled`

**Type:** `boolean`
**Default:** `true`

**Description:** Enable photo filtering to exclude icons/thumbnails

**Example:**
```json
"photo_filter_enabled": true
```

**Impact:**
- `true`: Excludes non-photos (icons, web graphics)
- `false`: Processes all files matching extensions

---

#### `min_file_size`

**Type:** `integer` (bytes)
**Default:** `51200` (50KB)

**Description:** Minimum file size for valid photos

**Example:**
```json
"min_file_size": 51200
```

**Common Values:**
- 50KB (51200): Default, excludes most icons
- 10KB (10240): More permissive
- 100KB (102400): Strict, high-quality photos only

---

#### `min_width` / `min_height`

**Type:** `integer` (pixels)
**Default:** `800` × `600`

**Description:** Minimum photo dimensions

**Example:**
```json
"min_width": 800,
"min_height": 600
```

**Common Presets:**

| Preset | Width | Height | Use Case |
|--------|-------|--------|----------|
| Permissive | 640 | 480 | Include smaller photos |
| Default | 800 | 600 | Exclude thumbnails |
| HD | 1920 | 1080 | HD photos only |
| 4K | 3840 | 2160 | 4K photos only |

---

#### `max_width` / `max_height`

**Type:** `integer` (pixels)
**Default:** `50000` × `50000`

**Description:** Maximum photo dimensions

**Example:**
```json
"max_width": 50000,
"max_height": 50000
```

**Purpose:** Exclude extremely large graphics (website banners, etc.)

---

#### `exclude_square_smaller_than`

**Type:** `integer` (pixels)
**Default:** `400`

**Description:** Exclude square images smaller than N×N

**Example:**
```json
"exclude_square_smaller_than": 400
```

**Purpose:** Filter out square icons/logos
- Square images < 400×400 are likely icons
- Square images ≥ 400×400 could be photos

---

#### `require_exif`

**Type:** `boolean`
**Default:** `false`

**Description:** Only accept images with EXIF metadata

**Example:**
```json
"require_exif": false
```

**Impact:**
- `true`: Only camera photos (strict)
- `false`: Accept all images (permissive)

**Use Case:** Set to `true` to exclude screenshots, generated images

---

#### `excluded_filename_patterns`

**Type:** `array of strings`
**Default:** `["favicon", "icon", "logo", "thumb", "button", "badge", "sprite"]`

**Description:** Filename patterns to exclude

**Example:**
```json
"excluded_filename_patterns": [
  "favicon",
  "icon",
  "logo",
  "thumb",
  "thumbnail",
  "button",
  "badge",
  "sprite",
  "screenshot"
]
```

**Notes:**
- Case-insensitive matching
- Matches anywhere in filename
- Example: `company_logo.png` → excluded (contains "logo")

---

#### `move_filtered_files`

**Type:** `boolean`
**Default:** `false`

**Description:** Move filtered files to separate folder

**Example:**
```json
"move_filtered_files": false
```

**Impact:**
- `true`: Moves filtered files to `filtered_files_folder`
- `false`: Leaves filtered files in place

---

#### `filtered_files_folder`

**Type:** `string`
**Default:** `"filtered_non_photos"`

**Description:** Where to move filtered files (if enabled)

**Example:**
```json
"filtered_files_folder": "filtered_non_photos"
```

---

## Configuration Examples

### Minimal Configuration

```json
{
  "source_directory": ["D:\\Photos"],
  "destination_directory": "E:\\Organized"
}
```

Uses all default values.

---

### Conservative Configuration

**Use Case:** First-time user, want maximum safety

```json
{
  "source_directory": ["D:\\Test Photos"],
  "destination_directory": "E:\\Test Output",

  "copy_files": true,
  "move_files": false,

  "batch_size": 50,
  "photo_filter_enabled": false
}
```

**Features:**
- Small batch size for frequent checkpoints
- Copy mode (preserves originals)
- No filtering (processes everything)

---

### Performance Configuration

**Use Case:** Large collection, reliable system

```json
{
  "source_directory": [
    "D:\\iPhone Backup",
    "D:\\Android Backup",
    "E:\\Old PC"
  ],
  "destination_directory": "F:\\Master Archive",

  "copy_files": true,
  "move_files": false,

  "batch_size": 500,

  "partial_hash_enabled": true,
  "partial_hash_bytes": 16384,
  "partial_hash_min_file_size": 1048576,

  "photo_filter_enabled": true,
  "min_file_size": 51200
}
```

**Features:**
- Large batch size for performance
- All optimizations enabled
- Photo filtering enabled

---

### Strict Quality Configuration

**Use Case:** Only high-quality photos

```json
{
  "source_directory": ["D:\\Camera DCIM"],
  "destination_directory": "E:\\Quality Photos",

  "photo_filter_enabled": true,
  "min_file_size": 102400,
  "min_width": 1920,
  "min_height": 1080,
  "require_exif": true,

  "file_endings": [".jpg", ".jpeg", ".png", ".heic"]
}
```

**Features:**
- Minimum 100KB file size
- HD resolution minimum (1920×1080)
- Requires EXIF (camera photos only)
- No videos

---

### Move Mode Configuration

**Use Case:** Consolidating from multiple locations

```json
{
  "source_directory": [
    "D:\\Old Laptop Backup",
    "E:\\External Drive 1",
    "F:\\External Drive 2"
  ],
  "destination_directory": "G:\\Master Archive",

  "copy_files": false,
  "move_files": true,

  "batch_size": 100
}
```

**⚠️ Warning:** This will remove files from source locations!

---

## Validation Rules

The application validates all settings on startup.

### Path Validation

```python
✅ Valid:
  "D:\\Photos"
  "/home/user/photos"
  "C:\\Users\\Name\\Pictures"

❌ Invalid:
  "../../etc/passwd"  # Directory traversal
  "../../../system"   # Parent references
```

### Copy/Move Validation

```python
✅ Valid:
  copy_files=true, move_files=false
  copy_files=false, move_files=true

❌ Invalid:
  copy_files=true, move_files=true   # Both true
  copy_files=false, move_files=false # Both false
```

### Type Validation

```python
✅ Valid:
  "batch_size": 100              # Integer
  "copy_files": true             # Boolean
  "source_directory": ["path"]   # Array

❌ Invalid:
  "batch_size": "100"            # String (should be int)
  "copy_files": "yes"            # String (should be bool)
  "source_directory": "path"     # String (auto-converted to array)
```

---

## Default Values

Complete list of defaults (from `constants.py`):

```python
DEFAULT_DATABASE_NAME = 'PhotoDB.db'
DEFAULT_BATCH_SIZE = 100
DEFAULT_FILE_ENDINGS = ['.jpg', '.jpeg', '.png', '.heic', '.tif', '.mov', '.mp4']

PARTIAL_HASH_BYTES = 16384  # 16KB
PARTIAL_HASH_MIN_FILE_SIZE = 1048576  # 1MB

MIN_PHOTO_FILE_SIZE = 51200  # 50KB
MIN_PHOTO_WIDTH = 800
MIN_PHOTO_HEIGHT = 600
MAX_PHOTO_WIDTH = 50000
MAX_PHOTO_HEIGHT = 50000
MIN_SQUARE_SIZE = 400
```

---

## Advanced Configuration

### Multiple Configuration Files

```python
# Development
config_dev = Config('settings.dev.json')

# Production
config_prod = Config('settings.prod.json')

# Testing
config_test = Config('settings.test.json')
```

### Runtime Configuration Changes

```python
config = Config('settings.json')

# Modify in-memory
config.set('batch_size', 200)

# Save changes (optional)
config.save()
```

### Accessing Configuration

```python
# Property access
batch_size = config.batch_size
source_dirs = config.source_directory

# Dictionary access
batch_size = config['batch_size']
source_dirs = config.get('source_directory')

# With defaults
custom = config.get('custom_setting', default='fallback')
```

---

## Migration Guide

### Upgrading from Version 1.x

**Changes in Version 2.0:**

1. **New Settings:**
   - `photo_filter_enabled`
   - `min_file_size`, `min_width`, `min_height`
   - `exclude_square_smaller_than`
   - `partial_hash_enabled`, `partial_hash_bytes`

2. **Removed Settings:**
   - None (fully backward compatible)

3. **Changed Defaults:**
   - `batch_size`: 100 (unchanged)
   - `copy_files`: true (unchanged)

**Migration Steps:**

```json
// Old settings.json (v1.x)
{
  "source_directory": "D:\\Photos",
  "destination_directory": "E:\\Sorted"
}

// New settings.json (v2.0) - Add new features
{
  "source_directory": ["D:\\Photos"],  // Now array
  "destination_directory": "E:\\Sorted",

  // New: Photo filtering
  "photo_filter_enabled": true,
  "min_file_size": 51200
}
```

---

## Troubleshooting

### "Configuration file not found"

**Problem:** `settings.json` doesn't exist

**Solution:**
```bash
# Create from template
cp settings.example.json settings.json
# Edit with your paths
```

---

### "Missing required settings"

**Problem:** Missing `source_directory` or `destination_directory`

**Solution:**
```json
{
  "source_directory": ["path/here"],
  "destination_directory": "path/here"
}
```

---

### "Invalid path: contains '..'"

**Problem:** Security validation detected path traversal

**Solution:** Use absolute paths:
```json
// ❌ Wrong
"source_directory": "../../../Photos"

// ✅ Correct
"source_directory": "D:\\Photos"
```

---

### "copy_files and move_files cannot both be True"

**Problem:** Conflicting operation modes

**Solution:** Choose one:
```json
// Copy mode
{"copy_files": true, "move_files": false}

// OR Move mode
{"copy_files": false, "move_files": true}
```

---

## Best Practices

1. **Start with defaults** - Only override what you need
2. **Use copy mode first** - Test before using move mode
3. **Test with small dataset** - Use subset of photos initially
4. **Backup database** - Copy `PhotoDB.db` before major runs
5. **Document changes** - Comment non-standard settings
6. **Version control** - Track `settings.json` in git (without sensitive paths)

---

## Quick Reference

```json
{
  // REQUIRED
  "source_directory": ["path"],
  "destination_directory": "path",

  // OPERATION (pick one)
  "copy_files": true | false,
  "move_files": true | false,

  // ORGANIZATION
  "group_by_year": true | false,
  "group_by_day": true | false,

  // PERFORMANCE
  "batch_size": 50-1000,
  "partial_hash_enabled": true | false,

  // FILTERING
  "photo_filter_enabled": true | false,
  "min_file_size": bytes,
  "min_width": pixels,
  "min_height": pixels
}
```

---

**See Also:**
- [README.md](README.md) - Project overview
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical details
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues

---

*Last updated: 2026-01-02*
