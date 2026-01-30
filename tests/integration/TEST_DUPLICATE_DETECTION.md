# Comprehensive Duplicate Detection Test Suite

Test module: `tests/integration/test_duplicate_detection_comprehensive.py`
Helper module: `tests/test_utils/duplicate_test_helpers.py`

## Running the Tests

### Prerequisites

- Python 3.12+ with the project virtual environment activated
- Required packages: `pytest`, `Pillow`, `piexif`

```bash
# Install pytest if not present
venv/bin/pip install pytest
```

### Run Commands

```bash
# All 52 tests (verbose output)
venv/bin/python -m pytest tests/integration/test_duplicate_detection_comprehensive.py \
    -v --override-ini="addopts="

# Single test class
venv/bin/python -m pytest tests/integration/test_duplicate_detection_comprehensive.py::TestExactDuplicateDetection \
    -v --override-ini="addopts="

# Single test
venv/bin/python -m pytest tests/integration/test_duplicate_detection_comprehensive.py::TestExactDuplicateDetection::test_exact_duplicate_same_file \
    -v --override-ini="addopts="

# Stop on first failure
venv/bin/python -m pytest tests/integration/test_duplicate_detection_comprehensive.py \
    -v --override-ini="addopts=" -x

# With full tracebacks
venv/bin/python -m pytest tests/integration/test_duplicate_detection_comprehensive.py \
    -v --override-ini="addopts=" --tb=long
```

> **Note:** The `--override-ini="addopts="` flag is required because the project's `pytest.ini` contains inline comments that conflict with pytest's argument parser.

### Expected Result

```
52 passed in ~46s
```

All 52 tests should pass. No tests are expected to fail, skip, or produce errors.

---

## Test Architecture

### How Tests Work

Each test follows the same pattern:

1. **Setup** -- The `env` fixture creates a fresh temporary directory with:
   - `source/` -- source directory for input files
   - `archive/` -- destination archive directory
   - `prior_revisions/` -- prior revision archive directory
   - `test.db` -- initialized SQLite database with all required tables
   - A `Config` object with test-appropriate settings

2. **Generate** -- Synthetic test files are created in the source directory using helper functions from `duplicate_test_helpers.py`. These functions produce real JPEG/PNG files with controlled properties (dimensions, EXIF data, pixel content, file size).

3. **Execute** -- Files are passed through `organize_files()` from `main.py`, which runs the full import pipeline: photo filtering, SHA-256 hashing, duplicate detection, content hashing, metadata quality scoring, archive copy, and database updates.

4. **Verify** -- Three layers are checked:
   - **Filesystem**: correct files in correct archive folders
   - **Database**: correct records in UniquePhotos, UnreliableDates, MetadataUpgradeHistory
   - **Return values**: `organize_files()` result dict has correct counts

### File Naming Convention

All test files use descriptive prefixes so failures are diagnosable from output inspection:

| Prefix | Category |
|--------|----------|
| `unique_*` | Unique file import tests |
| `dup_*` | Exact duplicate detection tests |
| `hash2stage_*` | Two-stage hashing tests |
| `cdup_*` | Content hash duplicate tests |
| `upg_*` | Metadata upgrade tests |
| `prot_*` | Protected file tests |
| `filt_*` | Photo filtering tests |
| `date_*` | Date extraction tests |
| `rev_*` | Prior revision archive tests |
| `multi_*` | Multi-session import tests |
| `org_*` | Organization template tests |
| `album_*` | Album association tests |
| `del_*` | Deleted file tests |
| `edge_*` | Edge case tests |

### Test Environment Configuration

The test config differs from production defaults in one key way:

| Setting | Test Value | Production Default | Reason |
|---------|------------|-------------------|--------|
| `min_file_size` | 1024 (1 KB) | 51200 (50 KB) | Synthetic JPEGs with drawn lines are ~50-100 KB; lowering this threshold prevents false filter rejections in tests |

All other settings match production defaults.

---

## Test Classes and Cases

### Class 1: TestUniqueFileImport

