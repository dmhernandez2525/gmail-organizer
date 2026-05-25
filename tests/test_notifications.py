"""Tests for NotificationManager in gmail_organizer/notifications.py."""

import hashlib
import hmac
import json
import socket
import threading
from unittest.mock import MagicMock, patch, call

import pytest

from gmail_organizer.notifications import (
    NotificationEvent,
    NotificationManager,
    WebhookConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager(tmp_path):
    """Create a NotificationManager backed by a temporary directory."""
    return NotificationManager(config_dir=str(tmp_path))


def _public_addrinfo(host="93.184.216.34", port=443):
    """Return a fake getaddrinfo result pointing to a public IP."""
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port)),
    ]


def _private_addrinfo(host="192.168.1.1", port=443):
    """Return a fake getaddrinfo result pointing to a private IP."""
    return [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port)),
    ]


# ---------------------------------------------------------------------------
# _validate_webhook_url tests
# ---------------------------------------------------------------------------

class TestValidateWebhookUrl:
    """Tests for the static _validate_webhook_url method."""

    def test_rejects_http_scheme(self):
        with pytest.raises(ValueError, match="HTTPS"):
            NotificationManager._validate_webhook_url("http://example.com/hook")

    def test_rejects_no_scheme(self):
        with pytest.raises(ValueError):
            NotificationManager._validate_webhook_url("example.com/hook")

    def test_rejects_no_hostname(self):
        with pytest.raises(ValueError, match="no hostname"):
            NotificationManager._validate_webhook_url("https:///path")

    @pytest.mark.parametrize("host", [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "metadata.google.internal",
        "169.254.169.254",
    ])
    def test_rejects_blocked_hosts(self, host):
        with pytest.raises(ValueError, match="blocked host"):
            NotificationManager._validate_webhook_url(f"https://{host}/hook")

    @patch("socket.getaddrinfo", side_effect=socket.gaierror("DNS fail"))
    def test_rejects_unresolvable_hostname(self, mock_dns):
        with pytest.raises(ValueError, match="Cannot resolve"):
            NotificationManager._validate_webhook_url("https://no-such-host.invalid/hook")

    @patch("socket.getaddrinfo", return_value=_private_addrinfo())
    def test_rejects_private_ip(self, mock_dns):
        with pytest.raises(ValueError, match="non-public IP"):
            NotificationManager._validate_webhook_url("https://internal.example.com/hook")

    @patch("socket.getaddrinfo", return_value=_private_addrinfo("127.0.0.2"))
    def test_rejects_loopback_ip(self, mock_dns):
        with pytest.raises(ValueError, match="non-public IP"):
            NotificationManager._validate_webhook_url("https://sneaky.example.com/hook")

    @patch("socket.getaddrinfo", return_value=_private_addrinfo("169.254.1.1"))
    def test_rejects_link_local_ip(self, mock_dns):
        with pytest.raises(ValueError, match="non-public IP"):
            NotificationManager._validate_webhook_url("https://link-local.example.com/hook")

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_accepts_valid_https_public_url(self, mock_dns):
        # Should not raise
        NotificationManager._validate_webhook_url("https://hooks.example.com/endpoint")

    @patch("socket.getaddrinfo", return_value=_private_addrinfo("10.0.0.1"))
    def test_rejects_rfc1918_10_range(self, mock_dns):
        with pytest.raises(ValueError, match="non-public IP"):
            NotificationManager._validate_webhook_url("https://internal.corp/hook")


# ---------------------------------------------------------------------------
# add_webhook / get_webhooks
# ---------------------------------------------------------------------------

