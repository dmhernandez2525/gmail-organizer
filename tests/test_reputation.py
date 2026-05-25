"""Tests for the sender reputation scoring module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from gmail_organizer.reputation import SenderProfile, SenderReputation


class TestSenderProfile:
    """Tests for the SenderProfile dataclass."""

    def test_domain_extracted_from_email(self):
        profile = SenderProfile(sender_email="alice@example.com")
        assert profile.domain == "example.com"

    def test_domain_lowercased(self):
        profile = SenderProfile(sender_email="alice@Example.COM")
        assert profile.domain == "example.com"

    def test_domain_not_overridden_if_provided(self):
        profile = SenderProfile(sender_email="alice@example.com", domain="custom.org")
        assert profile.domain == "custom.org"

    def test_domain_empty_for_invalid_email(self):
        profile = SenderProfile(sender_email="no-at-sign")
        assert profile.domain == ""

    def test_defaults(self):
        profile = SenderProfile(sender_email="x@y.com")
        assert profile.reputation_score == 50.0
        assert profile.reputation_level == "unknown"
        assert profile.total_emails == 0
        assert profile.is_automated is False
        assert profile.first_seen is None


class TestExtractEmail:
    """Tests for the _extract_email helper."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_angle_bracket_format(self):
        assert self.rep._extract_email("Alice <alice@example.com>") == "alice@example.com"

    def test_bare_email(self):
        assert self.rep._extract_email("bob@example.com") == "bob@example.com"

    def test_empty_string(self):
        assert self.rep._extract_email("") == ""

    def test_uppercase_normalized(self):
        assert self.rep._extract_email("BOB@EXAMPLE.COM") == "bob@example.com"


class TestExtractName:
    """Tests for the _extract_name helper."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_name_with_angle_brackets(self):
        assert self.rep._extract_name("Alice Smith <alice@example.com>") == "Alice Smith"

    def test_quoted_name(self):
        assert self.rep._extract_name('"Alice Smith" <alice@example.com>') == "Alice Smith"

    def test_no_name(self):
        assert self.rep._extract_name("alice@example.com") == ""

    def test_empty(self):
        assert self.rep._extract_name("") == ""


class TestExtractAllEmails:
    """Tests for _extract_all_emails."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_multiple_emails(self):
        result = self.rep._extract_all_emails("a@b.com, c@d.org")
        assert result == ["a@b.com", "c@d.org"]

    def test_empty(self):
        assert self.rep._extract_all_emails("") == []


class TestParseDate:
    """Tests for the _parse_date helper."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_iso_format(self):
        dt = self.rep._parse_date("2024-06-15 10:30:00")
        assert dt == datetime(2024, 6, 15, 10, 30, 0)

    def test_date_only(self):
        dt = self.rep._parse_date("2024-06-15")
        assert dt == datetime(2024, 6, 15)

    def test_rfc2822_format(self):
        dt = self.rep._parse_date("Mon, 15 Jun 2024 10:30:00")
        assert dt is not None
        assert dt.day == 15

    def test_iso_with_timezone(self):
        dt = self.rep._parse_date("2024-06-15T10:30:00Z")
        assert dt is not None

    def test_strips_parenthesized_tz(self):
        dt = self.rep._parse_date("2024-06-15 10:30:00 (UTC)")
        assert dt is not None

    def test_empty_returns_none(self):
        assert self.rep._parse_date("") is None

    def test_garbage_returns_none(self):
        assert self.rep._parse_date("not-a-date") is None

    def test_datetime_passthrough(self):
        dt = datetime(2024, 1, 1)
        assert self.rep._parse_date(dt) is dt


class TestCheckAuthentication:
    """Tests for _check_authentication."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_no_headers_returns_none(self):
        assert self.rep._check_authentication({}) is None
        assert self.rep._check_authentication({"headers": {}}) is None

    def test_spf_pass_in_auth_results(self):
        email = {"headers": {"Authentication-Results": "spf=pass dkim=none"}}
        assert self.rep._check_authentication(email) is True

    def test_dkim_pass_in_auth_results(self):
        email = {"headers": {"Authentication-Results": "spf=none dkim=pass"}}
        assert self.rep._check_authentication(email) is True

    def test_spf_fail_in_auth_results(self):
        email = {"headers": {"Authentication-Results": "spf=fail dkim=none"}}
        assert self.rep._check_authentication(email) is False

    def test_dkim_fail_in_auth_results(self):
        email = {"headers": {"Authentication-Results": "spf=none dkim=fail"}}
        assert self.rep._check_authentication(email) is False

    def test_softfail(self):
        email = {"headers": {"Authentication-Results": "spf=softfail"}}
        assert self.rep._check_authentication(email) is False

    def test_lowercase_header_key(self):
        email = {"headers": {"authentication-results": "spf=pass"}}
        assert self.rep._check_authentication(email) is True

    def test_received_spf_pass(self):
        email = {"headers": {"Received-SPF": "Pass (domain verified)"}}
        assert self.rep._check_authentication(email) is True

    def test_received_spf_fail(self):
        email = {"headers": {"Received-SPF": "Fail"}}
        assert self.rep._check_authentication(email) is False

    def test_dkim_signature_present(self):
        email = {"headers": {"DKIM-Signature": "v=1; a=rsa-sha256"}}
        assert self.rep._check_authentication(email) is True

    def test_no_pass_no_fail_returns_none(self):
        email = {"headers": {"Authentication-Results": "spf=none dkim=none"}}
        assert self.rep._check_authentication(email) is None


