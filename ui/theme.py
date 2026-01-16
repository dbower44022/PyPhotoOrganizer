"""
Modern Theme System for PyPhotoOrganizer

Provides centralized theming with light/dark mode support, modern color palette,
and consistent styling across all components.

Usage:
    from ui.theme import Theme, ThemeManager

    # Get current theme
    theme = ThemeManager.get_theme()

    # Apply to widget
    widget.setStyleSheet(theme.get_widget_style('button'))

    # Toggle theme
    ThemeManager.set_dark_mode(True)
"""

from dataclasses import dataclass
from typing import Optional
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import QSettings


@dataclass
class ColorPalette:
    """Modern color palette with semantic naming."""

    # Primary brand colors
    primary: str = "#0066FF"  # Vibrant blue
    primary_hover: str = "#0052CC"
    primary_light: str = "#E6F0FF"

    # Status colors (modern, accessible)
    success: str = "#10B981"  # Emerald green
    success_light: str = "#D1FAE5"
    warning: str = "#F59E0B"  # Amber
    warning_light: str = "#FEF3C7"
    error: str = "#EF4444"  # Red
    error_light: str = "#FEE2E2"
    info: str = "#0EA5E9"  # Sky blue
    info_light: str = "#E0F2FE"

    # Photo status colors (for overlays)
    status_unreliable: str = "#F59E0B"  # Amber - needs attention
    status_corrected: str = "#10B981"  # Emerald - corrected, needs reorg
    status_reorganized: str = "#0EA5E9"  # Sky - complete
    status_revision: str = "#8B5CF6"  # Violet - has revisions

    # Neutral grays
    gray_50: str = "#FAFAFA"
    gray_100: str = "#F5F5F5"
    gray_200: str = "#E5E5E5"
    gray_300: str = "#D4D4D4"
    gray_400: str = "#A3A3A3"
    gray_500: str = "#737373"
    gray_600: str = "#525252"
    gray_700: str = "#404040"
    gray_800: str = "#262626"
    gray_900: str = "#171717"

    # Backgrounds
    bg_primary: str = "#FFFFFF"
    bg_secondary: str = "#F5F5F5"
    bg_tertiary: str = "#E5E5E5"

    # Text
    text_primary: str = "#171717"
    text_secondary: str = "#525252"
    text_muted: str = "#737373"
    text_disabled: str = "#A3A3A3"

    # Borders
    border_light: str = "#E5E5E5"
    border_medium: str = "#D4D4D4"

    # Selection
    selection_bg: str = "rgba(0, 102, 255, 0.15)"
    selection_border: str = "#0066FF"
    hover_bg: str = "rgba(0, 102, 255, 0.08)"


@dataclass
class DarkColorPalette(ColorPalette):
    """Dark theme color overrides."""

    # Backgrounds
    bg_primary: str = "#1A1A1A"
    bg_secondary: str = "#262626"
    bg_tertiary: str = "#333333"

    # Text
    text_primary: str = "#FAFAFA"
    text_secondary: str = "#A3A3A3"
    text_muted: str = "#737373"
    text_disabled: str = "#525252"

    # Borders
    border_light: str = "#404040"
    border_medium: str = "#525252"

    # Grays adjusted for dark mode
    gray_50: str = "#262626"
    gray_100: str = "#333333"
    gray_200: str = "#404040"
    gray_300: str = "#525252"

    # Selection (slightly brighter for dark mode)
    selection_bg: str = "rgba(0, 102, 255, 0.25)"
    hover_bg: str = "rgba(0, 102, 255, 0.12)"


