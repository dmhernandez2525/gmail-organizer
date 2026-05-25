"""Tests for the sync scheduler module."""

import json
import pytest
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from gmail_organizer.scheduler import ScheduleConfig, SyncScheduler


class TestScheduleConfig:
    """Tests for the ScheduleConfig dataclass."""

    def test_defaults(self):
        config = ScheduleConfig()
        assert config.enabled is False
        assert config.interval_minutes == 30
        assert config.last_run == ""
        assert config.next_run == ""
        assert config.run_count == 0

    def test_custom_values(self):
        config = ScheduleConfig(
            enabled=True,
            interval_minutes=60,
            last_run="2024-01-01T00:00:00",
            next_run="2024-01-01T01:00:00",
            run_count=5,
        )
        assert config.enabled is True
        assert config.interval_minutes == 60
        assert config.run_count == 5


class TestSyncSchedulerInit:
    """Tests for SyncScheduler initialization."""

    def test_default_config_dir(self, tmp_path, monkeypatch):
        # Patch __file__ so it uses tmp_path
        scheduler = SyncScheduler(config_dir=str(tmp_path / "config"))
        assert scheduler._config_dir.exists()

    def test_custom_config_dir(self, tmp_path):
        config_dir = tmp_path / "my-config"
        scheduler = SyncScheduler(config_dir=str(config_dir))
        assert config_dir.exists()

    def test_loads_existing_config(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_data = {
            "account1": {
                "enabled": True,
                "interval_minutes": 15,
                "last_run": "2024-01-01T00:00:00",
                "next_run": "2024-01-01T00:15:00",
                "run_count": 10,
            }
        }
        config_file = config_dir / "sync_schedule.json"
        config_file.write_text(json.dumps(config_data))

        scheduler = SyncScheduler(config_dir=str(config_dir))
        sched = scheduler.get_schedule("account1")
        assert sched.enabled is True
        assert sched.interval_minutes == 15
        assert sched.run_count == 10

    def test_handles_corrupt_config(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "sync_schedule.json"
        config_file.write_text("NOT VALID JSON")

        # Should not raise
        scheduler = SyncScheduler(config_dir=str(config_dir))
        assert scheduler.get_all_schedules() == {}


class TestGetSchedule:
    """Tests for get_schedule."""

    def test_returns_default_for_new_account(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        sched = scheduler.get_schedule("new-account")
        assert sched.enabled is False
        assert sched.interval_minutes == 30

    def test_returns_same_object(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        s1 = scheduler.get_schedule("acct")
        s2 = scheduler.get_schedule("acct")
        assert s1 is s2


class TestGetAllSchedules:
    """Tests for get_all_schedules."""

    def test_returns_copy(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.get_schedule("a")
        scheduler.get_schedule("b")
        all_scheds = scheduler.get_all_schedules()
        assert len(all_scheds) == 2
        assert "a" in all_scheds
        assert "b" in all_scheds


class TestUpdateSchedule:
    """Tests for update_schedule."""

    def test_enable_schedule(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct", enabled=True, interval_minutes=10)
        sched = scheduler.get_schedule("acct")
        assert sched.enabled is True
        assert sched.interval_minutes == 10
        assert sched.next_run != ""

    def test_disable_clears_next_run(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct", enabled=True, interval_minutes=10)
        scheduler.stop()  # prevent background thread interference
        scheduler.update_schedule("acct", enabled=False)
        sched = scheduler.get_schedule("acct")
        assert sched.enabled is False
        assert sched.next_run == ""

    def test_interval_clamped_min(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct", interval_minutes=1)
        sched = scheduler.get_schedule("acct")
        assert sched.interval_minutes == 5  # min is 5

    def test_interval_clamped_max(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct", interval_minutes=9999)
        sched = scheduler.get_schedule("acct")
        assert sched.interval_minutes == 1440  # max is 1440

    def test_saves_config_to_disk(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct", enabled=True, interval_minutes=20)
        scheduler.stop()

        config_path = tmp_path / "sync_schedule.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "acct" in data
        assert data["acct"]["enabled"] is True
        assert data["acct"]["interval_minutes"] == 20

    def test_starts_scheduler_when_enabled(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        assert not scheduler.is_running()
        scheduler.update_schedule("acct", enabled=True)
        assert scheduler.is_running()
        scheduler.stop()

    def test_stops_scheduler_when_all_disabled(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct", enabled=True)
        scheduler.update_schedule("acct", enabled=False)
        assert not scheduler.is_running()


class TestStartStop:
    """Tests for start and stop."""

    def test_start_creates_thread(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.start()
        assert scheduler.is_running()
        assert scheduler._thread is not None
        assert scheduler._thread.daemon is True
        scheduler.stop()

    def test_start_idempotent(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.start()
        thread1 = scheduler._thread
        scheduler.start()  # second call should be a no-op
        assert scheduler._thread is thread1
        scheduler.stop()

    def test_stop_sets_running_false(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.start()
        scheduler.stop()
        assert not scheduler.is_running()


class TestSetSyncCallback:
    """Tests for set_sync_callback."""

    def test_callback_stored(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        cb = MagicMock()
        scheduler.set_sync_callback(cb)
        assert scheduler._sync_callback is cb


class TestCheckAndTrigger:
    """Tests for _check_and_trigger."""

    def test_triggers_due_account(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        callback = MagicMock()
        scheduler.set_sync_callback(callback)

        # Set up a schedule that is past due
        past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        scheduler.update_schedule("acct", enabled=True, interval_minutes=10)
        scheduler.stop()  # stop background thread
        scheduler._schedules["acct"].next_run = past_time

        scheduler._check_and_trigger()
        callback.assert_called_once_with("acct")

    def test_does_not_trigger_future_schedule(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        callback = MagicMock()
        scheduler.set_sync_callback(callback)

        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        scheduler.update_schedule("acct", enabled=True, interval_minutes=60)
        scheduler.stop()
        scheduler._schedules["acct"].next_run = future_time

        scheduler._check_and_trigger()
        callback.assert_not_called()

    def test_does_not_trigger_disabled(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        callback = MagicMock()
        scheduler.set_sync_callback(callback)

        scheduler.update_schedule("acct", enabled=False)
        scheduler._check_and_trigger()
        callback.assert_not_called()

    def test_skips_invalid_next_run(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        callback = MagicMock()
        scheduler.set_sync_callback(callback)

        scheduler.update_schedule("acct", enabled=True)
        scheduler.stop()
        scheduler._schedules["acct"].next_run = "not-a-date"

        scheduler._check_and_trigger()
        callback.assert_not_called()


class TestTriggerSync:
    """Tests for _trigger_sync."""

    def test_successful_trigger_updates_state(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        callback = MagicMock()
        scheduler.set_sync_callback(callback)

        scheduler.update_schedule("acct", enabled=True, interval_minutes=15)
        scheduler.stop()

        old_next = scheduler._schedules["acct"].next_run
        scheduler._trigger_sync("acct")

        sched = scheduler.get_schedule("acct")
        assert sched.run_count == 1
        assert sched.last_run != ""
        assert sched.next_run != old_next  # next_run was updated

    def test_failed_callback_still_reschedules(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        callback = MagicMock(side_effect=Exception("sync failed"))
        scheduler.set_sync_callback(callback)

        scheduler.update_schedule("acct", enabled=True, interval_minutes=15)
        scheduler.stop()
        old_count = scheduler._schedules["acct"].run_count

        scheduler._trigger_sync("acct")

        sched = scheduler.get_schedule("acct")
        # run_count should NOT increment on failure
        assert sched.run_count == old_count
        # next_run should still be updated
        assert sched.next_run != ""

    def test_no_callback_set(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct", enabled=True)
        scheduler.stop()
        # Should not raise
        scheduler._trigger_sync("acct")


class TestSchedulerLoop:
    """Tests for the background scheduler loop."""

    @patch("gmail_organizer.scheduler.time.sleep", side_effect=StopIteration)
    def test_loop_calls_check_and_exits(self, mock_sleep, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler._running = True

        with pytest.raises(StopIteration):
            scheduler._scheduler_loop()

        mock_sleep.assert_called_once_with(30)

    def test_loop_exits_when_stopped(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler._running = False
        # Should return immediately without calling sleep
        scheduler._scheduler_loop()


class TestGetStatusSummary:
    """Tests for get_status_summary."""

    def test_empty_state(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        status = scheduler.get_status_summary()
        assert status["scheduler_running"] is False
        assert status["enabled_count"] == 0
        assert status["total_accounts"] == 0
        assert status["next_sync_time"] is None
        assert status["next_sync_account"] == ""

    def test_with_enabled_accounts(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("acct1", enabled=True, interval_minutes=10)
        scheduler.update_schedule("acct2", enabled=True, interval_minutes=20)
        scheduler.stop()

        status = scheduler.get_status_summary()
        assert status["enabled_count"] == 2
        assert status["total_accounts"] == 2
        assert status["next_sync_time"] is not None
        assert status["next_sync_account"] in ("acct1", "acct2")

    def test_next_sync_picks_earliest(self, tmp_path):
        scheduler = SyncScheduler(config_dir=str(tmp_path))
        scheduler.update_schedule("later", enabled=True, interval_minutes=60)
        scheduler.stop()
        scheduler.update_schedule("sooner", enabled=True, interval_minutes=5)
        scheduler.stop()

        # Manually set next_run to control ordering
        scheduler._schedules["sooner"].next_run = "2024-01-01T00:05:00"
        scheduler._schedules["later"].next_run = "2024-01-01T01:00:00"

        status = scheduler.get_status_summary()
        assert status["next_sync_account"] == "sooner"
        assert status["next_sync_time"] == "2024-01-01T00:05:00"


class TestSaveLoadRoundTrip:
    """Tests for config persistence."""

    def test_save_and_reload(self, tmp_path):
        config_dir = str(tmp_path / "state")
        scheduler1 = SyncScheduler(config_dir=config_dir)
        scheduler1.update_schedule("acct", enabled=True, interval_minutes=45)
        scheduler1.stop()

        # Create a new scheduler that loads from the same directory
        scheduler2 = SyncScheduler(config_dir=config_dir)
        sched = scheduler2.get_schedule("acct")
        assert sched.enabled is True
        assert sched.interval_minutes == 45
