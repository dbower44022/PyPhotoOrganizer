# CLAUDE_DATE_EXTRACTION.md

Date extraction and validation system for PyPhotoOrganizer.

**See also:** [CLAUDE.md](CLAUDE.md) for core project guidelines.

## Overview

The system reads all available date metadata and uses an intelligent algorithm to select the most accurate original creation date.

## EXIF IFD Access (PIL 10.x)

**Important:** In PIL 10.x, `getexif()` only returns the base IFD. DateTimeOriginal and other EXIF-specific tags are in sub-IFDs:

```python
from PIL.ExifTags import IFD

exif = img.getexif()              # Base IFD (contains DateTime)
exif_ifd = exif.get_ifd(IFD.Exif) # EXIF IFD (contains DateTimeOriginal)
gps_ifd = exif.get_ifd(IFD.GPSInfo)  # GPS IFD (contains GPSDateStamp)
```

## Date Fields Read

| IFD | Tag ID | Field Name | Description |
|-----|--------|------------|-------------|
| Base (IFD0) | 306 | DateTime | File modification time |
| EXIF | 36867 | DateTimeOriginal | When photo was taken (best) |
| EXIF | 36868 | DateTimeDigitized | When digitized |
| EXIF | 50971 | PreviewDateTime | When preview generated |
| GPS | 29 | GPSDateStamp | GPS date (UTC, YYYY:MM:DD) |
| GPS | 7 | GPSTimeStamp | GPS time (UTC, tuple H,M,S) |

## Image Date Priority Algorithm

1. **DateTimeOriginal** - If present and valid, always use (most authoritative)

2. **Earliest Valid Date** - If no DateTimeOriginal, use earliest among:
   - DateTimeDigitized
   - GPSDateTime (combined GPSDateStamp + GPSTimeStamp)
   - DateTime
   - PreviewDateTime

   *Rationale:* Files can only be modified AFTER creation, so earliest = most likely original.

3. **IPTC Date Created** - Fallback for images without EXIF (tag 2:55)

4. **XMP CreateDate** - Fallback for XMP-only files

5. **Filename Date** - Extract from filename patterns (e.g., `IMG_20230415_123456.jpg`)

6. **Path Date** - Extract from folder structure (e.g., `/Photos/2023/04/15/`)

7. **OS Metadata** - File creation/modification time (least reliable)

8. **Year 1000 Fallback** - Indicates complete failure

## Video Date Priority

1. **ffprobe** - `creation_time` tag from format metadata
2. **mutagen** - `©day` tag for MP4/MOV files
3. **QuickTime atoms** - `mvhd` atom creation_time (handles 1904 epoch)
4. **Filename Date** - Extract from filename patterns (e.g., `VID_20230415_123456.mp4`)
5. **Path Date** - Extract from folder structure
6. **OS Metadata** - File timestamps
7. **Year 1000 Fallback**

## Filename Date Patterns

The system recognizes these filename patterns (in priority order):

| Pattern | Example | Captures |
|---------|---------|----------|
| `IMG_YYYYMMDD_HHMMSS` | `IMG_20230415_123456.jpg` | Full datetime |
| `VID_YYYYMMDD_HHMMSS` | `VID_20230415_123456.mp4` | Full datetime |
| `PXL_YYYYMMDD_HHMMSS` | `PXL_20230415_123456.jpg` | Full datetime (Pixel phones) |
| `YYYYMMDD_HHMMSS` | `20230415_123456.jpg` | Full datetime |
| `YYYYMMDD-HHMMSS` | `20230415-123456.jpg` | Full datetime |
| `YYYY-MM-DD_HH-MM-SS` | `2023-04-15_12-34-56.jpg` | Full datetime |
| `YYYY-MM-DD HH.MM.SS` | `2023-04-15 at 12.34.56.jpg` | Full datetime (iOS) |
| `Screenshot_YYYYMMDD-HHMMSS` | `Screenshot_20230415-123456.png` | Full datetime |
| `IMG-YYYYMMDD-WA` | `IMG-20230415-WA0001.jpg` | Date only (WhatsApp) |
| `YYYY-MM-DD` | `2023-04-15.jpg` | Date only |
| `YYYYMMDD` | `20230415.jpg` | Date only |

Functions: `extract_filename_date()`, `_get_filename_patterns()` in `date_extraction.py`.

## Path Date Patterns

The system recognizes these folder structures:

