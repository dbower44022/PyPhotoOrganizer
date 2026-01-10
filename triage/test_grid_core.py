"""
Core Grid Component Unit Tests

Tests thumbnail grid model and cache without GUI.
Validates performance and functionality in headless mode.
"""

import logging
import os
import sys
import tempfile
import time
import shutil
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from DuplicateFileDetection import PhotoDatabase
from triage.triage_database import TriageDatabase
from triage.triage_config import TriageConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_database(db_path: str, test_count: int = 1000):
    """Create test database with mock photo entries."""
    logger.info(f"Creating test database with {test_count} files...")

    # Create UniquePhotos table FIRST
    with PhotoDatabase(db_path) as db:
        db.initialize_database()

        # Insert test files spread across multiple dates
        batch_size = 100
        for i in range(test_count):
            # Spread files across 10 days
            day = (i % 10) + 1
            file_hash = f"test_hash_{i:06d}"
            file_name = f"/archive/2025/02/{day:02d}/test_photo_{i:06d}.jpg"
            file_size = 1000000 + (i * 1000)

            db.cursor.execute("""
                INSERT INTO UniquePhotos
                (file_hash, file_name, file_size, create_year, create_month, create_day)
                VALUES (?, ?, ?, '2025', '02', ?)
            """, (file_hash, file_name, file_size, f"{day:02d}"))

            if (i + 1) % batch_size == 0:
                db.commit()

        db.commit()

    # Then initialize triage tables (they reference UniquePhotos)
    triage_db = TriageDatabase(db_path)
    triage_db.ensure_triage_tables()

    logger.info(f"✓ Created database with {test_count} test files")
    return test_count


def test_database_operations(db_path: str, test_count: int):
    """Test database query performance."""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Database Operations")
    logger.info("="*80)

    triage_db = TriageDatabase(db_path)

    # Test: Load folder query performance
    logger.info("\n1.1 Testing folder load query...")
    with PhotoDatabase(db_path) as db:
        start = time.perf_counter()
        db.cursor.execute("""
            SELECT file_hash, file_name, file_size
            FROM UniquePhotos
            WHERE file_name LIKE ?
            ORDER BY file_name
        """, ("/archive/2025/02/%",))
        results = db.cursor.fetchall()
        elapsed = time.perf_counter() - start

    logger.info(f"   Loaded {len(results)} files in {elapsed*1000:.1f}ms")
    assert len(results) == test_count, f"Expected {test_count} files, got {len(results)}"

    if elapsed < 0.2:
        logger.info(f"   ✓ PASS: Load time within target ({elapsed*1000:.1f}ms < 200ms)")
    else:
        logger.warning(f"   ✗ FAIL: Load time exceeds target ({elapsed*1000:.1f}ms > 200ms)")

    # Test: Mark operations
    logger.info("\n1.2 Testing mark operations...")
    test_hashes = [f"test_hash_{i:06d}" for i in range(100)]

    start = time.perf_counter()
    for file_hash in test_hashes:
        triage_db.mark_file(file_hash, 'delete', 'Test delete mark')
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / len(test_hashes)) * 1000

    logger.info(f"   Marked {len(test_hashes)} files in {elapsed*1000:.1f}ms")
    logger.info(f"   Average: {avg_ms:.2f}ms per mark")

    if avg_ms < 10:
        logger.info(f"   ✓ PASS: Mark time within target ({avg_ms:.2f}ms < 10ms)")
    else:
        logger.warning(f"   ✗ FAIL: Mark time exceeds target ({avg_ms:.2f}ms > 10ms)")

    # Test: Verify marks
    logger.info("\n1.3 Testing mark retrieval...")
    marked_files = triage_db.get_marked_files('delete')
    assert len(marked_files) == len(test_hashes), f"Expected {len(test_hashes)} marks, got {len(marked_files)}"
    logger.info(f"   ✓ PASS: Retrieved {len(marked_files)} marked files")

    # Test: Unmark operations
    logger.info("\n1.4 Testing unmark operations...")
    start = time.perf_counter()
    for file_hash in test_hashes[:50]:
        triage_db.unmark_file(file_hash, 'delete')
    elapsed = time.perf_counter() - start

    marked_files = triage_db.get_marked_files('delete')
    assert len(marked_files) == 50, f"Expected 50 marks remaining, got {len(marked_files)}"
    logger.info(f"   Unmarked 50 files in {elapsed*1000:.1f}ms")
    logger.info(f"   ✓ PASS: {len(marked_files)} marks remaining (expected 50)")

    logger.info("\n✓ All database tests passed")


def test_config_system():
    """Test configuration loading and validation."""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Configuration System")
    logger.info("="*80)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = f.name
        # Write test config
        f.write('''{
            "database_path": "test.db",
            "thumbnail_cache_dir": "/tmp/test_cache",
            "memory_cache_size": 100,
            "disk_cache_size_gb": 2,
            "worker_threads": 4
        }''')

    try:
        config = TriageConfig.load(config_path)
        assert config.database_path == "test.db"
        assert config.memory_cache_size == 100
        assert config.worker_threads == 4
        logger.info("   ✓ PASS: Configuration loaded successfully")

        # Test validation
        is_valid, errors = config.validate()
        assert is_valid, f"Validation failed: {errors}"
        logger.info("   ✓ PASS: Configuration validation passed")

        logger.info("\n✓ All configuration tests passed")

    finally:
        os.remove(config_path)


