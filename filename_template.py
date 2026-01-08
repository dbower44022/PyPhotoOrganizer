"""
Filename Template Module

Provides template-based filename generation with support for:
- Date/time variables ({year}, {month}, {day}, {month_name}, {month_sname}, {day_name}, {day_sname}, {hour}, {minute}, {second})
- Original filename preservation ({original_name}, {original_name_no_ext}, {ext})
- Sequential counters ({counter}, {counter:04d})
- Format specifiers for zero-padding
- Case-insensitive placeholders ({year}, {YEAR}, {Year} all work the same)

This module integrates with the file organization system to allow users to
customize how files are renamed when copied to the archive.

Example Templates:
    {year}{month}{day}_{hour}{minute}{second}              → 20250203_143015.jpg
    {year}-{month}-{day}_{original_name}                   → 2025-02-03_vacation_beach.jpg
    {year}_{month_name}_{day_name}_{counter:03d}           → 2025_February_Monday_001.jpg
    {YEAR}_{MONTH_SNAME}_{DAY_SNAME}_{counter:03d}         → 2025_Feb_Mon_001.jpg (case-insensitive)
    photo_{counter:04d}                                     → photo_0001.jpg
    {year}{month}{day}_{counter:03d}                       → 20250203_001.jpg
    {original_name}                                         → My Photo.jpg (default)

Author: PyPhotoOrganizer
Version: 2.3
"""

from datetime import datetime
import re
import os
import logging

logger = logging.getLogger(__name__)