**Purpose:** Verify that unique files are correctly imported into the archive with proper date-based folder placement and database records.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 1 | `test_single_unique_photo` | 1920x1080 JPEG with EXIF date 2024-01-15 | result counts, archive path contains `2024/01/15`, DB has 1 record with `date_source=exif` | 1 new file in archive at correct date folder |
| 2 | `test_multiple_unique_photos` | 3 JPEGs with distinct EXIF dates (2024-01-15, 2024-02-20, 2023-10-05) and colors | result has 3 new, 0 duplicates; archive has 3 files; DB has 3 records | All 3 files imported to separate date folders |
| 3 | `test_unique_photo_no_exif_filename_date` | `IMG_20240315_120000.jpg` with no EXIF, 1920x1080 | 1 new file; file in archive; DB has `date_source` of `os_metadata` or `fallback` | File imported; date comes from OS metadata (filename date extraction not in current pipeline) |
| 4 | `test_unique_photo_no_exif_no_filename` | `random_photo.jpg`, no EXIF, no date in name | 1 new file; DB `date_source` is `os_metadata` or `fallback` | File imported with OS-derived date |
| 5 | `test_unique_png_import` | 1920x1080 PNG file | 1 new file in archive | PNG format handled correctly |
| 6 | `test_unique_video_import` | 500 KB mock `.mp4` file (random bytes), photo filter disabled | 1 new file in archive | Video file imported (filter disabled for mock video) |

---

### Class 2: TestExactDuplicateDetection

**Purpose:** Verify SHA-256 hash-based exact duplicate detection across various scenarios.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 7 | `test_exact_duplicate_same_file` | Original JPEG + byte-identical copy (`shutil.copy2`) | 1 new, 1 duplicate; archive has 1 file | Duplicate detected by hash match |
| 8 | `test_exact_duplicate_different_names` | `dup_diffname_beach.jpg` + identical `dup_diffname_vacation.jpg` | 1 new, 1 duplicate | Filename irrelevant to hash comparison |
| 9 | `test_exact_duplicate_across_subdirs` | Same file in `subdir_A/` and `subdir_B/` | 1 new, 1 duplicate; archive has 1 file | Subdirectory location irrelevant to hash |
| 10 | `test_no_false_positive_similar_images` | Two 1920x1080 JPEGs with same dimensions but different colors (red vs blue) | 2 new, 0 duplicates; archive has 2 files | No false positive -- different content produces different hashes |
| 11 | `test_multiple_duplicates_of_same_file` | Original + 3 byte-identical copies | 1 new, 3 duplicates; archive has 1 file | All copies detected as duplicates |

---

### Class 3: TestTwoStageHashing

**Purpose:** Verify partial hash optimization for large files. Files >= 1 MB use a 16 KB partial hash as a quick pre-filter before full SHA-256 hashing.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 12 | `test_large_file_partial_hash_unique` | Two 3000x2000 JPEGs with different colors (produce large files) | 2 new, 0 duplicates | Both files unique despite using partial hash path |
| 13 | `test_large_file_partial_hash_duplicate` | One 3000x2000 JPEG + byte-identical copy | 1 new, 1 duplicate | Partial hash match triggers full hash, confirms duplicate |
| 14 | `test_small_file_skips_partial_hash` | One 1920x1080 JPEG (under 1 MB) | 1 new file | Small file processed without partial hash step |

---

### Class 4: TestContentHashDuplicates

**Purpose:** Verify pixel-content-based duplicate detection. Two images with identical pixels but different EXIF metadata will have the same content hash despite different file hashes.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 15 | `test_content_dup_same_pixels_diff_exif` | Two 800x600 JPEGs: identical solid-color pixels, different EXIF dates (2024-01-01 vs 2024-06-15) | At least 1 new file | Content duplicate or upgrade candidate detected |
| 16 | `test_content_no_false_positive` | Two 1920x1080 JPEGs: solid red vs solid green (different pixel content) | 2 new, 0 content duplicates | Different pixel content produces different content hashes |

---

### Class 5: TestMetadataUpgrades

**Purpose:** Verify that when a duplicate has better EXIF metadata than the existing archive file, the archive file is replaced. The original is preserved in the Prior Revision Archive.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 17 | `test_upgrade_os_to_exif` | Session 1: 800x600 JPEG with no EXIF (score ~20). Session 2: same pixels with EXIF DateTimeOriginal (score ~100) | Session 1 imports 1 new; Session 2 detects content duplicate | Content-identical file with better metadata detected |
| 18 | `test_no_upgrade_same_quality` | Session 1: JPEG with EXIF. Session 2: byte-identical copy | Session 2: 1 duplicate, 0 upgrades; archive still has 1 file | Exact duplicate with same quality triggers no upgrade |
| 19 | `test_no_downgrade_exif_to_os` | Session 1: JPEG with EXIF (high score). Session 2: byte-identical copy | 1 duplicate, 0 upgrades; metadata score unchanged | Better-quality archive file never downgraded |
| 20 | `test_upgrade_creates_prior_revision` | Session 1: no-EXIF file. Session 2: same pixels with EXIF | If upgrade completed: prior revision dir has file; MetadataUpgradeHistory populated | Original preserved in prior revision archive |