class TestAddWebhook:
    """Tests for adding webhooks and listing them."""

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_add_webhook_returns_config(self, mock_dns, manager):
        wh = manager.add_webhook(
            url="https://hooks.example.com/a",
            name="My Hook",
            events=["sync_complete", "security_alert"],
            secret="s3cret",
        )
        assert isinstance(wh, WebhookConfig)
        assert wh.url == "https://hooks.example.com/a"
        assert wh.name == "My Hook"
        assert wh.events == ["sync_complete", "security_alert"]
        assert wh.secret == "s3cret"
        assert wh.enabled is True

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_add_webhook_appears_in_list(self, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/b")
        hooks = manager.get_webhooks()
        assert len(hooks) == 1
        assert hooks[0].url == "https://hooks.example.com/b"

    def test_add_webhook_rejects_bad_url(self, manager):
        with pytest.raises(ValueError):
            manager.add_webhook(url="http://evil.com/hook")

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_add_webhook_default_name_from_url(self, mock_dns, manager):
        url = "https://hooks.example.com/default-name-test"
        wh = manager.add_webhook(url=url)
        assert wh.name == url[:30]

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_add_webhook_default_events(self, mock_dns, manager):
        wh = manager.add_webhook(url="https://hooks.example.com/defaults")
        assert wh.events == ["sync_complete"]


# ---------------------------------------------------------------------------
# remove_webhook / update_webhook
# ---------------------------------------------------------------------------

class TestRemoveWebhook:
    """Tests for removing webhooks by index."""

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_remove_webhook_by_index(self, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/c")
        manager.add_webhook(url="https://hooks.example.com/d")

        result = manager.remove_webhook(0)

        assert result is True
        hooks = manager.get_webhooks()
        assert len(hooks) == 1
        assert hooks[0].url == "https://hooks.example.com/d"

    def test_remove_webhook_invalid_index(self, manager):
        assert manager.remove_webhook(99) is False

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_remove_webhook_negative_index(self, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/neg")
        assert manager.remove_webhook(-1) is False


class TestUpdateWebhook:
    """Tests for updating webhook configuration."""

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_update_webhook_disable(self, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/e")

        result = manager.update_webhook(0, enabled=False)

        assert result is True
        hooks = manager.get_webhooks()
        assert hooks[0].enabled is False

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_update_webhook_enable(self, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/enable")

        manager.update_webhook(0, enabled=False)
        manager.update_webhook(0, enabled=True)

        hooks = manager.get_webhooks()
        assert hooks[0].enabled is True

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_update_webhook_events(self, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/f")

        manager.update_webhook(0, events=["priority_email"])

        hooks = manager.get_webhooks()
        assert hooks[0].events == ["priority_email"]

    def test_update_webhook_invalid_index(self, manager):
        assert manager.update_webhook(99, enabled=True) is False


# ---------------------------------------------------------------------------
# notify, history, and clear_history
# ---------------------------------------------------------------------------

class TestNotifyAndHistory:
    """Tests for the notify/history/clear_history workflow."""

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen")
    def test_notify_records_history(self, mock_urlopen, mock_dns, manager):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        manager.add_webhook(url="https://hooks.example.com/h", events=["sync_complete"])

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Sync done",
            message="All emails synced.",
        )
        manager.notify(event)
        _wait_for_threads()

        history = manager.get_history()
        assert len(history) == 1
        assert history[0]["event_type"] == "sync_complete"
        assert history[0]["webhooks_fired"] == 1

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen")
    def test_notify_skips_disabled_webhook(self, mock_urlopen, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/i", events=["sync_complete"])

        manager.update_webhook(0, enabled=False)

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Sync done",
            message="Synced.",
        )
        manager.notify(event)
        _wait_for_threads()

        history = manager.get_history()
        assert history[0]["webhooks_fired"] == 0
        mock_urlopen.assert_not_called()

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen")
    def test_notify_skips_non_matching_event(self, mock_urlopen, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/j", events=["security_alert"])

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Sync",
            message="Done.",
        )
        manager.notify(event)
        _wait_for_threads()

        history = manager.get_history()
        assert history[0]["webhooks_fired"] == 0

    def test_clear_history(self, manager):
        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="T",
            message="M",
        )
        manager.notify(event)
        assert len(manager.get_history()) == 1

        manager.clear_history()
        assert len(manager.get_history()) == 0

    def test_get_history_limit(self, manager):
        for i in range(5):
            event = NotificationEvent(
                event_type="sync_complete",
                account_name="test@gmail.com",
                title=f"Event {i}",
                message="M",
            )
            manager.notify(event)

        assert len(manager.get_history(limit=3)) == 3

    def test_get_history_returns_most_recent_first(self, manager):
        for i in range(3):
            event = NotificationEvent(
                event_type="sync_complete",
                account_name="test@gmail.com",
                title=f"Event {i}",
                message="M",
            )
            manager.notify(event)

        history = manager.get_history()
        assert history[0]["title"] == "Event 2"
        assert history[-1]["title"] == "Event 0"

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen")
    def test_notify_fires_to_multiple_matching_webhooks(
        self, mock_urlopen, mock_dns, manager
    ):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        manager.add_webhook(
            url="https://hooks.example.com/multi1", events=["sync_complete"]
        )
        manager.add_webhook(
            url="https://hooks.example.com/multi2", events=["sync_complete"]
        )

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Multi",
            message="Both should fire.",
        )
        manager.notify(event)
        _wait_for_threads()

        history = manager.get_history()
        assert history[0]["webhooks_fired"] == 2
        assert mock_urlopen.call_count == 2


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    """Tests for get_stats."""

    def test_empty_stats(self, manager):
        stats = manager.get_stats()
        assert stats == {
            "webhook_count": 0,
            "enabled_count": 0,
            "total_notifications": 0,
            "recent_failures": 0,
        }

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_stats_reflect_webhooks_and_history(self, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/k", events=["sync_complete"])
        manager.add_webhook(url="https://hooks.example.com/l", events=["sync_complete"])

        manager.update_webhook(1, enabled=False)

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="T",
            message="M",
        )
        manager.notify(event)

        stats = manager.get_stats()
        assert stats["webhook_count"] == 2
        assert stats["enabled_count"] == 1
        assert stats["total_notifications"] == 1

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen", side_effect=Exception("fail"))
    def test_stats_count_failures(self, mock_urlopen, mock_dns, manager):
        manager.add_webhook(url="https://hooks.example.com/stat-fail", events=["sync_complete"])

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Fail",
            message="M",
        )
        manager.notify(event)
        _wait_for_threads()

        stats = manager.get_stats()
        assert stats["recent_failures"] == 1


# ---------------------------------------------------------------------------
# Config persistence (save / load round-trip)
# ---------------------------------------------------------------------------

class TestConfigPersistence:
    """Tests for config save and load round-trip."""

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_config_round_trip(self, mock_dns, tmp_path):
        mgr1 = NotificationManager(config_dir=str(tmp_path))
        mgr1.add_webhook(
            url="https://hooks.example.com/persist",
            name="Persist Test",
            events=["security_alert"],
            secret="key123",
        )

        # Create a second manager from the same directory to verify it loads saved config
        mgr2 = NotificationManager(config_dir=str(tmp_path))
        hooks = mgr2.get_webhooks()
        assert len(hooks) == 1
        assert hooks[0].url == "https://hooks.example.com/persist"
        assert hooks[0].name == "Persist Test"
        assert hooks[0].events == ["security_alert"]
        assert hooks[0].secret == "key123"

    def test_history_round_trip(self, tmp_path):
        mgr1 = NotificationManager(config_dir=str(tmp_path))
        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Persistence",
            message="Check history persistence.",
        )
        mgr1.notify(event)

        mgr2 = NotificationManager(config_dir=str(tmp_path))
        history = mgr2.get_history()
        assert len(history) == 1
        assert history[0]["title"] == "Persistence"

    def test_config_file_written_to_disk(self, tmp_path):
        """Verify the JSON config file is actually created on disk."""
        mgr = NotificationManager(config_dir=str(tmp_path))
        config_path = tmp_path / NotificationManager.CONFIG_FILE

        with patch("socket.getaddrinfo", return_value=_public_addrinfo()):
            mgr.add_webhook(url="https://hooks.example.com/disk")

        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert len(data) == 1
        assert data[0]["url"] == "https://hooks.example.com/disk"

    def test_history_file_written_to_disk(self, tmp_path):
        mgr = NotificationManager(config_dir=str(tmp_path))
        history_path = tmp_path / NotificationManager.HISTORY_FILE

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Disk check",
            message="M",
        )
        mgr.notify(event)

        assert history_path.exists()
        data = json.loads(history_path.read_text())
        assert len(data) == 1

    def test_load_config_handles_missing_file(self, tmp_path):
        """Manager should initialize cleanly when no config file exists."""
        mgr = NotificationManager(config_dir=str(tmp_path))
        assert mgr.get_webhooks() == []

    def test_load_history_handles_missing_file(self, tmp_path):
        """Manager should initialize cleanly when no history file exists."""
        mgr = NotificationManager(config_dir=str(tmp_path))
        assert mgr.get_history() == []


