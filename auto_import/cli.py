"""
CLI for Auto-Import Service.

Provides command-line interface for managing the auto-import service.
"""

import argparse
import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Optional

# Set up basic logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


def setup_logging(log_file: str = None, log_level: str = 'INFO'):
    """Set up logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_format)
            root_logger.addHandler(file_handler)
            logger.info(f"Logging to file: {log_file}")
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")


def cmd_start(args):
    """Start the auto-import service."""
    from auto_import.config import ConfigManager
    from auto_import.service import ServiceManager

    logger.info("Starting auto-import service...")

    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load()

        # Set up logging from config
        setup_logging(config.log_file, config.log_level)

        # Create and start service
        service = ServiceManager(config)
        service.start()

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Service failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_run_once(args):
    """Run a single import cycle."""
    from auto_import.config import ConfigManager
    from auto_import.service import ServiceManager

    logger.info("Running single import cycle...")

    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load()

        # Set up logging from config
        setup_logging(config.log_file, config.log_level)

        # Create service and run once
        service = ServiceManager(config)
        result = service.run_once()

        # Print summary
        print("\n" + "=" * 50)
        print("Import Cycle Complete")
        print("=" * 50)
        print(f"Files scanned:   {result.files_scanned}")
        print(f"Files imported:  {result.files_imported}")
        print(f"Duplicates:      {result.files_duplicate}")
        print(f"Filtered:        {result.files_filtered}")
        print(f"Failed:          {result.files_failed}")
        print(f"Duration:        {result.duration_seconds:.1f} seconds")

        if result.errors:
            print("\nErrors:")
            for error in result.errors[:10]:
                print(f"  - {error}")
            if len(result.errors) > 10:
                print(f"  ... and {len(result.errors) - 10} more")

        if result.files_failed > 0:
            sys.exit(1)

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_status(args):
    """Show service status."""
    from auto_import.config import ConfigManager
    from auto_import.watcher import DirectoryWatcher
    from auto_import.scheduler import Scheduler

    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load()

        # Check PID file
        pid = None
        running = False
        if config.pid_file and os.path.exists(config.pid_file):
            try:
                with open(config.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                # Check if process is running
                try:
                    os.kill(pid, 0)
                    running = True
                except OSError:
                    running = False
            except (ValueError, IOError):
                pass

        # Print status
        print("\n" + "=" * 50)
        print("Auto-Import Service Status")
        print("=" * 50)

        if running:
            print(f"Service:         RUNNING (PID {pid})")
        else:
            print("Service:         NOT RUNNING")

        print(f"Database:        {config.database_path}")

        # Schedule info
        scheduler = Scheduler(config.schedule)
        print(f"Schedule:        {scheduler.get_schedule_description()}")

        if config.schedule.quiet_hours_start:
            in_quiet = config.schedule.is_quiet_hours()
            quiet_status = "ACTIVE" if in_quiet else "inactive"
            print(f"Quiet hours:     {config.schedule.quiet_hours_start} - "
                  f"{config.schedule.quiet_hours_end} ({quiet_status})")

        # Watch directories
        print("\nWatch Directories:")
        print("-" * 50)

        watcher = DirectoryWatcher(config)
        watch_status = watcher.get_watch_status()

        for path, info in watch_status.items():
            status_parts = []
            status_parts.append("enabled" if info['enabled'] else "disabled")
            status_parts.append("available" if info['available'] else "NOT AVAILABLE")
            status = ", ".join(status_parts)

            print(f"  {info['name']}:")
            print(f"    Path: {path}")
            print(f"    Status: {status}")
            print(f"    Processed files: {info['processed_count']}")

        # Email notification status
        print("\nNotifications:")
        print("-" * 50)
        if config.notifications.enabled and config.notifications.email.is_configured():
            print(f"  Email: enabled ({', '.join(config.notifications.email.recipients)})")
        else:
            print("  Email: disabled or not configured")

        print()

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_stop(args):
    """Stop the running service."""
    from auto_import.config import ConfigManager

    try:
        # Load configuration to get PID file
        config_manager = ConfigManager(args.config)
        config = config_manager.load()

        if not config.pid_file:
            logger.error("No PID file configured")
            sys.exit(1)

        if not os.path.exists(config.pid_file):
            logger.error("PID file not found - service may not be running")
            sys.exit(1)

        # Read PID
        try:
            with open(config.pid_file, 'r') as f:
                pid = int(f.read().strip())
        except (ValueError, IOError) as e:
            logger.error(f"Could not read PID file: {e}")
            sys.exit(1)

        # Send SIGTERM
        logger.info(f"Sending SIGTERM to process {pid}...")
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("Stop signal sent successfully")
        except OSError as e:
            logger.error(f"Could not send signal: {e}")
            sys.exit(1)

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Stop failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_validate(args):
    """Validate configuration file."""
    from auto_import.config import ConfigManager

    try:
        config_manager = ConfigManager(args.config)
        config = config_manager.load()

        print("\n" + "=" * 50)
        print("Configuration Valid")
        print("=" * 50)
        print(f"Database:            {config.database_path}")
        print(f"Watch directories:   {len(config.watch_directories)}")
        print(f"Schedule mode:       {config.schedule.mode}")

        for wd in config.watch_directories:
            available = "✓" if wd.is_available() else "✗"
            enabled = "enabled" if wd.enabled else "disabled"
            print(f"  {available} {wd.path} [{enabled}]")

        print("\nConfiguration is valid and ready to use.")
        print()

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration validation failed:\n{e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_generate_config(args):
    """Generate default configuration file."""
    from auto_import.config import ConfigManager

    output_path = args.output or 'autoimport.yaml'

    if os.path.exists(output_path) and not args.force:
        logger.error(f"File already exists: {output_path}")
        logger.error("Use --force to overwrite")
        sys.exit(1)

    config_content = ConfigManager.generate_default_config()

    try:
        with open(output_path, 'w') as f:
            f.write(config_content)
        logger.info(f"Configuration file generated: {output_path}")
        print(f"\nGenerated configuration file: {output_path}")
        print("Edit this file to configure your watch directories and settings.")
        print()

    except IOError as e:
        logger.error(f"Could not write configuration file: {e}")
        sys.exit(1)


def cmd_test_email(args):
    """Test email configuration."""
    from auto_import.config import ConfigManager
    from auto_import.reporter import ReportManager

    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load()

        if not config.notifications.email.is_configured():
            logger.error("Email is not configured in the configuration file")
            sys.exit(1)

        logger.info("Sending test email...")
        reporter = ReportManager(config)
        reporter.test_email_config()

        print("\nTest email sent successfully!")
        print(f"Check inbox for: {', '.join(config.notifications.email.recipients)}")
        print()

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Email test failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_clear_state(args):
    """Clear processed file state."""
    from auto_import.config import ConfigManager
    from auto_import.watcher import DirectoryWatcher

    try:
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load()

        watcher = DirectoryWatcher(config)

        if args.directory:
            # Find matching watch directory
            watch_dir = None
            for wd in config.watch_directories:
                if wd.path == args.directory or wd.name == args.directory:
                    watch_dir = wd.path
                    break

            if not watch_dir:
                logger.error(f"Watch directory not found: {args.directory}")
                sys.exit(1)

            watcher.clear_processed_files(
                watch_directory=watch_dir,
                older_than_days=args.older_than,
            )
            print(f"Cleared state for: {watch_dir}")

        else:
            watcher.clear_processed_files(older_than_days=args.older_than)
            print("Cleared all processed file state")

        print()

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Clear state failed: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='PyPhotoOrganizer Auto-Import Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate configuration:
    python -m auto_import generate-config -o myconfig.yaml

  Validate configuration:
    python -m auto_import validate -c myconfig.yaml

  Start service:
    python -m auto_import start -c myconfig.yaml

  Run single import:
    python -m auto_import run-once -c myconfig.yaml

  Check status:
    python -m auto_import status -c myconfig.yaml

  Stop service:
    python -m auto_import stop -c myconfig.yaml
"""
    )

    parser.add_argument(
        '--version', action='version',
        version='PyPhotoOrganizer Auto-Import Service 1.0.0'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Start command
    start_parser = subparsers.add_parser('start', help='Start the service')
    start_parser.add_argument(
        '-c', '--config', required=True,
        help='Path to configuration file'
    )
    start_parser.set_defaults(func=cmd_start)

    # Run-once command
    run_parser = subparsers.add_parser('run-once', help='Run single import cycle')
    run_parser.add_argument(
        '-c', '--config', required=True,
        help='Path to configuration file'
    )
    run_parser.set_defaults(func=cmd_run_once)

    # Status command
    status_parser = subparsers.add_parser('status', help='Show service status')
    status_parser.add_argument(
        '-c', '--config', required=True,
        help='Path to configuration file'
    )
    status_parser.set_defaults(func=cmd_status)

    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop the service')
    stop_parser.add_argument(
        '-c', '--config', required=True,
        help='Path to configuration file'
    )
    stop_parser.set_defaults(func=cmd_stop)

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    validate_parser.add_argument(
        '-c', '--config', required=True,
        help='Path to configuration file'
    )
    validate_parser.set_defaults(func=cmd_validate)

    # Generate config command
    gen_parser = subparsers.add_parser('generate-config', help='Generate default config')
    gen_parser.add_argument(
        '-o', '--output', default='autoimport.yaml',
        help='Output file path (default: autoimport.yaml)'
    )
    gen_parser.add_argument(
        '-f', '--force', action='store_true',
        help='Overwrite existing file'
    )
    gen_parser.set_defaults(func=cmd_generate_config)

    # Test email command
    email_parser = subparsers.add_parser('test-email', help='Test email configuration')
    email_parser.add_argument(
        '-c', '--config', required=True,
        help='Path to configuration file'
    )
    email_parser.set_defaults(func=cmd_test_email)

    # Clear state command
    clear_parser = subparsers.add_parser('clear-state', help='Clear processed file state')
    clear_parser.add_argument(
        '-c', '--config', required=True,
        help='Path to configuration file'
    )
    clear_parser.add_argument(
        '-d', '--directory',
        help='Clear only specific watch directory (path or name)'
    )
    clear_parser.add_argument(
        '--older-than', type=int,
        help='Clear entries older than N days'
    )
    clear_parser.set_defaults(func=cmd_clear_state)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run command
    args.func(args)


if __name__ == '__main__':
    main()