class TestIsAutomatedSender:
    """Tests for _is_automated_sender."""

    def setup_method(self):
        self.rep = SenderReputation()

    @pytest.mark.parametrize("email_addr", [
        "noreply@example.com",
        "no-reply@example.com",
        "notifications@example.com",
        "alerts@example.com",
        "updates@example.com",
        "mailer-daemon@example.com",
        "postmaster@example.com",
        "bounce@example.com",
        "newsletter@example.com",
        "digest@example.com",
        "info@example.com",
        "support@example.com",
        "news@example.com",
        "system@example.com",
        "auto@example.com",
        "do-not-reply@example.com",
    ])
    def test_automated_patterns(self, email_addr):
        data = {"total_count": 1, "replied_count": 0, "dates": []}
        assert self.rep._is_automated_sender(email_addr, data) is True

    def test_normal_sender_not_automated(self):
        data = {"total_count": 1, "replied_count": 0, "dates": []}
        assert self.rep._is_automated_sender("alice@example.com", data) is False

    def test_behavioral_heuristic_high_volume_no_replies(self):
        now = datetime.now()
        # 20 emails over 2 weeks, no replies => avg ~10/week
        dates = [now - timedelta(days=i) for i in range(20)]
        data = {"total_count": 20, "replied_count": 0, "dates": dates}
        assert self.rep._is_automated_sender("promo@shop.com", data) is True

    def test_behavioral_heuristic_with_replies(self):
        now = datetime.now()
        dates = [now - timedelta(days=i) for i in range(20)]
        data = {"total_count": 20, "replied_count": 5, "dates": dates}
        assert self.rep._is_automated_sender("colleague@work.com", data) is False


