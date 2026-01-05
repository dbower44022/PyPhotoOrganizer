#!/usr/bin/env python3
"""
Test script to verify database_path flow through Config object.

This simulates what main_window.py does when starting processing.
"""

import logging
from config import Config
import constants

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_database_path_flow():
    """Test that database_path flows correctly through Config object."""

    # Simulate what main_window.py does
    logger.info("=" * 80)
    logger.info("TEST: Simulating main_window.py flow")
    logger.info("=" * 80)

    # Simulate: self.current_database_path (what user selected)
    selected_database = "PhotoDB_Test24DB.db"
    logger.info(f"User selected database: '{selected_database}'")

    # Simulate: config = self.settings_tab.get_config()
    # (simplified - just the database_path part)
    config = {
        'database_path': constants.DEFAULT_DATABASE_NAME,  # Line 908 of settings_tab.py
        'source_directory': ['/test/source'],
        'destination_directory': '/test/dest',
        'batch_size': 100,
        'copy_files': True,
        'move_files': False
    }
    logger.info(f"Config from settings_tab (before override): database_path = '{config['database_path']}'")

    # Simulate: config['database_path'] = self.current_database_path
    config['database_path'] = selected_database
    logger.info(f"Config after override: database_path = '{config['database_path']}'")

    # Simulate: self.worker = ProcessingWorker(config)
    # Worker creates: self.config = Config(settings_dict=self.config_dict)
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Creating Config object (simulating worker)")
    logger.info("=" * 80)

    config_obj = Config(settings_dict=config)

    # Simulate: self.config.database_path
    result_database_path = config_obj.database_path

    logger.info("\n" + "=" * 80)
    logger.info("TEST: Results")
    logger.info("=" * 80)
    logger.info(f"Expected database_path: '{selected_database}'")
    logger.info(f"Actual database_path:   '{result_database_path}'")

    if result_database_path == selected_database:
        logger.info("✓ SUCCESS: Database path matches!")
    else:
        logger.error("✗ FAILURE: Database path mismatch!")
        logger.error(f"  Expected: '{selected_database}'")
        logger.error(f"  Got:      '{result_database_path}'")
        return False

    return True

if __name__ == '__main__':
    success = test_database_path_flow()
    exit(0 if success else 1)