| Pattern | Example | Precision |
|---------|---------|-----------|
| `/YYYY/MM/DD/` | `/Photos/2023/04/15/photo.jpg` | Full date |
| `/YYYY-MM-DD/` | `/Archive/2023-04-15/photo.jpg` | Full date |
| `/YYYY/MM/` | `/Photos/2023/04/photo.jpg` | Year + month (day=1) |
| `/YYYY-MM/` | `/Archive/2023-04/photo.jpg` | Year + month (day=1) |
| `/YYYY/` | `/Photos/2023/photo.jpg` | Year only (month=1, day=1) |

Path dates are less reliable than filename dates because:
- Year-only paths provide no month/day information
- Paths may represent organization date, not capture date

Functions: `extract_path_date()`, `extract_filename_or_path_date()` in `date_extraction.py`.

## Date Validation

Dates validated before use:
- Must be parseable (format: `YYYY:MM:DD HH:MM:SS`)
- Year must be 1990 to current+1 (digital camera era)
- Not Unix epoch (1970-01-01 00:00:00)
- Not null date (0000:00:00 00:00:00)

## Unreliable Date Flagging

Dates flagged as unreliable when:
- No EXIF/video metadata found (only OS date)
- Year equals 1000 (fallback date)
- Year < 1990 (before consumer digital cameras)
- Year > current year + 1 (future date)
- Unix epoch date (1970-01-01)
- File is in user-specified unreliable path

## Key Functions

| Function | Purpose |
|----------|---------|
| `get_creation_date()` | Main entry point - returns `(year, month, day, date_source, is_reliable)` |
| `validate_exif_date()` | Validates/parses EXIF date strings |
| `extract_exif_dates()` | Reads dates from all IFDs |
| `select_best_exif_date()` | Implements priority + earliest-date algorithm |
| `extract_iptc_date()` | IPTC date extraction |
| `extract_xmp_date()` | XMP date extraction |
| `extract_video_date()` | Video metadata extraction (ffprobe, mutagen, QuickTime) |
| `extract_filename_date()` | Extract date from filename patterns |
| `extract_path_date()` | Extract date from directory path structure |
| `extract_filename_or_path_date()` | Try filename first, then path |
| `get_os_timestamp()` | OS file creation/modification time |

All functions located in `date_extraction.py`.

## Date Source Values

Stored in `UniquePhotos.date_source`:

| Value | Meaning |
|-------|---------|
| `exif` | DateTimeOriginal |
| `exif_digitized` | DateTimeDigitized |
| `exif_gps` | GPS timestamp |
| `exif_datetime` | DateTime (modification) |
| `exif_preview` | PreviewDateTime |
| `iptc` | IPTC Date Created |
| `xmp` | XMP CreateDate |
| `video_metadata` | ffprobe creation_time |
| `video_quicktime` | QuickTime atom |
| `filename` | Date from filename pattern |
| `path_ymd` | Full date from directory path |
| `path_ym` | Year/month from directory path |
| `path_y` | Year only from directory path |
| `os_metadata` | OS file timestamps |
| `fallback` | Year 1000 default |

## Metadata Quality Score Integration

Date source feeds into metadata quality scoring (Schema v7):

```python
METADATA_SOURCE_SCORES = {
    'exif': 80,
    'exif_digitized': 70,
    'exif_gps': 65,
    'video_metadata': 60,
    'video_quicktime': 55,
    'exif_datetime': 50,
    'exif_preview': 45,
    'iptc': 40,
    'xmp': 35,
    'filename': 30,        # Date from filename
    'path_ymd': 28,        # Full date from path
    'path_ym': 25,         # Year/month from path
    'path_y': 22,          # Year only from path
    'os_metadata': 20,
    'fallback': 0
}

def calculate_metadata_quality_score(date_source, is_reliable):
    base = METADATA_SOURCE_SCORES.get(date_source, 0)
    bonus = 20 if is_reliable else 0
    return base + bonus  # 0-100
```

## Common Issues

### "Wrong date used"
Check priority: DateTimeOriginal trumps all. If missing, earliest date wins.

### "Date from wrong timezone"
GPS dates are UTC. EXIF dates are local time (no timezone info in standard EXIF).

### "Very old date (1904)"
QuickTime epoch issue - should be handled by `_try_video_date()`.

### "Future date"
Flagged as unreliable. Check camera date settings.
