# Development Guide

> Guide for contributors and developers

**Last Updated:** 2026-01-02

---

## Getting Started

### Prerequisites

- Python 3.8+
- Git
- Text editor or IDE (VS Code, PyCharm recommended)

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd PyPhotoOrganizer

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt  # If available
```

---

## Project Structure

```
PyPhotoOrganizer/
├── main.py                    # Entry point
├── config.py                  # Configuration
├── constants.py              # Constants
├── utils.py                  # Utilities
├── DuplicateFileDetection.py # Core logic
├── photo_filter.py           # Filtering
├── settings.json             # Config file
├── requirements.txt          # Dependencies
├── PhotoDB.db               # Database
├── *.log                    # Log files
└── docs/                    # Documentation
    ├── README.md
    ├── ARCHITECTURE.md
    ├── CONFIGURATION.md
    ├── API.md
    ├── DEVELOPMENT.md (this file)
    ├── TROUBLESHOOTING.md
    └── QUICKREF.md
```

---

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Follow existing code style
- Add comments for complex logic
- Update documentation
- Test your changes

### 3. Commit Changes

```bash
git add .
git commit -m "Add feature: description"
```

### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
# Create pull request on GitHub
```

---

## Code Style Guide

### Python Style

Follow PEP 8 with these guidelines:

```python
# ✓ Good: Descriptive names
def calculate_file_hash(file_path):
    ...

# ✗ Bad: Unclear names
def calc(fp):
    ...

# ✓ Good: Type hints
def get_file_size(file_path: str) -> int:
    ...

# ✓ Good: Docstrings
def hash_file(filename: str) -> str:
    """
    Calculate SHA-256 hash of entire file.

    Parameters:
        filename (str): Path to file

    Returns:
        str: SHA-256 hash
    """
    ...
```

### Constants

- Use `constants.py` for all magic numbers
- UPPER_CASE naming
- Include comments explaining values

```python
# ✓ Good
FILE_READ_CHUNK_SIZE = 4096  # Optimal disk read size

# ✗ Bad
chunk = file.read(4096)  # Magic number
```

### Error Handling

```python
# ✓ Good: Specific exceptions
try:
    process_file(file_path)
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
except PermissionError:
    logger.error(f"Permission denied: {file_path}")

# ✗ Bad: Bare except
try:
    process_file(file_path)
except:
    pass
```

### Logging

```python
# ✓ Good: Appropriate levels
logger.debug("Processing file: details")
logger.info("Milestone reached")
logger.warning("Skipping invalid file")
logger.error("Operation failed")
logger.critical("Fatal error")

# ✗ Bad: Everything as info
logger.info("Debug information")
```

---

## Testing

### Manual Testing

1. Create test dataset:
```bash
mkdir test_photos
# Add mix of photos, duplicates, icons
```

2. Create test config:
```json
{
  "source_directory": ["test_photos"],
  "destination_directory": "test_output",
  "batch_size": 10
}
```

3. Run and verify:
```bash
python main.py
```

### Test Checklist

- [ ] Processes photos correctly
- [ ] Detects duplicates accurately
- [ ] Organizes by date correctly
- [ ] Handles errors gracefully
- [ ] Progress bars display correctly
- [ ] Database commits work
- [ ] Resume capability works
- [ ] Photo filtering works
- [ ] HEIC conversion works

---

## Adding New Features

### Example: Adding New Filter

1. **Add constant** (constants.py):
```python
MAX_ASPECT_RATIO = 4.0  # Exclude panoramas
```

2. **Add setting** (config.py):
```python
DEFAULTS = {
    ...
    'max_aspect_ratio': constants.MAX_ASPECT_RATIO,
}
```

3. **Implement logic** (photo_filter.py):
```python
def _check_aspect_ratio(self, width, height):
    aspect = width / height
    if aspect > self.max_aspect_ratio:
        return False, "Aspect ratio too wide"
    return True, None
```

4. **Update documentation**:
- Add to CONFIGURATION.md
- Add to API.md
- Update README.md if user-facing

5. **Test thoroughly**

---

## Common Development Tasks

### Adding New Constant

