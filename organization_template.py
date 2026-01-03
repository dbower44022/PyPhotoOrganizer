"""
Organization Template System

Provides flexible folder structure templates for organizing photos and videos.
"""

import re
import os
from datetime import datetime
from typing import List, Tuple, Dict


class OrganizationTemplate:
    """
    Parse and apply organization templates for file organization.

    Supports placeholders like {YYYY}, {MM}, {DD}, {Month_Short}, etc.
    """

    # Predefined organization presets
    PRESETS = {
        'day_with_names': {
            'name': 'By Day (with month/day names)',
            'template': '{YYYY}/{MM-Month_Short}/{DD-Day_Short}',
            'description': 'Photos organized by day with readable month and day names. Easy to browse chronologically and find photos from a specific date.',
        },
        'month_with_name': {
            'name': 'By Month (with month name)',
            'template': '{YYYY}/{MM-Month_Short}',
            'description': 'Photos organized by month with readable month names. Fewer folders, good for finding photos from a specific month.',
        },
        'year_only': {
            'name': 'By Year',
            'template': '{YYYY}',
            'description': 'Photos organized only by year. Minimal folder structure, all photos from each year in one folder.',
        },
        'legacy_default': {
            'name': 'By Day (legacy)',
            'template': '{YYYY}/{MM}/{DD}',
            'description': 'Classic date-based organization with numeric month and day. Compatible with existing archives.',
        },
    }

    # Valid placeholders and their functions
    PLACEHOLDERS = {
        '{YYYY}': lambda dt: dt.strftime('%Y'),
        '{YY}': lambda dt: dt.strftime('%y'),
        '{MM}': lambda dt: dt.strftime('%m'),
        '{M}': lambda dt: str(int(dt.strftime('%m'))),
        '{Month_Name}': lambda dt: dt.strftime('%B'),
        '{Month_Short}': lambda dt: dt.strftime('%b'),
        '{MM-Month_Short}': lambda dt: f"{dt.strftime('%m')}-{dt.strftime('%b')}",
        '{DD}': lambda dt: dt.strftime('%d'),
        '{D}': lambda dt: str(int(dt.strftime('%d'))),
        '{Day_Name}': lambda dt: dt.strftime('%A'),
        '{Day_Short}': lambda dt: dt.strftime('%a'),
        '{DD-Day_Short}': lambda dt: f"{dt.strftime('%d')}-{dt.strftime('%a')}",
    }

    @classmethod
    def parse(cls, template: str, date: datetime) -> str:
        """
        Convert template + date to actual folder path.

        Args:
            template: Template string with placeholders
            date: Date to use for placeholders

        Returns:
            Resolved path string

        Example:
            >>> parse('{YYYY}/{MM-Month_Short}/{DD}', datetime(2025, 2, 3))
            '2025/02-Feb/03'
        """
        path = template
        for placeholder, func in cls.PLACEHOLDERS.items():
            if placeholder in path:
                path = path.replace(placeholder, func(date))
        return path

    @classmethod
    def validate(cls, template: str) -> Tuple[bool, str]:
        """
        Validate if template is valid and safe.

        Args:
            template: Template string to validate

        Returns:
            Tuple of (is_valid, error_message)

        Validation checks:
        - No path traversal attempts (../)
        - No absolute paths
        - Only valid placeholders
        - Valid folder name characters
        """
        if not template:
            return False, "Template cannot be empty"

        # Check for path traversal
        if '..' in template:
            return False, "Template cannot contain '..' (path traversal attempt)"

        # Check for absolute paths
        if template.startswith('/') or template.startswith('\\') or ':' in template:
            return False, "Template cannot be an absolute path"

        # Extract all placeholders from template
        placeholder_pattern = r'\{[^}]+\}'
        found_placeholders = re.findall(placeholder_pattern, template)

        # Check if all placeholders are valid
        for placeholder in found_placeholders:
            if placeholder not in cls.PLACEHOLDERS:
                return False, f"Invalid placeholder: {placeholder}. Valid placeholders: {', '.join(cls.PLACEHOLDERS.keys())}"

        # Check for invalid characters (after removing placeholders)
        temp_without_placeholders = template
        for placeholder in cls.PLACEHOLDERS.keys():
            temp_without_placeholders = temp_without_placeholders.replace(placeholder, 'X')

        # Valid characters: alphanumeric, space, dash, underscore, forward slash
        invalid_chars = re.findall(r'[^a-zA-Z0-9 \-_/]', temp_without_placeholders)
        if invalid_chars:
            return False, f"Invalid characters in template: {', '.join(set(invalid_chars))}"

        # All checks passed
        return True, ""

    @classmethod
    def generate_examples(cls, template: str) -> List[str]:
        """
        Generate example paths for preview.

        Args:
            template: Template string

        Returns:
            List of example paths
        """
        example_dates = [
            datetime(2025, 2, 3),   # Monday
            datetime(2025, 2, 4),   # Tuesday
            datetime(2024, 12, 31), # Wednesday
        ]

        examples = []
        for dt in example_dates:
            try:
                path = cls.parse(template, dt)
                examples.append(f"{path}/IMG_{dt.strftime('%Y%m%d')}.jpg")
            except Exception:
                examples.append("[Error parsing template]")

        return examples

    @classmethod
    def get_preset_names(cls) -> List[str]:
        """Get list of preset names for dropdown."""
        return [preset['name'] for preset in cls.PRESETS.values()]

    @classmethod
    def get_preset_by_name(cls, name: str) -> Dict:
        """Get preset configuration by name."""
        for preset in cls.PRESETS.values():
            if preset['name'] == name:
                return preset
        return None

    @classmethod
    def get_preset_by_template(cls, template: str) -> Dict:
        """Get preset configuration by template string."""
        for key, preset in cls.PRESETS.items():
            if preset['template'] == template:
                return preset
        return None

    @classmethod
    def format_description(cls, template: str) -> str:
        """
        Generate human-readable description of what the template does.

        Args:
            template: Template string

        Returns:
            Description text
        """
        # Check if it's a known preset
        preset = cls.get_preset_by_template(template)
        if preset:
            return preset['description']

        # Generate description for custom template
        parts = []
        if '{YYYY}' in template or '{YY}' in template:
            parts.append("year")
        if any(m in template for m in ['{MM}', '{M}', '{Month_Name}', '{Month_Short}', '{MM-Month_Short}']):
            parts.append("month")
        if any(d in template for d in ['{DD}', '{D}', '{Day_Name}', '{Day_Short}', '{DD-Day_Short}']):
            parts.append("day")

        if parts:
            return f"Custom organization by {', '.join(parts)}."
        else:
            return "Custom organization template."
