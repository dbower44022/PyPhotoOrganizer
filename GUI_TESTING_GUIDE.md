# GUI Testing Guide

## Prerequisites

### 1. Install PySide6

**Option A: Using pip (recommended)**
```bash
pip install PySide6>=6.4.0
```

**Option B: Using system package manager (Ubuntu/Debian)**
```bash
sudo apt install python3-pyside6.qtwidgets python3-pyside6.qtcore python3-pyside6.qtgui
```

**Option C: Install all requirements at once**
```bash
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
python3 -c "import PySide6; print(f'PySide6 version: {PySide6.__version__}')"
```

Expected output: `PySide6 version: 6.x.x`

---

## Quick Test (Without Real Photos)

### Step 1: Launch the GUI

```bash
cd /home/doug/Dropbox/Projects/python\ Projects/PyPhotoOrganizer/PyPhotoOrganizer
python3 main_gui.py
```

### Step 2: Verify All Tabs

1. **Setup Tab** - Should show:
   - Empty source folders list with Add/Remove buttons
   - Destination folder field with Browse button
   - Copy/Move radio buttons (Copy selected by default)
   - Start/Stop buttons (Start enabled, Stop disabled)

2. **Progress Tab** - Should show:
   - Overall progress bar at 0%
   - Stage label showing "Idle"
   - All progress indicators at 0
   - Empty status log

3. **Results Tab** - Should show:
   - All statistics at 0
   - Empty breakdown tree
   - Export button disabled

4. **Logs Tab** - Should show:
   - Log level filter dropdown
   - Search box
   - Auto-scroll checkbox (checked)
   - Empty log table

5. **Settings Tab** - Should show:
   - All settings groups with default values
   - Folder structure preview showing "2024/11/25/photo.jpg"
   - Load/Save/Restore Defaults/Validate buttons

### Step 3: Test Settings Tab

1. Click **"Restore Defaults"** - Should show confirmation dialog
2. Uncheck **"Group by year"** - Folder preview should change to "2024-11/25/photo.jpg"
3. Uncheck **"Group by day"** - Folder preview should change to "2024-11/photo.jpg"
4. Re-check both - Preview should return to "2024/11/25/photo.jpg"
5. Click **"Validate Settings"** - Should show "All settings are valid" message

### Step 4: Close GUI

- Click X button or File → Exit
- Should close without errors

---

## Full Test (With Sample Photos)

### Step 1: Create Test Dataset

```bash
# Create test directories
mkdir -p ~/test_photos_source
mkdir -p ~/test_photos_dest

# Copy some existing photos to test directory (replace with your photo paths)
# Or download sample images
cd ~/test_photos_source
wget -O photo1.jpg https://via.placeholder.com/1920x1080.jpg
wget -O photo2.jpg https://via.placeholder.com/1920x1080.jpg
wget -O photo3.jpg https://via.placeholder.com/800x600.jpg
cp photo1.jpg photo1_duplicate.jpg  # Create a duplicate
```

### Step 2: Run Full Processing

1. **Launch GUI:**
   ```bash
   python3 main_gui.py
   ```

2. **Setup Tab:**
   - Click "Add Folder..." and select `~/test_photos_source`
   - Click "Browse..." for destination and select `~/test_photos_dest`
   - Verify "Copy Files" is selected (safe mode)
   - Click "Start Processing"

3. **Progress Tab (auto-switches):**
   - Watch "Scanning Directories" stage (should be quick with 1 folder)
   - Watch "Processing Files" stage:
     - Progress bar should animate
     - Current file should display
     - Rate should show files/sec
     - Time remaining should update
     - Stats should show: Unique: X, Duplicates: Y, Filtered: Z
   - Watch "Organizing Files" stage:
     - Files being copied should display
     - Bytes copied should increment

4. **Results Tab (auto-switches when done):**
   - Should show completion dialog
   - Summary statistics should match processed files
   - Breakdown tree should show categories
   - Click "Export Results..." and save to test_results.json
   - Verify exported file exists and contains data

5. **Logs Tab:**
   - Should show processing log entries
   - Test log level filter (select "INFO" - should hide DEBUG messages)
   - Test search (type "Processing" - should filter entries)
   - Test auto-scroll (uncheck, scroll up, check again)

### Step 3: Verify Results

