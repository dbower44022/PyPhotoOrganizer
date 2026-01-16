"""
Preview Package - Unified Image Preview Components

This package provides reusable image preview widgets with consistent
functionality across the PyPhotoOrganizer application.

Components:
    - UnifiedImageViewer: Full-featured image viewer with zoom capabilities
    - ZoomableImageViewer: Alias for UnifiedImageViewer (backward compatibility)
    - ImagePreviewWidget: Alias for UnifiedImageViewer (backward compatibility)
"""

from ui.preview.zoomable_viewer import UnifiedImageViewer

# Backward compatibility aliases
ZoomableImageViewer = UnifiedImageViewer
ImagePreviewWidget = UnifiedImageViewer

__all__ = [
    'UnifiedImageViewer',
    'ZoomableImageViewer',      # Alias for backward compatibility
    'ImagePreviewWidget',       # Alias for backward compatibility
]
