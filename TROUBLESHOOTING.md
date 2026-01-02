# Troubleshooting Guide

> Solutions to common issues and problems

**Last Updated:** 2026-01-02

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Configuration Issues](#configuration-issues)
- [Runtime Errors](#runtime-errors)
- [Performance Issues](#performance-issues)
- [Database Issues](#database-issues)
- [File Processing Issues](#file-processing-issues)
- [HEIC Conversion Issues](#heic-conversion-issues)
- [Logging and Debugging](#logging-and-debugging)

---

## Installation Issues

### ModuleNotFoundError: No module named 'PIL'

**Problem:** Pillow not installed

**Solution:**
```bash
pip install Pillow>=10.0.0
```

---

### ModuleNotFoundError: No module named 'pillow_heif'

**Problem:** HEIC support not installed

**Solution:**
```bash
pip install pillow-heif>=0.13.0
```

---

### Requirements Installation Fails

**Problem:** Dependency conflicts

**Solution:**
```bash
# Create fresh virtual environment
python -m venv venv_new
source venv_new/bin/activate  # or venv_new\Scripts\activate on Windows

# Install with no cache
pip install --no-cache-dir -r requirements.txt
```

---

## Configuration Issues

### FileNotFoundError: settings.json not found

**Problem:** Configuration file missing

**Solution:**
```bash
# Create settings.json
cat > settings.json << EOF
{
  "source_directory": ["path/to/photos"],
  "destination_directory": "path/to/output"
}
EOF
```

---

### ValueError: Missing required settings

**Problem:** Required settings not provided

**Solution:**
```json
{
  "source_directory": ["YOUR_PATH_HERE"],
  "destination_directory": "YOUR_PATH_HERE"
}
```

Both `source_directory` and `destination_directory` are required.

---

### ValueError: Path traversal detected

**Problem:** Config contains `..` patterns

**Solution:**
```json
// ❌ Wrong
"source_directory": ["../../Photos"]

// ✅ Correct - Use absolute paths
"source_directory": ["D:\\Photos"]
```

---

### ValueError: copy_files and move_files cannot both be True

**Problem:** Conflicting operation modes

**Solution:**
```json
// Choose one:
{"copy_files": true, "move_files": false}
// OR
{"copy_files": false, "move_files": true}
```

---

### JSONDecodeError: Invalid JSON

**Problem:** Syntax error in settings.json

**Solution:**
```bash
# Validate JSON online: jsonlint.com
# Common issues:
- Missing commas
- Trailing commas
- Unquoted keys
- Single quotes instead of double quotes
```

**Valid JSON:**
```json
{
  "source_directory": ["D:\\Photos"],
  "destination_directory": "E:\\Output"
}
```

---

## Runtime Errors

### PermissionError: Access denied

**Problem:** Insufficient permissions

**Solutions:**

**Windows:**
```bash
# Run as administrator
# Right-click -> Run as Administrator
```

**Linux:**
```bash
# Check permissions
ls -la file_path

# Fix permissions
chmod 644 file_path
sudo chown user:user file_path
```

---

### FileNotFoundError during processing

**Problem:** Source file deleted/moved during processing

**Solution:**
- Don't modify source directories during processing
- Re-run application (will skip already processed files)

---

### OSError: Disk full

**Problem:** Destination drive out of space

**Solution:**
```bash
# Check disk space
df -h  # Linux
dir    # Windows

# Free space or use different destination
```

---

### MemoryError

**Problem:** Processing too many files at once

**Solution:**
```json
{
  "batch_size": 50  // Reduce from 100
}
```

Or process fewer source directories at a time.

---

## Performance Issues

### Very Slow Processing

**Diagnosis:**
```python
# Add timing
import time
start = time.time()
# ... process files ...
print(f"Time: {time.time() - start:.2f}s")
```

**Common Causes & Solutions:**

**1. Partial hashing disabled**
```json
{
  "partial_hash_enabled": true  // Enable this
}
```

**2. Small batch size**
```json
{
  "batch_size": 500  // Increase from 100
}
```

**3. Photo filtering disabled**
```json
{
  "photo_filter_enabled": true  // Enable filtering
}
```

**4. Slow disk I/O**
- Use SSD for database
- Use local drives (not network)
- Close other disk-intensive programs

---

### Database Queries Slow

**Problem:** Missing indexes

**Solution:**
```sql
-- Check indexes
sqlite3 PhotoDB.db
.indices UniquePhotos

-- Should show:
-- idx_partial_hash
-- idx_file_size
-- idx_date
-- idx_file_name
```

If missing, run:
```python
with PhotoDatabase('PhotoDB.db') as db:
    db.initialize_database()
```

---

### Progress Bar Frozen

**Problem:** Processing very large file

**Diagnosis:**
- Progress bar updates per file
- Large files take longer
- Check log file for progress

**Solution:**
- Wait (especially for large videos)
- Enable partial hashing
- Check if file is corrupted

---

## Database Issues

### DatabaseError: Table already exists

**Problem:** Trying to recreate existing database

**Solution:**
```python
# Database is OK, ignore this error
# OR delete and recreate:
rm PhotoDB.db
python main.py
```

---

### DatabaseError: Database locked

**Problem:** Multiple processes accessing database

**Solution:**
- Close other instances of application
- Check for background processes
- Wait and retry

---

### Incorrect duplicate count

**Problem:** Database out of sync

**Solution:**
```bash
# Backup database
cp PhotoDB.db PhotoDB.db.backup

# Clear and rebuild
rm PhotoDB.db
python main.py
```

**Warning:** This will reprocess all files!

---

### Database file too large

**Problem:** Database growing unexpectedly

**Diagnosis:**
```bash
sqlite3 PhotoDB.db
SELECT COUNT(*) FROM UniquePhotos;
```

**Solution:**
```sql
-- Vacuum database
VACUUM;

-- Remove old records (if needed)
DELETE FROM UniquePhotos WHERE create_year = '1000';
VACUUM;
```

---

## File Processing Issues

### Files not being processed

**Diagnosis:**
```python
# Check file list
files = get_file_list(...)
print(f"Found {len(files)} files")
print(files[:5])  # First 5
```

**Common Causes:**

**1. Wrong file extensions**
```json
{
  "file_endings": [".jpg", ".jpeg", ".png", ".heic"]
}
```

**2. Subdirectories not included**
```json
{
  "include_subdirectories": true
}
```

**3. Files filtered out**
```json
{
  "photo_filter_enabled": false  // Temporarily disable
}
```

---

### Duplicates not detected

**Diagnosis:**
```python
# Manually check hashes
hash1 = hash_file("file1.jpg")
hash2 = hash_file("file2.jpg")
print(f"Hash1: {hash1}")
print(f"Hash2: {hash2}")
print(f"Match: {hash1 == hash2}")
```

**Common Causes:**

**1. Files actually different**
- Different resolution
- Different compression
- Edited/modified

**2. Database out of sync**
- Rebuild database (see above)

**3. Partial hash collision**
- Rare but possible
- Check full hashes

---

### Files skipped with "already exists"

**Problem:** Destination file already exists

**Expected Behavior:**
- If identical: Skip (correct)
- If different: Create with _1, _2, etc.

**Check:**
```python
# Verify files are identical
import filecmp
filecmp.cmp("source.jpg", "dest.jpg", shallow=False)
```

---

### Wrong date organization

**Diagnosis:**
```python
# Check date extraction
year, month, day = get_creation_date("photo.jpg")
print(f"Date: {year}-{month}-{day}")
```

**Common Causes:**

**1. No EXIF data**
- Uses file system date instead
- May be incorrect for copied files

**2. Invalid date returned**
- Returns "1000-01-01" on error
- Check file is valid image

**3. Timezone issues**
- EXIF dates are local time
- File system dates may vary

**Solution:**
```bash
# Add EXIF data manually (if needed)
exiftool -DateTimeOriginal="2024:11:25 14:30:00" photo.jpg
```

---

## HEIC Conversion Issues

### HEIC files not converting

**Problem:** pillow_heif not working

**Diagnosis:**
```python
import pillow_heif
print(pillow_heif.__version__)
```

**Solution:**
```bash
pip install --upgrade pillow-heif
```

---

### Converted images corrupted

**Problem:** Format parameter error

**Fixed in v2.0:**
```python
# ❌ Old (wrong)
heic_image.save(path, format("jpeg"))

# ✅ New (correct)
heic_image.save(path, format="JPEG")
```

**Solution:** Update to latest version

---

### EXIF data lost in conversion

**Problem:** Pillow not preserving EXIF

**Solution:**
```python
# Save with EXIF
heic_image.save(path, format="JPEG", exif=heic_image.info.get('exif'))
```

---

## Logging and Debugging

### Log file too large

**Problem:** Verbose logging creating huge files

**Solution:**
```python
# Reduce logging level
logger.setLevel(logging.INFO)  # Instead of DEBUG
```

Or rotate logs:
```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

---

### Debug specific file

**Add temporary logging:**
```python
if "problem_file.jpg" in file_path:
    logger.setLevel(logging.DEBUG)
    logger.debug(f"Processing: {file_path}")
    logger.debug(f"Size: {os.path.getsize(file_path)}")
    logger.debug(f"Hash: {hash_file(file_path)}")
```

---

### Enable verbose output

**In main.py:**
```python
# Temporary debug mode
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

---

## Common Error Messages

### "Image file is truncated"

**Problem:** Corrupted or incomplete image file

**Solution:**
- Skip file (expected behavior)
- Try re-downloading original
- Check disk integrity

---

### "Cannot identify image file"

**Problem:** File is not a valid image or wrong extension

**Solution:**
- Verify file type: `file photo.jpg`
- Let VerifyFileType() correct extension
- Remove non-image files from source

---

### "Hash collision detected"

**Problem:** Extremely rare partial hash collision

**Behavior:** Application automatically calculates full hash

**Action:** None needed (handled automatically)

---

## Getting Further Help

### Collect Debug Information

Before reporting issue, collect:

```bash
# 1. Python version
python --version

# 2. Package versions
pip list | grep -E "Pillow|pillow-heif|tqdm"

# 3. Configuration (remove sensitive paths)
cat settings.json

# 4. Error log
tail -100 main_app_error.log

# 5. Database stats
sqlite3 PhotoDB.db "SELECT COUNT(*) FROM UniquePhotos;"
```

### Report Issue

Include:
1. Python version
2. Operating system
3. Configuration (sanitized)
4. Error message
5. Steps to reproduce
6. Expected vs actual behavior

---

## Emergency Recovery

### Application Crashed Mid-Run

**Don't worry!** Progress is saved.

**Recovery:**
1. Check log files for last processed file
2. Database contains all completed batches
3. Simply re-run:
```bash
python main.py
```

Application will skip already-processed files.

---

### Database Corrupted

**Symptoms:**
- SQLite error messages
- Incorrect counts
- Processing failures

**Recovery:**
```bash
# 1. Backup corrupted DB
cp PhotoDB.db PhotoDB.db.corrupt

# 2. Try integrity check
sqlite3 PhotoDB.db "PRAGMA integrity_check;"

# 3. If corrupted, rebuild
rm PhotoDB.db
python main.py  # Reprocess all files
```

---

### Lost All Originals (Move Mode)

**Prevention:** Always backup before using move mode!

**If it happens:**
1. Check destination directory - files should be there
2. Check database for file locations
3. Use photo recovery software if needed

---

## Performance Checklist

Run through this checklist for optimal performance:

- [ ] Partial hashing enabled
- [ ] Batch size 100-500
- [ ] Photo filtering enabled
- [ ] Database on SSD
- [ ] Source on local drive (not network)
- [ ] Sufficient RAM available
- [ ] Antivirus exceptions set
- [ ] Database indexes created
- [ ] Logging level = INFO (not DEBUG)

---

## Prevention Best Practices

1. **Always backup before move mode**
2. **Test with small dataset first**
3. **Monitor first few hundred files**
4. **Keep database backed up**
5. **Use version control for settings**
6. **Document customizations**
7. **Update regularly**

---

---

## GUI Issues

### GUI Won't Launch

**Problem:** `python main_gui.py` fails

**Solutions:**

**1. PySide6 not installed**
```bash
# Check if installed
python3 -c "import PySide6; print('OK')"

# Install if missing
pip install PySide6>=6.4.0
```

**2. No display available (headless system)**
```bash
# Check DISPLAY variable
echo $DISPLAY

# Solution: Use CLI instead
python main.py
```

**3. Import errors**
```bash
# Ensure you're in correct directory
cd /path/to/PyPhotoOrganizer
python main_gui.py
```

---

### GUI Freezes During Processing

**Problem:** GUI becomes unresponsive

**Diagnosis:**
- This should NOT happen (worker thread design)
- If it does, there's a bug

**Solutions:**
1. Check Logs tab for errors
2. Check `main_app_error.log` for exceptions
3. Kill and restart: `Ctrl+C` then relaunch
4. Processing should resume from last checkpoint

---

### Progress Not Updating

**Problem:** Progress bars stuck at 0%

**Possible Causes:**

**1. No files to process**
- Check source directories exist
- Check file extensions match `file_endings` setting

**2. Worker thread crashed**
- Check Logs tab for errors
- Look for red error messages

**3. Callback not being invoked**
- Check `main_app_error.log`
- Should see progress messages

---

### Settings Won't Save

**Problem:** Settings changes don't persist

**Solution:**
1. Click "Save to File" button in Settings tab
2. Check file permissions on `settings.json`
3. Verify JSON is valid (click "Validate Settings")

---

### Export Results Fails

**Problem:** Can't export to CSV/JSON

**Solutions:**
- Check destination folder has write permissions
- Ensure filename doesn't contain invalid characters
- Check disk space available

---

### Log Viewer Empty

**Problem:** Logs tab shows no entries

**Solutions:**
1. Click "Refresh" button
2. Check log file exists: `ls main_app_error.log`
3. Start processing to generate new logs
4. Check log level filter (set to "All")

---

### Time Estimates Inaccurate

**Problem:** "Remaining time" is way off

**Expected Behavior:**
- First 10-20 seconds: "Calculating..."
- After warmup: Should be accurate within ±20%
- Large files may cause temporary spikes

**Not a bug:** EMA algorithm needs time to stabilize

---

### GUI Specific Error Messages

**Error: "QApplication: Cannot create a QApplication"**

**Solution:** Already running a Qt application
```bash
# Kill existing instance
killall python main_gui.py
# Or restart system
```

**Error: "qt.qpa.plugin: Could not load the Qt platform plugin"**

**Solution:** Missing Qt platform plugin
```bash
# Ubuntu/Debian
sudo apt install libxcb-xinerama0

# Or reinstall PySide6
pip uninstall PySide6
pip install PySide6
```

---

**Still having issues?** Check:
- [README.md](README.md) - Overview
- [CONFIGURATION.md](CONFIGURATION.md) - Settings
- [API.md](API.md) - Code reference
- [GUI_TESTING_GUIDE.md](GUI_TESTING_GUIDE.md) - GUI testing procedures
- [GitHub Issues](https://github.com/your-repo/issues)

---

*Last updated: 2026-01-02*
