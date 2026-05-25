"""Tests for gmail_organizer.priority -- PriorityScorer."""

import json
import pytest
from datetime import datetime, timedelta
from email.utils import format_datetime
from gmail_organizer.priority import PriorityScorer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_email(
    sender="alice@example.com",
    subject="Hello",
    labels=None,
    to="",
    date=None,
):
    """Build a minimal email dict matching the format PriorityScorer expects."""
    if date is None:
        date = format_datetime(datetime.now())
    return {
        "sender": sender,
        "subject": subject,
        "labels": labels or [],
        "to": to,
        "date": date,
    }


def _date_str(days_ago=0):
    """Return an RFC 2822 date string for N days ago."""
    dt = datetime.now() - timedelta(days=days_ago)
    return format_datetime(dt)


# ---------------------------------------------------------------------------
# Urgency scoring
# ---------------------------------------------------------------------------

class TestUrgencyScore:
    @pytest.fixture
    def scorer(self, tmp_path):
        return PriorityScorer(config_dir=str(tmp_path))

    def test_high_urgency_keyword(self, scorer):
        assert scorer._urgency_score("urgent: please respond") == 1.0

    def test_medium_urgency_keyword(self, scorer):
        assert scorer._urgency_score("meeting tomorrow at 3pm") == 0.6

    def test_low_urgency_keyword(self, scorer):
        assert scorer._urgency_score("weekly newsletter digest") == 0.1

    def test_no_keywords_neutral(self, scorer):
        assert scorer._urgency_score("random chit chat") == 0.3

    def test_case_insensitive(self, scorer):
        assert scorer._urgency_score("ASAP fix needed") == 1.0


# ---------------------------------------------------------------------------
# Recency scoring
# ---------------------------------------------------------------------------

class TestRecencyScore:
    @pytest.fixture
    def scorer(self, tmp_path):
        return PriorityScorer(config_dir=str(tmp_path))

    def test_today_returns_1(self, scorer):
        assert scorer._recency_score(_date_str(0)) == 1.0

    def test_old_email_returns_0(self, scorer):
        assert scorer._recency_score(_date_str(60)) == 0.0

    def test_empty_string_returns_0(self, scorer):
        assert scorer._recency_score("") == 0.0

    def test_invalid_date_returns_0(self, scorer):
        assert scorer._recency_score("not-a-date") == 0.0


# ---------------------------------------------------------------------------
# Priority level mapping
# ---------------------------------------------------------------------------

class TestGetPriorityLevel:
    @pytest.fixture
    def scorer(self, tmp_path):
        return PriorityScorer(config_dir=str(tmp_path))

    def test_high(self, scorer):
        assert scorer._get_priority_level(0.8) == "high"

    def test_medium(self, scorer):
        assert scorer._get_priority_level(0.5) == "medium"

    def test_low(self, scorer):
        assert scorer._get_priority_level(0.2) == "low"

    def test_boundary_high(self, scorer):
        assert scorer._get_priority_level(0.7) == "high"

    def test_boundary_medium(self, scorer):
        assert scorer._get_priority_level(0.4) == "medium"


# ---------------------------------------------------------------------------
# VIP and low priority sender overrides
# ---------------------------------------------------------------------------

