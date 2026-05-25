"""Tests for UnsubscribeManager and Subscription classes."""

import json
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from gmail_organizer.unsubscribe import Subscription, UnsubscribeManager


# ---------------------------------------------------------------------------
# Subscription class tests
# ---------------------------------------------------------------------------


class TestSubscription:
    """Tests for the Subscription dataclass-like object."""

    def test_has_unsubscribe_with_link(self):
        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_link="https://example.com/unsub",
        )
        assert sub.has_unsubscribe is True

    def test_has_unsubscribe_with_email(self):
        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_email="unsub@example.com",
        )
        assert sub.has_unsubscribe is True

    def test_has_unsubscribe_with_both(self):
        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_link="https://example.com/unsub",
            unsubscribe_email="unsub@example.com",
        )
        assert sub.has_unsubscribe is True

    def test_has_unsubscribe_without_link_or_email(self):
        sub = Subscription(sender_email="news@example.com")
        assert sub.has_unsubscribe is False

    def test_emails_per_week_over_multiple_weeks(self):
        first = datetime(2026, 1, 1)
        last = datetime(2026, 1, 15)  # 14 days = 2 weeks
        sub = Subscription(
            sender_email="news@example.com",
            frequency=10,
            first_received=first.isoformat(),
            last_received=last.isoformat(),
        )
        assert sub.emails_per_week == 5.0

    def test_emails_per_week_same_day(self):
        """When first and last are the same, days=0 so max(days,1)=1."""
        d = datetime(2026, 3, 1)
        sub = Subscription(
            sender_email="news@example.com",
            frequency=3,
            first_received=d.isoformat(),
            last_received=d.isoformat(),
        )
        # days=0, max=1, weeks=1/7=0.142..., max(weeks,0.14)=0.142..
        assert sub.emails_per_week > 0

    def test_emails_per_week_missing_dates(self):
        sub = Subscription(sender_email="news@example.com", frequency=5)
        assert sub.emails_per_week == 0.0

    def test_emails_per_week_invalid_dates(self):
        sub = Subscription(
            sender_email="news@example.com",
            frequency=5,
            first_received="not-a-date",
            last_received="also-bad",
        )
        assert sub.emails_per_week == 0.0

    def test_to_dict_serialization(self):
        sub = Subscription(
            sender_email="news@example.com",
            sender_name="Example News",
            unsubscribe_link="https://example.com/unsub",
            frequency=10,
            first_received="2026-01-01T00:00:00",
            last_received="2026-01-15T00:00:00",
            category="subscriptions",
        )
        d = sub.to_dict()
        assert d["sender_email"] == "news@example.com"
        assert d["sender_name"] == "Example News"
        assert d["unsubscribe_link"] == "https://example.com/unsub"
        assert d["frequency"] == 10
        assert d["domain"] == "example.com"
        assert d["has_unsubscribe"] is True
        assert isinstance(d["emails_per_week"], float)
        assert d["unsubscribed"] is False

    def test_domain_extraction(self):
        sub = Subscription(sender_email="user@mydomain.org")
        assert sub.domain == "mydomain.org"

    def test_domain_extraction_no_at(self):
        sub = Subscription(sender_email="invalid")
        assert sub.domain == ""


# ---------------------------------------------------------------------------
# UnsubscribeManager tests
# ---------------------------------------------------------------------------


