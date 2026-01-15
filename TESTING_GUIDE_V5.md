# Schema v5 Testing Guide

## Quick Start

This guide walks you through testing the v5 schema implementation step-by-step.

## Prerequisites

- Backup your current database before testing
- Have a small test photo collection ready (10-20 photos recommended)
- Python environment set up with all dependencies

## Test Sequence

### Test 1: Database Migration (5 minutes)

**Backup your database:**
```bash
cd /home/doug/Dropbox/Projects/python\ Projects/PyPhotoOrganizer/PyPhotoOrganizer
cp PhotoDB_BowerPhotoArchiveDB.db PhotoDB_BowerPhotoArchiveDB.db.v4.backup
```

**Run migration:**
```bash
python migrations/schema_v5.py PhotoDB_BowerPhotoArchiveDB.db
```

**Expected output:**
```
================================================================================
⚠️  WARNING: BREAKING CHANGE - FRESH IMPORT REQUIRED
================================================================================
This migration will:
  1. Drop FileHashHistory, FileVersions, ModificationSession, ModificationLog tables
  2. Recreate UniquePhotos table with new schema
  3. Clear all existing photo records

Preserved:
  • Database configuration and settings
  • Source directory configurations
  • Import audit history

Continue with migration? (yes/no): yes

Starting migration...

================================================================================
STARTING DATABASE MIGRATION: Schema v5 - Unified UniquePhotos
Database: PhotoDB_BowerPhotoArchiveDB.db
⚠️  WARNING: This is a BREAKING CHANGE - fresh imports required
================================================================================
Current schema version: 4
------------------------------------------------------------
Phase 1: Dropping obsolete tables...
  ✓ Dropped table: FileHashHistory
  ✓ Dropped table: FileVersions
  ✓ Dropped table: ModificationSession
  ✓ Dropped table: ModificationLog
✓ Obsolete tables removed
------------------------------------------------------------
Phase 2: Recreating UniquePhotos table with v5 schema...
⚠️  All existing UniquePhotos data will be lost
⚠️  Fresh import of photos required after migration
  ✓ Dropped old UniquePhotos table
  ✓ Created new UniquePhotos table with revision tracking
Creating UniquePhotos indexes...
  ✓ Created index: idx_unique_partial_hash
  ✓ Created index: idx_unique_revised
  ✓ Created index: idx_unique_source
  ✓ Created index: idx_unique_year
  ✓ Created index: idx_unique_date
✓ UniquePhotos indexes created (5 indexes)
------------------------------------------------------------
Phase 3: Clearing UnreliableDates table...
  ✓ Cleared 0 records from UnreliableDates
  ℹ  Records will be repopulated during fresh import
Clearing DeletedFiles table...
  ✓ Cleared 0 records from DeletedFiles
Resetting photo counter in DatabaseMetadata...
  ✓ Reset total_photos to 0
------------------------------------------------------------
Phase 4: Updating schema version to 5...
✓ Schema version updated to 5
================================================================================
✓✓✓ DATABASE MIGRATION COMPLETED SUCCESSFULLY ✓✓✓
================================================================================

✓ Migration completed successfully

⚠️  Next step: Re-import photos using the Setup tab
```

**Verification:**
```bash
# Check schema version
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT schema_version FROM DatabaseMetadata WHERE id=1"
# Expected output: 5

# Check UniquePhotos schema
sqlite3 PhotoDB_BowerPhotoArchiveDB.db ".schema UniquePhotos"
# Should show revised_photo, revision_reason, source_path, revision_timestamp columns

# Check obsolete tables are gone
sqlite3 PhotoDB_BowerPhotoArchiveDB.db ".tables"
# Should NOT show FileHashHistory or FileVersions
```

**Pass criteria:**
- ✅ Migration completes without errors
- ✅ Schema version = 5
- ✅ UniquePhotos has new columns
- ✅ FileHashHistory table does not exist
- ✅ FileVersions table does not exist

---

### Test 2: Fresh Import (10-15 minutes)

**Start GUI:**
```bash
python main_gui.py
```

**Import workflow:**
1. Open Setup tab
2. Verify source directories are still configured (should be preserved)
3. Select a test directory with ~10-20 photos
4. Click "Start Processing"
5. Watch progress in Progress tab
6. Check Results tab when complete

**Expected behavior:**
- Files process normally
- Duplicate detection works (if re-importing same photos)
- Database populates with v5 records
- UnreliableDates repopulates for flagged files
- No errors in Logs tab

**Verification:**
```bash
# Check source_path is populated
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT file_hash, file_name, source_path, revised_photo FROM UniquePhotos LIMIT 5"
# All original imports should have:
# - source_path = original import location
# - revised_photo = NULL

# Check record count
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT COUNT(*) FROM UniquePhotos"
# Should match number of unique photos imported
```