class Theme:
    """
    Complete theme definition with colors, fonts, spacing, and component styles.
    """

    def __init__(self, dark_mode: bool = False):
        self.dark_mode = dark_mode
        self.colors = DarkColorPalette() if dark_mode else ColorPalette()

        # Spacing scale (4px base)
        self.spacing = {
            'xs': 4,
            'sm': 8,
            'md': 12,
            'lg': 16,
            'xl': 24,
            'xxl': 32,
        }

        # Border radius
        self.radius = {
            'sm': 4,
            'md': 8,
            'lg': 12,
            'xl': 16,
            'full': 9999,
        }

        # Font sizes
        self.font_size = {
            'xs': 11,
            'sm': 12,
            'md': 14,
            'lg': 16,
            'xl': 18,
            'xxl': 24,
        }

    def get_status_color(self, status: str) -> QColor:
        """Get QColor for photo status."""
        status_map = {
            'unreliable': self.colors.status_unreliable,
            'corrected': self.colors.status_corrected,
            'reorganized': self.colors.status_reorganized,
            'revision': self.colors.status_revision,
        }
        hex_color = status_map.get(status, self.colors.gray_500)
        return QColor(hex_color)

    def get_status_colors_dict(self) -> dict:
        """Get all status colors as QColor dict for delegate."""
        return {
            'unreliable': QColor(self.colors.status_unreliable),
            'corrected': QColor(self.colors.status_corrected),
            'reorganized': QColor(self.colors.status_reorganized),
            'revision': QColor(self.colors.status_revision),
            'normal': None,
        }

    def get_global_stylesheet(self) -> str:
        """Get global application stylesheet."""
        c = self.colors
        return f"""
            /* Global styles */
            QWidget {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                font-size: {self.font_size['md']}px;
            }}

            /* Main window */
            QMainWindow {{
                background-color: {c.bg_primary};
            }}

            /* Buttons */
            QPushButton {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_medium};
                border-radius: {self.radius['md']}px;
                padding: {self.spacing['sm']}px {self.spacing['md']}px;
                color: {c.text_primary};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c.bg_tertiary};
                border-color: {c.primary};
            }}
            QPushButton:pressed {{
                background-color: {c.primary_light if not self.dark_mode else c.gray_700};
            }}
            QPushButton:disabled {{
                background-color: {c.bg_secondary};
                color: {c.text_disabled};
                border-color: {c.border_light};
            }}

            /* Primary button */
            QPushButton[cssClass="primary"] {{
                background-color: {c.primary};
                border-color: {c.primary};
                color: white;
            }}
            QPushButton[cssClass="primary"]:hover {{
                background-color: {c.primary_hover};
            }}

            /* Input fields */
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_medium};
                border-radius: {self.radius['md']}px;
                padding: {self.spacing['sm']}px {self.spacing['md']}px;
                color: {c.text_primary};
                selection-background-color: {c.primary};
            }}
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border-color: {c.primary};
                outline: none;
            }}
            QLineEdit:disabled {{
                background-color: {c.bg_secondary};
                color: {c.text_disabled};
            }}

            /* Combo boxes */
            QComboBox {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_medium};
                border-radius: {self.radius['md']}px;
                padding: {self.spacing['sm']}px {self.spacing['md']}px;
                color: {c.text_primary};
            }}
            QComboBox:hover {{
                border-color: {c.primary};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {c.text_secondary};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_medium};
                border-radius: {self.radius['md']}px;
                selection-background-color: {c.primary_light if not self.dark_mode else c.gray_700};
            }}

            /* Checkboxes */
            QCheckBox {{
                spacing: {self.spacing['sm']}px;
                color: {c.text_primary};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {c.border_medium};
                border-radius: {self.radius['sm']}px;
                background-color: {c.bg_primary};
            }}
            QCheckBox::indicator:hover {{
                border-color: {c.primary};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c.primary};
                border-color: {c.primary};
            }}

            /* Group boxes */
            QGroupBox {{
                font-weight: 600;
                border: 1px solid {c.border_light};
                border-radius: {self.radius['lg']}px;
                margin-top: 12px;
                padding-top: 8px;
                background-color: {c.bg_secondary};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                color: {c.text_primary};
                background-color: {c.bg_secondary};
            }}

            /* Scroll areas */
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}

            /* Scroll bars */
            QScrollBar:vertical {{
                background-color: {c.bg_secondary};
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.gray_400};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.gray_500};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background-color: {c.bg_secondary};
                height: 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {c.gray_400};
                border-radius: 5px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c.gray_500};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}

            /* Labels */
            QLabel {{
                color: {c.text_primary};
            }}

            /* Tree widget */
            QTreeWidget {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: {self.radius['md']}px;
                alternate-background-color: {c.bg_secondary};
            }}
            QTreeWidget::item {{
                padding: {self.spacing['xs']}px;
            }}
            QTreeWidget::item:selected {{
                background-color: {c.selection_bg};
                color: {c.text_primary};
            }}
            QTreeWidget::item:hover {{
                background-color: {c.hover_bg};
            }}

            /* Date edit */
            QDateEdit {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_medium};
                border-radius: {self.radius['md']}px;
                padding: {self.spacing['xs']}px {self.spacing['sm']}px;
                color: {c.text_primary};
            }}
            QDateEdit:focus {{
                border-color: {c.primary};
            }}

            /* Status bar */
            QStatusBar {{
                background-color: {c.bg_secondary};
                border-top: 1px solid {c.border_light};
                color: {c.text_secondary};
            }}

            /* Menu bar */
            QMenuBar {{
                background-color: {c.bg_secondary};
                border-bottom: 1px solid {c.border_light};
            }}
            QMenuBar::item {{
                padding: 6px 12px;
                background-color: transparent;
            }}
            QMenuBar::item:selected {{
                background-color: {c.hover_bg};
                border-radius: {self.radius['sm']}px;
            }}

            /* Menus */
            QMenu {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_medium};
                border-radius: {self.radius['md']}px;
                padding: {self.spacing['xs']}px;
            }}
            QMenu::item {{
                padding: {self.spacing['sm']}px {self.spacing['lg']}px;
                border-radius: {self.radius['sm']}px;
            }}
            QMenu::item:selected {{
                background-color: {c.hover_bg};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {c.border_light};
                margin: {self.spacing['xs']}px {self.spacing['sm']}px;
            }}

            /* Splitter */
            QSplitter::handle {{
                background-color: {c.border_light};
            }}
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            QSplitter::handle:vertical {{
                height: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {c.primary};
            }}

            /* Tool tips */
            QToolTip {{
                background-color: {c.gray_800 if not self.dark_mode else c.gray_100};
                color: {c.gray_100 if not self.dark_mode else c.gray_800};
                border: none;
                border-radius: {self.radius['sm']}px;
                padding: {self.spacing['sm']}px {self.spacing['md']}px;
            }}

            /* Progress bar */
            QProgressBar {{
                background-color: {c.bg_tertiary};
                border: none;
                border-radius: {self.radius['sm']}px;
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {c.primary};
                border-radius: {self.radius['sm']}px;
            }}
        """

    def get_grid_view_stylesheet(self) -> str:
        """Get stylesheet for photo grid view."""
        c = self.colors
        return f"""
            QListView {{
                background-color: {c.bg_primary};
                border: none;
                outline: none;
            }}
            QListView::item:selected {{
                background-color: {c.selection_bg};
            }}
            QListView::item:hover {{
                background-color: {c.hover_bg};
            }}
        """

    def get_search_bar_stylesheet(self) -> str:
        """Get stylesheet for prominent search bar."""
        c = self.colors
        return f"""
            QWidget#searchBarContainer {{
                background-color: {c.bg_secondary};
                border-bottom: 1px solid {c.border_light};
                padding: {self.spacing['sm']}px;
            }}
            QLineEdit#searchInput {{
                background-color: {c.bg_primary};
                border: 2px solid {c.border_medium};
                border-radius: {self.radius['lg']}px;
                padding: {self.spacing['md']}px {self.spacing['xl']}px;
                font-size: {self.font_size['lg']}px;
                color: {c.text_primary};
            }}
            QLineEdit#searchInput:focus {{
                border-color: {c.primary};
            }}
            QLineEdit#searchInput::placeholder {{
                color: {c.text_muted};
            }}
        """

    def get_action_bar_stylesheet(self) -> str:
        """Get stylesheet for floating action bar."""
        c = self.colors
        return f"""
            QWidget#actionBar {{
                background-color: {c.gray_800 if not self.dark_mode else c.gray_200};
                border-radius: {self.radius['lg']}px;
                padding: {self.spacing['sm']}px {self.spacing['md']}px;
            }}
            QLabel#selectionCount {{
                color: {c.gray_100 if not self.dark_mode else c.gray_800};
                font-weight: 600;
                font-size: {self.font_size['md']}px;
                padding: 0 {self.spacing['md']}px;
            }}
            QPushButton#actionButton {{
                background-color: transparent;
                border: none;
                color: {c.gray_100 if not self.dark_mode else c.gray_800};
                padding: {self.spacing['sm']}px {self.spacing['md']}px;
                border-radius: {self.radius['md']}px;
                font-weight: 500;
            }}
            QPushButton#actionButton:hover {{
                background-color: {'rgba(255,255,255,0.1)' if not self.dark_mode else 'rgba(0,0,0,0.1)'};
            }}
        """

    def get_preview_info_stylesheet(self) -> str:
        """Get stylesheet for preview info bar."""
        c = self.colors
        return f"""
            QWidget#previewInfo {{
                background-color: {c.bg_secondary};
                border-top: 1px solid {c.border_light};
                padding: {self.spacing['sm']}px {self.spacing['md']}px;
            }}
            QLabel#previewFilename {{
                color: {c.text_primary};
                font-weight: 600;
                font-size: {self.font_size['md']}px;
            }}
            QLabel#previewDetails {{
                color: {c.text_secondary};
                font-size: {self.font_size['sm']}px;
            }}
        """

    def get_collapsible_section_stylesheet(self) -> str:
        """Get stylesheet for collapsible sections."""
        c = self.colors
        return f"""
            QWidget#collapsibleSection {{
                background-color: {c.bg_secondary};
                border: 1px solid {c.border_light};
                border-radius: {self.radius['lg']}px;
                margin-bottom: {self.spacing['sm']}px;
            }}
            QPushButton#sectionHeader {{
                background-color: transparent;
                border: none;
                padding: {self.spacing['md']}px;
                text-align: left;
                font-weight: 600;
                font-size: {self.font_size['md']}px;
                color: {c.text_primary};
            }}
            QPushButton#sectionHeader:hover {{
                background-color: {c.hover_bg};
            }}
            QWidget#sectionContent {{
                padding: 0 {self.spacing['md']}px {self.spacing['md']}px {self.spacing['md']}px;
            }}
        """