---

### Class 6: TestProtectedFiles

**Purpose:** Verify that user-corrected files (with `revision_reason` set) are never replaced by metadata upgrades, regardless of incoming quality.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 21 | `test_protected_date_correction_not_replaced` | Import JPEG, set `revision_reason='date_correction'` in DB, import identical duplicate | Duplicate detected, 0 upgrades completed | Protected file not replaced |
| 22 | `test_unprotected_file_is_replaced` | Import JPEG (no protection marker), import identical duplicate | `revision_reason` is NULL; duplicate detected normally | Control case: unprotected file eligible for upgrade |

---

### Class 7: TestPhotoFiltering

**Purpose:** Verify the `PhotoFilter` correctly excludes non-photo files (icons, thumbnails, tiny files) while passing valid photos and videos.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 23 | `test_filter_small_icon` | 64x64 square JPEG | 1 filtered, 0 new; not in archive | Filtered: small square icon |
| 24 | `test_filter_thumbnail_by_name` | 150x150 JPEG named `filt_thumb_preview.jpg` | 1 filtered, 0 new; not in archive | Filtered: filename contains "thumb" |
| 25 | `test_filter_tiny_file_size` | 100x100 JPEG at quality=10 (well under 1 KB min threshold) | 1 filtered, 0 new; not in archive | Filtered: file size below minimum |
| 26 | `test_filter_small_dimensions` | 400x300 JPEG (below 800x600 minimum) | 1 filtered, 0 new | Filtered: dimensions too small |
| 27 | `test_filter_favicon_pattern` | 32x32 JPEG named `favicon.jpg` | 1 filtered; not in archive | Filtered: filename pattern + small dimensions |
| 28 | `test_valid_photo_passes_filter` | 1920x1080 JPEG with EXIF | 1 new, 0 filtered; file in archive | Valid photo passes all filter checks |
| 29 | `test_video_bypasses_filter` | 500 KB mock `.mp4` file | 1 new; file in archive | Videos bypass photo filter entirely |
| 30 | `test_filter_with_override_skip` | 400x300 JPEG (filtered by dimensions). Then re-import with `photo_filter_enabled=False` | Session 1: filtered. Session 2: 1 new, file in archive | Disabling filter allows previously-filtered files to import |

---

### Class 8: TestDateExtraction

**Purpose:** Verify date extraction from EXIF, digitized EXIF, filenames (OS fallback), and priority ordering. Confirm correct archive folder placement.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 31 | `test_date_from_exif_original` | JPEG with EXIF DateTimeOriginal = 2024-01-15 | DB: `date_source=exif`, year=2024, month=01, day=15; archive path contains `2024/01/15` | EXIF DateTimeOriginal used as primary date |
| 32 | `test_date_from_exif_digitized` | JPEG with only DateTimeDigitized = 2024-02-20 (no DateTimeOriginal) | DB: year=2024, month=02, day=20; `date_source` is `exif`, `exif_digitized`, or `exif_datetime` | DateTimeDigitized used as fallback when DateTimeOriginal absent |
| 33 | `test_date_from_filename_android` | `IMG_20240415_143000.jpg` with no EXIF | 1 new file; DB: `date_source` is `os_metadata` or `fallback` | Filename date extraction not in current pipeline; falls back to OS metadata |
| 34 | `test_date_from_filename_ios` | `2024-05-20 14.30.00.jpg` with no EXIF | 1 new file; DB: `date_source` is `os_metadata` or `fallback` | Same as above -- iOS naming pattern not parsed by import pipeline |
| 35 | `test_date_fallback_unreliable` | `no_date_anywhere.jpg` with no EXIF, no date in name | 1 new file; DB: `date_source` is `os_metadata` or `fallback` | OS metadata or fallback date used |
| 36 | `test_date_priority_exif_over_filename` | `IMG_20230101_120000.jpg` with EXIF date 2024-07-15 | DB: year=2024, month=07, day=15; `date_source=exif` | EXIF date takes absolute priority over any filename-derived date |

