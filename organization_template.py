"""
Organization Template System

Provides flexible folder structure templates for organizing photos and videos.

Template variables match the filename template system for consistency:
- {year}, {month}, {day} - Numeric date components
- {month_name}, {day_name} - Full names (January, Monday)
- {month_sname}, {day_sname} - Short names (Jan, Mon)
- Case-insensitive: {year}, {YEAR}, {Year} all work identically

Legacy placeholders ({YYYY}, {MM}, {DD}, etc.) are still supported for backward compatibility.
"""

import re
import os
from datetime import datetime
from typing import List, Tuple, Dict


class OrganizationTemplate:
    """
    Parse and apply organization templates for file organization.

    Supports both new consistent placeholders ({year}, {month}, {day}, {month_name}, etc.)
    and legacy placeholders ({YYYY}, {MM}, {DD}, etc.) for backward compatibility.
    """

    # Predefined organization presets (updated to use new naming convention)
    PRESETS = {
        'day_with_names': {
            'name': 'By Day (with month/day names)',
            'template': '{year}/{month}-{month_sname}/{day}-{day_sname}',
            'description': 'Photos organized by day with readable month and day names. Easy to browse chronologically and find photos from a specific date.',
        },
        'month_with_name': {
            'name': 'By Month (with month name)',
            'template': '{year}/{month}-{month_sname}',
            'description': 'Photos organized by month with readable month names. Fewer folders, good for finding photos from a specific month.',
        },
        'year_only': {
            'name': 'By Year',
            'template': '{year}',
            'description': 'Photos organized only by year. Minimal folder structure, all photos from each year in one folder.',
        },
        'legacy_default': {
            'name': 'By Day (numeric)',
            'template': '{year}/{month}/{day}',
            'description': 'Classic date-based organization with numeric month and day. Compatible with existing archives.',
        },
    }

    # Valid placeholders and their functions (new naming convention)
    PLACEHOLDERS = {
        # Year
        '{year}': lambda dt: dt.strftime('%Y'),        # 2025
        '{year_short}': lambda dt: dt.strftime('%y'),  # 25

        # Month
        '{month}': lambda dt: dt.strftime('%m'),       # 02 (zero-padded)
        '{month_name}': lambda dt: dt.strftime('%B'),  # February
        '{month_sname}': lambda dt: dt.strftime('%b'), # Feb

        # Day
        '{day}': lambda dt: dt.strftime('%d'),         # 03 (zero-padded)
        '{day_name}': lambda dt: dt.strftime('%A'),    # Monday
        '{day_sname}': lambda dt: dt.strftime('%a'),   # Mon

        # Combined formats (for convenience)
        '{month}-{month_sname}': lambda dt: f"{dt.strftime('%m')}-{dt.strftime('%b')}",  # 02-Feb
        '{day}-{day_sname}': lambda dt: f"{dt.strftime('%d')}-{dt.strftime('%a')}",      # 03-Mon

        # Legacy placeholders (for backward compatibility)
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
            template: Template string with placeholders (case-insensitive)
            date: Date to use for placeholders

        Returns:
            Resolved path string

        Examples:
            >>> parse('{year}/{month}-{month_sname}/{day}', datetime(2025, 2, 3))
            '2025/02-Feb/03'
            >>> parse('{Year}/{Month_Name}', datetime(2025, 2, 3))  # Case-insensitive
            '2025/February'
            >>> parse('{YYYY}/{MM}/{DD}', datetime(2025, 2, 3))  # Legacy format
            '2025/02/03'
        """
        path = template

        # Process combined placeholders first (to avoid partial replacements)
        # e.g., '{month}-{month_sname}' should be processed before '{month}'
        # Using regex with IGNORECASE for case-insensitive matching
        combined_placeholders = [
            (r'\{month\}-\{month_sname\}', lambda dt: f"{dt.strftime('%m')}-{dt.strftime('%b')}"),
            (r'\{day\}-\{day_sname\}', lambda dt: f"{dt.strftime('%d')}-{dt.strftime('%a')}"),
            (r'\{MM-Month_Short\}', lambda dt: f"{dt.strftime('%m')}-{dt.strftime('%b')}"),  # Legacy
            (r'\{DD-Day_Short\}', lambda dt: f"{dt.strftime('%d')}-{dt.strftime('%a')}"),    # Legacy
        ]

        for pattern, func in combined_placeholders:
            path = re.sub(pattern, func(date), path, flags=re.IGNORECASE)

        # Then process individual placeholders (case-insensitive)
        individual_placeholders = {
            r'\{year\}': lambda dt: dt.strftime('%Y'),
            r'\{year_short\}': lambda dt: dt.strftime('%y'),
            r'\{month\}': lambda dt: dt.strftime('%m'),
            r'\{month_name\}': lambda dt: dt.strftime('%B'),
            r'\{month_sname\}': lambda dt: dt.strftime('%b'),
            r'\{day\}': lambda dt: dt.strftime('%d'),
            r'\{day_name\}': lambda dt: dt.strftime('%A'),
            r'\{day_sname\}': lambda dt: dt.strftime('%a'),
            # Legacy placeholders
            r'\{YYYY\}': lambda dt: dt.strftime('%Y'),
            r'\{YY\}': lambda dt: dt.strftime('%y'),
            r'\{MM\}': lambda dt: dt.strftime('%m'),
            r'\{M\}': lambda dt: str(int(dt.strftime('%m'))),
            r'\{Month_Name\}': lambda dt: dt.strftime('%B'),
            r'\{Month_Short\}': lambda dt: dt.strftime('%b'),
            r'\{DD\}': lambda dt: dt.strftime('%d'),
            r'\{D\}': lambda dt: str(int(dt.strftime('%d'))),
            r'\{Day_Name\}': lambda dt: dt.strftime('%A'),
            r'\{Day_Short\}': lambda dt: dt.strftime('%a'),
        }

        for pattern, func in individual_placeholders.items():
            path = re.sub(pattern, func(date), path, flags=re.IGNORECASE)

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

        # Check if all placeholders are valid (case-insensitive)
        for placeholder in found_placeholders:
            # Normalize to lowercase for comparison
            placeholder_lower = placeholder.lower()
            # Get all valid placeholders in lowercase
            valid_placeholders_lower = [p.lower() for p in cls.PLACEHOLDERS.keys()]

            if placeholder_lower not in valid_placeholders_lower:
                return False, f"Invalid placeholder: {placeholder}. Valid placeholders: {', '.join(cls.PLACEHOLDERS.keys())}"

        # Check for invalid characters (after removing placeholders - case insensitive)
        temp_without_placeholders = template
        for placeholder in cls.PLACEHOLDERS.keys():
            # Use case-insensitive replacement
            temp_without_placeholders = re.sub(re.escape(placeholder), 'X', temp_without_placeholders, flags=re.IGNORECASE)

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