class ThemeManager:
    """
    Singleton theme manager for application-wide theming.
    """

    _instance: Optional['ThemeManager'] = None
    _theme: Optional[Theme] = None
    _settings: Optional[QSettings] = None

    @classmethod
    def instance(cls) -> 'ThemeManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if ThemeManager._instance is not None:
            raise RuntimeError("Use ThemeManager.instance() instead")

        self._settings = QSettings("PyPhotoOrganizer", "Theme")
        dark_mode = self._settings.value("dark_mode", True, type=bool)
        self._theme = Theme(dark_mode=dark_mode)

    @classmethod
    def get_theme(cls) -> Theme:
        """Get current theme."""
        return cls.instance()._theme

    @classmethod
    def set_dark_mode(cls, enabled: bool):
        """Set dark mode and save preference."""
        manager = cls.instance()
        manager._theme = Theme(dark_mode=enabled)
        manager._settings.setValue("dark_mode", enabled)

    @classmethod
    def is_dark_mode(cls) -> bool:
        """Check if dark mode is enabled."""
        return cls.instance()._theme.dark_mode

    @classmethod
    def toggle_theme(cls):
        """Toggle between light and dark mode."""
        cls.set_dark_mode(not cls.is_dark_mode())


# Convenience functions
def get_theme() -> Theme:
    """Get current theme."""
    return ThemeManager.get_theme()


def get_status_color(status: str) -> QColor:
    """Get QColor for photo status."""
    return ThemeManager.get_theme().get_status_color(status)


def is_dark_mode() -> bool:
    """Check if dark mode is enabled."""
    return ThemeManager.is_dark_mode()