**Pass criteria:**
- ✅ Import completes without errors
- ✅ source_path populated for all files
- ✅ revised_photo = NULL for all original imports
- ✅ Duplicate detection works correctly
- ✅ UnreliableDates repopulated (if applicable)

---

### Test 3: Rotation (5 minutes)

**Setup:**
1. Go to Date Corrections tab
2. Select 1-2 files from the grid
3. Click "Rotate Selected..."
4. Choose "90° Clockwise"
5. Click "Apply"

**Expected behavior:**
- Progress dialog shows rotation progress
- Files rotate successfully
- Grid refreshes
- Thumbnails show rotated images
- Scroll position preserved

**Verification:**
```bash
# Check revision records created
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT file_hash, revised_photo, revision_reason, revision_timestamp FROM UniquePhotos WHERE revised_photo IS NOT NULL"
# Should show:
# - new file_hash (different from parent)
# - revised_photo = parent hash
# - revision_reason = 'rotation'
# - revision_timestamp = recent timestamp

# Check UnreliableDates updated
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT file_hash FROM UnreliableDates WHERE file_hash IN (SELECT file_hash FROM UniquePhotos WHERE revised_photo IS NOT NULL)"
# Should show new hash (not old hash)
```

**Pass criteria:**
- ✅ Rotation completes without errors
- ✅ Revision records created correctly
- ✅ UnreliableDates updated with new hash
- ✅ Thumbnails refresh correctly
- ✅ revised_photo links to parent hash
- ✅ revision_reason = 'rotation'

---

### Test 4: EXIF Date Correction (5 minutes)

**Setup:**
1. Stay in Date Corrections tab
2. Select 1-2 files with unreliable dates
3. Click "Correct Date..."
4. Enable "Write EXIF to archive file"
5. Enter correct date (e.g., 1995-07-15)
6. Click "Apply"

**Expected behavior:**
- EXIF written to archive file
- Revision record created
- UnreliableDates updated with new hash
- File marked for reorganization (if enabled)
- Success message shown

**Verification:**
```bash
# Check EXIF editing revisions
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT file_hash, revised_photo, revision_reason FROM UniquePhotos WHERE revision_reason = 'exif_edit'"
# Should show:
# - new file_hash
# - revised_photo = parent hash
# - revision_reason = 'exif_edit'

# Check revision chain
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "
WITH RECURSIVE chain(file_hash, revised_photo, revision_reason, level) AS (
  SELECT file_hash, revised_photo, revision_reason, 0
  FROM UniquePhotos
  WHERE revised_photo IS NULL
  UNION ALL
  SELECT u.file_hash, u.revised_photo, u.revision_reason, c.level + 1
  FROM UniquePhotos u
  JOIN chain c ON u.revised_photo = c.file_hash
)
SELECT file_hash, revised_photo, revision_reason, level FROM chain WHERE level > 0
"
# Shows complete revision chain
```

**Pass criteria:**
- ✅ EXIF written successfully
- ✅ Revision record created
- ✅ UnreliableDates updated
- ✅ revision_reason = 'exif_edit'
- ✅ Revision chain query works

---

### Test 5: Delete to Vault (3 minutes)

**Setup:**
1. Stay in Date Corrections tab
2. Select 1-2 files
3. Click "Delete Selected..."
4. Confirm deletion

**Expected behavior:**
- Files moved to Delete Vault
- Files removed from Date Corrections grid
- DeletedFiles records created
- UnreliableDates records removed

**Verification:**
```bash
# Check files removed from UnreliableDates
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT COUNT(*) FROM UnreliableDates WHERE file_hash IN (SELECT file_hash FROM DeletedFiles WHERE is_restored = 0)"
# Should be 0

# Check DeletedFiles table
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT file_hash, original_archive_path, delete_vault_path, is_restored FROM DeletedFiles WHERE is_restored = 0"
# Should show deleted file records
```

**Pass criteria:**
- ✅ Files moved to vault successfully
- ✅ Files removed from Date Corrections grid
- ✅ DeletedFiles records created
- ✅ UnreliableDates records removed

---

### Test 6: Restore from Vault (3 minutes)

**Setup:**
1. Click "View Deleted Files..."
2. Select files to restore
3. Click "Restore Selected"
4. Confirm restoration

**Expected behavior:**
- Files moved back to archive
- DeletedFiles.is_restored = 1
- UniquePhotos.file_name updated
- Success message shown

**Verification:**
```bash
# Check restoration
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT file_hash, is_restored, restore_timestamp FROM DeletedFiles WHERE is_restored = 1"
# Should show restored files with timestamp

# Check UniquePhotos updated
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT file_hash, file_name FROM UniquePhotos WHERE file_hash IN (SELECT file_hash FROM DeletedFiles WHERE is_restored = 1)"
# Should show updated file_name (archive path)
```

