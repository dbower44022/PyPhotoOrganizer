# Simplified Placeholder Fix - Eliminating QPainter

## Critical Discovery

The crash was happening **BEFORE** any of our Python paint code executed. The debug logs showed:

```
01:47:59,198 - Placeholder created: type=<class 'PySide6.QtGui.QPixmap'>, isNull=False
[APPLICATION CRASHES - No further logs]
```

**Missing from logs**:
- No `paint() ENTRY` messages
- No `data() called` messages
- No `sizeHint() called` messages

This means **Qt crashes internally during view layout**, not in our Python code.

## Root Cause Hypothesis

The original placeholder creation used `QPainter.drawText()` to render "Loading..." text:

```python
# ORIGINAL (PROBLEMATIC):
pixmap = QPixmap(size, size)
pixmap.fill(QColor(60, 60, 60))

painter = QPainter(pixmap)
painter.setPen(QPen(QColor(120, 120, 120)))

font = QFont()
font.setPointSize(max(8, size // 20))
painter.setFont(font)
painter.drawText(pixmap.rect(), Qt.AlignCenter, text)  # ← SUSPECTED CAUSE

painter.end()
return pixmap
```

**Problem**: Even though the QPixmap reports `isNull=False`, something about the text rendering creates a QPixmap that Qt's internal C++ rendering code cannot handle. This causes a segfault **before Python code is reached**.

## The Fix: Ultra-Minimal Placeholder

Simplified to the absolute minimum - just a solid color rectangle:

```python
# NEW (SIMPLIFIED):
from PySide6.QtGui import QColor

pixmap = QPixmap(size, size)

# Verify creation
if pixmap.isNull():
    logger.error("Failed to create placeholder QPixmap")
    return pixmap

# Fill with solid color - NO PAINTER, NO TEXT
pixmap.fill(QColor(80, 80, 100))  # Dark blue-gray

# Verify still valid
if pixmap.isNull():
    logger.error("Placeholder became null after fill")
    return QPixmap()

return pixmap
```

**What's eliminated**:
- ❌ QPainter creation
- ❌ Font creation
- ❌ Text rendering (`drawText`)
- ❌ Pen setup
- ❌ Painter activation
- ❌ `painter.end()` call

**What remains**:
- ✅ QPixmap(size, size) creation
- ✅ Solid color fill via `pixmap.fill(QColor)`
- ✅ Validation (isNull checks)

## Why This Should Work

`QPixmap.fill(QColor)` is a **direct C++ method** that:
- Does not use QPainter
- Does not involve font rendering
- Is the simplest possible QPixmap operation
- Cannot introduce rendering artifacts

If this still crashes, then the issue is **not with placeholder creation** but with:
- Qt's internal view layout code
- Model/View synchronization
- Memory corruption elsewhere
- Graphics driver incompatibility

## Testing

When you run the application with this fix:

1. **If it works**: The issue was QPainter/text rendering creating incompatible QPixmaps
2. **If it still crashes**: The issue is deeper in Qt's view rendering or system graphics

Expected log output:
```
INFO - Creating placeholder for 982a271a... size=256
INFO - Created simple placeholder: 256x256, isNull=False
DEBUG - paint() ENTRY - row 0
DEBUG - paint() got thumbnail: <class 'QPixmap'>, isNull=False
```

If we see `paint() ENTRY` logs, we know Qt successfully accepted the placeholder and started rendering.

## Fallback Strategy

If this simplified version still crashes, we have three options:

1. **Return None instead of placeholder** - Let delegate handle with "Loading..." text
2. **Create placeholder from PIL Image** - Use PIL to create JPEG, load as QPixmap
3. **Disable virtual scrolling** - Load all thumbnails before showing view

## Files Modified

- **triage/thumbnail_generator.py** - PlaceholderGenerator.create_placeholder()
  - Removed QPainter, Font, Text rendering
  - Simple `pixmap.fill(QColor)` only

## Summary

**Before**: QPainter + drawText → QPixmap that crashes Qt internally

**After**: QPixmap.fill(QColor) → Simplest possible placeholder

This is the **bare minimum** QPixmap creation. If this works, we've isolated the problem to text rendering. If not, the issue is elsewhere.
