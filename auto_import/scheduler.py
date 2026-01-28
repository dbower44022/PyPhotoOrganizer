"""
Scheduler for Auto-Import Service.

Handles timing calculations for interval and cron-based scheduling.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from auto_import.config import ScheduleConfig

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Handles scheduling logic for the auto-import service.

    Supports:
    - Interval mode: Run every N minutes
    - Cron mode: Run at specific times (simplified cron syntax)
    - Continuous mode: Run as fast as possible
    """

    def __init__(self, config: ScheduleConfig):
        """
        Initialize Scheduler.

        Args:
            config: Schedule configuration
        """
        self.config = config
        self._last_run: Optional[datetime] = None

    def get_next_run_time(self, from_time: datetime = None) -> datetime:
        """
        Calculate next run time.

        Args:
            from_time: Calculate from this time (default: now)

        Returns:
            datetime of next scheduled run
        """
        if from_time is None:
            from_time = datetime.now()

        if self.config.mode == 'continuous':
            # Run immediately
            return from_time

        elif self.config.mode == 'interval':
            return self._get_next_interval_time(from_time)

        elif self.config.mode == 'cron':
            return self._get_next_cron_time(from_time)

        else:
            logger.warning(f"Unknown schedule mode: {self.config.mode}, using interval")
            return self._get_next_interval_time(from_time)

    def _get_next_interval_time(self, from_time: datetime) -> datetime:
        """Calculate next run time for interval mode."""
        if self._last_run is None:
            # First run - run now
            return from_time

        next_run = self._last_run + timedelta(minutes=self.config.interval_minutes)

        # If we're past the next scheduled time, run now
        if from_time >= next_run:
            return from_time

        return next_run

    def _get_next_cron_time(self, from_time: datetime) -> datetime:
        """
        Calculate next run time for cron mode.

        Supports simplified cron format: minute hour day_of_month month day_of_week
        Uses * for wildcards and specific numbers.
        """
        try:
            return self._parse_cron_next(from_time)
        except Exception as e:
            logger.error(f"Cron parsing error: {e}, falling back to interval")
            return self._get_next_interval_time(from_time)

    def _parse_cron_next(self, from_time: datetime) -> datetime:
        """Parse cron expression and find next matching time."""
        parts = self.config.cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {self.config.cron_expression}")

        minute, hour, day, month, dow = parts

        # Start from next minute
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Search for next matching time (limit to 366 days to avoid infinite loop)
        max_iterations = 366 * 24 * 60  # One year of minutes

        for _ in range(max_iterations):
            if (self._matches_cron_field(minute, candidate.minute) and
                self._matches_cron_field(hour, candidate.hour) and
                self._matches_cron_field(day, candidate.day) and
                self._matches_cron_field(month, candidate.month) and
                self._matches_cron_dow(dow, candidate.weekday())):
                return candidate

            candidate += timedelta(minutes=1)

        # If no match found within a year, use interval fallback
        logger.warning("Could not find next cron match, using interval fallback")
        return from_time + timedelta(minutes=self.config.interval_minutes)

    def _matches_cron_field(self, field: str, value: int) -> bool:
        """Check if value matches cron field expression."""
        if field == '*':
            return True

        # Handle */N (every N)
        if field.startswith('*/'):
            try:
                interval = int(field[2:])
                return value % interval == 0
            except ValueError:
                return False

        # Handle ranges (e.g., 1-5)
        if '-' in field:
            try:
                start, end = field.split('-')
                return int(start) <= value <= int(end)
            except ValueError:
                return False

        # Handle lists (e.g., 1,3,5)
        if ',' in field:
            try:
                values = [int(v.strip()) for v in field.split(',')]
                return value in values
            except ValueError:
                return False

        # Handle single value
        try:
            return int(field) == value
        except ValueError:
            return False

    def _matches_cron_dow(self, field: str, weekday: int) -> bool:
        """
        Check if weekday matches cron day-of-week field.

        Cron uses 0-6 (Sunday=0), Python uses 0-6 (Monday=0).
        We convert Python weekday to cron format.
        """
        if field == '*':
            return True

        # Convert Python weekday (Monday=0) to cron (Sunday=0)
        cron_dow = (weekday + 1) % 7

        return self._matches_cron_field(field, cron_dow)

    def mark_run_completed(self):
        """Mark that a run has completed."""
        self._last_run = datetime.now()

    def get_seconds_until_next_run(self) -> float:
        """
        Get seconds until next scheduled run.

        Returns:
            Seconds until next run (0 if should run now)
        """
        next_run = self.get_next_run_time()
        delta = (next_run - datetime.now()).total_seconds()
        return max(0, delta)

    def should_run_now(self) -> bool:
        """
        Check if we should run now.

        Returns:
            True if it's time to run
        """
        if self.config.mode == 'continuous':
            return True

        next_run = self.get_next_run_time()
        return datetime.now() >= next_run

    def get_schedule_description(self) -> str:
        """Get human-readable description of schedule."""
        if self.config.mode == 'continuous':
            return "Continuous (as fast as possible)"

        elif self.config.mode == 'interval':
            interval = self.config.interval_minutes
            if interval == 1:
                return "Every minute"
            elif interval < 60:
                return f"Every {interval} minutes"
            elif interval == 60:
                return "Every hour"
            elif interval % 60 == 0:
                hours = interval // 60
                return f"Every {hours} hours"
            else:
                hours = interval // 60
                mins = interval % 60
                return f"Every {hours}h {mins}m"

        elif self.config.mode == 'cron':
            return f"Cron: {self.config.cron_expression}"

        return f"Unknown mode: {self.config.mode}"

    def get_status(self) -> dict:
        """Get scheduler status information."""
        now = datetime.now()
        next_run = self.get_next_run_time(now)

        return {
            'mode': self.config.mode,
            'description': self.get_schedule_description(),
            'last_run': self._last_run.isoformat() if self._last_run else None,
            'next_run': next_run.isoformat(),
            'seconds_until_next': self.get_seconds_until_next_run(),
            'quiet_hours': {
                'enabled': bool(self.config.quiet_hours_start),
                'start': self.config.quiet_hours_start,
                'end': self.config.quiet_hours_end,
                'currently_active': self.config.is_quiet_hours(),
            },
        }