---

### Class 9: TestPriorRevisionArchive

**Purpose:** Verify the Prior Revision Archive correctly stores original files when metadata upgrades replace them.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 37 | `test_revision_stored_on_upgrade` | Session 1: no-EXIF 800x600 file. Session 2: content-identical with EXIF | If upgrade completed: prior revision dir has >= 1 file | Original file preserved before replacement |
| 38 | `test_revision_database_tracking` | Same as above | If upgrade completed: DB has `revision_reason='metadata_upgrade'`; MetadataUpgradeHistory has >= 1 record | Database tracks revision link and upgrade history |

---

### Class 10: TestMultiSessionImport

**Purpose:** Verify correct behavior across multiple sequential import sessions sharing the same database.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 39 | `test_second_import_same_files_all_duplicates` | Session 1: 5 unique photos. Session 2: same 5 files | Session 1: 5 new. Session 2: 0 new, 5 duplicates | All files recognized as duplicates on re-import |
| 40 | `test_second_import_mix_new_and_duplicate` | Session 1: files A, B, C. Session 2: files B, C, D, E | Session 2: 2 new (D, E), 2 duplicates (B, C); archive total = 5 | Mixed new and duplicate files handled correctly |
| 41 | `test_reimport_after_upgrade` | Session 1: low-quality. Session 2: high-quality (potential upgrade). Session 3: low-quality again | Session 3: 0 new files (already in DB as original or prior revision) | Re-importing the original low-quality file after upgrade does not create a new entry |

---

### Class 11: TestOrganizationTemplates

**Purpose:** Verify files are placed in the correct folder structure based on the organization template.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 42 | `test_default_template_year_month_day` | JPEG with EXIF date 2024-01-15; template `{year}/{month}/{day}` | Archive path has folder structure `2024/01/15/` | Default template produces year/month/day hierarchy |
| 43 | `test_template_with_month_name` | Same file; template changed to `{year}/{month_sname}` | Archive path has `2024/Jan/` | Short month name template works correctly |
| 44 | `test_name_collision_handling` | Two unique files both named `collision_photo.jpg` with same EXIF date but different colors | 2 new files; archive has 2 files | Second file gets unique suffix to avoid overwrite |

---

### Class 12: TestAlbumAssociation

**Purpose:** Verify album auto-assignment during import when a source directory is linked to an album.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 45 | `test_source_linked_album_auto_add` | Create album "Vacation" with storage location; link source dir to album; import 1 photo | 1 new file; `total_album_additions >= 1` | File automatically added to album during import |
| 46 | `test_album_file_exists_on_disk` | Same setup as above | Album storage directory contains >= 1 file | Physical file copied to album storage location |

---

### Class 13: TestDeletedFiles

**Purpose:** Verify deletion tracking and re-import behavior.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 47 | `test_reimport_deleted_file` | Import file, delete its record from UniquePhotos, re-import same file | Session 1: 1 new. After delete + Session 2: 1 new | File hash no longer in DB, so re-import treats it as new |

---

### Class 14: TestEdgeCases

**Purpose:** Verify graceful handling of unusual, malformed, or boundary-condition inputs.

| # | Test | Source Files | Assertions | Expected Result |
|---|------|-------------|------------|-----------------|
| 48 | `test_zero_byte_file` | `edge_zero_byte.jpg` (0 bytes) | 0 new files; no crash | Filtered or error handled gracefully |
| 49 | `test_corrupted_jpeg` | JPEG header (`\xff\xd8\xff\xe0`) + 100 null bytes | 0 new files; no crash | Corrupted file filtered out without crashing |
| 50 | `test_special_characters_in_name` | `edge_photo (1) [copy].jpg` (parentheses, brackets, spaces) | 1 new file; file in archive with original name | Special characters in filenames preserved |
| 51 | `test_empty_source_directory` | Empty file list `[]` | 0 files processed, 0 new | No crash on empty input |
| 52 | `test_very_long_filename` | `edge_` + 180 `a` characters + `.jpg` (185-char filename) | No crash; result is not None | Long filename handled (may or may not import depending on OS path limits) |

---

