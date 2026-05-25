"""Tests for the EmailAnalytics engine."""

import pytest
from datetime import datetime, timedelta

from gmail_organizer.analytics import EmailAnalytics


# ---------------------------------------------------------------------------
# Helpers / sample data
# ---------------------------------------------------------------------------

def _make_email(sender="Alice <alice@example.com>", date="Mon, 10 Mar 2025 09:30:00 +0000",
                labels=None, subject="Hello"):
    """Build a minimal email dict for testing."""
    return {
        "sender": sender,
        "date": date,
        "labels": labels or [],
        "subject": subject,
    }


def _sample_emails():
    """Return a deterministic batch of emails spanning multiple days/senders."""
    return [
        _make_email(sender="Alice <alice@example.com>", date="Mon, 10 Mar 2025 09:00:00 +0000"),
        _make_email(sender="Alice <alice@example.com>", date="Tue, 11 Mar 2025 14:00:00 +0000"),
        _make_email(sender="Bob <bob@other.org>", date="Tue, 11 Mar 2025 16:00:00 +0000"),
        _make_email(sender="carol@example.com", date="Wed, 12 Mar 2025 08:30:00 +0000"),
        _make_email(sender="dave@other.org", date="Wed, 12 Mar 2025 22:00:00 +0000", labels=["SENT"]),
        _make_email(sender="Alice <alice@example.com>", date="Thu, 13 Mar 2025 10:00:00 +0000", labels=["IMPORTANT"]),
        _make_email(sender="eve@newdomain.io", date="Fri, 14 Mar 2025 07:00:00 +0000"),
    ]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestEmailAnalyticsInit:
    def test_empty_list(self):
        analytics = EmailAnalytics([])
        assert analytics.emails == []

    def test_stores_emails(self):
        emails = _sample_emails()
        analytics = EmailAnalytics(emails)
        assert len(analytics.emails) == 7

    def test_caches_are_none_initially(self):
        analytics = EmailAnalytics([])
        assert analytics._parsed_dates is None
        assert analytics._senders is None
        assert analytics._domains is None


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

class TestParseDates:
    def test_standard_rfc2822(self):
        emails = [_make_email(date="Mon, 10 Mar 2025 09:30:00 +0000")]
        analytics = EmailAnalytics(emails)
        parsed = analytics._parse_dates()
        assert len(parsed) == 1
        assert parsed[0][1].year == 2025
        assert parsed[0][1].month == 3
        assert parsed[0][1].day == 10

    def test_fallback_iso_format(self):
        emails = [_make_email(date="2025-03-10 14:00:00")]
        analytics = EmailAnalytics(emails)
        parsed = analytics._parse_dates()
        assert len(parsed) == 1
        assert parsed[0][1].hour == 14

    def test_fallback_dmy_format(self):
        emails = [_make_email(date="10 Mar 2025 09:00:00")]
        analytics = EmailAnalytics(emails)
        parsed = analytics._parse_dates()
        assert len(parsed) == 1

    def test_missing_date_skipped(self):
        emails = [_make_email(date="")]
        analytics = EmailAnalytics(emails)
        assert analytics._parse_dates() == []

    def test_unparseable_date_skipped(self):
        emails = [_make_email(date="not-a-date")]
        analytics = EmailAnalytics(emails)
        assert analytics._parse_dates() == []

    def test_results_are_cached(self):
        analytics = EmailAnalytics(_sample_emails())
        first = analytics._parse_dates()
        second = analytics._parse_dates()
        assert first is second

    def test_sorted_chronologically(self):
        emails = [
            _make_email(date="Wed, 12 Mar 2025 10:00:00 +0000"),
            _make_email(date="Mon, 10 Mar 2025 08:00:00 +0000"),
        ]
        analytics = EmailAnalytics(emails)
        parsed = analytics._parse_dates()
        assert parsed[0][1] < parsed[1][1]


# ---------------------------------------------------------------------------
# Sender / domain extraction
# ---------------------------------------------------------------------------

class TestSenderExtraction:
    def test_angle_bracket_format(self):
        analytics = EmailAnalytics([])
        assert analytics._extract_sender_email("Alice <Alice@Example.com>") == "alice@example.com"

    def test_bare_email(self):
        analytics = EmailAnalytics([])
        assert analytics._extract_sender_email("BOB@other.org") == "bob@other.org"

    def test_name_only(self):
        analytics = EmailAnalytics([])
        assert analytics._extract_sender_email("NoEmail") == "noemail"


class TestDomainExtraction:
    def test_extracts_domain(self):
        analytics = EmailAnalytics([])
        assert analytics._extract_domain("Alice <alice@example.com>") == "example.com"

    def test_bare_email_domain(self):
        analytics = EmailAnalytics([])
        assert analytics._extract_domain("user@sub.domain.co") == "sub.domain.co"

    def test_no_at_sign(self):
        analytics = EmailAnalytics([])
        assert analytics._extract_domain("NoAtSign") == "noatsign"