class FilenameTemplate:
    """
    Handles filename template parsing and generation.

    This class provides methods to parse filename templates with variable substitution,
    validate templates for security and correctness, and generate example outputs for preview.
    """

    # Supported placeholders (for documentation and validation)
    VALID_PLACEHOLDERS = [
        'year', 'month', 'day', 'month_name', 'month_sname', 'day_name', 'day_sname',
        'hour', 'minute', 'second',
        'original_name', 'original_name_no_ext', 'ext',
        'folder_name', 'parent_folder_name',
        'counter'  # Can include format specifier: counter:04d
    ]

    @staticmethod
    def parse(template, file_date, original_filename, counter=1):
        """
        Parse template and generate filename.

        Args:
            template (str): Template string (e.g., "{year}{month}{day}_{original_name_no_ext}")
            file_date (datetime): datetime object with file's creation date
            original_filename (str): Original file path (full path or just filename)
            counter (int): Sequential counter value (for batch operations)

        Returns:
            str: Generated filename

        Raises:
            Exception: If template parsing fails

        Example:
            >>> from datetime import datetime
            >>> FilenameTemplate.parse(
            ...     "{year}{month}{day}_{counter:04d}",
            ...     datetime(2025, 2, 3, 14, 30, 15),
            ...     "IMG_001.jpg",
            ...     counter=5
            ... )
            '20250203_0005.jpg'
        """
        try:
            # Extract components from original filename
            original_name = os.path.basename(original_filename)
            name_no_ext = os.path.splitext(original_name)[0]
            ext = os.path.splitext(original_name)[1]

            # Extract folder names from path
            folder_name = "unknown"
            parent_folder_name = "unknown"

            # Get the directory path
            dir_path = os.path.dirname(original_filename)
            if dir_path:
                # Get immediate parent folder name
                folder_name = os.path.basename(dir_path)

                # Get grandparent folder name
                parent_dir_path = os.path.dirname(dir_path)
                if parent_dir_path:
                    parent_folder_name = os.path.basename(parent_dir_path)

            result = template

            # Replace date/time placeholders (case-insensitive)
            result = re.sub(r'\{year\}', str(file_date.year), result, flags=re.IGNORECASE)
            result = re.sub(r'\{month\}', f"{file_date.month:02d}", result, flags=re.IGNORECASE)
            result = re.sub(r'\{day\}', f"{file_date.day:02d}", result, flags=re.IGNORECASE)
            result = re.sub(r'\{month_name\}', file_date.strftime('%B'), result, flags=re.IGNORECASE)   # Full month name (e.g., "January")
            result = re.sub(r'\{month_sname\}', file_date.strftime('%b'), result, flags=re.IGNORECASE)  # Short month name (e.g., "Jan")
            result = re.sub(r'\{day_name\}', file_date.strftime('%A'), result, flags=re.IGNORECASE)     # Full day name (e.g., "Monday")
            result = re.sub(r'\{day_sname\}', file_date.strftime('%a'), result, flags=re.IGNORECASE)    # Short day name (e.g., "Mon")
            result = re.sub(r'\{hour\}', f"{file_date.hour:02d}", result, flags=re.IGNORECASE)
            result = re.sub(r'\{minute\}', f"{file_date.minute:02d}", result, flags=re.IGNORECASE)
            result = re.sub(r'\{second\}', f"{file_date.second:02d}", result, flags=re.IGNORECASE)

            # Replace filename placeholders (case-insensitive)
            result = re.sub(r'\{original_name\}', original_name, result, flags=re.IGNORECASE)
            result = re.sub(r'\{original_name_no_ext\}', name_no_ext, result, flags=re.IGNORECASE)
            result = re.sub(r'\{ext\}', ext, result, flags=re.IGNORECASE)

            # Replace folder name placeholders (case-insensitive)
            result = re.sub(r'\{folder_name\}', folder_name, result, flags=re.IGNORECASE)
            result = re.sub(r'\{parent_folder_name\}', parent_folder_name, result, flags=re.IGNORECASE)

            # Handle counter with format specifier (case-insensitive)
            # Pattern: {counter:04d} → 0001, {counter:03d} → 001, {counter} → 1
            counter_pattern = r'\{counter(?::(\d+)d)?\}'

            def replace_counter(match):
                format_spec = match.group(1)
                if format_spec:
                    width = int(format_spec)
                    return f"{counter:0{width}d}"
                else:
                    return str(counter)

            result = re.sub(counter_pattern, replace_counter, result, flags=re.IGNORECASE)

            # If template doesn't include extension, append original extension
            if not os.path.splitext(result)[1]:
                result += ext

            logger.debug(f"Template parsing: '{template}' + '{original_name}' → '{result}'")
            return result

        except Exception as e:
            logger.error(f"Failed to parse filename template: {str(e)}", exc_info=True)
            # Fallback to original filename
            logger.warning(f"Falling back to original filename: {original_filename}")
            return os.path.basename(original_filename)

    @staticmethod
    def validate(template):
        """
        Validate template for security and correctness.

        Checks for:
        - Path traversal attempts (.., /, \\)
        - Dangerous characters (<, >, :, ", |, ?, *)
        - Unknown placeholders
        - Invalid format specifiers

        Args:
            template (str): Template string to validate

        Returns:
            tuple: (is_valid: bool, error_message: str or None)

        Example:
            >>> FilenameTemplate.validate("{year}{month}{day}_{original_name}")
            (True, None)
            >>> FilenameTemplate.validate("{year}/{month}")
            (False, "Template cannot contain path separators or '..' sequences")
        """
        # Check for path traversal attempts
        if '..' in template or '/' in template or '\\' in template:
            return False, "Template cannot contain path separators or '..' sequences"

        # Extract placeholders first (we'll check them separately)
        placeholder_pattern = r'\{([^}]+)\}'
        placeholders = re.findall(placeholder_pattern, template)

        # Remove all placeholders from template to check for dangerous chars outside of them
        template_without_placeholders = re.sub(r'\{[^}]+\}', '', template)

        # Check for dangerous characters outside placeholders (Windows/Linux filename restrictions)
        # Note: ':' is allowed inside {counter:04d} format specifiers
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            if char in template_without_placeholders:
                return False, f"Template cannot contain '{char}' character"

        for placeholder in placeholders:
            # Normalize to lowercase for case-insensitive comparison
            placeholder_lower = placeholder.lower()

            # Handle counter with format specifier (case-insensitive)
            if placeholder_lower.startswith('counter'):
                if placeholder_lower == 'counter':
                    continue
                # Validate format specifier: counter:04d
                if not re.match(r'^counter:\d+d$', placeholder_lower):
                    return False, f"Invalid counter format: {{{placeholder}}} (use {{counter}} or {{counter:04d}})"
                continue

            # Check if placeholder is valid (case-insensitive)
            if placeholder_lower not in FilenameTemplate.VALID_PLACEHOLDERS:
                return False, f"Unknown placeholder: {{{placeholder}}}"

        logger.debug(f"Template validation passed: {template}")
        return True, None

    @staticmethod
    def get_example_output(template):
        """
        Generate example output for preview.

        Uses hardcoded example values:
        - Date: 2025-02-03 14:30:15
        - Original filename: IMG_1234.jpg
        - Counter: 1

        Args:
            template (str): Template string

        Returns:
            str: Example filename or error message

        Example:
            >>> FilenameTemplate.get_example_output("{year}{month}{day}_{counter:04d}")
            '20250203_0001.jpg'
        """
        example_date = datetime(2025, 2, 3, 14, 30, 15)
        example_filename = "IMG_1234.jpg"

        try:
            return FilenameTemplate.parse(template, example_date, example_filename, counter=1)
        except Exception as e:
            return f"Error: {str(e)}"
