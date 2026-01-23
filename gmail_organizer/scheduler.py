"""Scheduled sync manager for automatic periodic email syncing."""

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled sync."""

    enabled: bool = False
    interval_minutes: int = 30
    last_run: str = ""
    next_run: str = ""
    run_count: int = 0


class SyncScheduler:
    """Manages scheduled automatic syncing for Gmail accounts.

    Runs a background daemon thread that periodically triggers syncs
    according to per-account schedule configurations.
    """

    CONFIG_FILE = "sync_schedule.json"

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the scheduler.

        Args:
            config_dir: Directory to store schedule config.
                       Defaults to .sync-state/ in the project root.
        """
        if config_dir:
            self._config_dir = Path(config_dir)
        else:
            self._config_dir = Path(__file__).parent.parent / ".sync-state"
        self._config_dir.mkdir(exist_ok=True)

        self._schedules: Dict[str, ScheduleConfig] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sync_callback: Optional[Callable] = None

        self._load_config()

    def set_sync_callback(self, callback: Callable[[str], None]):
        """Set the callback function to trigger a sync.

        Args:
            callback: Function that takes account_name and starts a sync.
        """
        self._sync_callback = callback

    def get_schedule(self, account_name: str) -> ScheduleConfig:
        """Get the schedule config for an account.

        Args:
            account_name: Name of the account.

        Returns:
            ScheduleConfig for the account (creates default if not exists).
        """
        with self._lock:
            if account_name not in self._schedules:
                self._schedules[account_name] = ScheduleConfig()
            return self._schedules[account_name]

    def get_all_schedules(self) -> Dict[str, ScheduleConfig]:
        """Get all schedule configurations."""
        with self._lock:
            return dict(self._schedules)

    def update_schedule(
        self,
        account_name: str,
        enabled: Optional[bool] = None,
        interval_minutes: Optional[int] = None,
    ):
        """Update schedule configuration for an account.

        Args:
            account_name: Name of the account.
            enabled: Whether scheduled sync is enabled.
            interval_minutes: Minutes between syncs (5-1440).
        """
        with self._lock:
            if account_name not in self._schedules:
                self._schedules[account_name] = ScheduleConfig()

            schedule = self._schedules[account_name]

            if enabled is not None:
                schedule.enabled = enabled

            if interval_minutes is not None:
                schedule.interval_minutes = max(5, min(1440, interval_minutes))

            if schedule.enabled and not schedule.next_run:
                next_time = datetime.now() + timedelta(minutes=schedule.interval_minutes)
                schedule.next_run = next_time.isoformat()

            if not schedule.enabled:
                schedule.next_run = ""

        self._save_config()

        # Start or stop scheduler thread as needed
        if self._has_any_enabled():
            self.start()
        else:
            self.stop()

    def start(self):
        """Start the scheduler background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True

        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the scheduler background thread."""
        with self._lock:
            self._running = False

    def is_running(self) -> bool:
        """Check if the scheduler is currently active."""
        with self._lock:
            return self._running

    def get_status_summary(self) -> Dict:
        """Get a summary of scheduler status.

        Returns:
            Dict with scheduler_running, enabled_count, next_sync info.
        """
        with self._lock:
            enabled = [
                (name, sched) for name, sched in self._schedules.items()
                if sched.enabled
            ]
            next_sync = None
            next_account = ""
            for name, sched in enabled:
                if sched.next_run:
                    if next_sync is None or sched.next_run < next_sync:
                        next_sync = sched.next_run
                        next_account = name

            return {
                "scheduler_running": self._running,
                "enabled_count": len(enabled),
                "total_accounts": len(self._schedules),
                "next_sync_time": next_sync,
                "next_sync_account": next_account,
            }

    def _scheduler_loop(self):
        """Background thread loop that checks and triggers syncs."""
        while True:
            with self._lock:
                if not self._running:
                    break

            self._check_and_trigger()
            time.sleep(30)  # Check every 30 seconds

    def _check_and_trigger(self):
        """Check if any accounts are due for sync and trigger them."""
        now = datetime.now()

        with self._lock:
            accounts_to_sync = []
            for name, schedule in self._schedules.items():
                if not schedule.enabled:
                    continue
                if not schedule.next_run:
                    continue

                try:
                    next_time = datetime.fromisoformat(schedule.next_run)
                    if now >= next_time:
                        accounts_to_sync.append(name)
                except (ValueError, TypeError):
                    continue

        # Trigger syncs outside the lock
        for account_name in accounts_to_sync:
            self._trigger_sync(account_name)

    def _trigger_sync(self, account_name: str):
        """Trigger a sync for an account and update schedule.

        Args:
            account_name: Account to sync.
        """
        if self._sync_callback:
            try:
                self._sync_callback(account_name)
            except Exception:
                pass

        with self._lock:
            schedule = self._schedules.get(account_name)
            if schedule:
                schedule.last_run = datetime.now().isoformat()
                schedule.run_count += 1
                next_time = datetime.now() + timedelta(minutes=schedule.interval_minutes)
                schedule.next_run = next_time.isoformat()

        self._save_config()

    def _has_any_enabled(self) -> bool:
        """Check if any account has scheduling enabled."""
        with self._lock:
            return any(s.enabled for s in self._schedules.values())

    def _save_config(self):
        """Save schedule configuration to disk."""
        config_path = self._config_dir / self.CONFIG_FILE
        with self._lock:
            data = {
                name: asdict(schedule)
                for name, schedule in self._schedules.items()
            }

        try:
            with open(config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_config(self):
        """Load schedule configuration from disk."""
        config_path = self._config_dir / self.CONFIG_FILE
        if not config_path.exists():
            return

        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            with self._lock:
                for name, config_dict in data.items():
                    self._schedules[name] = ScheduleConfig(**config_dict)
        except Exception:
            pass
