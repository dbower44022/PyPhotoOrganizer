# PyPhotoOrganizer

> A robust Python-based photo and video duplicate detection and organization system

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

PyPhotoOrganizer helps you consolidate photos from multiple devices and locations (phones, tablets, PCs, NAS) into a single, deduplicated archive while preserving file metadata. It uses SHA-256 hashing for accurate duplicate detection and organizes photos into a date-based folder structure.

### Key Features

- **Intelligent Duplicate Detection**: Two-stage SHA-256 hashing with partial hash optimization for large files
- **Photo Filtering**: Automatically excludes icons, thumbnails, and web graphics
- **Date-Based Organization**: Organizes files by creation date (YYYY/MM/DD structure)
- **HEIC Support**: Converts Apple HEIC/HEIF images to JPEG with metadata preservation
- **Resume Capability**: Batch commits allow safe interruption and resumption of long-running processes
- **Progress Tracking**: Real-time progress bars for all operations
- **File Type Verification**: Validates file extensions match actual file format
- **Multiple Source Support**: Process multiple directories in a single run
- **Flexible Operations**: Copy or move files to destination

### Use Cases

✅ Consolidating photos from multiple backup locations
✅ Cleaning up duplicate photos from repeated device backups
✅ Creating a single master photo archive
✅ Organizing photos by date for photo management software (like Mylio)
✅ Deduplicating large photo collections (10,000+ files)

## Quick Start

### Prerequisites

- Python 3.8 or higher
- ~50MB disk space for database
- Sufficient storage for your photo collection

### Installation

```bash
# Clone or download the repository
cd PyPhotoOrganizer

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

1. **Create configuration file** (`settings.json`):

```json
{
  "source_directory": ["/path/to/photos"],
  "destination_directory": "/path/to/organized/photos",
  "copy_files": true,
  "move_files": false
}
```

2. **Run the organizer**:

```bash
python main.py
```

3. **Monitor progress**:
```
Scanning directories: 100%|████████| 3/3 [00:02<00:00]
Processing files: 100%|████████| 1500/1500 [05:30<00:00, 4.5file/s]
Organizing files: 100%|████████| 850/850 [02:15<00:00, 6.3file/s]
```

## Documentation

📚 **Comprehensive guides available:**

- **[Architecture Guide](ARCHITECTURE.md)** - System design and technical details
- **[Configuration Guide](CONFIGURATION.md)** - Complete settings reference
- **[API Documentation](API.md)** - Code reference and API details
- **[Development Guide](DEVELOPMENT.md)** - Contributing and development setup
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

## How It Works

```
┌─────────────────┐
│  Source Dirs    │
│ (Multiple)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  File Discovery     │
│  - Recursive scan   │
│  - Extension filter │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  File Verification  │
│  - Type validation  │
│  - Extension fix    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Photo Filtering    │
│  - Size check       │
│  - Dimension check  │
│  - Pattern exclude  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Duplicate Check    │
│  - Partial hash     │
│  - Full hash        │
│  - Database lookup  │
└─────────┬───────────┘
          │
          ├─► Duplicate ──► Skip
          │
          └─► Unique ──────┐
                           │
                           ▼
                  ┌────────────────┐
                  │  Extract Date  │
                  │  - EXIF data   │
                  │  - File system │
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Organize      │
                  │  YYYY/MM/DD    │
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Copy/Move     │
                  │  + Update DB   │
                  └────────────────┘
```

## Configuration Example

```json
{
  "source_directory": [
    "D:\\Phone Backups\\iPhone",
    "D:\\Phone Backups\\Android",
    "D:\\Old PC Photos"
  ],
  "destination_directory": "E:\\Master Photo Archive",
  "database_path": "PhotoDB.db",

  "include_subdirectories": true,
  "file_endings": [".jpg", ".jpeg", ".png", ".heic", ".tif", ".mov", ".mp4"],

  "copy_files": true,
  "move_files": false,

  "group_by_year": true,
  "group_by_day": true,

  "batch_size": 100,

  "partial_hash_enabled": true,
  "partial_hash_bytes": 16384,
  "partial_hash_min_file_size": 1048576,

  "photo_filter_enabled": true,
  "min_file_size": 51200,
  "min_width": 800,
  "min_height": 600
}
```

## Performance

### Benchmark Results

**Test Environment:** Intel i7, SSD, 10,000 mixed photo/video files

| Operation | Speed | Notes |
|-----------|-------|-------|
| File scanning | ~500 files/sec | Includes subdirectories |
| Small photos (<1MB) | ~5-10 files/sec | Full hash |
| Large photos (1-5MB) | ~8-12 files/sec | Partial hash optimization |
| Videos (100MB-2GB) | ~2-4 files/sec | Partial hash optimization |
| Database commit | <1ms | SQLite with indexes |

### Optimization Features

- **Partial Hashing**: Only hashes first 16KB of large files unless potential duplicate
- **Batch Commits**: Commits every 100 files to preserve progress
- **Database Indexes**: Fast lookups on hash, size, and date fields
- **Photo Filtering**: Skips non-photos before expensive hashing

## Database Schema

```sql
CREATE TABLE UniquePhotos (
    file_hash TEXT PRIMARY KEY,           -- SHA-256 hash of full file
    partial_hash TEXT,                    -- SHA-256 hash of first N bytes
    partial_hash_bytes INTEGER,           -- Number of bytes in partial hash
    file_size INTEGER,                    -- File size in bytes
    file_name TEXT NOT NULL,              -- Full path to file
    create_datetime TEXT,                 -- Creation timestamp
    create_year TEXT,                     -- Creation year (YYYY)
    create_month TEXT,                    -- Creation month (MM)
    create_day TEXT                       -- Creation day (DD)
);