# ---------------------------------------------------------------------------
# HMAC signature generation
# ---------------------------------------------------------------------------

class TestHMACSignature:
    """Tests for HMAC signature header when a webhook secret is configured."""

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen")
    def test_hmac_signature_present(self, mock_urlopen, mock_dns, manager):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        secret = "my-webhook-secret"
        manager.add_webhook(
            url="https://hooks.example.com/signed",
            events=["sync_complete"],
            secret=secret,
        )

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Signed",
            message="Verify HMAC.",
        )
        manager.notify(event)
        _wait_for_threads()

        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        sig_header = req.get_header("X-webhook-signature")
        assert sig_header is not None
        assert sig_header.startswith("sha256=")

        # Verify the signature matches expected HMAC
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            req.data,
            hashlib.sha256,
        ).hexdigest()
        assert sig_header == f"sha256={expected_sig}"

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen")
    def test_no_signature_without_secret(self, mock_urlopen, mock_dns, manager):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        manager.add_webhook(
            url="https://hooks.example.com/unsigned",
            events=["sync_complete"],
            secret="",
        )

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Unsigned",
            message="No HMAC.",
        )
        manager.notify(event)
        _wait_for_threads()

        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        sig_header = req.get_header("X-webhook-signature")
        assert sig_header is None


# ---------------------------------------------------------------------------
# _fire_webhook failure handling
# ---------------------------------------------------------------------------

