# PyPhotoOrganizer Test Suite

Comprehensive automated testing for PyPhotoOrganizer using pytest.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Installation](#installation)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Writing New Tests](#writing-new-tests)
- [Continuous Integration](#continuous-integration)

## Overview

This test suite provides comprehensive coverage of PyPhotoOrganizer functionality:

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test complete workflows end-to-end
- **Database Tests**: Test database operations and schema
- **Test Data Generation**: Utilities to create synthetic test images and scenarios

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and pytest configuration
├── pytest.ini                  # Pytest settings (in project root)
│
├── unit/                       # Unit tests for individual components
│   ├── test_hashing.py         # File hashing functions
│   ├── test_date_extraction.py # Date extraction from EXIF/metadata
│   ├── test_photo_filter.py    # Photo filtering logic
│   └── test_utilities.py       # Utility functions
│
├── database/                   # Database operation tests
│   ├── test_photo_database.py  # PhotoDatabase class tests
│   └── test_database_metadata.py # DatabaseMetadata class tests
│
├── integration/                # End-to-end workflow tests
│   └── test_full_workflow.py   # Complete processing workflows
│
└── test_utils/                 # Test data generation utilities
    ├── image_generator.py      # Synthetic image creation
    ├── test_file_generator.py  # Test file structures
    └── mock_data.py            # Mock data factory
```

## Installation

### 1. Install Test Dependencies

```bash
# Install pytest and related packages
pip install pytest pytest-cov pytest-timeout

# Application dependencies (if not already installed)
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
# Check pytest is installed
pytest --version

# Should show pytest 7.0 or higher
```

## Running Tests

### Run All Tests

```bash
# From project root directory
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=. --cov-report=html
```

### Run Specific Test Categories

```bash
# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration

# Only database tests
pytest -m database

# Exclude slow tests
pytest -m "not slow"
```

### Run Specific Test Files

```bash
# Run all hashing tests
pytest tests/unit/test_hashing.py

# Run all database tests
pytest tests/database/

# Run specific test class
pytest tests/unit/test_hashing.py::TestFileHashing

# Run specific test function
pytest tests/unit/test_hashing.py::TestFileHashing::test_hash_file_consistency
```

### Run Tests by Pattern

```bash
# Run all tests with "duplicate" in name
pytest -k duplicate

# Run all tests with "date" in name
pytest -k date

# Combine patterns
pytest -k "hash or filter"
```

### Useful Test Options

```bash
# Stop after first failure
pytest -x

# Stop after 5 failures
pytest --maxfail=5

# Show local variables in tracebacks
pytest -l

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Quiet mode (less output)
pytest -q

# Very verbose (show all test names)
pytest -vv

# Show print statements
pytest -s
```

## Test Categories

### Unit Tests (`tests/unit/`)

Test individual functions and classes in isolation:

- **test_hashing.py**: SHA-256 hashing, partial hashing, duplicate detection
- **test_date_extraction.py**: EXIF date extraction, reliability detection, fallback methods
- **test_photo_filter.py**: File size/dimension filtering, icon detection, filename patterns
- **test_utilities.py**: Unique filename generation, directory operations, template parsing

```bash
# Run all unit tests
pytest tests/unit/

# Run only hashing tests
pytest tests/unit/test_hashing.py -v
```

### Database Tests (`tests/database/`)

Test database operations and schema:

- **test_photo_database.py**: PhotoDatabase context manager, insert/query operations, transactions
- **test_database_metadata.py**: Metadata management, source directories, unreliable dates, settings

```bash
# Run all database tests
pytest tests/database/

# Run only metadata tests
pytest tests/database/test_database_metadata.py -v
```

### Integration Tests (`tests/integration/`)

Test complete end-to-end workflows:

- **test_full_workflow.py**: Complete processing pipeline, duplicate detection, filtering, multi-source

```bash
# Run all integration tests
pytest tests/integration/

# Run integration tests excluding slow ones
pytest tests/integration/ -m "not slow"
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests (auto-applied by directory)
- `@pytest.mark.integration` - Integration tests (auto-applied)
- `@pytest.mark.database` - Database tests (auto-applied)
- `@pytest.mark.slow` - Tests that take significant time (>5 seconds)
- `@pytest.mark.requires_ffmpeg` - Tests requiring FFmpeg installation

```bash
# Run only fast tests
pytest -m "not slow"

# Run tests requiring FFmpeg
pytest -m requires_ffmpeg

# Combine markers
pytest -m "unit and not slow"
```

## Fixtures

Common fixtures available in all tests (defined in `conftest.py`):

### Directory Fixtures

- `temp_dir` - Temporary directory (auto-cleanup)
- `source_dir` - Source directory for test files
- `dest_dir` - Destination directory for organized files
- `multiple_source_dirs` - List of 3 source directories

### Database Fixtures

- `test_db_path` - Path for test database file
- `empty_database` - Initialized empty database
- `populated_database` - Database with sample records
- `in_memory_database` - In-memory SQLite database (fast)

### Settings Fixtures

- `default_settings` - Default configuration
- `settings_with_filtering` - Settings with photo filtering enabled
- `settings_without_filtering` - Settings with filtering disabled
- `settings_file` - Temporary settings.json file

### Test Data Fixtures

- `image_generator` - ImageGenerator instance
- `file_generator` - TestFileGenerator instance
- `mock_factory` - MockDataFactory instance
- `sample_images` - Collection of 5 sample images
- `sample_images_with_duplicates` - Images with duplicates
- `filtered_files` - Icons and thumbnails (should be filtered)
- `unreliable_date_files` - Files with date issues

### Scenario Fixtures

- `simple_scenario` - Simple test scenario (5 files)
- `duplicates_scenario` - Scenario with duplicates
- `mixed_formats_scenario` - Various file formats
- `large_collection_scenario` - 50+ files (slow)

## Writing New Tests

### Basic Test Structure

```python
import pytest
from tests.test_utils.image_generator import ImageGenerator

def test_my_feature(temp_dir, test_db_path):
    """Test description."""
    # Setup
    img_path = os.path.join(temp_dir, "test.jpg")
    ImageGenerator.create_test_image(img_path)

    # Execute
    result = my_function(img_path)

    # Assert
    assert result == expected_value
```

### Using Fixtures

```python
def test_with_database(empty_database, dest_dir):
    """Test using database fixture."""
    from database_metadata import DatabaseMetadata

    metadata = DatabaseMetadata(empty_database)
    metadata.initialize_metadata(
        database_name="Test",
        archive_location=dest_dir
    )

    # Test code here...
```

### Creating Test Data

```python
from tests.test_utils.image_generator import ImageGenerator
from datetime import datetime

def test_with_custom_image(temp_dir):
    """Test with custom generated image."""
    img_path = os.path.join(temp_dir, "custom.jpg")

    ImageGenerator.create_test_image(
        path=img_path,
        width=1920,
        height=1080,
        format="JPEG",
        text="Test Image",
        exif_date=datetime(2024, 6, 15, 14, 30, 0),
        camera_make="Canon",
        camera_model="EOS 5D"
    )

    # Test code here...
```

### Using Test Scenarios

```python
def test_with_scenario(temp_dir):
    """Test using predefined scenario."""
    from tests.test_utils.test_file_generator import TestFileGenerator

    scenario_path = os.path.join(temp_dir, "scenario")
    scenario = TestFileGenerator.create_test_scenario(
        scenario_path,
        'duplicates'  # or 'simple', 'mixed_formats', etc.
    )

    files = scenario['files']
    originals = scenario['original']
    duplicates = scenario['duplicates']

    # Test code here...
```

### Adding Test Markers

```python
import pytest

@pytest.mark.slow
def test_large_dataset():
    """Test with large dataset (takes >5 seconds)."""
    # Test code...

@pytest.mark.requires_ffmpeg
def test_video_processing():
    """Test requiring FFmpeg."""
    # Test code...
```

## Coverage Reports

Generate coverage reports to identify untested code:

```bash
# Run tests with coverage
pytest --cov=. --cov-report=html --cov-report=term

# Open HTML coverage report
# (Linux)
xdg-open htmlcov/index.html

# (macOS)
open htmlcov/index.html

# (Windows)
start htmlcov/index.html
```

Coverage report shows:
- Which lines of code are tested
- Which branches are covered
- Overall coverage percentage
- Files needing more tests

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        pytest --cov=. --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## Troubleshooting

### Tests Not Found

```bash
# Ensure you're in project root
cd /path/to/PyPhotoOrganizer

# Run with discovery
pytest --collect-only
```

### Import Errors

```bash
# Ensure application modules are in path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run tests as module
python -m pytest
```

### Fixture Errors

```bash
# List all available fixtures
pytest --fixtures

# Show fixture setup/teardown
pytest --setup-show
```

### Database Locked Errors

```bash
# Ensure tests clean up properly
pytest -v --tb=short

# Use in-memory database for faster tests
# (already default for most test fixtures)
```

## Best Practices

1. **Keep tests independent**: Each test should set up its own data and not depend on other tests
2. **Use fixtures**: Leverage fixtures for common setup/teardown
3. **Test edge cases**: Test boundary conditions, empty inputs, invalid data
4. **Clear test names**: Use descriptive names that explain what is being tested
5. **One assertion per test**: Focus each test on a single behavior (when practical)
6. **Fast tests**: Keep tests fast; mark slow tests with `@pytest.mark.slow`
7. **Clean up**: Use fixtures with auto-cleanup (temp_dir, etc.)

## Questions or Issues?

- Check existing tests for examples
- Run `pytest --fixtures` to see available fixtures
- Run `pytest --markers` to see test markers
- Consult pytest documentation: https://docs.pytest.org/