```bash
# Check destination folder
ls -R ~/test_photos_dest

# Should see structure like:
# 2024/11/25/photo1.jpg
# 2024/11/25/photo2.jpg
# etc.

# Verify source files still exist (Copy mode)
ls ~/test_photos_source
# All original files should still be there
```

### Step 4: Test Move Mode (DESTRUCTIVE - Use Test Data Only!)

1. **Setup Tab:**
   - Add test source folder again
   - Select different destination (or delete previous)
   - Select **"Move Files"** radio button
   - Click "Start Processing"
   - **WARNING DIALOG** should appear asking for confirmation
   - Click "Yes" to confirm

2. After processing, verify:
   - Source folder should be empty (files moved)
   - Destination should have all files organized

---

## Error Testing

### Test 1: Missing Source Folder

1. Setup Tab: Leave source folders list empty
2. Click "Start Processing"
3. Expected: Error dialog "Please select at least one source folder"

### Test 2: Missing Destination

1. Setup Tab: Add source folder, leave destination empty
2. Click "Start Processing"
3. Expected: Error dialog "Please select a destination folder"

### Test 3: Invalid Settings

1. Settings Tab: Set batch size to 0 (if spinbox allows)
2. Click "Validate Settings"
3. Expected: Error dialog showing validation failure

### Test 4: Cancel During Processing

1. Start processing with large dataset
2. Click "Stop Processing" button while running
3. Expected: Confirmation dialog
4. Click "Yes"
5. Expected: Processing stops gracefully, progress saved to database

---

## Performance Test (Large Dataset)

### Setup

```bash
# Create 1000 test files
mkdir -p ~/test_photos_large
cd ~/test_photos_large

for i in {1..1000}; do
    cp ~/test_photos_source/photo1.jpg photo_$i.jpg
done
```

### Expectations

- **Scanning:** Should be instant (1 directory)
- **Processing:** ~100-1000 files/sec depending on system
- **Time Estimates:**
  - Should show "Calculating..." for first few seconds
  - Should stabilize to realistic estimate after ~10 seconds
  - Should be accurate within ±20%
- **Memory:** Should not exceed 500MB
- **UI:** Should remain responsive throughout

---

## Regression Testing (CLI Still Works)

Verify the command-line interface still works:

```bash
python3 main.py
```

Expected: CLI should run exactly as before, with tqdm progress bars

---

## Known Limitations

1. **Display:** Requires X11/Wayland display (won't work in pure SSH without X forwarding)
2. **Platform:** Tested on Linux, should work on Windows/macOS with PySide6 installed
3. **Large Datasets:** Byte calculation for 100,000+ files may add 1-2 seconds startup time

---

## Troubleshooting

### Error: "No module named 'PySide6'"

**Solution:** Install PySide6 (see Prerequisites above)

### Error: "Cannot connect to X server"

**Solution:** You're in a headless environment. Either:
- Use X forwarding: `ssh -X user@host`
- Use VNC/remote desktop
- Use CLI version: `python3 main.py`

### GUI Window Doesn't Appear

**Solution:**
```bash
# Check DISPLAY environment variable
echo $DISPLAY

# Test basic Qt
python3 -c "from PySide6.QtWidgets import QApplication; app = QApplication([]); print('Qt OK')"
```

### Import Errors for Config/Constants

**Solution:** Ensure you're in the correct directory:
```bash
cd /home/doug/Dropbox/Projects/python\ Projects/PyPhotoOrganizer/PyPhotoOrganizer
python3 main_gui.py
```

### Progress Doesn't Update

**Possible causes:**
- Worker thread crashed (check Logs tab for errors)
- No files to process (check source directories)
- Callback not being invoked (check main_app_error.log)

---

## Success Criteria

✅ All tabs render without errors
✅ Folder selection dialogs work
✅ Settings can be saved/loaded
✅ Processing completes successfully
✅ Progress updates in real-time
✅ Time estimates are reasonably accurate
✅ Results are displayed correctly
✅ Logs are viewable and searchable
✅ Export functionality works
✅ CLI mode still works unchanged

---

## Reporting Issues

If you encounter issues, collect:

1. **Error messages** from GUI dialogs
2. **Log files:**
   - `main_app_error.log`
   - `DuplicateFileDetection_app_error.log`
3. **Python version:** `python3 --version`
4. **PySide6 version:** `python3 -c "import PySide6; print(PySide6.__version__)"`
5. **OS version:** `uname -a`
6. **Steps to reproduce** the issue

---

**Last Updated:** 2026-01-02
