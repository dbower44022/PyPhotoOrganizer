"""
Filename Template Module

Provides template-based filename generation with support for:
- Date/time variables ({year}, {month}, {day}, {hour}, {minute}, {second})
- Original filename preservation ({original_name}, {original_name_no_ext}, {ext})
- Sequential counters ({counter}, {counter:04d})
- Format specifiers for zero-padding

This module integrates with the file organization system to allow users to
customize how files are renamed when copied to the archive.

Example Templates:
    {year}{month}{day}_{hour}{minute}{second}              → 20250203_143015.jpg
    {year}-{month}-{day}_{original_name}                   → 2025-02-03_vacation_beach.jpg
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
        'year', 'month', 'day',
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

            # Replace date/time placeholders
            result = result.replace('{year}', str(file_date.year))
            result = result.replace('{month}', f"{file_date.month:02d}")
            result = result.replace('{day}', f"{file_date.day:02d}")
            result = result.replace('{hour}', f"{file_date.hour:02d}")
            result = result.replace('{minute}', f"{file_date.minute:02d}")
            result = result.replace('{second}', f"{file_date.second:02d}")

            # Replace filename placeholders
            result = result.replace('{original_name}', original_name)
            result = result.replace('{original_name_no_ext}', name_no_ext)
            result = result.replace('{ext}', ext)

            # Replace folder name placeholders
            result = result.replace('{folder_name}', folder_name)
            result = result.replace('{parent_folder_name}', parent_folder_name)

            # Handle counter with format specifier
            # Pattern: {counter:04d} → 0001, {counter:03d} → 001, {counter} → 1
            counter_pattern = r'\{counter(?::(\d+)d)?\}'

            def replace_counter(match):
                format_spec = match.group(1)
                if format_spec:
                    width = int(format_spec)
                    return f"{counter:0{width}d}"
                else:
                    return str(counter)

            result = re.sub(counter_pattern, replace_counter, result)

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

        # Check for dangerous characters (Windows/Linux filename restrictions)
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            if char in template:
                return False, f"Template cannot contain '{char}' character"

        # Check for valid placeholders
        pattern = r'\{([^}]+)\}'
        placeholders = re.findall(pattern, template)

        for placeholder in placeholders:
            # Handle counter with format specifier
            if placeholder.startswith('counter'):
                if placeholder == 'counter':
                    continue
                # Validate format specifier: counter:04d
                if not re.match(r'^counter:\d+d$', placeholder):
                    return False, f"Invalid counter format: {{{placeholder}}} (use {{counter}} or {{counter:04d}})"
                continue

            # Check if placeholder is valid
            if placeholder not in FilenameTemplate.VALID_PLACEHOLDERS:
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