class TestCalcAvgPerWeek:
    """Tests for _calc_avg_per_week."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_empty_list(self):
        assert self.rep._calc_avg_per_week([]) == 0.0

    def test_single_date(self):
        assert self.rep._calc_avg_per_week([datetime.now()]) == 1.0

    def test_two_weeks_span(self):
        now = datetime.now()
        dates = [now - timedelta(days=14), now]
        result = self.rep._calc_avg_per_week(dates)
        assert result == 1.0  # 2 emails / 2 weeks

    def test_same_day(self):
        now = datetime.now()
        result = self.rep._calc_avg_per_week([now, now])
        assert result == 2.0  # span is 0, returns len(dates)


class TestScoreFunctions:
    """Tests for individual scoring functions."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_score_frequency_zero_total(self):
        assert self.rep._score_frequency(0.0, 0) == 0.0

    def test_score_frequency_zero_avg(self):
        assert self.rep._score_frequency(0.0, 5) == 20.0

    def test_score_frequency_sweet_spot(self):
        score = self.rep._score_frequency(2.0, 5)
        assert score >= 80.0

    def test_score_frequency_moderate_high(self):
        score = self.rep._score_frequency(10.0, 50)
        assert score == 60.0

    def test_score_frequency_very_high(self):
        score = self.rep._score_frequency(20.0, 100)
        assert score >= 10.0  # floor at 10

    def test_score_frequency_very_low(self):
        score = self.rep._score_frequency(0.3, 2)
        assert 40.0 <= score <= 70.0

    def test_score_reply_rate_zero(self):
        assert self.rep._score_reply_rate(0.0) == 20.0

    def test_score_reply_rate_half(self):
        assert self.rep._score_reply_rate(0.5) == 100.0

    def test_score_reply_rate_capped(self):
        assert self.rep._score_reply_rate(1.0) == 100.0

    def test_score_authentication_no_data(self):
        data = {"auth_total_count": 0, "auth_pass_count": 0}
        assert self.rep._score_authentication(data) == 50.0

    def test_score_authentication_all_pass(self):
        data = {"auth_total_count": 10, "auth_pass_count": 10}
        assert self.rep._score_authentication(data) == 100.0

    def test_score_authentication_half_pass(self):
        data = {"auth_total_count": 10, "auth_pass_count": 5}
        assert self.rep._score_authentication(data) == 50.0

    def test_score_relationship_age_none(self):
        assert self.rep._score_relationship_age(None) == 30.0

    def test_score_relationship_age_today(self):
        score = self.rep._score_relationship_age(datetime.now())
        assert score <= 25.0  # very new

    def test_score_relationship_age_old(self):
        old = datetime.now() - timedelta(days=400)
        score = self.rep._score_relationship_age(old)
        assert score == 100.0

    def test_score_read_rate_zero(self):
        assert self.rep._score_read_rate(0.0) == 10.0

    def test_score_read_rate_full(self):
        assert self.rep._score_read_rate(1.0) == 100.0


class TestDetermineLevel:
    """Tests for _determine_level."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_trusted(self):
        assert self.rep._determine_level(80.0) == "trusted"

    def test_neutral(self):
        assert self.rep._determine_level(50.0) == "neutral"

    def test_suspicious(self):
        assert self.rep._determine_level(30.0) == "suspicious"

    def test_unknown(self):
        assert self.rep._determine_level(10.0) == "unknown"

    def test_boundary_trusted(self):
        assert self.rep._determine_level(70.0) == "trusted"

    def test_boundary_neutral(self):
        assert self.rep._determine_level(40.0) == "neutral"

    def test_boundary_suspicious(self):
        assert self.rep._determine_level(20.0) == "suspicious"


class TestAnalyzeSenders:
    """Tests for the main analyze_senders method."""

    def setup_method(self):
        self.rep = SenderReputation()

    def _make_email(self, sender, date, read=True, replied=False, headers=None):
        return {
            "from": sender,
            "date": date,
            "read": read,
            "replied": replied,
            "headers": headers or {},
        }

    def test_empty_list(self):
        assert self.rep.analyze_senders([]) == []

    def test_single_sender(self):
        now = datetime.now()
        emails = [
            self._make_email("Alice <alice@example.com>", now.isoformat()),
        ]
        profiles = self.rep.analyze_senders(emails)
        assert len(profiles) == 1
        assert profiles[0].sender_email == "alice@example.com"
        assert profiles[0].sender_name == "Alice"
        assert profiles[0].total_emails == 1

    def test_multiple_senders_sorted_by_score(self):
        now = datetime.now()
        old = now - timedelta(days=200)
        # Create a "trusted" sender with many old emails and replies
        emails = []
        for i in range(10):
            emails.append(self._make_email(
                "Trusted <trusted@corp.com>",
                (old + timedelta(days=i * 10)).isoformat(),
                read=True,
                replied=True,
                headers={"Authentication-Results": "spf=pass dkim=pass"},
            ))
        # Create a single new sender
        emails.append(self._make_email("new@spam.org", now.isoformat(), read=False))

        profiles = self.rep.analyze_senders(emails)
        assert len(profiles) == 2
        # Trusted sender should be first (higher score)
        assert profiles[0].sender_email == "trusted@corp.com"
        assert profiles[0].reputation_score > profiles[1].reputation_score

    def test_reply_detection_from_sent(self):
        now = datetime.now()
        emails = [
            self._make_email("bob@example.com", now.isoformat()),
            # User sent an email to bob
            self._make_email("me@gmail.com", now.isoformat(), read=False),
        ]
        # Make the user's email go to bob
        emails[1]["to"] = "bob@example.com"
        profiles = self.rep.analyze_senders(emails, user_email="me@gmail.com")
        bob_profile = [p for p in profiles if p.sender_email == "bob@example.com"][0]
        assert bob_profile.reply_rate > 0.0

    def test_is_read_field(self):
        now = datetime.now()
        emails = [{"from": "a@b.com", "date": now.isoformat(), "is_read": True, "headers": {}}]
        profiles = self.rep.analyze_senders(emails)
        assert profiles[0].read_rate == 1.0

    def test_sender_field_fallback(self):
        now = datetime.now()
        emails = [{"sender": "Alice <alice@x.com>", "date": now.isoformat(), "headers": {}}]
        profiles = self.rep.analyze_senders(emails)
        assert profiles[0].sender_email == "alice@x.com"


class TestGetFirstTimeSenders:
    """Tests for get_first_time_senders."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_empty(self):
        assert self.rep.get_first_time_senders([]) == []

    def test_first_time_within_lookback(self):
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        emails = [
            {"sender": "new@example.com", "date": date_str},
        ]
        result = self.rep.get_first_time_senders(emails, lookback_days=7)
        assert len(result) == 1
        assert result[0]["sender_email"] == "new@example.com"
        assert result[0]["domain"] == "example.com"
        assert result[0]["email_count"] == 1

    def test_old_sender_excluded(self):
        old = datetime.now() - timedelta(days=60)
        date_str = old.strftime("%Y-%m-%d %H:%M:%S")
        emails = [
            {"sender": "old@example.com", "date": date_str},
        ]
        result = self.rep.get_first_time_senders(emails, lookback_days=30)
        assert len(result) == 0

    def test_multiple_emails_earliest_used(self):
        now = datetime.now()
        earlier = now - timedelta(days=5)
        emails = [
            {"sender": "sender@example.com", "date": now.strftime("%Y-%m-%d %H:%M:%S")},
            {"sender": "sender@example.com", "date": earlier.strftime("%Y-%m-%d %H:%M:%S")},
        ]
        result = self.rep.get_first_time_senders(emails, lookback_days=30)
        assert len(result) == 1
        assert result[0]["email_count"] == 2

    def test_invalid_date_skipped(self):
        emails = [{"from": "a@b.com", "date": "garbage"}]
        result = self.rep.get_first_time_senders(emails)
        assert len(result) == 0

    def test_missing_from_skipped(self):
        emails = [{"date": datetime.now().isoformat()}]
        result = self.rep.get_first_time_senders(emails)
        assert len(result) == 0


