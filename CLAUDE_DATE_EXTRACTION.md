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

4. **OS Metadata** - File creation/modification time (least reliable)

5. **Year 1000 Fallback** - Indicates complete failure

## Video Date Priority

1. **ffprobe** - `creation_time` tag from format metadata
2. **mutagen** - `©day` tag for MP4/MOV files
3. **QuickTime atoms** - `mvhd` atom creation_time (handles 1904 epoch)
4. **OS Metadata** - File timestamps
5. **Year 1000 Fallback**

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
| `get_creation_date()` | Main entry point - returns `(datetime, date_source, is_reliable)` |
| `_validate_exif_date()` | Validates/parses EXIF date strings |
| `_read_all_exif_dates()` | Reads dates from all IFDs |
| `_select_best_exif_date()` | Implements priority + earliest-date algorithm |
| `_try_iptc_date()` | IPTC date extraction fallback |
| `_try_video_date()` | Video metadata extraction |

All functions located in `DuplicateFileDetection.py`.

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
| `video_metadata` | ffprobe creation_time |
| `video_quicktime` | QuickTime atom |
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