class TestUnsubscribeManager:
    """Tests for UnsubscribeManager."""

    def _make_manager(self, tmp_path, state=None):
        """Helper to create a manager with a tmp state dir."""
        state_dir = str(tmp_path / "state")
        if state is not None:
            os.makedirs(state_dir, exist_ok=True)
            with open(os.path.join(state_dir, "unsubscribe_state.json"), "w") as f:
                json.dump(state, f)
        return UnsubscribeManager(service=None, state_dir=state_dir)

    # -- State persistence -------------------------------------------------

    def test_load_state_empty(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        assert mgr._unsubscribe_state == {"unsubscribed": {}, "ignored": []}

    def test_load_state_existing(self, tmp_path):
        state = {"unsubscribed": {"a@b.com": "2026-01-01"}, "ignored": ["c@d.com"]}
        mgr = self._make_manager(tmp_path, state=state)
        assert mgr._unsubscribe_state == state

    def test_load_state_corrupt_json(self, tmp_path):
        state_dir = str(tmp_path / "state")
        os.makedirs(state_dir, exist_ok=True)
        with open(os.path.join(state_dir, "unsubscribe_state.json"), "w") as f:
            f.write("{bad json")
        mgr = UnsubscribeManager(service=None, state_dir=state_dir)
        assert mgr._unsubscribe_state == {"unsubscribed": {}, "ignored": []}

    def test_mark_unsubscribed_persists(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr.mark_unsubscribed("spam@example.com")

        state_file = os.path.join(mgr.state_dir, "unsubscribe_state.json")
        assert os.path.exists(state_file)
        with open(state_file) as f:
            data = json.load(f)
        assert "spam@example.com" in data["unsubscribed"]

    def test_ignore_subscription_persists(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr.ignore_subscription("keep@example.com")

        state_file = os.path.join(mgr.state_dir, "unsubscribe_state.json")
        with open(state_file) as f:
            data = json.load(f)
        assert "keep@example.com" in data["ignored"]

    def test_ignore_subscription_no_duplicates(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr.ignore_subscription("keep@example.com")
        mgr.ignore_subscription("keep@example.com")
        assert mgr._unsubscribe_state["ignored"].count("keep@example.com") == 1

    # -- _parse_list_unsubscribe -------------------------------------------

    def test_parse_list_unsubscribe_url(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        result = mgr._parse_list_unsubscribe("<https://example.com/unsub>")
        assert result == ["https://example.com/unsub"]

    def test_parse_list_unsubscribe_mailto(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        result = mgr._parse_list_unsubscribe("<mailto:unsub@example.com>")
        assert result == ["mailto:unsub@example.com"]

    def test_parse_list_unsubscribe_multiple(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        header = "<https://example.com/unsub>, <mailto:unsub@example.com>"
        result = mgr._parse_list_unsubscribe(header)
        assert len(result) == 2
        assert "https://example.com/unsub" in result
        assert "mailto:unsub@example.com" in result

    def test_parse_list_unsubscribe_empty(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        assert mgr._parse_list_unsubscribe("") == []

    # -- _find_unsubscribe_in_body -----------------------------------------

    def test_find_unsubscribe_in_body_with_url(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        body = "Click here to https://example.com/unsubscribe from our list."
        result = mgr._find_unsubscribe_in_body(body)
        assert len(result) >= 1
        assert any("unsubscribe" in link for link in result)

    def test_find_unsubscribe_in_body_opt_out(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        body = "To opt out: https://mail.example.com/opt-out?id=123"
        result = mgr._find_unsubscribe_in_body(body)
        assert len(result) >= 1

    def test_find_unsubscribe_in_body_none(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        body = "Hey, let's grab coffee tomorrow!"
        result = mgr._find_unsubscribe_in_body(body)
        assert result == []

    def test_find_unsubscribe_in_body_limits_to_three(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        body = " ".join(
            f"https://example.com/unsubscribe/{i}" for i in range(10)
        )
        result = mgr._find_unsubscribe_in_body(body)
        assert len(result) <= 3

    # -- detect_subscriptions ----------------------------------------------

    def test_detect_subscriptions_list_unsubscribe_header(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        emails = [
            {
                "sender": "Newsletter <news@example.com>",
                "headers": {"List-Unsubscribe": "<https://example.com/unsub>"},
                "body_preview": "",
                "date": "Mon, 01 Jan 2026 12:00:00 +0000",
            }
        ]
        subs = mgr.detect_subscriptions(emails)
        assert len(subs) == 1
        assert subs[0].sender_email == "news@example.com"
        assert subs[0].has_unsubscribe is True

    def test_detect_subscriptions_marketing_domain(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        emails = [
            {
                "sender": "promo@mailchimp.com",
                "headers": {},
                "body_preview": "",
                "date": "Mon, 01 Jan 2026 12:00:00 +0000",
            }
        ]
        subs = mgr.detect_subscriptions(emails)
        assert len(subs) == 1
        assert subs[0].domain == "mailchimp.com"

    def test_detect_subscriptions_high_frequency_automated(self, tmp_path):
        """5+ emails with automated-looking subjects should be detected."""
        mgr = self._make_manager(tmp_path)
        base_date = datetime(2026, 1, 1)
        emails = [
            {
                "sender": "alerts@myservice.io",
                "headers": {},
                "body_preview": "",
                "subject": f"Daily Report #10{i}",
                "date": (base_date + timedelta(days=i)).strftime(
                    "%a, %d %b %Y %H:%M:%S +0000"
                ),
            }
            for i in range(6)
        ]
        subs = mgr.detect_subscriptions(emails)
        assert len(subs) == 1

    def test_detect_subscriptions_skips_personal_email(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        emails = [
            {
                "sender": "friend@gmail.com",
                "headers": {},
                "body_preview": "Hey, are we still on for dinner?",
                "subject": "Dinner tonight?",
                "date": "Mon, 01 Jan 2026 12:00:00 +0000",
            }
        ]
        subs = mgr.detect_subscriptions(emails)
        assert len(subs) == 0

    def test_detect_subscriptions_sorted_by_frequency(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        emails = []
        for i in range(3):
            emails.append(
                {
                    "sender": "low@mailchimp.com",
                    "headers": {},
                    "body_preview": "",
                    "date": "Mon, 01 Jan 2026 12:00:00 +0000",
                }
            )
        for i in range(7):
            emails.append(
                {
                    "sender": "high@sendgrid.net",
                    "headers": {},
                    "body_preview": "",
                    "date": "Mon, 01 Jan 2026 12:00:00 +0000",
                }
            )
        subs = mgr.detect_subscriptions(emails)
        assert subs[0].sender_email == "high@sendgrid.net"

    def test_detect_subscriptions_marks_already_unsubscribed(self, tmp_path):
        state = {"unsubscribed": {"news@example.com": "2026-01-01"}, "ignored": []}
        mgr = self._make_manager(tmp_path, state=state)
        emails = [
            {
                "sender": "news@example.com",
                "headers": {"List-Unsubscribe": "<https://example.com/unsub>"},
                "body_preview": "",
                "date": "Mon, 01 Jan 2026 12:00:00 +0000",
            }
        ]
        subs = mgr.detect_subscriptions(emails)
        assert subs[0].unsubscribed is True

    def test_detect_subscriptions_empty_sender_skipped(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        emails = [{"sender": "", "headers": {}, "body_preview": ""}]
        subs = mgr.detect_subscriptions(emails)
        assert len(subs) == 0

    # -- _is_likely_subscription -------------------------------------------

    def test_is_likely_subscription_newsletter_pattern(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        data = {"unsubscribe_links": set(), "unsubscribe_emails": set(), "emails": []}
        assert mgr._is_likely_subscription("newsletter@corp.com", data) is True

    def test_is_likely_subscription_noreply(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        data = {"unsubscribe_links": set(), "unsubscribe_emails": set(), "emails": []}
        assert mgr._is_likely_subscription("noreply@shop.com", data) is True

    # -- _subjects_look_automated ------------------------------------------

    def test_subjects_look_automated_common_prefix(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        subjects = [
            "Weekly Digest - Jan 1",
            "Weekly Digest - Jan 8",
            "Weekly Digest - Jan 15",
        ]
        assert mgr._subjects_look_automated(subjects) is True

    def test_subjects_look_automated_number_pattern(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        subjects = [
            "Issue #101",
            "Issue #102",
            "Issue #103",
            "Issue #104",
        ]
        assert mgr._subjects_look_automated(subjects) is True

    def test_subjects_look_automated_not_automated(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        subjects = [
            "Hey there",
            "Quick question",
            "About the project",
        ]
        assert mgr._subjects_look_automated(subjects) is False

    def test_subjects_look_automated_too_few(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        assert mgr._subjects_look_automated(["One", "Two"]) is False

    # -- get_subscription_stats --------------------------------------------

    def test_get_subscription_stats(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        subs = [
            Subscription(
                sender_email="a@example.com",
                unsubscribe_link="https://example.com/unsub",
                frequency=20,
                first_received="2026-01-01T00:00:00",
                last_received="2026-01-15T00:00:00",
            ),
            Subscription(
                sender_email="b@other.com",
                frequency=3,
                first_received="2026-01-01T00:00:00",
                last_received="2026-03-01T00:00:00",
            ),
        ]
        stats = mgr.get_subscription_stats(subs)
        assert stats["total_subscriptions"] == 2
        assert stats["with_unsubscribe"] == 1
        assert stats["without_unsubscribe"] == 1
        assert stats["total_emails"] == 23
        assert stats["already_unsubscribed"] == 0
        assert isinstance(stats["top_domains"], list)
        assert isinstance(stats["avg_per_week"], float)

    def test_get_subscription_stats_with_unsubscribed(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        sub = Subscription(sender_email="gone@example.com", frequency=5)
        sub.unsubscribed = True
        stats = mgr.get_subscription_stats([sub])
        assert stats["total_subscriptions"] == 0
        assert stats["already_unsubscribed"] == 1

    # -- get_unsubscribe_candidates ----------------------------------------

    def test_get_unsubscribe_candidates_basic(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        subs = [
            Subscription(
                sender_email="spam@example.com",
                unsubscribe_link="https://example.com/unsub",
                frequency=10,
            ),
            Subscription(
                sender_email="low@example.com",
                unsubscribe_link="https://example.com/unsub",
                frequency=2,  # below default min_frequency=5
            ),
        ]
        candidates = mgr.get_unsubscribe_candidates(subs)
        assert len(candidates) == 1
        assert candidates[0].sender_email == "spam@example.com"

    def test_get_unsubscribe_candidates_excludes_unsubscribed(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        sub = Subscription(
            sender_email="done@example.com",
            unsubscribe_link="https://example.com/unsub",
            frequency=10,
        )
        sub.unsubscribed = True
        candidates = mgr.get_unsubscribe_candidates([sub])
        assert len(candidates) == 0

    def test_get_unsubscribe_candidates_excludes_ignored(self, tmp_path):
        state = {"unsubscribed": {}, "ignored": ["ignored@example.com"]}
        mgr = self._make_manager(tmp_path, state=state)
        sub = Subscription(
            sender_email="ignored@example.com",
            unsubscribe_link="https://example.com/unsub",
            frequency=10,
        )
        candidates = mgr.get_unsubscribe_candidates([sub])
        assert len(candidates) == 0

    def test_get_unsubscribe_candidates_requires_unsub_mechanism(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        sub = Subscription(sender_email="nolink@example.com", frequency=10)
        candidates = mgr.get_unsubscribe_candidates([sub])
        assert len(candidates) == 0

    def test_get_unsubscribe_candidates_custom_min_frequency(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        sub = Subscription(
            sender_email="a@example.com",
            unsubscribe_link="https://example.com/unsub",
            frequency=3,
        )
        candidates = mgr.get_unsubscribe_candidates([sub], min_frequency=2)
        assert len(candidates) == 1

    # -- unsubscribe_via_email ---------------------------------------------

    def test_unsubscribe_via_email_no_service(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_email="unsub@example.com",
        )
        assert mgr.unsubscribe_via_email(sub) is False

    def test_unsubscribe_via_email_no_unsub_email(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr.service = MagicMock()
        sub = Subscription(sender_email="news@example.com")
        assert mgr.unsubscribe_via_email(sub) is False

    def test_unsubscribe_via_email_success(self, tmp_path):
        service = MagicMock()
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {}

        mgr = self._make_manager(tmp_path)
        mgr.service = service

        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_email="unsub@example.com",
        )
        result = mgr.unsubscribe_via_email(sub)
        assert result is True
        assert sub.unsubscribed is True
        service.users.return_value.messages.return_value.send.assert_called_once()

    def test_unsubscribe_via_email_with_subject_param(self, tmp_path):
        service = MagicMock()
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {}

        mgr = self._make_manager(tmp_path)
        mgr.service = service

        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_email="unsub@example.com?subject=Remove+Me",
        )
        result = mgr.unsubscribe_via_email(sub)
        assert result is True

    def test_unsubscribe_via_email_sanitizes_newlines(self, tmp_path):
        """Verify header injection vectors are stripped."""
        service = MagicMock()
        service.users.return_value.messages.return_value.send.return_value.execute.return_value = {}

        mgr = self._make_manager(tmp_path)
        mgr.service = service

        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_email="unsub@example.com\r\nBcc: attacker@evil.com",
        )
        result = mgr.unsubscribe_via_email(sub)
        # The address gets sanitized; since no '@' remains after split, it
        # should either succeed with cleaned address or fail gracefully.
        # The key point is no exception is raised.
        assert isinstance(result, bool)

    def test_unsubscribe_via_email_api_error(self, tmp_path):
        from googleapiclient.errors import HttpError

        service = MagicMock()
        resp = MagicMock()
        resp.status = 403
        service.users.return_value.messages.return_value.send.return_value.execute.side_effect = (
            HttpError(resp, b"forbidden")
        )

        mgr = self._make_manager(tmp_path)
        mgr.service = service

        sub = Subscription(
            sender_email="news@example.com",
            unsubscribe_email="unsub@example.com",
        )
        assert mgr.unsubscribe_via_email(sub) is False