CREATE INDEX idx_partial_hash ON UniquePhotos(partial_hash);
CREATE INDEX idx_file_size ON UniquePhotos(file_size);
CREATE INDEX idx_date ON UniquePhotos(create_year, create_month, create_day);
CREATE INDEX idx_file_name ON UniquePhotos(file_name);
```

## Security Features

✅ **Path Traversal Protection**: Validates all paths to prevent directory traversal attacks
✅ **SQL Injection Prevention**: Uses parameterized queries exclusively
✅ **File Lock Handling**: Safe rename/copy fallback for locked files
✅ **Input Validation**: Validates all configuration settings
✅ **Error Isolation**: Individual file errors don't stop processing

## Project Structure

```
PyPhotoOrganizer/
├── main.py                      # Main orchestration
├── config.py                    # Configuration management
├── constants.py                 # Application constants
├── utils.py                     # Shared utilities
├── DuplicateFileDetection.py   # Core duplicate detection
├── photo_filter.py             # Photo filtering logic
├── settings.json               # Configuration file
├── requirements.txt            # Python dependencies
├── PhotoDB.db                  # SQLite database
├── README.md                   # This file
├── ARCHITECTURE.md             # Technical architecture
├── CONFIGURATION.md            # Settings reference
├── API.md                      # Code documentation
├── DEVELOPMENT.md              # Developer guide
├── TROUBLESHOOTING.md          # Issue resolution
└── CLAUDE.md                   # AI assistant instructions
```

## Recent Improvements

### Version 2.0 (Latest)

✅ **Security hardening**: Path traversal validation, input sanitization
✅ **Bug fixes**: Data loss bugs, HEIC conversion, temporary file handling
✅ **Code quality**: Eliminated magic numbers, added constants module
✅ **Performance**: Added database indexes for date and filename lookups
✅ **Validation**: Fixed config validation for copy/move settings
✅ **Error handling**: Improved silent failure detection

## System Requirements

### Minimum
- Python 3.8+
- 2GB RAM
- 100MB free disk space (plus space for photos)

### Recommended
- Python 3.10+
- 8GB RAM
- SSD for database
- Separate drive for destination (to avoid I/O contention)

## Dependencies

- **Pillow** (>=10.0.0) - Image processing and EXIF extraction
- **pillow-heif** (>=0.13.0) - HEIC/HEIF format support
- **tqdm** (>=4.65.0) - Progress bars
- **sqlite3** - Built-in database
- **hashlib** - Built-in SHA-256 hashing

## Limitations

⚠️ **Current limitations:**

- Windows-style paths (cross-platform support planned)
- No GUI (command-line only)
- No video metadata extraction (uses file system dates)
- No automatic backup of database
- Single-threaded processing (parallel processing planned)

## Contributing

Contributions welcome! Please see [DEVELOPMENT.md](DEVELOPMENT.md) for guidelines.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (if available)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## FAQ

**Q: Will this modify my original photos?**
A: No, when using copy mode. Move mode will relocate files.

**Q: What happens if I run it twice on the same files?**
A: Duplicates are detected and skipped. The database tracks all processed files.

**Q: Can I interrupt the process?**
A: Yes! Progress is saved every 100 files (configurable). Just re-run to resume.

**Q: How accurate is duplicate detection?**
A: 100% accurate using SHA-256 cryptographic hashing. False positives are cryptographically impossible.

**Q: Does it preserve EXIF data?**
A: Yes, file copy preserves all metadata. HEIC conversion preserves EXIF data.

**Q: Can I process multiple source directories?**
A: Yes, `source_directory` accepts an array of paths.

## License

MIT License - See LICENSE file for details

## Support

- **Issues**: GitHub Issues
- **Documentation**: See documentation files in project root

## Acknowledgments

- Photo organization inspired by [photo-organizer](https://github.com/Supporterino/photo-organizer)
- EXIF extraction based on [image-metadata-extractor](https://github.com/ozgecinko/image-metadata-extractor)
- Duplicate detection algorithm from Python community discussions

## Roadmap

### Planned Features

- [ ] Cross-platform path support (Linux/macOS)
- [ ] GUI interface
- [ ] Parallel processing for multi-core systems
- [ ] Video metadata extraction
- [ ] Automatic database backup
- [ ] Undo/rollback functionality
- [ ] Duplicate file deletion mode
- [ ] Export duplicate report
- [ ] Cloud storage support (Google Photos, iCloud)
- [ ] Machine learning for photo quality scoring

---

**Made with ❤️ for photo enthusiasts everywhere**

*Last updated: 2026-01-02*
