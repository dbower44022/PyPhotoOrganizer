# Photo Review User Guide

**Version 1.0.0**

Photo Review is a standalone application within PyPhotoOrganizer for fast visual review of archived photos. It provides powerful query-based filtering, saved queries, and quick actions for managing your photo archive.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Query System](#query-system)
4. [Filtering Photos](#filtering-photos)
5. [Working with Photos](#working-with-photos)
6. [Actions](#actions)
7. [Keyboard Shortcuts](#keyboard-shortcuts)
8. [Tips and Best Practices](#tips-and-best-practices)

---

## Getting Started

### Launching Photo Review

Run the standalone application:

```bash
python photo_review.py
```

### Database Selection

On startup, you must select a PyPhotoOrganizer database:

1. **Browse Existing**: Navigate to find an existing `.db` file
2. **Recent Databases**: Select from recently used databases
3. **Create New**: Create a new database (requires configuring archive location)

The selected database determines which photo archive you'll be reviewing.

---

## Interface Overview

```
+------------------------------------------------------------------+
|  Photo Review - [Database Name]                                  |
+------------------------------------------------------------------+
|  File  |  Query  |  View  |  Actions  |  Help                    |
+------------------------------------------------------------------+
| +-------------+ +----------------------------------------------+ |
| | Query Panel | |                                              | |
| |   [300px]   | |           Thumbnail Grid                     | |
| |             | |                                              | |
| | - Saved     | |   Virtual scrolling for 10,000+ items        | |
| |   Queries   | |   Shift/Ctrl multi-select                    | |
| | - Search    | |   Right-click context menu                   | |
| | - Date      | |                                              | |
| |   Filters   | +----------------------------------------------+ |
| | - Status    | |           Preview Panel (collapsible)        | |
| |   Filters   | |           Rubber band zoom                   | |
| | - Folder    | |           Double-click to detach             | |
| |   Browser   | |                                              | |
| +-------------+ +----------------------------------------------+ |
+------------------------------------------------------------------+
|  1,247 photos | Selected: 15 | Query: "2024 January"             |
+------------------------------------------------------------------+
```

### Main Components

| Component | Description |
|-----------|-------------|
| **Query Panel** | Left sidebar with filters, saved queries, and folder browser |
| **Thumbnail Grid** | Main photo display area with virtual scrolling |
| **Preview Panel** | Bottom panel showing selected photo (collapsible) |
| **Status Bar** | Photo count, selection count, current query info |

---

## Query System

### Saved Queries

The saved queries dropdown provides quick access to frequently used filters:

- **System Queries** (built-in, cannot be deleted):
  - "All Photos" - Browse entire archive
  - "Recent Imports (7 Days)" - Recently added photos
  - "Unreliable Dates - Pending" - Files needing date correction
  - "Needs Reorganization" - Corrected files waiting to be moved
  - "Photos This Year" - Current year's photos

- **User Queries**: Your custom saved queries

#### Saving a Query

1. Configure your desired filters
2. Click **Save** or press **Ctrl+S**
3. Enter a descriptive name
4. Query is saved for future use

#### Query Usage Tracking

The system tracks when queries are used and sorts by most recent usage.

---

## Filtering Photos

### Version Filter

The "Show" dropdown filters photos by their revision status:

| Option | Description |
|--------|-------------|
| **Current Versions Only** | Shows only the latest version of each photo (files in main archive) |
| **All Versions** | Shows all photos including prior revisions |
| **Prior Versions Only** | Shows only superseded versions (files moved after rotation) |

**Default**: Current Versions Only

### Search

The search box performs full-text search across:
- Filename
- File path
- Original date
- Flag reason

Search is case-insensitive and supports partial matches.

### Date Filters

#### Creation Date
Filter photos by their creation date (from EXIF or file metadata):
- Use the date pickers to set a range
- Quick buttons: **Today**, **7 Days**, **30 Days**
- Check "Filter by creation date" to enable

#### Correction Date
Filter by when dates were corrected:
- Shows only photos that have had their dates manually corrected
- Useful for reviewing recent corrections

### Status Filters

| Filter | Description |
|--------|-------------|
| **Has unreliable date** | Photos flagged with questionable date information |
| **Needs date correction** | Unreliable dates not yet corrected |
| **Needs reorganization** | Corrected photos waiting to be moved to correct folder |
| **Has revisions** | Photos that have been rotated (have prior versions) |

### Filename Pattern

Filter by filename pattern (substring match):
- Example: `IMG_` finds all files containing "IMG_"
- Example: `vacation` finds files with "vacation" in the name

### Folder Browser

Navigate your archive structure:
- Click a year to see months
- Click a month to see days
- Click a folder to view its contents
- Photo counts shown next to each folder

---

## Working with Photos

### Thumbnail Grid

The main grid displays photos as thumbnails with status overlays.

#### Thumbnail Sizes

| Key | Size | Best For |
|-----|------|----------|
| **1** | Small (150px) | Overview of many photos |
| **2** | Medium (200px) | Balanced view (default) |
| **3** | Large (300px) | Detailed inspection |

#### Status Overlays

Colored badges in the top-right corner indicate status:

| Color | Symbol | Meaning |
|-------|--------|---------|
| Yellow/Orange | **?** | Unreliable date - needs correction |
| Green | **!** | Date corrected - needs reorganization |
| Blue | **✓** | Reorganized - complete |
| Purple | **R** | Has revisions (was rotated) |

#### Selection

- **Click**: Select single item
- **Ctrl+Click**: Toggle selection (add/remove)
- **Shift+Click**: Select range from last click
- **Ctrl+A**: Select all
- **Escape**: Deselect all

### Preview Panel

The bottom preview panel shows the selected photo:
- **Single selection**: Shows full preview
- **Rubber band zoom**: Click and drag to zoom into a region
- **Double-click**: Reset zoom to fit
- **Press P**: Toggle panel visibility

### Detached Preview Window

For detailed inspection on a second monitor:
- **Double-click** a thumbnail to open detached preview
- **Press Space** on selected item
- Window shows:
  - Large zoomable image
  - File details (paths, dates, status)
  - Action buttons (Open File, Copy Path, Correct Date)

---

## Actions

### Delete to Vault

Move selected photos to the Delete Vault (soft delete):

1. Select photos to delete
2. Press **Delete** or use right-click menu
3. Confirm deletion
4. Files are moved to Delete Vault (can be restored later)

**Note**: Requires Delete Vault to be configured in main application settings.

### Rotate Image

Rotate selected photos:

1. Select photos to rotate
2. Press **R** or **Ctrl+R** or use right-click menu
3. Choose rotation angle (90° CW, 90° CCW, 180°, or custom)
4. Original is moved to Prior Revision Archive
5. Rotated version takes its place in main archive

**Note**: Requires Prior Revision Archive to be configured.

### Correct Date

Fix incorrect dates on photos:

1. Select photos to correct
2. Press **D** or **Ctrl+D** or use right-click menu
3. For single file: Enter the correct date
4. For multiple files:
   - **Same date**: Apply same date to all
   - **Sequential dates**: Increment by 1 day per file
5. Options:
   - Write EXIF to archive file (recommended)
   - Mark for reorganization (moves to correct date folder)

### Open File

Open selected photo in default image viewer:
- Press **Ctrl+O** or use right-click menu

### Open in Folder

Open the folder containing the selected photo:
- Press **Ctrl+E** or use right-click menu
- On Windows: Opens Explorer with file selected
- On macOS: Opens Finder with file revealed
- On Linux: Opens file manager in folder

### Copy Path

Copy the full file path to clipboard:
- Use right-click menu → Copy Path

### Refresh Thumbnail

Force regeneration of thumbnail for selected photos:
- Use right-click menu → Refresh Thumbnail
- Useful if file was modified externally

---

## Keyboard Shortcuts

### View

| Shortcut | Action |
|----------|--------|
| **1** | Small thumbnails (150px) |
| **2** | Medium thumbnails (200px) |
| **3** | Large thumbnails (300px) |
| **P** | Toggle preview panel |
| **Space** | Show selected in detached preview |

### Selection

| Shortcut | Action |
|----------|--------|
| **Ctrl+A** | Select all |
| **Escape** | Deselect all |
| **Shift+Click** | Select range |
| **Ctrl+Click** | Toggle selection |

### Actions

| Shortcut | Action |
|----------|--------|
| **Delete** | Delete selected to vault |
| **R** or **Ctrl+R** | Rotate selected |
| **D** or **Ctrl+D** | Correct date |
| **Ctrl+O** | Open file |
| **Ctrl+E** | Open in folder |

### Query

| Shortcut | Action |
|----------|--------|
| **F5** | Run query |
| **Ctrl+S** | Save current query |
| **Ctrl+Shift+C** | Clear all filters |
| **Ctrl+O** | Open different database |
| **Ctrl+Q** | Exit application |

---

## Tips and Best Practices

### Performance Tips

1. **Use filters**: Narrow down results instead of loading entire archive
2. **Smaller thumbnails**: Use size 1 or 2 when reviewing many photos
3. **Version filter**: Keep on "Current Versions Only" unless reviewing revisions

### Workflow: Reviewing Unreliable Dates

1. Select saved query: "Unreliable Dates - Pending"
2. Review each photo in preview
3. For photos with known dates:
   - Select multiple from same event
   - Use batch correction with sequential dates
4. After correcting, run "Needs Reorganization" query
5. Click "Reorganize All Marked" in main application

### Workflow: Cleaning Up Duplicates

1. Browse by folder or date
2. Look for similar thumbnails
3. Select duplicates to remove
4. Delete to vault (can restore if mistake)

### Workflow: Reviewing Rotations

1. Set version filter to "All Versions"
2. Look for photos with purple "R" overlay
3. Compare current and prior versions
4. Can restore prior version if rotation was wrong

### Saving Custom Queries

Create queries for your common review tasks:
- "Vacation 2024" - Date range for a specific trip
- "Phone Photos" - Filename pattern "IMG_" or "PXL_"
- "Large Files" - Use filename pattern with file info
- "Recent Corrections" - Correction date last 7 days

---

## Troubleshooting

### Thumbnails Show "Loading..."

- Thumbnails are generated on-demand
- Large files take longer to process
- Check that file exists at shown path

### "Corrupted" Placeholder Shown

- File may be damaged or incomplete
- Try opening the file directly to verify
- Consider deleting corrupted files

### Photos Not Appearing

- Check version filter (set to "All Versions" to see everything)
- Verify files weren't deleted (check Delete Vault)
- Run query again (F5)

### Prior Revision Archive Not Configured

- Required for rotation feature
- Configure in main application: Archive Settings → Prior Revision Archive

### Delete Vault Not Configured

- Required for delete feature
- Configure in main application: System Settings → Delete Vault Location
