"""
Three-Tier Thumbnail Caching System

Provides high-performance thumbnail access through three cache levels:
- L1: Memory cache (LRU OrderedDict, ~500 items, <1ms access)
- L2: Disk cache (JPEG files, 50-100ms access)
- L3: Original files (full decode + resize, 500-2000ms)

Performance targets:
- Memory hit: <1ms
- Disk hit: 50-100ms
- Miss (generate): 500-2000ms (async, returns placeholder immediately)

Key features:
- Prefetching (load visible + next/previous N items)
- Background generation (QThreadPool)
- LRU eviction (memory and disk)
- Automatic cache cleanup
"""

import logging
import os
import threading
import queue
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from PySide6.QtCore import QThreadPool, Qt, QObject, Signal
from PySide6.QtGui import QPixmap

from triage.thumbnail_generator import ThumbnailWorker, PlaceholderGenerator
from triage.triage_database import TriageDatabase

logger = logging.getLogger(__name__)


class ThumbnailCache(QObject):
    """
    Three-tier LRU cache for thumbnails.

    Architecture:
    1. Memory cache: OrderedDict of QPixmap objects (instant access)
    2. Disk cache: JPEG files on disk (fast access)
    3. Original files: Generate on-demand (slow, async)

    Signals:
        thumbnail_ready(str, int): Emitted when thumbnail generation completes
                                   Args: file_hash, size

    Usage:
        cache = ThumbnailCache(db_path, cache_dir)
        cache.thumbnail_ready.connect(on_thumbnail_loaded)
        pixmap = cache.get_thumbnail(file_hash, file_path, size=256)
        # Returns immediately (None if not ready)
        # Emits thumbnail_ready signal when available
    """

    # Signal emitted when a thumbnail finishes generating and is added to cache
    thumbnail_ready = Signal(str, int)  # file_hash, size

    def __init__(self, db_path: str, cache_dir: str,
                 memory_size: int = 500, disk_size_gb: int = 5,
                 worker_threads: int = 8, parent=None):
        """
        Initialize three-tier cache.

        Args:
            db_path: Path to SQLite database
            cache_dir: Root directory for disk cache
            memory_size: Max thumbnails in memory (default: 500)
            disk_size_gb: Max disk cache size in GB (default: 5)
            worker_threads: Number of background thumbnail workers (default: 8)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.db_path = db_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # L1: Memory cache (LRU OrderedDict)
        # Key: "{file_hash}_{size}", Value: QPixmap
        self.memory_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self.memory_size = memory_size

        # L2: Disk cache
        self.disk_size_bytes = disk_size_gb * 1024 * 1024 * 1024
        self.triage_db = TriageDatabase(db_path)

        # Ensure triage tables exist and are up-to-date
        self.triage_db.ensure_triage_tables()

        # L3: Background thumbnail generation
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(worker_threads)

        # Track in-progress generations to avoid duplicates
        self._generating: set = set()  # Set of cache keys being generated

        # Async database write queue (eliminates contention and UI blocking)
        self._db_write_queue = queue.Queue()
        self._db_writer_thread = threading.Thread(
            target=self._database_writer_worker,
            daemon=True,  # Allow graceful shutdown
            name="ThumbnailCacheDBWriter"
        )
        self._db_writer_running = True
        self._db_writer_thread.start()

        # Statistics
        self.stats = {
            'memory_hits': 0,
            'disk_hits': 0,
            'misses': 0,
            'generated': 0,
            'errors': 0,
            'db_writes_queued': 0,
            'db_writes_completed': 0
        }

        # Placeholder generator
        self.placeholder_gen = PlaceholderGenerator()

        # Cache warming control
        self._warming_stop_requested = False

        logger.info(f"Thumbnail cache initialized: memory={memory_size}, "
                   f"disk={disk_size_gb}GB, workers={worker_threads}, "
                   f"async_db_writes=enabled")

    def get_thumbnail(self, file_hash: str, file_path: str,
                     size: int = 256, priority: str = 'normal') -> QPixmap:
        """
        Get thumbnail with three-tier fallback.

        Returns immediately - either cached thumbnail or placeholder.
        If not cached, queues background generation.

        Args:
            file_hash: SHA-256 hash from UniquePhotos
            file_path: Full path to original image
            size: Thumbnail size in pixels (256, 512, or 1024)
            priority: 'high' (visible), 'normal' (prefetch), 'low' (background)

        Returns:
            QPixmap (either cached or placeholder)
        """
        cache_key = f"{file_hash}_{size}"

        # L1: Check memory cache (instant)
        if cache_key in self.memory_cache:
            # Move to end (LRU touch)
            self.memory_cache.move_to_end(cache_key)
            self.stats['memory_hits'] += 1
            logger.debug(f"Memory hit: {file_hash[:8]}... size={size}")
            return self.memory_cache[cache_key]

        # L2: Check disk cache (50-100ms)
        cache_entry = self.triage_db.get_thumbnail(file_hash, size)
        if cache_entry:
            disk_path = cache_entry['thumbnail_path']
            if os.path.exists(disk_path):
                pixmap = QPixmap(disk_path)
                if not pixmap.isNull():
                    # Add to memory cache
                    self._add_to_memory_cache(cache_key, pixmap)
                    self.stats['disk_hits'] += 1
                    logger.debug(f"Disk hit: {file_hash[:8]}... size={size}")
                    return pixmap

        # L3: Generate from original (async) - return None (delegate will draw placeholder)
        self.stats['misses'] += 1
        logger.debug(f"Cache miss: {file_hash[:8]}... size={size} - queueing generation")
        self._queue_generation(file_hash, file_path, size, priority)

        # CRITICAL FIX: Return None instead of creating QPixmap placeholder
        # Qt crashes when trying to render QPixmaps created in memory (even simple fill)
        # But works fine with QPixmaps loaded from disk
        # Let the delegate draw the placeholder directly during paint() instead
        return None

    def prefetch(self, file_items: List[Dict[str, Any]],
                visible_range: Tuple[int, int], prefetch_count: int = 50):
        """
        Prefetch thumbnails for items near visible area.

        Strategy: Load visible items (high priority) + next/previous N items (normal priority)

        Args:
            file_items: List of file dicts with 'file_hash' and 'file_path' keys
            visible_range: (start_index, end_index) of visible items
            prefetch_count: Number of items to prefetch before/after visible area
        """
        if not file_items:
            return

        start_idx, end_idx = visible_range
        total_items = len(file_items)

        # Prefetch range: visible +/- prefetch_count
        prefetch_start = max(0, start_idx - prefetch_count)
        prefetch_end = min(total_items, end_idx + prefetch_count)

        prefetched = 0
        for i in range(prefetch_start, prefetch_end):
            if i >= len(file_items):
                break

            item = file_items[i]
            file_hash = item.get('file_hash')
            file_path = item.get('file_path')

            if not file_hash or not file_path:
                continue

            # Determine priority: high for visible, normal for prefetch
            priority = 'high' if start_idx <= i < end_idx else 'normal'

            # This will return immediately (cached or placeholder)
            self.get_thumbnail(file_hash, file_path, size=256, priority=priority)
            prefetched += 1

        logger.debug(f"Prefetched {prefetched} thumbnails "
                    f"(visible: {end_idx - start_idx}, "
                    f"range: {prefetch_start}-{prefetch_end})")

    def prefetch_directional(self, file_items: List[Dict[str, Any]],
                            visible_range: Tuple[int, int],
                            prefetch_before: int = 50,
                            prefetch_after: int = 100,
                            thumbnail_size: int = 200):
        """
        Direction-aware prefetch with asymmetric before/after counts.

        This method is optimized for smooth scrolling by:
        1. Loading visible items with HIGH priority
        2. Loading items in scroll direction with NORMAL priority
        3. Loading items opposite to scroll direction with LOW priority
        4. Using the correct thumbnail size (not hardcoded)

        Args:
            file_items: List of file dicts with 'file_hash' and 'file_path'/'archive_path' keys
            visible_range: (start_index, end_index) of visible items
            prefetch_before: Number of items to prefetch before visible area
            prefetch_after: Number of items to prefetch after visible area
            thumbnail_size: Size of thumbnails to generate (default: 200)
        """
        if not file_items:
            return

        start_idx, end_idx = visible_range
        total_items = len(file_items)

        if start_idx >= total_items or end_idx <= 0:
            return

        # Clamp ranges
        start_idx = max(0, start_idx)
        end_idx = min(total_items, end_idx)

        # Calculate prefetch ranges
        prefetch_start = max(0, start_idx - prefetch_before)
        prefetch_end = min(total_items, end_idx + prefetch_after)

        # Track stats
        high_priority_count = 0
        normal_priority_count = 0
        low_priority_count = 0

        # Process in order: visible (high), after (normal), before (low)
        # This ensures scroll direction gets priority in the thread pool

        # 1. High priority: visible items
        for i in range(start_idx, end_idx):
            if i >= total_items:
                break
            item = file_items[i]
            file_hash = item.get('file_hash')
            # Support both 'file_path' and 'archive_path' keys
            file_path = item.get('file_path') or item.get('archive_path')

            if file_hash and file_path:
                self.get_thumbnail(file_hash, file_path, size=thumbnail_size, priority='high')
                high_priority_count += 1

        # 2. Normal priority: items after visible (scroll down direction)
        for i in range(end_idx, prefetch_end):
            if i >= total_items:
                break
            item = file_items[i]
            file_hash = item.get('file_hash')
            file_path = item.get('file_path') or item.get('archive_path')

            if file_hash and file_path:
                self.get_thumbnail(file_hash, file_path, size=thumbnail_size, priority='normal')
                normal_priority_count += 1

        # 3. Low priority: items before visible (scroll up direction - less common)
        for i in range(prefetch_start, start_idx):
            if i >= total_items:
                break
            item = file_items[i]
            file_hash = item.get('file_hash')
            file_path = item.get('file_path') or item.get('archive_path')

            if file_hash and file_path:
                self.get_thumbnail(file_hash, file_path, size=thumbnail_size, priority='low')
                low_priority_count += 1

        total_prefetched = high_priority_count + normal_priority_count + low_priority_count
        logger.debug(f"Directional prefetch: visible={end_idx - start_idx}, "
                    f"high={high_priority_count}, normal={normal_priority_count}, "
                    f"low={low_priority_count}, total={total_prefetched}, size={thumbnail_size}")

    def _add_to_memory_cache(self, cache_key: str, pixmap: QPixmap):
        """
        Add pixmap to memory cache with LRU eviction.

        Args:
            cache_key: "{file_hash}_{size}"
            pixmap: QPixmap to cache
        """
        # Add to cache
        self.memory_cache[cache_key] = pixmap

        # Evict oldest if over limit
        while len(self.memory_cache) > self.memory_size:
            evicted_key, evicted_pixmap = self.memory_cache.popitem(last=False)
            logger.debug(f"Evicted from memory cache: {evicted_key}")

    def _queue_generation(self, file_hash: str, file_path: str,
                         size: int, priority: str):
        """
        Queue thumbnail generation with priority.

        Args:
            file_hash: SHA-256 hash
            file_path: Path to original image
            size: Thumbnail size (256, 512, 1024)
            priority: 'high', 'normal', or 'low'
        """
        cache_key = f"{file_hash}_{size}"

        # Skip if already generating
        if cache_key in self._generating:
            return

        # Mark as generating
        self._generating.add(cache_key)

        # Create worker
        worker = ThumbnailWorker(
            file_hash=file_hash,
            file_path=file_path,
            size=size,
            cache_dir=self.cache_dir,
            cache=self  # Pass cache reference for async DB writes
        )

        # Connect signals
        worker.signals.finished.connect(self._on_thumbnail_generated)
        worker.signals.error.connect(self._on_generation_error)

        # Queue with priority
        # QThreadPool priority: higher number = higher priority
        priority_map = {'high': 10, 'normal': 5, 'low': 0}
        thread_priority = priority_map.get(priority, 5)

        self.thread_pool.start(worker, priority=thread_priority)
        logger.debug(f"Queued thumbnail generation: {file_hash[:8]}... "
                    f"size={size} priority={priority}")

    def _on_thumbnail_generated(self, file_hash: str, size: int, disk_path: str):
        """
        Handle completed thumbnail generation.

        CRITICAL: This runs in the main GUI thread - safe to create QPixmap here!

        Args:
            file_hash: SHA-256 hash
            size: Thumbnail size
            disk_path: Path to thumbnail JPEG file on disk
        """
        try:
            cache_key = f"{file_hash}_{size}"

            # Check if this thumbnail is still needed (might have switched folders)
            if cache_key not in self._generating:
                logger.debug(f"Ignoring stale thumbnail generation: {file_hash[:8]}... size={size}")
                return

            # CRITICAL: Validate file exists before trying to load QPixmap
            # Qt can crash internally if file doesn't exist or is corrupted
            if not os.path.exists(disk_path):
                logger.error(f"Thumbnail file does not exist: {disk_path}")
                self._generating.discard(cache_key)
                self.stats['errors'] += 1
                return

            # Validate file size (ensure it's not 0 bytes from failed write)
            try:
                file_size = os.path.getsize(disk_path)
                if file_size == 0:
                    logger.error(f"Thumbnail file is 0 bytes (failed write): {disk_path}")
                    self._generating.discard(cache_key)
                    self.stats['errors'] += 1
                    # Delete the empty file
                    try:
                        os.remove(disk_path)
                    except:
                        pass
                    return
            except OSError as e:
                logger.error(f"Cannot access thumbnail file {disk_path}: {e}")
                self._generating.discard(cache_key)
                self.stats['errors'] += 1
                return

            # Load QPixmap from disk (MAIN THREAD - SAFE!)
            pixmap = QPixmap(disk_path)

            if pixmap.isNull():
                logger.warning(f"QPixmap failed to load thumbnail from {disk_path} (file exists but is invalid)")
                self._generating.discard(cache_key)
                self.stats['errors'] += 1
                # Delete the corrupted file
                try:
                    os.remove(disk_path)
                    logger.debug(f"Deleted corrupted thumbnail: {disk_path}")
                except Exception as del_error:
                    logger.debug(f"Could not delete corrupted thumbnail: {del_error}")
                return

            # Add to memory cache
            self._add_to_memory_cache(cache_key, pixmap)

            # Mark as no longer generating
            self._generating.discard(cache_key)

            self.stats['generated'] += 1
            logger.debug(f"Thumbnail generated: {file_hash[:8]}... size={size}")

            # Emit signal to notify model/view that thumbnail is ready
            self.thumbnail_ready.emit(file_hash, size)

        except Exception as e:
            logger.error(f"Error loading generated thumbnail: {e}", exc_info=True)
            # Ensure we always clean up the generating flag
            try:
                self._generating.discard(f"{file_hash}_{size}")
            except:
                pass
            self.stats['errors'] += 1

    def _on_generation_error(self, file_hash: str, error_msg: str):
        """
        Handle thumbnail generation error.

        Args:
            file_hash: SHA-256 hash
            error_msg: Error message
        """
        try:
            # Remove from generating set (allow retry later)
            # Use list() to create a copy before iterating (thread-safe)
            for cache_key in list(self._generating):
                if cache_key.startswith(file_hash):
                    self._generating.discard(cache_key)

            self.stats['errors'] += 1
            logger.warning(f"Thumbnail generation error for {file_hash[:8]}...: {error_msg}")

        except Exception as e:
            # Don't crash if error handling itself fails
            logger.error(f"Error in error handler for {file_hash[:8]}...: {e}", exc_info=True)
            # Try to at least increment error count
            try:
                self.stats['errors'] += 1
            except:
                pass

    def cleanup_disk_cache(self):
        """
        Clean up disk cache using LRU eviction if over size limit.

        Returns:
            Number of thumbnails deleted
        """
        deleted_count = self.triage_db.cleanup_lru_thumbnails(self.disk_size_bytes)

        if deleted_count > 0:
            logger.info(f"Disk cache cleanup: deleted {deleted_count} thumbnails")

        return deleted_count

    def clear_memory_cache(self):
        """Clear all thumbnails from memory cache."""
        count = len(self.memory_cache)
        self.memory_cache.clear()
        logger.info(f"Cleared {count} thumbnails from memory cache")

    def invalidate_hash(self, file_hash: str):
        """
        Invalidate all cached thumbnails for a specific file hash.

        Used when file is modified (rotated, edited) and hash changes.
        Removes thumbnails from both memory and disk cache.

        Args:
            file_hash: SHA-256 hash to invalidate
        """
        # Remove from memory cache (all sizes)
        memory_removed = 0
        keys_to_remove = [key for key in self.memory_cache.keys() if key.startswith(f"{file_hash}_")]
        for key in keys_to_remove:
            del self.memory_cache[key]
            memory_removed += 1

        # Remove from disk cache database and files
        disk_removed = self.triage_db.delete_thumbnails_for_hash(file_hash)

        if memory_removed > 0 or disk_removed > 0:
            logger.info(f"Invalidated thumbnails for hash {file_hash[:8]}... "
                       f"(memory: {memory_removed}, disk: {disk_removed})")

    def cancel_all_generation(self):
        """
        Cancel all pending thumbnail generation.

        Call this when switching folders to prevent old workers from
        completing and trying to update the cache with stale data.
        """
        # Clear the generating set
        generating_count = len(self._generating)
        self._generating.clear()

        # Note: We cannot cancel already-running workers in QThreadPool
        # But we clear the generating set so when they complete,
        # _on_thumbnail_generated will see they're not in the set and ignore them

        if generating_count > 0:
            logger.info(f"Cancelled {generating_count} pending thumbnail generations")

    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dict with cache hit/miss stats
        """
        total_requests = (self.stats['memory_hits'] +
                         self.stats['disk_hits'] +
                         self.stats['misses'])

        if total_requests > 0:
            memory_hit_rate = self.stats['memory_hits'] / total_requests * 100
            disk_hit_rate = self.stats['disk_hits'] / total_requests * 100
            miss_rate = self.stats['misses'] / total_requests * 100
        else:
            memory_hit_rate = disk_hit_rate = miss_rate = 0.0

        return {
            'total_requests': total_requests,
            'memory_hits': self.stats['memory_hits'],
            'disk_hits': self.stats['disk_hits'],
            'misses': self.stats['misses'],
            'generated': self.stats['generated'],
            'errors': self.stats['errors'],
            'memory_hit_rate': memory_hit_rate,
            'disk_hit_rate': disk_hit_rate,
            'miss_rate': miss_rate,
            'memory_size': len(self.memory_cache),
            'generating': len(self._generating)
        }

    def wait_for_completion(self, timeout_ms: int = 30000):
        """
        Wait for all pending thumbnail generations to complete.

        Args:
            timeout_ms: Timeout in milliseconds (default: 30 seconds)

        Returns:
            True if all completed, False if timeout
        """
        return self.thread_pool.waitForDone(timeout_ms)

    def queue_database_write(self, file_hash: str, disk_path: str, size: int, file_mtime: float):
        """
        Queue a database write operation (non-blocking).

        This is called by thumbnail workers to avoid database contention.
        Writes are processed by a dedicated background thread.

        Args:
            file_hash: SHA-256 hash of source file
            disk_path: Path to cached thumbnail file
            size: Thumbnail size in pixels
            file_mtime: File modification time (timestamp)
        """
        try:
            self._db_write_queue.put({
                'file_hash': file_hash,
                'disk_path': disk_path,
                'size': size,
                'file_mtime': file_mtime
            }, block=False)
            self.stats['db_writes_queued'] += 1
        except queue.Full:
            logger.warning(f"Database write queue full - dropping write for {file_hash[:8]}...")

    def _database_writer_worker(self):
        """
        Background thread that processes database writes from queue.

        This eliminates database lock contention by ensuring only one thread
        writes to the database at a time.
        """
        logger.info("Database writer thread started")

        while self._db_writer_running:
            try:
                # Wait for write operation (1 second timeout for graceful shutdown)
                write_op = self._db_write_queue.get(timeout=1.0)

                # Perform database write
                try:
                    self.triage_db.add_thumbnail(
                        write_op['file_hash'],
                        write_op['disk_path'],
                        write_op['size'],
                        write_op['file_mtime']
                    )
                    self.stats['db_writes_completed'] += 1
                except Exception as e:
                    logger.warning(f"Database write failed for {write_op['file_hash'][:8]}...: {e}")

                self._db_write_queue.task_done()

            except queue.Empty:
                # Timeout - continue loop (allows graceful shutdown)
                continue
            except Exception as e:
                logger.error(f"Database writer thread error: {e}", exc_info=True)

        logger.info("Database writer thread stopped")

    def shutdown(self):
        """
        Gracefully shutdown the thumbnail cache.

        Stops the database writer thread and waits for pending writes.
        """
        logger.info("Shutting down thumbnail cache...")

        # Stop database writer thread
        self._db_writer_running = False

        # Stop any warming operation
        self._warming_stop_requested = True

        # Wait for queue to drain (max 5 seconds)
        try:
            self._db_write_queue.join()
        except Exception as e:
            logger.warning(f"Queue drain timeout: {e}")

        # Wait for thread to finish
        if self._db_writer_thread.is_alive():
            self._db_writer_thread.join(timeout=2.0)

        logger.info(f"Thumbnail cache shutdown complete. "
                   f"Queued: {self.stats['db_writes_queued']}, "
                   f"Completed: {self.stats['db_writes_completed']}")

    # ========================================================================
    # Cache Warming
    # ========================================================================

    # Signal emitted during cache warming progress (current, total, file_hash)
    warming_progress = Signal(int, int, str)
    warming_complete = Signal(int, int, int)  # generated, skipped, errors

    def warm_cache(self, file_items: List[Dict[str, Any]], size: int = 256,
                   batch_size: int = 50, progress_callback=None) -> Dict[str, int]:
        """
        Pre-generate thumbnails for a list of files (cache warming).

        This method processes files in batches, checking if each file already
        has a cached thumbnail before generating. Useful for startup or idle
        time to improve user experience when browsing.

        Args:
            file_items: List of file dicts with 'file_hash' and 'file_path' keys
            size: Thumbnail size to generate (default: 256)
            batch_size: Number of files to queue before yielding (default: 50)
            progress_callback: Optional callback(current, total, file_hash) for progress

        Returns:
            Dict with warming statistics:
                - queued: Number of thumbnails queued for generation
                - skipped: Number already cached (skipped)
                - errors: Number that failed
                - total: Total files processed

        Note:
            This method queues generation in the background. To wait for
            completion, call wait_for_completion() after warming.
        """
        self._warming_stop_requested = False

        stats = {
            'queued': 0,
            'skipped': 0,
            'errors': 0,
            'total': len(file_items)
        }

        if not file_items:
            logger.info("Cache warming: No files to process")
            return stats

        logger.info(f"Cache warming: Starting for {len(file_items)} files, size={size}")

        for idx, item in enumerate(file_items):
            # Check for stop request
            if self._warming_stop_requested:
                logger.info(f"Cache warming: Stopped after {idx} files")
                break

            file_hash = item.get('file_hash')
            file_path = item.get('file_path') or item.get('archive_path')

            if not file_hash or not file_path:
                stats['errors'] += 1
                continue

            # Check if already in memory cache
            cache_key = f"{file_hash}_{size}"
            if cache_key in self.memory_cache:
                stats['skipped'] += 1
                continue

            # Check if already in disk cache
            cache_entry = self.triage_db.get_thumbnail(file_hash, size)
            if cache_entry and os.path.exists(cache_entry['thumbnail_path']):
                stats['skipped'] += 1
                continue

            # Check if file exists
            if not os.path.exists(file_path):
                stats['errors'] += 1
                continue

            # Queue for generation (low priority for warming)
            self._queue_generation(file_hash, file_path, size, priority='low')
            stats['queued'] += 1

            # Progress callback
            if progress_callback:
                progress_callback(idx + 1, len(file_items), file_hash)

            # Emit progress signal
            self.warming_progress.emit(idx + 1, len(file_items), file_hash)

            # Yield periodically to allow other operations
            if stats['queued'] % batch_size == 0:
                # Brief pause to prevent overwhelming the thread pool
                import time
                time.sleep(0.01)

        # Emit completion signal
        self.warming_complete.emit(stats['queued'], stats['skipped'], stats['errors'])

        logger.info(f"Cache warming complete: queued={stats['queued']}, "
                   f"skipped={stats['skipped']}, errors={stats['errors']}")

        return stats

    def warm_cache_async(self, file_items: List[Dict[str, Any]], size: int = 256):
        """
        Start cache warming in a background thread.

        This is a convenience method that runs warm_cache() in a background thread
        so it doesn't block the UI. Progress can be monitored via signals:
        - warming_progress: Emitted for each file (current, total, file_hash)
        - warming_complete: Emitted when done (generated, skipped, errors)

        Args:
            file_items: List of file dicts with 'file_hash' and 'file_path' keys
            size: Thumbnail size to generate (default: 256)
        """
        def _warm_thread():
            try:
                self.warm_cache(file_items, size)
            except Exception as e:
                logger.error(f"Cache warming thread error: {e}", exc_info=True)

        warming_thread = threading.Thread(
            target=_warm_thread,
            daemon=True,
            name="ThumbnailCacheWarming"
        )
        warming_thread.start()
        logger.info(f"Cache warming started in background for {len(file_items)} files")

    def stop_warming(self):
        """
        Request stop of any ongoing cache warming operation.

        The warming will stop at the next file boundary (not immediately).
        """
        self._warming_stop_requested = True
        logger.info("Cache warming stop requested")

    def get_warming_candidates(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get list of files that need thumbnail generation.

        Queries the database for files that don't have cached thumbnails,
        prioritizing recently added files.

        Args:
            limit: Maximum number of files to return (default: 1000)

        Returns:
            List of dicts with 'file_hash' and 'file_path' keys
        """
        try:
            import sqlite3

            candidates = []
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get files from UniquePhotos that don't have thumbnails in cache
                # Priority: most recently added first
                cursor.execute("""
                    SELECT up.file_hash, up.file_name as file_path
                    FROM UniquePhotos up
                    LEFT JOIN ThumbnailCache tc ON up.file_hash = tc.file_hash
                    WHERE tc.file_hash IS NULL
                        AND up.file_name IS NOT NULL
                        AND up.storage_type IN ('archive', 'video_archive')
                    ORDER BY up.rowid DESC
                    LIMIT ?
                """, (limit,))

                for row in cursor.fetchall():
                    candidates.append({
                        'file_hash': row['file_hash'],
                        'file_path': row['file_path']
                    })

            logger.info(f"Found {len(candidates)} cache warming candidates")
            return candidates

        except Exception as e:
            logger.error(f"Error getting warming candidates: {e}", exc_info=True)
            return []


if __name__ == '__main__':
    # Test three-tier caching
    import sys
    import tempfile
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # Create test database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    # Initialize database
    from triage.triage_database import TriageDatabase
    triage_db = TriageDatabase(test_db_path)
    triage_db.ensure_triage_tables()

    # Create test cache directory
    cache_dir = Path(tempfile.gettempdir()) / 'test_thumbnail_cache'

    # Initialize cache
    cache = ThumbnailCache(
        db_path=test_db_path,
        cache_dir=str(cache_dir),
        memory_size=10,
        disk_size_gb=1,
        worker_threads=4
    )

    # Create test image
    from PIL import Image
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        test_image_path = f.name

    test_img = Image.new('RGB', (1920, 1080), color=(100, 150, 200))
    test_img.save(test_image_path, 'JPEG')

    print(f"Created test image: {test_image_path}")

    # Test cache operations
    test_hash = "test_hash_abc123"

    # First request: should miss and queue generation
    print("\n1. First request (expected: cache miss, placeholder returned)")
    pixmap1 = cache.get_thumbnail(test_hash, test_image_path, size=256, priority='high')
    print(f"   Pixmap size: {pixmap1.width()}x{pixmap1.height()}")
    print(f"   Is null: {pixmap1.isNull()}")

    # Wait for generation
    print("\n2. Waiting for thumbnail generation...")
    cache.wait_for_completion(timeout_ms=5000)

    # Second request: should hit memory cache
    print("\n3. Second request (expected: memory cache hit)")
    pixmap2 = cache.get_thumbnail(test_hash, test_image_path, size=256, priority='normal')
    print(f"   Pixmap size: {pixmap2.width()}x{pixmap2.height()}")

    # Clear memory cache
    print("\n4. Clearing memory cache...")
    cache.clear_memory_cache()

    # Third request: should hit disk cache
    print("\n5. Third request (expected: disk cache hit)")
    pixmap3 = cache.get_thumbnail(test_hash, test_image_path, size=256, priority='normal')
    print(f"   Pixmap size: {pixmap3.width()}x{pixmap3.height()}")

    # Print statistics
    print("\n6. Cache statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        if 'rate' in key:
            print(f"   {key}: {value:.1f}%")
        else:
            print(f"   {key}: {value}")

    # Cleanup
    print("\n7. Cleaning up...")
    os.remove(test_image_path)
    os.remove(test_db_path)
    import shutil
    shutil.rmtree(cache_dir)
    print("   ✓ Test completed successfully!")