# ---------------------------------------------------------------------------
# Volume over time
# ---------------------------------------------------------------------------

class TestVolumeOverTime:
    def test_empty_emails(self):
        assert EmailAnalytics([]).get_volume_over_time() == {}

    def test_daily_granularity(self):
        volume = EmailAnalytics(_sample_emails()).get_volume_over_time("daily")
        assert "2025-03-10" in volume
        assert "2025-03-11" in volume
        assert volume["2025-03-11"] == 2  # Alice + Bob on the 11th

    def test_weekly_granularity(self):
        volume = EmailAnalytics(_sample_emails()).get_volume_over_time("weekly")
        # All emails fall in the same week (March 10 is a Monday)
        assert "2025-03-10" in volume
        assert volume["2025-03-10"] == 7

    def test_monthly_granularity(self):
        volume = EmailAnalytics(_sample_emails()).get_volume_over_time("monthly")
        assert "2025-03" in volume
        assert volume["2025-03"] == 7

    def test_unknown_granularity_defaults_to_daily(self):
        volume = EmailAnalytics(_sample_emails()).get_volume_over_time("bogus")
        # Should behave like daily
        assert "2025-03-10" in volume

    def test_keys_sorted(self):
        volume = EmailAnalytics(_sample_emails()).get_volume_over_time("daily")
        keys = list(volume.keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Hourly and day-of-week distributions
# ---------------------------------------------------------------------------

class TestHourlyDistribution:
    def test_all_24_hours_present(self):
        dist = EmailAnalytics(_sample_emails()).get_hourly_distribution()
        assert set(dist.keys()) == set(range(24))
        assert sum(dist.values()) == 7

    def test_empty(self):
        dist = EmailAnalytics([]).get_hourly_distribution()
        assert all(v == 0 for v in dist.values())


class TestDayOfWeekDistribution:
    def test_all_days_present(self):
        dist = EmailAnalytics(_sample_emails()).get_day_of_week_distribution()
        expected_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        assert list(dist.keys()) == expected_days

    def test_counts_correct(self):
        dist = EmailAnalytics(_sample_emails()).get_day_of_week_distribution()
        assert dist["Monday"] == 1
        assert dist["Tuesday"] == 2
        assert dist["Saturday"] == 0


# ---------------------------------------------------------------------------
# Top senders / domains
# ---------------------------------------------------------------------------

class TestTopSenders:
    def test_correct_ranking(self):
        top = EmailAnalytics(_sample_emails()).get_top_senders(limit=3)
        # Alice has 3 emails, everyone else has 1
        assert top[0] == ("alice@example.com", 3)

    def test_limit_respected(self):
        top = EmailAnalytics(_sample_emails()).get_top_senders(limit=2)
        assert len(top) == 2

    def test_empty_emails(self):
        assert EmailAnalytics([]).get_top_senders() == []

    def test_missing_sender_skipped(self):
        emails = [{"date": "Mon, 10 Mar 2025 09:00:00 +0000"}]
        assert EmailAnalytics(emails).get_top_senders() == []


class TestTopDomains:
    def test_correct_ranking(self):
        top = EmailAnalytics(_sample_emails()).get_top_domains(limit=3)
        domains = dict(top)
        assert domains["example.com"] == 4  # alice*3 + carol
        assert domains["other.org"] == 2     # bob + dave

    def test_limit_respected(self):
        top = EmailAnalytics(_sample_emails()).get_top_domains(limit=1)
        assert len(top) == 1


# ---------------------------------------------------------------------------
# Inbox growth rate
# ---------------------------------------------------------------------------

class TestInboxGrowthRate:
    def test_cumulative(self):
        growth = EmailAnalytics(_sample_emails()).get_inbox_growth_rate()
        assert growth["2025-03"] == 7

    def test_multiple_months(self):
        emails = [
            _make_email(date="Mon, 10 Feb 2025 09:00:00 +0000"),
            _make_email(date="Mon, 10 Mar 2025 09:00:00 +0000"),
            _make_email(date="Tue, 11 Mar 2025 09:00:00 +0000"),
        ]
        growth = EmailAnalytics(emails).get_inbox_growth_rate()
        assert growth["2025-02"] == 1
        assert growth["2025-03"] == 3

    def test_empty(self):
        assert EmailAnalytics([]).get_inbox_growth_rate() == {}


# ---------------------------------------------------------------------------
# Response patterns
# ---------------------------------------------------------------------------

class TestResponsePatterns:
    def test_sent_vs_received(self):
        result = EmailAnalytics(_sample_emails()).get_response_patterns()
        assert result["sent"] == 1   # dave's email has SENT label
        assert result["received"] == 6
        assert result["total"] == 7
        assert result["ratio"] == round(1 / 6, 2)

    def test_all_sent(self):
        emails = [_make_email(labels=["SENT"]) for _ in range(3)]
        result = EmailAnalytics(emails).get_response_patterns()
        assert result["sent"] == 3
        assert result["received"] == 0
        assert result["ratio"] == 3.0  # 3 / max(0,1) = 3.0

    def test_empty(self):
        result = EmailAnalytics([]).get_response_patterns()
        assert result["total"] == 0
        assert result["ratio"] == 0.0


# ---------------------------------------------------------------------------
# Label distribution
# ---------------------------------------------------------------------------

class TestLabelDistribution:
    def test_counts(self):
        emails = [
            _make_email(labels=["INBOX", "IMPORTANT"]),
            _make_email(labels=["INBOX"]),
            _make_email(labels=["SENT"]),
        ]
        dist = EmailAnalytics(emails).get_label_distribution()
        assert dist["INBOX"] == 2
        assert dist["IMPORTANT"] == 1
        assert dist["SENT"] == 1

    def test_empty(self):
        assert EmailAnalytics([]).get_label_distribution() == {}


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------

class TestDateRange:
    def test_normal_range(self):
        result = EmailAnalytics(_sample_emails()).get_date_range()
        assert result["oldest"] == "2025-03-10"
        assert result["newest"] == "2025-03-14"
        assert result["span_days"] in (3, 4)  # inclusive vs exclusive day count

    def test_empty(self):
        result = EmailAnalytics([]).get_date_range()
        assert result["oldest"] == "N/A"
        assert result["newest"] == "N/A"
        assert result["span_days"] == 0


# ---------------------------------------------------------------------------
# Busiest / quietest periods
# ---------------------------------------------------------------------------

class TestBusiestPeriods:
    def test_returns_top_n(self):
        busiest = EmailAnalytics(_sample_emails()).get_busiest_periods(top_n=2)
        assert len(busiest) == 2
        # Busiest day should be one with 2 emails
        assert busiest[0][1] >= busiest[1][1]

    def test_empty(self):
        assert EmailAnalytics([]).get_busiest_periods() == []


class TestQuietPeriods:
    def test_returns_top_n(self):
        quietest = EmailAnalytics(_sample_emails()).get_quiet_periods(top_n=2)
        assert len(quietest) == 2
        assert quietest[0][1] <= quietest[1][1]

    def test_empty(self):
        assert EmailAnalytics([]).get_quiet_periods() == []


# ---------------------------------------------------------------------------
# Monthly stats
# ---------------------------------------------------------------------------

class TestMonthlyStats:
    def test_single_month(self):
        stats = EmailAnalytics(_sample_emails()).get_monthly_stats()
        assert len(stats) == 1
        s = stats[0]
        assert s["month"] == "2025-03"
        assert s["count"] == 7
        assert s["unique_senders"] == 5  # alice, bob, carol, dave, eve
        assert s["avg_per_day"] == round(7 / 30, 1)

    def test_multiple_months(self):
        emails = [
            _make_email(date="Mon, 10 Feb 2025 09:00:00 +0000"),
            _make_email(date="Mon, 10 Mar 2025 09:00:00 +0000"),
        ]
        stats = EmailAnalytics(emails).get_monthly_stats()
        assert len(stats) == 2
        assert stats[0]["month"] == "2025-02"
        assert stats[1]["month"] == "2025-03"

    def test_empty(self):
        assert EmailAnalytics([]).get_monthly_stats() == []


# ---------------------------------------------------------------------------
# Comprehensive summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_keys_present(self):
        summary = EmailAnalytics(_sample_emails()).get_summary()
        expected_keys = {
            "total_emails", "date_range", "unique_senders",
            "unique_domains", "sent", "received", "avg_per_day",
        }
        assert expected_keys.issubset(summary.keys())

    def test_values(self):
        summary = EmailAnalytics(_sample_emails()).get_summary()
        assert summary["total_emails"] == 7
        assert summary["unique_senders"] == 5
        assert summary["unique_domains"] == 3  # example.com, other.org, newdomain.io
        assert summary["sent"] == 1
        assert summary["received"] == 6

    def test_avg_per_day(self):
        summary = EmailAnalytics(_sample_emails()).get_summary()
        span = summary["date_range"]["span_days"]
        assert summary["avg_per_day"] == round(7 / max(span, 1), 1)

    def test_empty(self):
        summary = EmailAnalytics([]).get_summary()
        assert summary["total_emails"] == 0
        assert summary["sent"] == 0
