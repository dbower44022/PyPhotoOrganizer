# Photo Review

A standalone application within PyPhotoOrganizer for fast visual review of archived photos.

## Features

- **Query-Based Filtering**: Filter photos by date, status, filename pattern, and more
- **Version Filtering**: View current versions, all versions, or prior versions only
- **Saved Queries**: Save and reuse common filter configurations
- **Virtual Scrolling**: Smooth performance with 10,000+ photos
- **Quick Actions**: Delete, rotate, and correct dates directly from the grid
- **Status Overlays**: Visual indicators for unreliable dates, corrections, and revisions
- **Detachable Preview**: Large preview window for detailed inspection

## Quick Start

```bash
# Run Photo Review standalone
python photo_review.py

# Or from the photo_review package directory
python -m photo_review
```

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](PHOTO_REVIEW_USER_GUIDE.md) | End-user documentation, workflows, keyboard shortcuts |
| [Architecture](PHOTO_REVIEW_ARCHITECTURE.md) | Technical documentation, class reference, API |

## Module Structure

```
photo_review/
├── __init__.py              # Package initialization
├── review_window.py         # Main window (PhotoReviewWindow)
├── query_panel.py           # Filter sidebar (QueryPanel)
├── query_builder.py         # SQL generation (PhotoQueryBuilder)
├── photo_grid_model.py      # Data model (PhotoGridModel)
├── photo_grid_view.py       # Grid widget (PhotoGridView)
├── photo_grid_delegate.py   # Item renderer (PhotoGridDelegate)
└── README.md                # This file
```

## Key Classes

| Class | Purpose |
|-------|---------|
| `PhotoReviewWindow` | Main application window, coordinates all components |
| `QueryPanel` | Left sidebar with filters, saved queries, folder browser |
| `PhotoQueryBuilder` | Generates parameterized SQL queries |
| `PhotoGridModel` | Qt model for thumbnail data |
| `PhotoGridView` | Qt view with selection and context menu |
| `PhotoGridDelegate` | Custom rendering with status overlays |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `1` / `2` / `3` | Thumbnail size (small/medium/large) |
| `Space` | Open detached preview |
| `Delete` | Delete selected to vault |
| `R` | Rotate selected |
| `D` | Correct date |
| `F5` | Run query |
| `Ctrl+A` | Select all |
| `Escape` | Deselect all |

## Requirements

- Python 3.8+
- PySide6
- PyPhotoOrganizer database

## Integration

Photo Review shares components with the main PyPhotoOrganizer application:
- Uses the same database schema
- Reuses workers (delete, rotate)
- Reuses dialogs (date correction, rotation)
- Shares thumbnail cache system

Changes made in Photo Review are immediately visible in the main application.

## Version

Current version: **1.0.0**
