"""Webhook and notification system for Gmail Organizer events."""

import json
import threading
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class NotificationEvent:
    """A notification event that can trigger webhooks."""

    event_type: str  # sync_complete, security_alert, priority_email, follow_up_overdue
    account_name: str
    title: str
    message: str
    timestamp: str = ""
    data: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""

    url: str
    name: str = ""
    enabled: bool = True
    events: List[str] = field(default_factory=lambda: ["sync_complete"])
    secret: str = ""
    last_triggered: str = ""
    failure_count: int = 0


# Available event types
EVENT_TYPES = {
    "sync_complete": "Sync completed for an account",
    "security_alert": "Security threat detected",
    "priority_email": "High-priority email received",
    "follow_up_overdue": "Follow-up item is overdue",
    "scheduled_sync": "Scheduled sync triggered",
    "export_complete": "Email export completed",
}


class NotificationManager:
    """Manages webhooks and in-app notifications."""

    CONFIG_FILE = "notification_config.json"
    HISTORY_FILE = "notification_history.json"
    MAX_HISTORY = 100

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the notification manager.

        Args:
            config_dir: Directory for config/history files.
                       Defaults to .sync-state/ in project root.
        """
        if config_dir:
            self._config_dir = Path(config_dir)
        else:
            self._config_dir = Path(__file__).parent.parent / ".sync-state"
        self._config_dir.mkdir(exist_ok=True)

        self._webhooks: List[WebhookConfig] = []
        self._history: List[Dict] = []
        self._lock = threading.Lock()

        self._load_config()
        self._load_history()

    def add_webhook(self, url: str, name: str = "", events: List[str] = None,
                    secret: str = "") -> WebhookConfig:
        """Add a new webhook endpoint.

        Args:
            url: The webhook URL to POST to.
            name: Human-readable name for this webhook.
            events: List of event types to subscribe to.
            secret: Optional secret for webhook signature verification.

        Returns:
            The created WebhookConfig.
        """
        webhook = WebhookConfig(
            url=url,
            name=name or url[:30],
            events=events or ["sync_complete"],
            secret=secret,
        )

        with self._lock:
            self._webhooks.append(webhook)

        self._save_config()
        return webhook

    def remove_webhook(self, index: int) -> bool:
        """Remove a webhook by index.

        Args:
            index: Index of the webhook to remove.

        Returns:
            True if removed successfully.
        """
        with self._lock:
            if 0 <= index < len(self._webhooks):
                self._webhooks.pop(index)
                self._save_config()
                return True
        return False

    def update_webhook(self, index: int, enabled: Optional[bool] = None,
                       events: Optional[List[str]] = None) -> bool:
        """Update a webhook configuration.

        Args:
            index: Index of the webhook to update.
            enabled: Whether the webhook is enabled.
            events: Updated event list.

        Returns:
            True if updated successfully.
        """
        with self._lock:
            if 0 <= index < len(self._webhooks):
                if enabled is not None:
                    self._webhooks[index].enabled = enabled
                if events is not None:
                    self._webhooks[index].events = events
                self._save_config()
                return True
        return False

    def get_webhooks(self) -> List[WebhookConfig]:
        """Get all configured webhooks."""
        with self._lock:
            return list(self._webhooks)

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get notification history.

        Args:
            limit: Maximum number of history entries to return.

        Returns:
            List of notification history dicts, most recent first.
        """
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def clear_history(self):
        """Clear all notification history."""
        with self._lock:
            self._history = []
        self._save_history()

    def notify(self, event: NotificationEvent):
        """Fire a notification event.

        Sends webhooks to all matching endpoints in background threads.
        Also records the event in history.

        Args:
            event: The NotificationEvent to fire.
        """
        # Record in history
        history_entry = {
            "event_type": event.event_type,
            "account_name": event.account_name,
            "title": event.title,
            "message": event.message,
            "timestamp": event.timestamp,
            "webhooks_fired": 0,
        }

        # Find matching webhooks
        with self._lock:
            matching = [
                (i, wh) for i, wh in enumerate(self._webhooks)
                if wh.enabled and event.event_type in wh.events
            ]

        # Fire webhooks in background threads
        for idx, webhook in matching:
            history_entry["webhooks_fired"] += 1
            thread = threading.Thread(
                target=self._fire_webhook,
                args=(webhook, event, idx),
                daemon=True
            )
            thread.start()

        # Save to history
        with self._lock:
            self._history.append(history_entry)
            if len(self._history) > self.MAX_HISTORY:
                self._history = self._history[-self.MAX_HISTORY:]

        self._save_history()

    def _fire_webhook(self, webhook: WebhookConfig, event: NotificationEvent,
                      webhook_index: int):
        """Send a POST request to a webhook URL.

        Args:
            webhook: The webhook configuration.
            event: The event to send.
            webhook_index: Index for updating failure count.
        """
        payload = json.dumps({
            "event_type": event.event_type,
            "account_name": event.account_name,
            "title": event.title,
            "message": event.message,
            "timestamp": event.timestamp,
            "data": event.data,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "GmailOrganizer/1.0",
        }

        if webhook.secret:
            import hashlib
            import hmac
            signature = hmac.new(
                webhook.secret.encode("utf-8"),
                payload,
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        try:
            req = urllib.request.Request(
                webhook.url,
                data=payload,
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                pass  # Success

            with self._lock:
                if webhook_index < len(self._webhooks):
                    self._webhooks[webhook_index].last_triggered = datetime.now().isoformat()
                    self._webhooks[webhook_index].failure_count = 0
            self._save_config()

        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            with self._lock:
                if webhook_index < len(self._webhooks):
                    self._webhooks[webhook_index].failure_count += 1
            self._save_config()

    def get_stats(self) -> Dict:
        """Get notification system statistics.

        Returns:
            Dict with webhook_count, enabled_count, total_notifications,
            and recent_failures.
        """
        with self._lock:
            enabled = sum(1 for w in self._webhooks if w.enabled)
            failures = sum(w.failure_count for w in self._webhooks)

            return {
                "webhook_count": len(self._webhooks),
                "enabled_count": enabled,
                "total_notifications": len(self._history),
                "recent_failures": failures,
            }

    def _save_config(self):
        """Save webhook configuration to disk."""
        config_path = self._config_dir / self.CONFIG_FILE
        with self._lock:
            data = [asdict(wh) for wh in self._webhooks]

        try:
            with open(config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_config(self):
        """Load webhook configuration from disk."""
        config_path = self._config_dir / self.CONFIG_FILE
        if not config_path.exists():
            return

        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            with self._lock:
                self._webhooks = [WebhookConfig(**item) for item in data]
        except Exception:
            pass

    def _save_history(self):
        """Save notification history to disk."""
        history_path = self._config_dir / self.HISTORY_FILE
        with self._lock:
            data = list(self._history)

        try:
            with open(history_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load_history(self):
        """Load notification history from disk."""
        history_path = self._config_dir / self.HISTORY_FILE
        if not history_path.exists():
            return

        try:
            with open(history_path, "r") as f:
                data = json.load(f)
            with self._lock:
                self._history = data[-self.MAX_HISTORY:]
        except Exception:
            pass