class TestFireWebhookFailure:
    """Tests for failure_count increments when webhook delivery fails."""

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen", side_effect=Exception("connection refused"))
    def test_failure_increments_count(self, mock_urlopen, mock_dns, manager):
        manager.add_webhook(
            url="https://hooks.example.com/fail",
            events=["sync_complete"],
        )

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="Fail",
            message="Should increment failure_count.",
        )
        manager.notify(event)
        _wait_for_threads()

        hooks = manager.get_webhooks()
        assert hooks[0].failure_count == 1

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen", side_effect=Exception("fail"))
    def test_multiple_failures_accumulate(self, mock_urlopen, mock_dns, manager):
        manager.add_webhook(
            url="https://hooks.example.com/multi-fail",
            events=["sync_complete"],
        )

        for _ in range(3):
            event = NotificationEvent(
                event_type="sync_complete",
                account_name="test@gmail.com",
                title="Fail",
                message="Again.",
            )
            manager.notify(event)
            _wait_for_threads()

        hooks = manager.get_webhooks()
        assert hooks[0].failure_count == 3

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    @patch("urllib.request.urlopen")
    def test_success_resets_failure_count(self, mock_urlopen, mock_dns, manager):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        manager.add_webhook(
            url="https://hooks.example.com/reset",
            events=["sync_complete"],
        )
        # Manually set failure_count to simulate prior failures
        manager._webhooks[0].failure_count = 5

        event = NotificationEvent(
            event_type="sync_complete",
            account_name="test@gmail.com",
            title="OK",
            message="Success.",
        )
        manager.notify(event)
        _wait_for_threads()

        hooks = manager.get_webhooks()
        assert hooks[0].failure_count == 0


# ---------------------------------------------------------------------------
# NotificationEvent dataclass
# ---------------------------------------------------------------------------

class TestNotificationEvent:
    """Tests for the NotificationEvent dataclass."""

    def test_auto_timestamp(self):
        ev = NotificationEvent(
            event_type="sync_complete",
            account_name="a",
            title="T",
            message="M",
        )
        assert ev.timestamp != ""

    def test_custom_timestamp_preserved(self):
        ev = NotificationEvent(
            event_type="sync_complete",
            account_name="a",
            title="T",
            message="M",
            timestamp="2026-01-01T00:00:00",
        )
        assert ev.timestamp == "2026-01-01T00:00:00"

    def test_default_data_is_empty_dict(self):
        ev = NotificationEvent(
            event_type="sync_complete",
            account_name="a",
            title="T",
            message="M",
        )
        assert ev.data == {}

    def test_custom_data_preserved(self):
        ev = NotificationEvent(
            event_type="sync_complete",
            account_name="a",
            title="T",
            message="M",
            data={"count": 42},
        )
        assert ev.data == {"count": 42}


# ---------------------------------------------------------------------------
# WebhookConfig dataclass
# ---------------------------------------------------------------------------

class TestWebhookConfig:
    """Tests for the WebhookConfig dataclass defaults."""

    def test_defaults(self):
        wh = WebhookConfig(url="https://example.com/hook")
        assert wh.enabled is True
        assert wh.events == ["sync_complete"]
        assert wh.secret == ""
        assert wh.last_triggered == ""
        assert wh.failure_count == 0
        assert wh.name == ""


# ---------------------------------------------------------------------------
# Deadlock documentation test
# ---------------------------------------------------------------------------

class TestDeadlockBug:
    """Documents the known deadlock in remove_webhook and update_webhook.

    Both methods call _save_config() while holding self._lock, but
    _save_config() also acquires self._lock (a non-reentrant threading.Lock).
    This causes a permanent deadlock. These tests verify the bug exists so it
    can be tracked and fixed.
    """

    @patch("socket.getaddrinfo", return_value=_public_addrinfo())
    def test_remove_webhook_no_longer_deadlocks(self, mock_dns, manager):
        """Verify the deadlock fix: remove_webhook now calls _save_config
        outside the lock, so it completes without hanging."""
        manager.add_webhook(url="https://hooks.example.com/deadlock")

        result_holder = []

        def attempt_remove():
            result_holder.append(manager.remove_webhook(0))

        t = threading.Thread(target=attempt_remove, daemon=True)
        t.start()
        t.join(timeout=2.0)

        assert not t.is_alive(), "remove_webhook deadlocked (should be fixed)"
        assert result_holder == [True]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _wait_for_threads(timeout: float = 2.0):
    """Wait for all non-main daemon threads to finish."""
    for t in threading.enumerate():
        if t is not threading.main_thread() and t.daemon:
            t.join(timeout=timeout)