class TestSenderOverrides:
    def test_vip_sender_gets_boost(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        scorer._config["vip_senders"] = ["boss@company.com"]
        # Build sender stats with a small corpus
        emails = [
            _make_email(sender="boss@company.com", subject="Status"),
            _make_email(sender="other@company.com", subject="FYI"),
        ]
        scorer._build_sender_stats(emails)
        vip_email = _make_email(sender="boss@company.com", subject="Status")
        normal_email = _make_email(sender="other@company.com", subject="Status")
        vip_score = scorer._score_email(vip_email)
        normal_score = scorer._score_email(normal_email)
        assert vip_score > normal_score

    def test_low_priority_sender_forced_low(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        scorer._config["low_priority_senders"] = ["spam@newsletters.com"]
        emails = [
            _make_email(sender="spam@newsletters.com", subject="Urgent deal!"),
        ]
        scorer._build_sender_stats(emails)
        score = scorer._score_email(
            _make_email(sender="spam@newsletters.com", subject="Urgent deal!")
        )
        assert score == 0.1


# ---------------------------------------------------------------------------
# Direct-to and question signals
# ---------------------------------------------------------------------------

class TestSignals:
    def test_direct_to_adds_score(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        emails = [
            _make_email(sender="a@b.com", subject="Hi", to="me@home.com"),
            _make_email(sender="a@b.com", subject="Hi", to="someone@else.com"),
        ]
        scorer._build_sender_stats(emails)
        direct = scorer._score_email(
            _make_email(sender="a@b.com", subject="Hi", to="me@home.com"),
            user_email="me@home.com",
        )
        indirect = scorer._score_email(
            _make_email(sender="a@b.com", subject="Hi", to="someone@else.com"),
            user_email="me@home.com",
        )
        assert direct > indirect

    def test_question_mark_adds_score(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        emails = [
            _make_email(sender="a@b.com", subject="Can you help?"),
            _make_email(sender="a@b.com", subject="Can you help"),
        ]
        scorer._build_sender_stats(emails)
        with_q = scorer._score_email(
            _make_email(sender="a@b.com", subject="can you help?")
        )
        without_q = scorer._score_email(
            _make_email(sender="a@b.com", subject="can you help")
        )
        assert with_q > without_q


# ---------------------------------------------------------------------------
# SENT emails
# ---------------------------------------------------------------------------

class TestSentEmails:
    def test_sent_email_score_is_zero(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        emails = [
            _make_email(sender="me@home.com", labels=["SENT"], to="a@b.com"),
        ]
        scorer._build_sender_stats(emails)
        score = scorer._score_email(
            _make_email(sender="me@home.com", labels=["SENT"], to="a@b.com")
        )
        assert score == 0.0


# ---------------------------------------------------------------------------
# score_emails integration
# ---------------------------------------------------------------------------

class TestScoreEmails:
    def test_returns_sorted_tuples(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        emails = [
            _make_email(sender="a@b.com", subject="fyi newsletter", date=_date_str(20)),
            _make_email(sender="b@c.com", subject="URGENT: action required", date=_date_str(0)),
        ]
        results = scorer.score_emails(emails)
        assert len(results) == 2
        # Each result is (email, score, level)
        assert results[0][1] >= results[1][1]
        # Urgent + recent should be scored higher
        assert results[0][0]["subject"] == "URGENT: action required"


# ---------------------------------------------------------------------------
# get_priority_stats
# ---------------------------------------------------------------------------

class TestGetPriorityStats:
    def test_counts_levels(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        scored = [
            ({}, 0.8, "high"),
            ({}, 0.5, "medium"),
            ({}, 0.5, "medium"),
            ({}, 0.2, "low"),
        ]
        stats = scorer.get_priority_stats(scored)
        assert stats["high"] == 1
        assert stats["medium"] == 2
        assert stats["low"] == 1
        assert stats["total"] == 4


# ---------------------------------------------------------------------------
# Config save/load round-trip
# ---------------------------------------------------------------------------

class TestConfigPersistence:
    def test_save_and_load(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        scorer._config["vip_senders"] = ["boss@work.com"]
        scorer._config["low_priority_senders"] = ["spam@junk.com"]
        scorer.save_config()

        scorer2 = PriorityScorer(config_dir=str(tmp_path))
        assert scorer2.vip_senders == ["boss@work.com"]
        assert scorer2.low_priority_senders == ["spam@junk.com"]

    def test_properties_trigger_save(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path))
        scorer.vip_senders = ["ceo@corp.com"]
        scorer.low_priority_senders = ["ads@promo.com"]

        scorer2 = PriorityScorer(config_dir=str(tmp_path))
        assert "ceo@corp.com" in scorer2.vip_senders
        assert "ads@promo.com" in scorer2.low_priority_senders

    def test_missing_config_uses_defaults(self, tmp_path):
        scorer = PriorityScorer(config_dir=str(tmp_path / "nonexistent"))
        assert scorer.vip_senders == []
        assert scorer.thresholds == {"high": 0.7, "medium": 0.4}