```python
# 1. Add to constants.py
NEW_CONSTANT = 42  # Description

# 2. Use in code
if value > constants.NEW_CONSTANT:
    ...

# 3. Update documentation
```

### Adding New Config Setting

```python
# 1. Add to Config.DEFAULTS
DEFAULTS = {
    'new_setting': default_value,
}

# 2. Add property (optional)
@property
def new_setting(self) -> type:
    return self._settings['new_setting']

# 3. Add validation if needed
def _validate_new_setting(self):
    ...

# 4. Document in CONFIGURATION.md
```

### Adding New Database Field

```sql
-- 1. Update schema (DuplicateFileDetection.py)
ALTER TABLE UniquePhotos ADD COLUMN new_field TEXT;

-- 2. Update insert/select queries
-- 3. Handle migration for existing databases
-- 4. Update documentation
```

---

## Debugging

### Enable Verbose Logging

```python
# In utils.py or main.py
logging.basicConfig(level=logging.DEBUG)
```

### Database Inspection

```bash
# Install SQLite browser
sqlite3 PhotoDB.db

# Query database
SELECT COUNT(*) FROM UniquePhotos;
SELECT * FROM UniquePhotos LIMIT 10;
```

### Common Debug Scenarios

**Issue: Files not being processed**
```python
# Add debug logging
logger.debug(f"File: {file_path}")
logger.debug(f"Size: {file_size}")
logger.debug(f"Hash: {file_hash}")
```

**Issue: Duplicates not detected**
```python
# Verify hash calculation
hash1 = hash_file(file1)
hash2 = hash_file(file2)
print(f"Hash1: {hash1}")
print(f"Hash2: {hash2}")
print(f"Match: {hash1 == hash2}")
```

---

## Performance Optimization

### Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
main()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Optimization Checklist

- [ ] Use partial hashing for large files
- [ ] Batch database commits
- [ ] Filter before hashing
- [ ] Use appropriate chunk sizes
- [ ] Index database queries
- [ ] Minimize logging in hot paths

---

## Security Considerations

### Input Validation

```python
# ✓ Always validate user input
if '..' in path:
    raise ValueError("Path traversal detected")

# ✓ Use parameterized queries
cursor.execute("SELECT * FROM table WHERE id = ?", (id,))

# ✗ Never use string formatting
cursor.execute(f"SELECT * FROM table WHERE id = {id}")
```

### File Operations

```python
# ✓ Validate file paths
if not os.path.exists(file_path):
    raise FileNotFoundError()

# ✓ Handle permissions
try:
    os.rename(old, new)
except PermissionError:
    shutil.copy2(old, new)
```

---

## Contributing Guidelines

### Code Review Checklist

- [ ] Code follows style guide
- [ ] No magic numbers
- [ ] Proper error handling
- [ ] Logging at appropriate levels
- [ ] Documentation updated
- [ ] No security issues
- [ ] Performance considered
- [ ] Tested manually

### Commit Message Format

```
type: short description

Longer description if needed.

Fixes #issue-number
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Tests
- `chore`: Maintenance

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tested manually
- [ ] Added/updated tests

## Checklist
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] No security issues
```

---

## Release Process

### Version Numbering

Format: `MAJOR.MINOR.PATCH`
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Checklist

1. [ ] Update version in all files
2. [ ] Update CHANGELOG.md
3. [ ] Run full test suite
4. [ ] Update documentation
5. [ ] Create git tag
6. [ ] Build release
7. [ ] Publish release notes

---

## Resources

### Documentation
- [Python PEP 8](https://pep8.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [SQLite Documentation](https://www.sqlite.org/docs.html)

### Tools
- **Linters:** pylint, flake8
- **Formatters:** black, autopep8
- **Type Checking:** mypy
- **IDE:** VS Code, PyCharm

### Learning Resources
- [Real Python](https://realpython.com/)
- [Python Documentation](https://docs.python.org/)
- [SQLite Tutorial](https://www.sqlitetutorial.net/)

---

## Getting Help

- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions
- **Email:** (if available)

---

**Happy Coding!** 🚀

*Last updated: 2026-01-02*