**Pass criteria:**
- ✅ Files restored successfully
- ✅ DeletedFiles.is_restored = 1
- ✅ UniquePhotos.file_name updated
- ✅ restore_timestamp set

---

### Test 7: Duplicate Detection (10 minutes)

**Scenario A: Import original file again**
1. Import a file that was already imported
2. Expected: Skipped as duplicate

**Scenario B: Import rotated file**
1. Import a file that you rotated in Test 3
2. Expected: Skipped as duplicate (revision hash found)

**Scenario C: Import EXIF-edited file**
1. Import a file that you EXIF-edited in Test 4
2. Expected: Skipped as duplicate (revision hash found)

**Verification:**
```bash
# Check duplicate detection in logs
grep "Duplicate detected" logs/main_app_error.log
# Should show duplicate detections for all scenarios

# Check FileProcessingLog
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT source_path, operation, status FROM FileProcessingLog WHERE operation = 'duplicate detected' ORDER BY process_timestamp DESC LIMIT 10"
# Should show recent duplicate detections
```

**Pass criteria:**
- ✅ Original files detected as duplicates
- ✅ Rotated files detected as duplicates
- ✅ EXIF-edited files detected as duplicates
- ✅ No false positives (unique files marked as duplicates)
- ✅ No false negatives (duplicates not detected)

---

## Performance Checks

### Query Performance
```bash
# Test duplicate detection speed (should be O(1))
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "EXPLAIN QUERY PLAN SELECT file_hash FROM UniquePhotos WHERE file_hash = 'test_hash'"
# Should show: SEARCH UniquePhotos USING PRIMARY KEY (file_hash=?)

# Test revision chain query
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "EXPLAIN QUERY PLAN SELECT * FROM UniquePhotos WHERE revised_photo = 'test_hash'"
# Should show: SEARCH UniquePhotos USING INDEX idx_unique_revised (revised_photo=?)
```

### Database Size
```bash
# Check database file size
ls -lh PhotoDB_BowerPhotoArchiveDB.db

# Compare with v4 backup
ls -lh PhotoDB_BowerPhotoArchiveDB.db.v4.backup

# Check table sizes
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "
SELECT name, COUNT(*) as records
FROM (
  SELECT 'UniquePhotos' as name FROM UniquePhotos
  UNION ALL SELECT 'UnreliableDates' FROM UnreliableDates
  UNION ALL SELECT 'DeletedFiles' FROM DeletedFiles
  UNION ALL SELECT 'FileProcessingLog' FROM FileProcessingLog
)
GROUP BY name
"
```

## Troubleshooting

### Issue: Migration fails with "database is locked"
**Solution**: Close all database connections, then retry:
```bash
pkill -f main_gui.py
python migrations/schema_v5.py PhotoDB_BowerPhotoArchiveDB.db
```

### Issue: Import shows errors in logs
**Solution**: Check logs for specific errors:
```bash
tail -f logs/main_app_error.log
```

### Issue: Duplicate detection not working
**Solution**: Verify UniquePhotos table has records:
```bash
sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT COUNT(*) FROM UniquePhotos"
```

### Issue: Rotation fails
**Solution**: Check permissions on archive directory:
```bash
ls -la /path/to/archive
```

### Issue: EXIF write fails
**Solution**: Check file format is supported (JPG/TIFF only):
```bash
file /path/to/archive/file.jpg
```

## Rollback Instructions

If critical issues found:

1. **Stop application:**
   ```bash
   pkill -f main_gui.py
   ```

2. **Restore v4 database:**
   ```bash
   cp PhotoDB_BowerPhotoArchiveDB.db.v4.backup PhotoDB_BowerPhotoArchiveDB.db
   ```

3. **Revert code (if needed):**
   ```bash
   git status  # Check current changes
   git stash   # Stash v5 changes
   # Or: git checkout HEAD~1  # Revert to previous commit
   ```

4. **Verify restoration:**
   ```bash
   sqlite3 PhotoDB_BowerPhotoArchiveDB.db "SELECT schema_version FROM DatabaseMetadata WHERE id=1"
   # Should show: 4
   ```

## Success Criteria

All tests must pass:
- ✅ Migration completes without errors
- ✅ Import works with source_path tracking
- ✅ Rotation creates revision records
- ✅ EXIF editing creates revision records
- ✅ Delete/restore works correctly
- ✅ Duplicate detection works for all scenarios
- ✅ No data loss
- ✅ No performance regression
- ✅ All revision chains valid

## Next Steps After Testing

1. Update documentation (ARCHITECTURE.md, API.md, CLAUDE.md, USER_GUIDE.md)
2. Remove obsolete code (VersionManager class)
3. Deploy to production with confidence
4. Monitor for any issues
5. Create v5 release notes

---

**Estimated Total Testing Time**: 45-60 minutes

**Status**: Ready to begin testing