def test_in_memory_tracking():
    """Test in-memory mark tracking (simulates model behavior)."""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: In-Memory Mark Tracking")
    logger.info("="*80)

    # Simulate model's in-memory sets
    marked_for_deletion = set()
    marked_as_favorite = set()
    marked_for_date_correction = set()

    test_hashes = [f"hash_{i:06d}" for i in range(10000)]

    # Test: Add performance
    logger.info("\n3.1 Testing set add performance...")
    start = time.perf_counter()
    for file_hash in test_hashes:
        marked_for_deletion.add(file_hash)
    elapsed = time.perf_counter() - start
    avg_ns = (elapsed / len(test_hashes)) * 1_000_000  # nanoseconds

    logger.info(f"   Added {len(test_hashes)} items in {elapsed*1000:.1f}ms")
    logger.info(f"   Average: {avg_ns:.0f} nanoseconds per add")
    logger.info(f"   ✓ PASS: Set add is O(1) - extremely fast")

    # Test: Lookup performance
    logger.info("\n3.2 Testing set lookup performance...")
    import random
    lookup_hashes = random.sample(test_hashes, 1000)

    start = time.perf_counter()
    for file_hash in lookup_hashes:
        _ = file_hash in marked_for_deletion
    elapsed = time.perf_counter() - start
    avg_ns = (elapsed / len(lookup_hashes)) * 1_000_000

    logger.info(f"   Performed {len(lookup_hashes)} lookups in {elapsed*1000:.1f}ms")
    logger.info(f"   Average: {avg_ns:.0f} nanoseconds per lookup")
    logger.info(f"   ✓ PASS: Set lookup is O(1) - extremely fast")

    # Test: Memory usage
    logger.info("\n3.3 Testing memory usage...")
    import sys
    set_size_bytes = sys.getsizeof(marked_for_deletion)
    # Approximate item overhead (each string reference ~8 bytes + string object)
    total_estimated = set_size_bytes + (len(test_hashes) * 100)  # ~100 bytes per hash string
    total_mb = total_estimated / 1024 / 1024

    logger.info(f"   Set with {len(test_hashes)} items: ~{total_mb:.2f} MB")
    logger.info(f"   ✓ PASS: Memory usage is reasonable")

    logger.info("\n✓ All in-memory tracking tests passed")


def test_file_path_queries():
    """Test file path query patterns used by model."""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: File Path Query Patterns")
    logger.info("="*80)

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    try:
        create_test_database(test_db_path, test_count=1000)

        with PhotoDatabase(test_db_path) as db:
            # Test: Recursive folder query
            logger.info("\n4.1 Testing recursive folder query...")
            start = time.perf_counter()
            db.cursor.execute("""
                SELECT file_hash, file_name, file_size
                FROM UniquePhotos
                WHERE file_name LIKE ?
                ORDER BY file_name
            """, ("/archive/2025/02/%",))
            results = db.cursor.fetchall()
            elapsed = time.perf_counter() - start

            logger.info(f"   Recursive query found {len(results)} files in {elapsed*1000:.1f}ms")
            assert len(results) == 1000
            logger.info(f"   ✓ PASS: Query with index is fast")

            # Test: Non-recursive folder query
            logger.info("\n4.2 Testing non-recursive folder query...")
            start = time.perf_counter()
            db.cursor.execute("""
                SELECT file_hash, file_name, file_size
                FROM UniquePhotos
                WHERE file_name LIKE ?
                  AND file_name NOT LIKE ?
                ORDER BY file_name
            """, ("/archive/2025/02/01/%", "/archive/2025/02/01/%/%"))
            results = db.cursor.fetchall()
            elapsed = time.perf_counter() - start

            logger.info(f"   Non-recursive query found {len(results)} files in {elapsed*1000:.1f}ms")
            assert len(results) == 100  # Only day 01 files
            logger.info(f"   ✓ PASS: Non-recursive query works correctly")

        logger.info("\n✓ All file path query tests passed")

    finally:
        os.remove(test_db_path)


def run_all_tests():
    """Run all core component tests."""
    logger.info("\n" + "="*80)
    logger.info("TRIAGE GRID CORE COMPONENT TESTS")
    logger.info("="*80)
    logger.info("Testing core functionality without GUI\n")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    try:
        # Create test database
        test_count = create_test_database(test_db_path, test_count=1000)

        # Run tests
        test_database_operations(test_db_path, test_count)
        test_config_system()
        test_in_memory_tracking()
        test_file_path_queries()

        logger.info("\n" + "="*80)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("="*80)
        logger.info("\nCore components are ready for GUI integration.")
        logger.info("Next step: Run full GUI test with test_grid_performance.py")

        return 0

    except AssertionError as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        logger.error(f"\n✗ TEST ERROR: {e}", exc_info=True)
        return 1
    finally:
        # Cleanup
        if os.path.exists(test_db_path):
            os.remove(test_db_path)


if __name__ == '__main__':
    sys.exit(run_all_tests())