class TestGetReputationStats:
    """Tests for get_reputation_stats."""

    def setup_method(self):
        self.rep = SenderReputation()

    def test_empty_profiles(self):
        stats = self.rep.get_reputation_stats([])
        assert stats["total_senders"] == 0
        assert stats["avg_reputation_score"] == 0.0
        assert stats["by_level"]["trusted"] == 0

    def test_stats_computed(self):
        profiles = [
            SenderProfile(
                sender_email="a@b.com",
                reputation_score=80.0,
                reputation_level="trusted",
                reply_rate=0.5,
                read_rate=0.8,
                is_automated=False,
            ),
            SenderProfile(
                sender_email="c@d.com",
                reputation_score=30.0,
                reputation_level="suspicious",
                reply_rate=0.0,
                read_rate=0.1,
                is_automated=True,
            ),
        ]
        stats = self.rep.get_reputation_stats(profiles)
        assert stats["total_senders"] == 2
        assert stats["by_level"]["trusted"] == 1
        assert stats["by_level"]["suspicious"] == 1
        assert stats["automated_count"] == 1
        assert stats["avg_reputation_score"] == 55.0
        assert len(stats["top_senders"]) == 2
        assert stats["top_senders"][0]["sender_email"] == "a@b.com"

    def test_suspicious_senders_listed(self):
        profiles = [
            SenderProfile(
                sender_email="spam@bad.com",
                sender_name="Spammer",
                reputation_score=10.0,
                reputation_level="unknown",
                domain="bad.com",
                total_emails=50,
            ),
        ]
        stats = self.rep.get_reputation_stats(profiles)
        assert len(stats["suspicious_senders"]) == 1
        assert stats["suspicious_senders"][0]["sender_email"] == "spam@bad.com"
