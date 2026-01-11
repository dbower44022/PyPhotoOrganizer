# PyPhotoOrganizer - Improvement Roadmap

## Table of Contents

1. [Short-Term Improvements (v2.4)](#short-term-improvements-v24)
2. [Medium-Term Features (v2.5-2.6)](#medium-term-features-v25-26)
3. [Long-Term Vision (v3.0+)](#long-term-vision-v30)
4. [Performance Optimizations](#performance-optimizations)
5. [Code Quality and Testing](#code-quality-and-testing)
6. [Platform-Specific Enhancements](#platform-specific-enhancements)
7. [Data Integrity and Safety](#data-integrity-and-safety)
8. [UI/UX Enhancements](#uiux-enhancements)
9. [Architecture Improvements](#architecture-improvements)
10. [Community and Distribution](#community-and-distribution)

---

## Short-Term Improvements (v2.4)

### 1. Video Thumbnail Extraction (HIGH PRIORITY)

**Current State**: Videos show placeholder icon (play button + "VIDEO" text)

**Improvement**: Extract actual frame from video using ffmpeg

**Implementation:**
```python
# In thumbnail_generator.py
def _extract_video_frame(self, video_path: str, output_path: str) -> bool:
    """Extract first frame from video using ffmpeg."""
    try:
        import subprocess

        # ffmpeg command: extract frame at 1 second mark
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:01.000',  # 1 second in
            '-vframes', '1',         # Extract 1 frame
            '-vf', f'scale={self.size}:{self.size}:force_original_aspect_ratio=decrease',
            '-q:v', '2',             # High quality
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0

    except Exception as e:
        logger.warning(f"Video frame extraction failed: {e}")
        return False

# Usage in ThumbnailWorker.run():
if file_ext in video_extensions:
    # Try to extract frame
    if self._extract_video_frame(self.file_path, str(disk_path)):
        # Success - real video frame
        self.signals.finished.emit(self.file_hash, self.size, str(disk_path))
    else:
        # Fallback to placeholder
        placeholder = self._create_video_placeholder()
        placeholder.save(str(disk_path), 'JPEG', quality=85)
        self.signals.finished.emit(self.file_hash, self.size, str(disk_path))
```

**Benefits:**
- Users can visually identify video content
- Better than generic placeholder
- Helps with organizing and finding videos

**Considerations:**
- Requires ffmpeg installation (check availability, show warning if missing)
- Timeout needed (corrupted videos could hang)
- Fallback to placeholder if extraction fails

**Effort Estimate**: 4-6 hours

---

### 2. Thumbnail Cache Warming on Startup

**Current State**: Thumbnails generated on-demand when viewed

**Improvement**: Background cache warming for most recently accessed files

**Implementation:**
```python
# In date_corrections_tab.py
def showEvent(self, event):
    """Tab becomes visible - refresh data and warm cache."""
    super().showEvent(event)

    if self.db_metadata:
        self.refresh_data()

        # Warm cache for first 100 files in background
        if not self._cache_warmed:
            self._warm_thumbnail_cache()

def _warm_thumbnail_cache(self):
    """Pre-generate thumbnails for first 100 files in background."""
    self._cache_warmed = True

    # Get first 100 file records
    records = self.grid_model.file_items[:100]

    # Queue low-priority thumbnail generation
    for record in records:
        file_hash = record.get('file_hash')
        file_path = record.get('source_path')
        size = self.thumbnail_cache.get_current_size()

        # Check if already cached (don't regenerate)
        if not self.thumbnail_cache.has_thumbnail(file_hash, size):
            # Queue with lowest priority (won't block UI)
            self.thumbnail_cache.get_thumbnail(
                file_hash, file_path, size, priority='background'
            )
```

**Benefits:**
- Faster initial scrolling experience
- Utilizes idle CPU time
- Doesn't block UI

**Effort Estimate**: 2-3 hours

---

### 3. Keyboard Shortcuts for Date Corrections

**Current State**: Mouse-only interaction

**Improvement**: Full keyboard navigation

**Shortcuts:**
```python
# In unreliable_dates_grid_view.py
def keyPressEvent(self, event: QKeyEvent):
    """Handle keyboard shortcuts."""
    key = event.key()
    modifiers = event.modifiers()

    # Thumbnail size shortcuts
    if key == Qt.Key_1:
        self.set_thumbnail_size('small')   # 150px
    elif key == Qt.Key_2:
        self.set_thumbnail_size('medium')  # 200px
    elif key == Qt.Key_3:
        self.set_thumbnail_size('large')   # 300px

    # Navigation shortcuts
    elif key == Qt.Key_Space:
        self.open_preview_window()
    elif key == Qt.Key_Return or key == Qt.Key_Enter:
        self.open_date_correction_dialog()
    elif key == Qt.Key_Delete:
        self.mark_files_for_deletion()

    # Selection shortcuts
    elif modifiers & Qt.ControlModifier and key == Qt.Key_A:
        self.selectAll()
    elif key == Qt.Key_Escape:
        self.clearSelection()

    # Multi-file operations
    elif modifiers & Qt.ControlModifier and key == Qt.Key_D:
        self.batch_correct_dates()
    elif modifiers & Qt.ControlModifier and key == Qt.Key_R:
        self.reorganize_selected()

    else:
        super().keyPressEvent(event)
```

**Benefits:**
- Power users can work faster
- Accessibility improvement
- Matches common UI patterns (Ctrl+A, Space, Delete, etc.)

**Effort Estimate**: 2-3 hours

---

### 4. Thumbnail Regeneration Tool

**Current State**: Corrupted/missing thumbnails require manual cache cleanup

**Improvement**: "Regenerate Thumbnails" button to rebuild cache

**Implementation:**
```python
# In date_corrections_tab.py
def on_regenerate_thumbnails(self):
    """Regenerate all thumbnails for current view."""
    reply = QMessageBox.question(
        self,
        "Regenerate Thumbnails",
        f"This will delete and regenerate all thumbnails for {len(self.grid_model.file_items)} files.\n\n"
        "This may take several minutes. Continue?",
        QMessageBox.Yes | QMessageBox.No
    )

    if reply == QMessageBox.Yes:
        # Clear cache
        self.thumbnail_cache.clear_all()

        # Delete disk cache
        cache_dir = self.thumbnail_cache.cache_dir
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)

        # Clear database
        triage_db = TriageDatabase(self.db_metadata.database_path)
        triage_db.clear_thumbnail_cache()

        # Refresh view (triggers regeneration)
        self.refresh_data()

        QMessageBox.information(
            self,
            "Thumbnails Cleared",
            "Thumbnail cache cleared. Thumbnails will regenerate as you scroll."
        )
```

**UI Addition:**
```python
# Add button to toolbar
self.regenerate_btn = QPushButton("Regenerate Thumbnails")
self.regenerate_btn.clicked.connect(self.on_regenerate_thumbnails)
toolbar_layout.addWidget(self.regenerate_btn)
```

**Benefits:**
- Fix corrupted thumbnails
- Refresh thumbnails after photo edits
- User control over cache

**Effort Estimate**: 1-2 hours

---

### 5. Improve Batch Date Correction UX

**Current State**: Sequential dates increment by 1 day per file

**Improvement**: More flexible date range options

**Features:**
- **Custom increment**: 1 hour, 1 day, 1 week, custom
- **Date range spread**: Spread files evenly across date range
- **Preserve intervals**: Maintain original time gaps between files
- **Custom date pattern**: Every Monday, weekends only, etc.

**Implementation:**
```python
# In date_correction_dialog.py (batch mode)
class BatchDateOptionsDialog(QDialog):
    """Advanced options for batch date correction."""

    def __init__(self, num_files, parent=None):
        super().__init__(parent)
        self.num_files = num_files
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Mode selection
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Sequential (1 day increment)",
            "Sequential (1 hour increment)",
            "Sequential (custom increment)",
            "Spread across date range",
            "Same date for all"
        ])
        layout.addWidget(QLabel("Batch Mode:"))
        layout.addWidget(self.mode_combo)

        # Date range inputs (for spread mode)
        self.start_date = QDateEdit()
        self.end_date = QDateEdit()
        layout.addWidget(QLabel("Start Date:"))
        layout.addWidget(self.start_date)
        layout.addWidget(QLabel("End Date:"))
        layout.addWidget(self.end_date)

        # Custom increment (for custom mode)
        self.increment_spinbox = QSpinBox()
        self.increment_spinbox.setRange(1, 1000)
        self.increment_unit = QComboBox()
        self.increment_unit.addItems(["Minutes", "Hours", "Days", "Weeks"])
        layout.addWidget(QLabel("Custom Increment:"))
        increment_layout = QHBoxLayout()
        increment_layout.addWidget(self.increment_spinbox)
        increment_layout.addWidget(self.increment_unit)
        layout.addLayout(increment_layout)

        # Preview
        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        layout.addWidget(QLabel("Preview:"))
        layout.addWidget(self.preview_label)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Update preview when mode changes
        self.mode_combo.currentTextChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self):
        """Show preview of date assignment."""
        mode = self.mode_combo.currentText()

        if mode == "Sequential (1 day increment)":
            preview = f"Files will be dated:\n"
            preview += f"  File 1: {self.start_date.date().toString()}\n"
            preview += f"  File 2: {self.start_date.date().addDays(1).toString()}\n"
            preview += f"  ...\n"
            preview += f"  File {self.num_files}: {self.start_date.date().addDays(self.num_files-1).toString()}"

        elif mode == "Spread across date range":
            days_range = self.start_date.date().daysTo(self.end_date.date())
            interval = days_range / (self.num_files - 1) if self.num_files > 1 else 0
            preview = f"Files will be spread across {days_range} days\n"
            preview += f"Interval: ~{interval:.1f} days between files"

        self.preview_label.setText(preview)
```

**Benefits:**
- Handle different photo organization scenarios
- Vacation photos (sequential by day)
- Event photos (sequential by hour)
- Scanned albums (spread across known date range)

**Effort Estimate**: 6-8 hours

---

## Medium-Term Features (v2.5-2.6)

### 6. Advanced Duplicate Detection (Visual Similarity)

**Current State**: Hash-based duplicate detection (exact matches only)

**Improvement**: Detect near-duplicates using perceptual hashing

**Technologies:**
- **imagehash** library (pHash, aHash, dHash)
- **Hamming distance** for similarity scoring

**Implementation:**
```python
# New module: duplicate_similarity.py
import imagehash
from PIL import Image

class SimilarityDetector:
    """Detect visually similar images (not just exact duplicates)."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.similarity_threshold = 5  # Hamming distance threshold

    def calculate_perceptual_hash(self, image_path):
        """Calculate perceptual hash for image."""
        img = Image.open(image_path)
        return str(imagehash.phash(img))

    def find_similar_images(self, target_hash):
        """Find images with similar perceptual hash."""
        # Query database for all perceptual hashes
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT file_hash, file_path, perceptual_hash FROM UniquePhotos WHERE perceptual_hash IS NOT NULL")

        similar_images = []
        target_hash_obj = imagehash.hex_to_hash(target_hash)

        for row in cursor.fetchall():
            candidate_hash = imagehash.hex_to_hash(row[2])
            distance = target_hash_obj - candidate_hash  # Hamming distance

            if distance <= self.similarity_threshold:
                similar_images.append({
                    'file_hash': row[0],
                    'file_path': row[1],
                    'similarity_score': distance
                })

        return similar_images
```

**Database Schema:**
```sql
ALTER TABLE UniquePhotos ADD COLUMN perceptual_hash TEXT;
CREATE INDEX idx_perceptual_hash ON UniquePhotos(perceptual_hash);
```

**UI Integration:**
- New tab: "Similar Images"
- Group similar images visually
- Allow user to select "best" version
- Delete/archive other versions

**Use Cases:**
- Multiple edits of same photo (cropped, filtered, etc.)
- Burst mode photos (nearly identical shots)
- Screenshots taken multiple times

**Effort Estimate**: 12-16 hours

---

### 7. EXIF Batch Editing

**Current State**: Only date correction supported

**Improvement**: Edit multiple EXIF fields in batch

**Features:**
- Camera make/model
- Copyright/artist
- GPS location
- Description/keywords
- Rating

**Implementation:**
```python
# In ui/exif_batch_editor.py
class ExifBatchEditor(QDialog):
    """Batch edit EXIF metadata for multiple files."""

    def __init__(self, selected_records, parent=None):
        super().__init__(parent)
        self.selected_records = selected_records
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Field selection
        self.field_checkboxes = {}
        fields = [
            ('camera_make', 'Camera Make'),
            ('camera_model', 'Camera Model'),
            ('copyright', 'Copyright'),
            ('artist', 'Artist/Photographer'),
            ('description', 'Description'),
            ('keywords', 'Keywords'),
            ('gps_latitude', 'GPS Latitude'),
            ('gps_longitude', 'GPS Longitude'),
            ('rating', 'Rating (0-5)')
        ]

        for field_name, field_label in fields:
            checkbox = QCheckBox(field_label)
            line_edit = QLineEdit()
            line_edit.setEnabled(False)

            checkbox.toggled.connect(lambda checked, le=line_edit: le.setEnabled(checked))

            row_layout = QHBoxLayout()
            row_layout.addWidget(checkbox)
            row_layout.addWidget(line_edit)
            layout.addLayout(row_layout)

            self.field_checkboxes[field_name] = (checkbox, line_edit)

        # Apply button
        apply_btn = QPushButton("Apply to All Selected Files")
        apply_btn.clicked.connect(self.apply_changes)
        layout.addWidget(apply_btn)

    def apply_changes(self):
        """Apply EXIF changes to all selected files."""
        from exif_writer import write_exif_fields

        changes = {}
        for field_name, (checkbox, line_edit) in self.field_checkboxes.items():
            if checkbox.isChecked():
                changes[field_name] = line_edit.text()

        # Apply to each file
        for record in self.selected_records:
            archive_path = record.get('archive_path')
            if archive_path and os.path.exists(archive_path):
                write_exif_fields(archive_path, changes)
```

**Benefits:**
- Copyright protection (batch add copyright to all photos)
- Organization (batch add keywords/descriptions)
- GPS correction (batch set location for photos from same event)

**Effort Estimate**: 10-12 hours

---

### 8. GPS Mapping Integration

**Current State**: GPS data stored in EXIF but not visualized

**Improvement**: Interactive map showing photo locations

**Technologies:**
- **folium** (Python library for Leaflet.js maps)
- **OpenStreetMap** tiles (free, no API key required)

**Implementation:**
```python
# New tab: ui/gps_map_tab.py
import folium
from PySide6.QtWebEngineWidgets import QWebEngineView

class GpsMapTab(QWidget):
    """Tab showing photos on an interactive map."""

    def __init__(self, db_metadata, parent=None):
        super().__init__(parent)
        self.db_metadata = db_metadata
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Web view for map
        self.map_view = QWebEngineView()
        layout.addWidget(self.map_view)

        # Load photos with GPS data
        self.load_map()

    def load_map(self):
        """Load map with photo markers."""
        # Get photos with GPS data
        conn = sqlite3.connect(self.db_metadata.database_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file_path, gps_latitude, gps_longitude, creation_date
            FROM UniquePhotos
            WHERE gps_latitude IS NOT NULL AND gps_longitude IS NOT NULL
        """)

        photos = cursor.fetchall()

        if not photos:
            return

        # Create map centered on average location
        avg_lat = sum(p[1] for p in photos) / len(photos)
        avg_lon = sum(p[2] for p in photos) / len(photos)

        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=10)

        # Add markers for each photo
        for file_path, lat, lon, date in photos:
            thumbnail_path = self._get_thumbnail_path(file_path)

            popup_html = f"""
                <div style='width: 200px;'>
                    <img src='{thumbnail_path}' width='200'><br>
                    <b>Date:</b> {date}<br>
                    <b>Location:</b> {lat:.4f}, {lon:.4f}
                </div>
            """

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color='blue', icon='camera')
            ).add_to(m)

        # Save map to HTML and load in web view
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            m.save(f.name)
            self.map_view.setUrl(QUrl.fromLocalFile(f.name))
```

**Features:**
- Cluster markers when zoomed out
- Filter by date range
- Click marker to view full image
- Export map as HTML
- Batch set location (drag photos to map to set GPS)

**Effort Estimate**: 12-16 hours

---

### 9. Smart Date Detection from Filenames

**Current State**: Date extraction from EXIF and file metadata only

**Improvement**: Parse dates from filenames with common patterns

**Implementation:**
```python
# In DuplicateFileDetection.py
import re
from datetime import datetime

class FilenameDateParser:
    """Extract dates from filenames using regex patterns."""

    PATTERNS = [
        # IMG_20240115_143022.jpg
        (r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', '%Y%m%d_%H%M%S'),

        # 2024-01-15 14-30-22.jpg
        (r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})-(\d{2})-(\d{2})', '%Y-%m-%d %H-%M-%S'),

        # Screenshot_2024-01-15_143022.png
        (r'Screenshot_(\d{4})-(\d{2})-(\d{2})_(\d{6})', 'Screenshot_%Y-%m-%d_%H%M%S'),

        # Photo 15-01-2024.jpg (day-month-year)
        (r'(\d{2})-(\d{2})-(\d{4})', '%d-%m-%Y'),

        # 20240115_IMG_1234.jpg
        (r'(\d{4})(\d{2})(\d{2})_', '%Y%m%d'),
    ]

    @staticmethod
    def parse_filename_date(filename):
        """Extract date from filename if pattern matches."""
        for pattern, date_format in FilenameDateParser.PATTERNS:
            match = re.search(pattern, filename)
            if match:
                try:
                    date_str = match.group(0)
                    dt = datetime.strptime(date_str, date_format)
                    return (str(dt.year), f"{dt.month:02d}", f"{dt.day:02d}")
                except ValueError:
                    continue
        return None

# Integration in get_creation_date():
def get_creation_date(file_path):
    """Extract creation date from EXIF, filename, or OS metadata."""

    # Try EXIF first
    exif_date = _try_exif_date(file_path)
    if exif_date:
        return (*exif_date, 'exif', True)

    # Try filename parsing
    filename = os.path.basename(file_path)
    filename_date = FilenameDateParser.parse_filename_date(filename)
    if filename_date:
        return (*filename_date, 'filename', True)  # High confidence

    # Fallback to OS metadata
    os_date = _try_os_metadata(file_path)
    return (*os_date, 'os_metadata', False)
```

**Benefits:**
- Better date detection for screenshots
- Handles scanned photos with date in filename
- Improves organization accuracy

**Effort Estimate**: 4-6 hours

---

### 10. Export and Sharing Features

**Current State**: Photos organized in vault, no export tools

**Improvement**: Export photos for sharing or backup

**Features:**

**10a. Album Export:**
```python
# New module: export_album.py
class AlbumExporter:
    """Export selected photos as an album."""

    def export_as_zip(self, photo_paths, output_path, include_metadata=True):
        """Export photos as ZIP archive."""
        import zipfile

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for photo_path in photo_paths:
                # Add photo
                zipf.write(photo_path, arcname=os.path.basename(photo_path))

                # Add metadata file if requested
                if include_metadata:
                    metadata = self._extract_metadata(photo_path)
                    metadata_filename = f"{os.path.splitext(os.path.basename(photo_path))[0]}_metadata.json"
                    zipf.writestr(metadata_filename, json.dumps(metadata, indent=2))

    def export_as_html_gallery(self, photo_paths, output_dir, title="Photo Album"):
        """Export photos as HTML gallery with thumbnails."""
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        thumbs_dir = os.path.join(output_dir, 'thumbnails')
        os.makedirs(thumbs_dir, exist_ok=True)

        # Copy photos and generate thumbnails
        for photo_path in photo_paths:
            shutil.copy(photo_path, output_dir)

            # Generate thumbnail
            img = Image.open(photo_path)
            img.thumbnail((200, 200))
            thumb_filename = f"thumb_{os.path.basename(photo_path)}"
            img.save(os.path.join(thumbs_dir, thumb_filename), 'JPEG', quality=85)

        # Generate HTML
        html_content = self._generate_gallery_html(photo_paths, title)
        with open(os.path.join(output_dir, 'index.html'), 'w') as f:
            f.write(html_content)
```

**10b. Slideshow Creator:**
```python
def create_slideshow_video(self, photo_paths, output_path, duration_per_photo=3):
    """Create MP4 slideshow from photos using ffmpeg."""
    import subprocess

    # Create temporary file list
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for photo_path in photo_paths:
            f.write(f"file '{photo_path}'\n")
            f.write(f"duration {duration_per_photo}\n")
        filelist_path = f.name

    # Run ffmpeg to create video
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', filelist_path,
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        output_path
    ]

    subprocess.run(cmd, check=True)
    os.remove(filelist_path)
```

**Effort Estimate**: 10-14 hours

---

## Long-Term Vision (v3.0+)

### 11. Face Detection and Tagging

**Technology**: OpenCV or face_recognition library

**Features:**
- Detect faces in photos
- Group photos by person
- Name tagging
- Search by person

**Implementation Sketch:**
```python
import face_recognition

class FaceManager:
    """Detect and manage faces in photos."""

    def detect_faces(self, image_path):
        """Detect faces and return face encodings."""
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)
        face_encodings = face_recognition.face_encodings(image, face_locations)
        return face_encodings

    def find_similar_faces(self, target_encoding, tolerance=0.6):
        """Find photos containing similar faces."""
        # Query database for all face encodings
        # Compare using face_recognition.compare_faces()
        # Return matching photos
```

**Database Schema:**
```sql
CREATE TABLE FaceEncodings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    face_encoding BLOB NOT NULL,  -- Serialized numpy array
    face_location TEXT,  -- JSON: {top, right, bottom, left}
    person_id INTEGER,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash),
    FOREIGN KEY (person_id) REFERENCES People(id)
);

CREATE TABLE People (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    representative_face_id INTEGER,  -- Face encoding to use for matching
    FOREIGN KEY (representative_face_id) REFERENCES FaceEncodings(id)
);
```

**Effort Estimate**: 20-30 hours

---

### 12. AI-Powered Auto-Tagging

**Technology**: TensorFlow/PyTorch with pre-trained models

**Features:**
- Auto-detect scene (beach, mountains, cityscape, indoor, etc.)
- Object detection (dog, cat, car, food, etc.)
- Activity detection (wedding, birthday, vacation, etc.)
- Generate searchable keywords

**Implementation:**
```python
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input, decode_predictions
import numpy as np

class AutoTagger:
    """Automatically tag photos using AI."""

    def __init__(self):
        self.model = MobileNetV2(weights='imagenet')

    def tag_image(self, image_path):
        """Generate tags for image."""
        # Load and preprocess image
        img = Image.open(image_path).resize((224, 224))
        img_array = np.array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)

        # Predict
        predictions = self.model.predict(img_array)
        decoded = decode_predictions(predictions, top=5)

        # Extract tags
        tags = [label for (_, label, score) in decoded[0] if score > 0.1]
        return tags
```

**Database Schema:**
```sql
CREATE TABLE PhotoTags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    tag TEXT NOT NULL,
    confidence REAL,  -- AI confidence score
    source TEXT,  -- 'ai' or 'user'
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
);

CREATE INDEX idx_photo_tags_tag ON PhotoTags(tag);
```

**UI Integration:**
- Auto-tag all photos button
- Search by tag
- Tag cloud visualization
- Manual tag editing/correction

**Effort Estimate**: 25-35 hours

---

### 13. Cloud Backup Integration

**Providers**: AWS S3, Google Drive, Dropbox, Backblaze B2

**Features:**
- One-click backup to cloud
- Incremental sync (only new/modified files)
- Encryption at rest
- Bandwidth throttling
- Cost estimation

**Implementation:**
```python
# In cloud_backup.py
import boto3

class CloudBackupManager:
    """Manage cloud backups of photo archive."""

    def __init__(self, provider, credentials):
        self.provider = provider
        if provider == 'aws_s3':
            self.client = boto3.client('s3',
                aws_access_key_id=credentials['access_key'],
                aws_secret_access_key=credentials['secret_key']
            )
            self.bucket = credentials['bucket_name']

    def sync_to_cloud(self, archive_path, progress_callback=None):
        """Sync local archive to cloud storage."""
        # Get list of local files
        local_files = self._get_local_file_list(archive_path)

        # Get list of cloud files
        cloud_files = self._get_cloud_file_list()

        # Determine what needs uploading
        to_upload = set(local_files) - set(cloud_files)

        # Upload with progress
        for i, file_path in enumerate(to_upload):
            relative_path = os.path.relpath(file_path, archive_path)
            self.client.upload_file(file_path, self.bucket, relative_path)

            if progress_callback:
                progress_callback(i + 1, len(to_upload), file_path)

    def restore_from_cloud(self, cloud_path, local_path):
        """Restore files from cloud to local archive."""
        # Download files from cloud
        # Verify hashes after download
```

**UI Integration:**
- Settings tab: Cloud provider configuration
- Backup tab: View sync status, trigger manual sync
- Scheduled backups (daily, weekly, monthly)

**Effort Estimate**: 15-25 hours

---

## Performance Optimizations

### 14. Multi-Core Thumbnail Generation

**Current State**: 4 worker threads (QThreadPool)

**Improvement**: Scale to available CPU cores

**Implementation:**
```python
import multiprocessing

# In ThumbnailCache.__init__:
def __init__(self, ...):
    # Detect CPU cores
    cpu_count = multiprocessing.cpu_count()

    # Use 75% of cores for thumbnails (leave some for UI)
    worker_count = max(2, int(cpu_count * 0.75))

    self._thread_pool = QThreadPool.globalInstance()
    self._thread_pool.setMaxThreadCount(worker_count)

    logger.info(f"Thumbnail cache initialized with {worker_count} workers (CPU cores: {cpu_count})")
```

**Benefits:**
- 2-4x faster thumbnail generation on 8-16 core systems
- Better utilization of modern CPUs

**Effort Estimate**: 1 hour

---

### 15. Faster JPEG Decoding (libjpeg-turbo)

**Current State**: PIL uses standard libjpeg

**Improvement**: Use libjpeg-turbo for 2-6x faster JPEG decode

**Implementation:**
```bash
# Install libjpeg-turbo
sudo apt install libjpeg-turbo8-dev  # Linux
brew install jpeg-turbo  # macOS

# Rebuild Pillow with turbo support
pip uninstall pillow
CFLAGS="-I/usr/include/libjpeg-turbo" pip install --no-cache-dir pillow
```

**Verification:**
```python
from PIL import features
print(f"JPEG support: {features.check_codec('jpg')}")
print(f"Using libjpeg-turbo: {features.check_feature('libjpeg_turbo')}")
```

**Benefits:**
- 2-6x faster thumbnail generation for JPEG files
- Reduced CPU usage
- Better battery life on laptops

**Effort Estimate**: 2-3 hours (documentation + testing)

---

### 16. SSD vs HDD Detection and Tuning

**Current State**: Same cache settings for all drives

**Improvement**: Detect drive type and optimize settings

**Implementation:**
```python
import subprocess
import platform

class DriveOptimizer:
    """Detect drive type and optimize cache settings."""

    @staticmethod
    def is_ssd(path):
        """Detect if path is on SSD or HDD."""
        system = platform.system()

        if system == 'Linux':
            # Get device for path
            device = subprocess.check_output(['df', path]).decode().split('\n')[1].split()[0]
            device_name = os.path.basename(device).rstrip('0123456789')

            # Check if rotational (0 = SSD, 1 = HDD)
            with open(f'/sys/block/{device_name}/queue/rotational', 'r') as f:
                return f.read().strip() == '0'

        elif system == 'Windows':
            # Use Windows Management Instrumentation
            import wmi
            c = wmi.WMI()
            for disk in c.Win32_DiskDrive():
                if disk.MediaType == 'Fixed hard disk media':
                    # SSD if no RPM or RPM = 0
                    return True  # Simplified detection

        return False  # Default to HDD (conservative)

# In ThumbnailCache.__init__:
def __init__(self, ...):
    # Detect drive type
    is_ssd = DriveOptimizer.is_ssd(cache_dir)

    # Optimize settings based on drive type
    if is_ssd:
        # SSD: Larger disk cache (faster access, more IOPS)
        self.disk_size_limit = 5 * 1024 * 1024 * 1024  # 5GB
        self.memory_cache_size = 300  # Smaller memory cache
    else:
        # HDD: Smaller disk cache, larger memory cache
        self.disk_size_limit = 2 * 1024 * 1024 * 1024  # 2GB
        self.memory_cache_size = 800  # Larger to avoid disk seeks

    logger.info(f"Drive type: {'SSD' if is_ssd else 'HDD'}, cache tuned accordingly")
```

**Benefits:**
- SSD: Take advantage of fast random access
- HDD: Minimize seeks, maximize memory cache

**Effort Estimate**: 4-6 hours

---

### 17. Database Query Optimization

**Current State**: Some queries could be optimized

**Improvements:**

**17a. Add Missing Indexes:**
```sql
-- Frequently filtered columns
CREATE INDEX IF NOT EXISTS idx_unreliable_dates_reason ON UnreliableDates(flag_reason);
CREATE INDEX IF NOT EXISTS idx_unreliable_dates_corrected ON UnreliableDates(corrected_date);
CREATE INDEX IF NOT EXISTS idx_unreliable_dates_needs_reorg ON UnreliableDates(needs_reorganization);

-- Date-based queries
CREATE INDEX IF NOT EXISTS idx_unique_photos_date ON UniquePhotos(creation_date);
CREATE INDEX IF NOT EXISTS idx_unique_photos_year ON UniquePhotos(CAST(SUBSTR(creation_date, 1, 4) AS INTEGER));

-- File operation logs (already have some, but could add composite)
CREATE INDEX IF NOT EXISTS idx_filelog_session_operation ON FileProcessingLog(session_id, operation);
```

**17b. Query Optimization Examples:**
```python
# BEFORE: Full table scan
cursor.execute("SELECT * FROM UnreliableDates WHERE corrected_date IS NOT NULL")

# AFTER: Uses idx_unreliable_dates_corrected
cursor.execute("SELECT * FROM UnreliableDates WHERE corrected_date IS NOT NULL")

# BEFORE: Sort in Python
records = cursor.execute("SELECT * FROM UniquePhotos").fetchall()
sorted_records = sorted(records, key=lambda r: r['creation_date'])

# AFTER: Sort in database using index
cursor.execute("SELECT * FROM UniquePhotos ORDER BY creation_date DESC")
records = cursor.fetchall()
```

**17c. Use EXPLAIN QUERY PLAN:**
```python
# Check query performance
cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM UnreliableDates WHERE flag_reason = 'no_exif'")
plan = cursor.fetchall()
print(plan)

# Should see: "SEARCH UnreliableDates USING INDEX idx_unreliable_dates_reason"
# Bad: "SCAN UnreliableDates" (full table scan)
```

**Effort Estimate**: 3-5 hours

---

## Code Quality and Testing

### 18. Unit Testing Framework

**Current State**: No automated tests

**Improvement**: Comprehensive test suite with pytest

**Structure:**
```
tests/
├── __init__.py
├── conftest.py  # Pytest fixtures
├── test_database_metadata.py
├── test_duplicate_detection.py
├── test_thumbnail_cache.py
├── test_exif_writer.py
├── test_filename_template.py
├── test_organization_template.py
└── test_photo_filter.py
```

**Example Test:**
```python
# tests/test_thumbnail_cache.py
import pytest
import tempfile
import shutil
from pathlib import Path
from triage.thumbnail_cache import ThumbnailCache

@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield str(db_path)

@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

def test_thumbnail_cache_initialization(temp_db, temp_cache_dir):
    """Test ThumbnailCache initializes correctly."""
    cache = ThumbnailCache(
        db_path=temp_db,
        cache_dir=temp_cache_dir,
        memory_size=100,
        disk_size_gb=1,
        worker_threads=2
    )

    assert cache.db_path == temp_db
    assert cache.cache_dir == Path(temp_cache_dir)
    assert cache._memory_cache_size == 100

def test_memory_cache_lru_eviction(temp_db, temp_cache_dir):
    """Test LRU eviction when memory cache is full."""
    cache = ThumbnailCache(temp_db, temp_cache_dir, memory_size=3)

    # Add 5 items (should evict 2 oldest)
    for i in range(5):
        pixmap = QPixmap(100, 100)
        cache._add_to_memory_cache(f"hash_{i}", 100, pixmap)

    # Memory cache should have only 3 items (most recent)
    assert len(cache._memory_cache) == 3
    assert ("hash_2", 100) in cache._memory_cache
    assert ("hash_3", 100) in cache._memory_cache
    assert ("hash_4", 100) in cache._memory_cache
    assert ("hash_0", 100) not in cache._memory_cache  # Evicted
    assert ("hash_1", 100) not in cache._memory_cache  # Evicted
```

**Coverage Goals:**
- Core modules: >80% coverage
- Critical paths: 100% coverage
- UI modules: Basic smoke tests

**Effort Estimate**: 30-40 hours

---

### 19. Type Hints Throughout Codebase

**Current State**: Limited type hints

**Improvement**: Full type annotations for better IDE support and error detection

**Example:**
```python
# BEFORE:
def get_thumbnail(self, file_hash, file_path, size, priority='normal'):
    # ...

# AFTER:
from typing import Optional
from PySide6.QtGui import QPixmap

def get_thumbnail(
    self,
    file_hash: str,
    file_path: str,
    size: int,
    priority: str = 'normal'
) -> Optional[QPixmap]:
    """
    Get thumbnail from cache or trigger async generation.

    Args:
        file_hash: SHA-256 hash of source file
        file_path: Path to source image file
        size: Thumbnail size in pixels (150, 200, or 300)
        priority: Generation priority ('high', 'normal', 'low', 'background')

    Returns:
        QPixmap if available in cache, None if generation queued
    """
    # ...
```

**Tools:**
- mypy for static type checking
- pyright for IDE integration

**Effort Estimate**: 15-20 hours

---

### 20. Continuous Integration (CI)

**Platform**: GitHub Actions

**Configuration:**
```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.9', '3.10', '3.11', '3.12']

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        pytest tests/ --cov=. --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v2
      with:
        files: ./coverage.xml
```

**Benefits:**
- Catch regressions before merge
- Test on multiple platforms/Python versions
- Track code coverage trends

**Effort Estimate**: 4-6 hours

---

## Platform-Specific Enhancements

### 21. macOS Integration

**Features:**
- Sandbox support (for Mac App Store distribution)
- Spotlight integration (index photos for system search)
- Quick Look plugin (preview in Finder)
- Notification Center integration

**Implementation:**
```python
# macOS-specific code in utils.py
if platform.system() == 'Darwin':
    # Spotlight metadata indexing
    import subprocess

    def index_for_spotlight(file_path, metadata):
        """Add metadata to Spotlight index."""
        # Use mdimport or xattr to add metadata
        subprocess.run(['mdimport', file_path])
```

**Effort Estimate**: 10-15 hours

---

### 22. Linux Packaging

**Formats:**
- AppImage (portable, universal)
- .deb (Debian/Ubuntu)
- .rpm (Fedora/RHEL)
- Flatpak (Sandboxed)

**Example AppImage:**
```bash
# Build script: build_appimage.sh
#!/bin/bash

# Install dependencies
pip install -r requirements.txt --target=./appdir/usr/lib/python3/site-packages

# Copy application files
cp -r *.py ui/ triage/ appdir/usr/bin/

# Create AppImage
appimagetool appdir PyPhotoOrganizer.AppImage
```

**Effort Estimate**: 8-12 hours

---

### 23. Windows Installer

**Tool**: Inno Setup or NSIS

**Features:**
- Start menu shortcuts
- Desktop icon
- File associations (.db files open with app)
- Uninstaller

**Inno Setup Script:**
```ini
[Setup]
AppName=PyPhotoOrganizer
AppVersion=2.4
DefaultDirName={pf}\PyPhotoOrganizer
DefaultGroupName=PyPhotoOrganizer
OutputBaseFilename=PyPhotoOrganizer_Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\PyPhotoOrganizer\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\PyPhotoOrganizer"; Filename: "{app}\PyPhotoOrganizer.exe"
Name: "{commondesktop}\PyPhotoOrganizer"; Filename: "{app}\PyPhotoOrganizer.exe"

[Registry]
Root: HKCR; Subkey: ".ppodb"; ValueData: "PyPhotoOrganizer.Database"; Flags: uninsdeletevalue
```

**Effort Estimate**: 6-10 hours

---

## Data Integrity and Safety

### 24. Hash Verification After Copy

**Current State**: Files copied without verification

**Improvement**: Verify hash after copy to ensure integrity

**Implementation:**
```python
# In main.py, organize_files()
def copy_with_verification(source_path, dest_path, expected_hash):
    """Copy file and verify hash matches."""
    # Copy file
    shutil.copy2(source_path, dest_path)

    # Verify hash
    actual_hash = hash_file(dest_path)

    if actual_hash != expected_hash:
        # Hash mismatch - file corrupted during copy
        logger.error(f"Hash verification failed for {dest_path}")
        logger.error(f"  Expected: {expected_hash}")
        logger.error(f"  Actual:   {actual_hash}")

        # Delete corrupted file
        os.remove(dest_path)

        raise IOError(f"File copy verification failed: {os.path.basename(dest_path)}")

    return True
```

**Benefits:**
- Detect disk errors during copy
- Ensure archive integrity
- Catch corrupted source files

**Effort Estimate**: 2-3 hours

---

### 25. Periodic Integrity Checks

**Feature**: Scan entire archive and verify all file hashes

**Implementation:**
```python
# New module: integrity_checker.py
class IntegrityChecker:
    """Verify archive integrity by checking file hashes."""

    def __init__(self, db_metadata):
        self.db_metadata = db_metadata

    def check_all_files(self, progress_callback=None):
        """Check integrity of all files in archive."""
        conn = sqlite3.connect(self.db_metadata.database_path)
        cursor = conn.cursor()

        cursor.execute("SELECT file_hash, file_path FROM UniquePhotos")
        all_files = cursor.fetchall()

        results = {
            'total': len(all_files),
            'verified': 0,
            'missing': [],
            'corrupted': [],
            'errors': []
        }

        for i, (expected_hash, file_path) in enumerate(all_files):
            try:
                # Check if file exists
                if not os.path.exists(file_path):
                    results['missing'].append(file_path)
                    continue

                # Verify hash
                actual_hash = hash_file(file_path)

                if actual_hash == expected_hash:
                    results['verified'] += 1
                else:
                    results['corrupted'].append({
                        'path': file_path,
                        'expected_hash': expected_hash,
                        'actual_hash': actual_hash
                    })

            except Exception as e:
                results['errors'].append({
                    'path': file_path,
                    'error': str(e)
                })

            if progress_callback:
                progress_callback(i + 1, len(all_files))

        return results
```

**UI Integration:**
- Settings tab: "Check Archive Integrity" button
- Progress dialog showing verification status
- Detailed report of issues found

**Effort Estimate**: 6-8 hours

---

### 26. Database Backup and Restore

**Current State**: No built-in backup tools

**Improvement**: Automatic database backups

**Implementation:**
```python
# In database_metadata.py
def backup_database(self, backup_path=None):
    """Create backup of database."""
    if backup_path is None:
        # Default: database_name_YYYYMMDD_HHMMSS.db.backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_dir = os.path.dirname(self.database_path)
        db_name = os.path.basename(self.database_path)
        backup_path = os.path.join(db_dir, f"{db_name}_{timestamp}.backup")

    # Use SQLite backup API for safe backup
    source_conn = sqlite3.connect(self.database_path)
    backup_conn = sqlite3.connect(backup_path)

    with backup_conn:
        source_conn.backup(backup_conn)

    source_conn.close()
    backup_conn.close()

    logger.info(f"Database backed up to: {backup_path}")
    return backup_path

def restore_database(self, backup_path):
    """Restore database from backup."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    # Create safety backup of current database
    safety_backup = self.backup_database()

    try:
        # Restore from backup
        backup_conn = sqlite3.connect(backup_path)
        restore_conn = sqlite3.connect(self.database_path)

        with restore_conn:
            backup_conn.backup(restore_conn)

        backup_conn.close()
        restore_conn.close()

        logger.info(f"Database restored from: {backup_path}")

    except Exception as e:
        # Restore failed - revert to safety backup
        logger.error(f"Restore failed: {e}")
        shutil.copy(safety_backup, self.database_path)
        raise
```

**Features:**
- Automatic daily backups
- Keep last N backups (configurable)
- One-click restore from backup list

**Effort Estimate**: 4-6 hours

---

## UI/UX Enhancements

### 27. Dark Mode Support

**Current State**: Light theme only

**Improvement**: Dark theme option

**Implementation:**
```python
# In main_window.py
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._apply_theme()

    def _apply_theme(self):
        """Apply dark or light theme based on settings."""
        theme = self.db_metadata.get_theme() if self.db_metadata else 'light'

        if theme == 'dark':
            # Dark theme stylesheet
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                }
                QTableView {
                    background-color: #252526;
                    gridline-color: #3e3e3e;
                    selection-background-color: #094771;
                }
                QHeaderView::section {
                    background-color: #2d2d30;
                    color: #d4d4d4;
                    border: 1px solid #3e3e3e;
                }
                QPushButton {
                    background-color: #0e639c;
                    color: #ffffff;
                    border: none;
                    padding: 5px 15px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
            """)
        else:
            # Light theme (default Qt style)
            self.setStyleSheet("")
```

**UI Toggle:**
- Settings tab: "Theme" dropdown (Light/Dark/System)
- Respects system theme preference

**Effort Estimate**: 6-8 hours

---

### 28. Customizable Grid Layouts

**Current State**: IconMode grid only

**Improvement**: Multiple view modes

**Modes:**
- **Grid (current)**: Thumbnails in grid
- **List**: Thumbnails + metadata in rows
- **Detail**: Large thumbnails + full EXIF sidebar
- **Timeline**: Chronological with date headers

**Implementation:**
```python
# In date_corrections_tab.py
def on_view_mode_changed(self, mode):
    """Switch between view modes."""
    if mode == 'grid':
        self.grid_view.setViewMode(QListView.IconMode)
        self.grid_view.setSpacing(2)

    elif mode == 'list':
        self.grid_view.setViewMode(QListView.ListMode)
        self.grid_view.setSpacing(0)
        # Use different delegate for list mode

    elif mode == 'timeline':
        # Group by date and show headers
        self._setup_timeline_view()
```

**Effort Estimate**: 10-14 hours

---

### 29. Drag-and-Drop Organization

**Current State**: Manual date correction only

**Improvement**: Drag files to calendar to set dates

**Implementation:**
```python
# New widget: DraggableCalendar
class DraggableCalendar(QCalendarWidget):
    """Calendar that accepts dropped files and sets their dates."""

    files_dropped = Signal(list, QDate)  # file_hashes, target_date

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        """Accept drag if it contains file hashes."""
        if event.mimeData().hasFormat('application/x-photo-hashes'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle dropped files - emit signal with target date."""
        file_hashes_json = event.mimeData().data('application/x-photo-hashes')
        file_hashes = json.loads(bytes(file_hashes_json).decode())

        # Get date from calendar position
        target_date = self.dateAt(event.pos())

        # Emit signal
        self.files_dropped.emit(file_hashes, target_date)
```

**UI Integration:**
- Show calendar in Date Corrections tab
- Drag thumbnails from grid to calendar
- Batch set date for all dropped files

**Effort Estimate**: 8-12 hours

---

## Architecture Improvements

### 30. Plugin System

**Vision**: Allow third-party extensions

**Architecture:**
```python
# New module: plugin_manager.py
class PluginManager:
    """Load and manage plugins."""

    def __init__(self):
        self.plugins = {}
        self.plugin_dir = Path.home() / '.pyphotorganizer' / 'plugins'
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    def load_plugins(self):
        """Load all plugins from plugin directory."""
        for plugin_path in self.plugin_dir.glob('*.py'):
            try:
                spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Plugin must have register_plugin() function
                if hasattr(module, 'register_plugin'):
                    plugin = module.register_plugin()
                    self.plugins[plugin.name] = plugin
                    logger.info(f"Loaded plugin: {plugin.name}")

            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_path}: {e}")
```

**Plugin Interface:**
```python
# Example plugin: custom_export.py
class ExportPlugin:
    """Base class for export plugins."""

    name = "Custom Export"
    version = "1.0"

    def export(self, photos, output_path):
        """Export photos in custom format."""
        raise NotImplementedError

def register_plugin():
    """Called by plugin manager to register plugin."""
    return MyCustomExporter()

class MyCustomExporter(ExportPlugin):
    name = "Instagram Grid Export"

    def export(self, photos, output_path):
        # Create Instagram-style 3x3 grid collages
        # ...
```

**Plugin Types:**
- Export formats (PDF, slideshow, web gallery)
- Import sources (Google Photos, iCloud, Flickr)
- Image effects (watermark, resize, filters)
- Metadata editors (GPS, keywords, ratings)

**Effort Estimate**: 15-20 hours

---

## Community and Distribution

### 31. Documentation Website

**Technology**: MkDocs or Sphinx

**Structure:**
```
docs/
├── index.md
├── getting-started/
│   ├── installation.md
│   ├── first-run.md
│   └── basic-workflow.md
├── user-guide/
│   ├── organizing-photos.md
│   ├── date-corrections.md
│   ├── duplicate-detection.md
│   └── settings.md
├── advanced/
│   ├── filename-templates.md
│   ├── organization-templates.md
│   └── batch-operations.md
├── developer/
│   ├── architecture.md
│   ├── contributing.md
│   └── plugin-development.md
└── api/
    └── reference.md
```

**Hosting**: GitHub Pages or Read the Docs

**Effort Estimate**: 20-30 hours

---

### 32. Video Tutorials

**Topics:**
- Getting started (10 min)
- Organizing your first collection (15 min)
- Date corrections workflow (8 min)
- Advanced features (12 min)

**Platform**: YouTube

**Effort Estimate**: 15-25 hours

---

### 33. PyPI Package

**Goal**: `pip install pyphotorganizer`

**Setup:**
```python
# setup.py
from setuptools import setup, find_packages

setup(
    name='pyphotorganizer',
    version='2.4.0',
    description='Deduplicate and organize photo collections',
    author='Doug Bower',
    packages=find_packages(),
    install_requires=[
        'PySide6>=6.4',
        'Pillow>=9.0',
        'piexif>=1.1',
        'tqdm>=4.60'
    ],
    entry_points={
        'console_scripts': [
            'pyphotorganizer=main_gui:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.9',
    ],
)
```

**Effort Estimate**: 4-6 hours

---

## Priority Matrix

| Priority | Effort | Feature |
|----------|--------|---------|
| HIGH | 4-6h | Video Thumbnail Extraction |
| HIGH | 2-3h | Keyboard Shortcuts |
| HIGH | 2-3h | Thumbnail Cache Warming |
| HIGH | 6-8h | Batch Date Improvements |
| MEDIUM | 1-2h | Thumbnail Regeneration Tool |
| MEDIUM | 12-16h | Visual Similarity Detection |
| MEDIUM | 10-12h | EXIF Batch Editing |
| MEDIUM | 3-5h | Database Query Optimization |
| MEDIUM | 6-8h | Dark Mode Support |
| LOW | 12-16h | GPS Mapping Integration |
| LOW | 10-14h | Export Features |
| LOW | 30-40h | Unit Testing Framework |
| LOW | 20-30h | Face Detection |

---

## Summary

The improvement roadmap covers:
- **Short-term** (v2.4): Video thumbnails, keyboard shortcuts, cache warming
- **Medium-term** (v2.5-2.6): Duplicate similarity, EXIF editing, GPS mapping
- **Long-term** (v3.0+): AI tagging, face detection, cloud backup
- **Performance**: Multi-core scaling, SSD optimization, query tuning
- **Quality**: Testing, type hints, CI/CD
- **Platform**: macOS integration, Linux packaging, Windows installer
- **Safety**: Hash verification, integrity checks, backups
- **UX**: Dark mode, custom layouts, drag-and-drop
- **Architecture**: Plugin system, modular design

**Recommended Next Steps:**
1. **v2.4 Release**: Focus on high-priority, low-effort improvements
   - Video thumbnail extraction (4-6h)
   - Keyboard shortcuts (2-3h)
   - Cache warming (2-3h)
   - Thumbnail regeneration (1-2h)
   - Total: ~15 hours

2. **v2.5 Release**: Medium-priority features
   - Batch date improvements (6-8h)
   - EXIF batch editing (10-12h)
   - Database optimization (3-5h)
   - Dark mode (6-8h)
   - Total: ~30 hours

3. **v3.0 Release**: Major features
   - Visual similarity detection (12-16h)
   - GPS mapping (12-16h)
   - Face detection (20-30h)
   - Total: ~60 hours