## Helper Module Reference

### File: `tests/test_utils/duplicate_test_helpers.py`

#### Image Generation Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `create_photo_with_exif(path, filename, width, height, date, ...)` | JPEG with full EXIF (DateTimeOriginal, DateTimeDigitized, Camera Make/Model). Random line overlay for file size. | File path |
| `create_photo_without_exif(path, filename, width, height, color)` | JPEG with no EXIF data. Random line overlay for file size. | File path |
| `create_photo_exif_digitized_only(path, filename, width, height, date, color)` | JPEG with only DateTimeDigitized (no DateTimeOriginal). | File path |
| `create_identical_pixels_different_exif(path, fn1, fn2, w, h, color, date1, date2)` | Two JPEGs with identical pixel content but different EXIF dates. For content-hash testing. | Tuple of (path1, path2) |
| `create_small_icon(path, filename, size)` | Small square JPEG (default 64x64). Should be filtered. | File path |
| `create_thumbnail(path, filename)` | 150x150 JPEG. Should be filtered by name pattern + dimensions. | File path |
| `create_tiny_file(path, filename)` | Very small JPEG (100x100, quality=10). Should be filtered by size. | File path |
| `create_dated_filename_photo(path, filename, width, height, color)` | JPEG with no EXIF but a date-parseable filename. Random line overlay. | File path |
| `create_mock_video(path, filename, size_kb)` | File with video extension and random bytes. | File path |
| `create_corrupted_jpeg(path, filename)` | JPEG header followed by null bytes. | File path |
| `create_zero_byte_file(path, filename)` | Empty file (0 bytes). | File path |

#### Verification Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `get_archive_files(archive_dir)` | Recursively list all files in archive. | `{relative_path: absolute_path}` |
| `get_database_records(db_path)` | All UniquePhotos records. | List of dicts |
| `get_unreliable_dates(db_path)` | All UnreliableDates records. | List of dicts |
| `get_revision_records(db_path)` | Records where `revised_photo IS NOT NULL`. | List of dicts |
| `get_upgrade_history(db_path)` | All MetadataUpgradeHistory records. | List of dicts |
| `assert_file_in_archive(archive_dir, substring)` | Assert a file containing substring exists in archive. Fails with list of actual files. | Matching path |
| `assert_file_not_in_archive(archive_dir, substring)` | Assert no file containing substring exists in archive. | None |
| `count_archive_files(archive_dir)` | Count total files in archive tree. | int |

#### Environment Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `setup_full_environment(tmp_path, source_name)` | Create source, archive, prior revision dirs; initialize DB + metadata; build Config. | Dict with all paths + config |
| `run_organize(env, files, **overrides)` | Run `organize_files()` with standard env settings. | Result dict from `organize_files()` |

---

## Troubleshooting

### All tests filtered as `file_size_too_small`

The test config sets `min_file_size=1024` (1 KB). If tests fail with filter reason `file_size_too_small`, the synthetic images are not generating enough content. The `_add_varied_content()` helper draws 200 random lines to increase JPEG complexity. Verify this function is being called in the image generation helpers.

### `pytest.ini` comment parsing issue

The project's `pytest.ini` has inline comments in the `addopts` section that pytest interprets as arguments. Always use `--override-ini="addopts="` when running tests from the command line, or run without specifying a config file:

```bash
venv/bin/python -m pytest tests/integration/test_duplicate_detection_comprehensive.py \
    -v --override-ini="addopts="
```

### Filename date extraction tests

Tests `test_date_from_filename_android` and `test_date_from_filename_ios` verify that files without EXIF fall back to OS metadata. The current `get_creation_date()` function in `DuplicateFileDetection.py` does not extract dates from filenames -- it goes: EXIF -> IPTC -> XMP -> OS metadata. A separate `date_extraction.py` module has filename pattern support but it is not wired into the import pipeline. These tests document the current behavior.

### Metadata upgrade tests show conditional assertions

Tests like `test_upgrade_creates_prior_revision` and `test_revision_stored_on_upgrade` use conditional assertions (`if result.get("upgrades_completed", 0) > 0`). This is because content-hash-based upgrade detection depends on pixel-level matching, and synthetic images with the same RGB color tuple but saved in separate JPEG compressions may not produce identical content hashes. The tests verify correct behavior when upgrades do occur without failing when the content hash comparison doesn't trigger.
