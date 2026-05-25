"""Tests for the EmailSummarizer and related dataclasses."""

import pytest
from datetime import datetime, timedelta

from gmail_organizer.summaries import EmailDigest, ThreadSummary, EmailSummarizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_email(
    sender="Alice <alice@example.com>",
    date="Mon, 10 Mar 2025 09:00:00 +0000",
    subject="Hello",
    body="This is the body",
    snippet=None,
    labels=None,
    category="primary",
    thread_id="t1",
    email_id="e1",
):
    email = {
        "sender": sender,
        "date": date,
        "subject": subject,
        "body": body,
        "labels": labels or [],
        "category": category,
        "threadId": thread_id,
        "email_id": email_id,
    }
    if snippet is not None:
        email["snippet"] = snippet
    return email


def _period_emails():
    """Emails all on 2025-03-10 for daily digest testing."""
    return [
        _make_email(sender="Alice <alice@example.com>", date="Mon, 10 Mar 2025 09:00:00 +0000",
                     subject="Project update", body="Here is the meeting update.",
                     thread_id="t1", email_id="e1", labels=["IMPORTANT"]),
        _make_email(sender="Bob <bob@other.org>", date="Mon, 10 Mar 2025 10:00:00 +0000",
                     subject="Re: Project update", body="Please review the attached.",
                     thread_id="t1", email_id="e2", category="work"),
        _make_email(sender="Carol <carol@shop.com>", date="Mon, 10 Mar 2025 14:00:00 +0000",
                     subject="Your order confirmation", body="Your order has been confirmed.",
                     thread_id="t2", email_id="e3", labels=["STARRED"],
                     category="shopping"),
        _make_email(sender="Dave <dave@example.com>", date="Mon, 10 Mar 2025 16:00:00 +0000",
                     subject="Urgent: deadline tomorrow", body="We need your input ASAP.",
                     thread_id="t3", email_id="e4", category="work"),
        _make_email(sender="Eve <eve@news.io>", date="Mon, 10 Mar 2025 18:00:00 +0000",
                     subject="Weekly announcement", body="Important announcement for the team.",
                     thread_id="t4", email_id="e5", category="updates"),
    ]


# ---------------------------------------------------------------------------
# EmailDigest dataclass
# ---------------------------------------------------------------------------

class TestEmailDigest:
    def test_defaults(self):
        d = EmailDigest(period_start="2025-03-10", period_end="2025-03-11")
        assert d.total_emails == 0
        assert d.total_threads == 0
        assert d.top_senders == []
        assert d.category_breakdown == {}
        assert d.busiest_hour == 0

    def test_custom_values(self):
        d = EmailDigest(
            period_start="2025-03-10",
            period_end="2025-03-11",
            total_emails=42,
            top_senders=[("alice@example.com", 10)],
        )
        assert d.total_emails == 42
        assert d.top_senders[0][0] == "alice@example.com"


class TestThreadSummary:
    def test_defaults(self):
        ts = ThreadSummary(thread_id="t1", subject="Test")
        assert ts.message_count == 0
        assert ts.has_question is False
        assert ts.has_action_item is False

    def test_custom_values(self):
        ts = ThreadSummary(
            thread_id="t1", subject="Test",
            participants=["a@b.com"], message_count=5,
            has_question=True,
        )
        assert ts.message_count == 5
        assert ts.has_question is True


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_rfc2822(self):
        dt = self.s._parse_date("Mon, 10 Mar 2025 09:30:00 +0000")
        assert dt is not None
        assert dt.year == 2025 and dt.month == 3 and dt.day == 10

    def test_iso_with_z(self):
        dt = self.s._parse_date("2025-03-10T09:30:00Z")
        assert dt is not None
        assert dt.tzinfo is None  # stripped

    def test_iso_with_tz(self):
        dt = self.s._parse_date("2025-03-10T09:30:00+05:00")
        assert dt is not None

    def test_date_only(self):
        dt = self.s._parse_date("2025-03-10")
        assert dt is not None
        assert dt.day == 10

    def test_datetime_passthrough(self):
        original = datetime(2025, 3, 10, 9, 30)
        assert self.s._parse_date(original) is original

    def test_empty_string(self):
        assert self.s._parse_date("") is None

    def test_garbage(self):
        assert self.s._parse_date("not a date at all") is None

    def test_parenthesized_timezone_stripped(self):
        dt = self.s._parse_date("Mon, 10 Mar 2025 09:30:00 +0000 (UTC)")
        assert dt is not None


# ---------------------------------------------------------------------------
# _extract_sender
# ---------------------------------------------------------------------------

class TestExtractSender:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_angle_brackets(self):
        email = {"sender": "Alice <Alice@Example.Com>"}
        assert self.s._extract_sender(email) == "alice@example.com"

    def test_bare_email(self):
        email = {"sender": "bob@other.org"}
        assert self.s._extract_sender(email) == "bob@other.org"

    def test_from_field_fallback(self):
        email = {"from": "carol@x.com"}
        assert self.s._extract_sender(email) == "carol@x.com"

    def test_plain_name(self):
        email = {"sender": "  Dave  "}
        assert self.s._extract_sender(email) == "Dave"

    def test_missing(self):
        assert self.s._extract_sender({}) == ""


# ---------------------------------------------------------------------------
# _get_period_range
# ---------------------------------------------------------------------------

class TestGetPeriodRange:
    def setup_method(self):
        self.s = EmailSummarizer()
        self.ref = datetime(2025, 3, 12, 15, 30)  # Wednesday

    def test_daily(self):
        start, end = self.s._get_period_range(self.ref, "daily")
        assert start == datetime(2025, 3, 12, 0, 0, 0)
        assert end == datetime(2025, 3, 13, 0, 0, 0)

    def test_weekly(self):
        start, end = self.s._get_period_range(self.ref, "weekly")
        assert start.weekday() == 0  # Monday
        assert (end - start).days == 7

    def test_monthly(self):
        start, end = self.s._get_period_range(self.ref, "monthly")
        assert start == datetime(2025, 3, 1, 0, 0, 0)
        assert end == datetime(2025, 4, 1, 0, 0, 0)

    def test_monthly_december(self):
        ref = datetime(2025, 12, 15)
        start, end = self.s._get_period_range(ref, "monthly")
        assert end == datetime(2026, 1, 1, 0, 0, 0)

    def test_custom_defaults_to_7_days(self):
        start, end = self.s._get_period_range(self.ref, "custom")
        assert (end - start).days == 7


# ---------------------------------------------------------------------------
# _filter_by_date
# ---------------------------------------------------------------------------

class TestFilterByDate:
    def test_filters_correctly(self):
        s = EmailSummarizer()
        emails = _period_emails()
        start = datetime(2025, 3, 10, 0, 0)
        end = datetime(2025, 3, 10, 12, 0)
        filtered = s._filter_by_date(emails, start, end)
        # 9am and 10am emails should match
        assert len(filtered) == 2

    def test_no_match(self):
        s = EmailSummarizer()
        emails = _period_emails()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 2)
        assert s._filter_by_date(emails, start, end) == []


# ---------------------------------------------------------------------------
# _needs_response
# ---------------------------------------------------------------------------

class TestNeedsResponse:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_question_in_subject(self):
        email = _make_email(subject="Can you help?", body="Hi there")
        assert self.s._needs_response(email) is True

    def test_action_pattern_in_body(self):
        email = _make_email(subject="Task", body="Please review the document.")
        assert self.s._needs_response(email) is True

    def test_urgent(self):
        email = _make_email(subject="Report", body="This is urgent")
        assert self.s._needs_response(email) is True

    def test_asap(self):
        email = _make_email(subject="Hey", body="Need this ASAP")
        assert self.s._needs_response(email) is True

    def test_no_response_needed(self):
        email = _make_email(subject="FYI", body="Just letting you know.")
        assert self.s._needs_response(email) is False

    def test_empty_fields(self):
        email = {"subject": None, "body": None}
        assert self.s._needs_response(email) is False


# ---------------------------------------------------------------------------
# _extract_highlights
# ---------------------------------------------------------------------------

class TestExtractHighlights:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_important_label_scores(self):
        emails = [
            _make_email(subject="Important announcement", body="Team update",
                        labels=["IMPORTANT"]),
        ]
        highlights = self.s._extract_highlights(emails)
        # IMPORTANT label = 3 points, "important" keyword = 1, "announcement" = 1 => 5, threshold 2
        assert len(highlights) == 1
        assert highlights[0]["score"] >= 2

    def test_starred_email(self):
        emails = [
            _make_email(subject="Meeting invite", body="confirmation", labels=["STARRED"]),
        ]
        highlights = self.s._extract_highlights(emails)
        # STARRED = 3, "meeting" = 1, "invite" = 1, "confirmation" = 1 => 6
        assert len(highlights) == 1

    def test_below_threshold_excluded(self):
        emails = [
            _make_email(subject="Hey", body="Nothing special"),
        ]
        highlights = self.s._extract_highlights(emails)
        assert len(highlights) == 0

    def test_sorted_by_score_descending(self):
        emails = [
            _make_email(subject="update", body="", labels=[]),
            _make_email(subject="Important announcement update", body="meeting", labels=["IMPORTANT"]),
        ]
        highlights = self.s._extract_highlights(emails)
        if len(highlights) >= 2:
            assert highlights[0]["score"] >= highlights[1]["score"]


# ---------------------------------------------------------------------------
# _extract_action_items
# ---------------------------------------------------------------------------

class TestExtractActionItems:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_please_review(self):
        emails = [_make_email(body="Please review the PR.")]
        items = self.s._extract_action_items(emails)
        assert len(items) == 1
        assert any("review" in a.lower() for a in items[0]["actions"])

    def test_deadline(self):
        emails = [_make_email(body="The deadline is Friday.")]
        items = self.s._extract_action_items(emails)
        assert len(items) == 1

    def test_action_required(self):
        emails = [_make_email(body="Action required: approve the budget.")]
        items = self.s._extract_action_items(emails)
        assert len(items) == 1

    def test_needs_your(self):
        emails = [_make_email(body="This needs your attention.")]
        items = self.s._extract_action_items(emails)
        assert len(items) == 1

    def test_no_action(self):
        emails = [_make_email(body="Just a friendly hello.")]
        items = self.s._extract_action_items(emails)
        assert len(items) == 0

    def test_max_three_actions(self):
        emails = [_make_email(
            body="Please review and confirm. Deadline is tomorrow. Action required ASAP. Needs your input."
        )]
        items = self.s._extract_action_items(emails)
        assert len(items) == 1
        assert len(items[0]["actions"]) <= 3


# ---------------------------------------------------------------------------
# _extract_trending_topics
# ---------------------------------------------------------------------------

class TestExtractTrendingTopics:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_basic(self):
        emails = [
            _make_email(subject="Project launch discussion"),
            _make_email(subject="Project launch timeline"),
            _make_email(subject="Budget review notes"),
        ]
        topics = self.s._extract_trending_topics(emails)
        topic_words = [t[0] for t in topics]
        assert "project" in topic_words
        assert "launch" in topic_words

    def test_re_prefix_stripped(self):
        emails = [
            _make_email(subject="Re: Project launch"),
            _make_email(subject="Fwd: Project launch"),
        ]
        topics = self.s._extract_trending_topics(emails)
        topic_words = [t[0] for t in topics]
        assert "project" in topic_words

    def test_stop_words_excluded(self):
        emails = [_make_email(subject="The email message from your account")]
        topics = self.s._extract_trending_topics(emails)
        topic_words = [t[0] for t in topics]
        for sw in ["email", "message", "from", "your"]:
            assert sw not in topic_words

    def test_short_words_excluded(self):
        emails = [_make_email(subject="Hi Bob can you do it?")]
        topics = self.s._extract_trending_topics(emails)
        # All words are 3 chars or fewer except none that pass stop-word filter
        assert len(topics) == 0

    def test_top_n_limit(self):
        emails = [_make_email(subject=f"topic_{i} discussion") for i in range(20)]
        topics = self.s._extract_trending_topics(emails, top_n=5)
        assert len(topics) <= 5


# ---------------------------------------------------------------------------
# _calc_weekly_avg
# ---------------------------------------------------------------------------

class TestCalcWeeklyAvg:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_single_date(self):
        dates = [datetime(2025, 3, 10)]
        assert self.s._calc_weekly_avg(dates) == 1.0

    def test_empty(self):
        assert self.s._calc_weekly_avg([]) == 0.0

    def test_two_weeks(self):
        dates = [
            datetime(2025, 3, 1),
            datetime(2025, 3, 8),
            datetime(2025, 3, 15),
        ]
        avg = self.s._calc_weekly_avg(dates)
        # Span = 14 days = 2 weeks, 3 emails => 1.5
        assert avg == 1.5

    def test_same_day(self):
        dates = [datetime(2025, 3, 10)] * 5
        assert self.s._calc_weekly_avg(dates) == 5.0


# ---------------------------------------------------------------------------
# generate_digest
# ---------------------------------------------------------------------------

class TestGenerateDigest:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_empty_emails(self):
        digest = self.s.generate_digest([], period="daily", reference_date="2025-03-10")
        assert digest.total_emails == 0
        assert digest.period_start == "2025-03-10"

    def test_daily_digest(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-03-10"
        )
        assert digest.total_emails == 5
        assert digest.period_start == "2025-03-10"

    def test_top_senders(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-03-10"
        )
        senders = dict(digest.top_senders)
        assert "alice@example.com" in senders

    def test_category_breakdown(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-03-10"
        )
        assert "work" in digest.category_breakdown
        assert digest.category_breakdown["work"] == 2

    def test_busiest_hour(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-03-10"
        )
        assert isinstance(digest.busiest_hour, int)
        assert 0 <= digest.busiest_hour <= 23

    def test_action_items_detected(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-03-10"
        )
        # Dave's email says "ASAP" and has "deadline" in subject
        assert len(digest.action_items) >= 1

    def test_response_needed(self):
        emails = [
            _make_email(subject="Can you review?", date="Mon, 10 Mar 2025 09:00:00 +0000"),
            _make_email(subject="FYI", date="Mon, 10 Mar 2025 10:00:00 +0000", body="No action."),
        ]
        digest = self.s.generate_digest(emails, period="daily", reference_date="2025-03-10")
        assert digest.response_needed >= 1

    def test_highlights(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-03-10"
        )
        # Eve's "announcement" + IMPORTANT Alice => highlights exist
        assert isinstance(digest.highlights, list)

    def test_top_subjects_deduped(self):
        emails = [
            _make_email(subject="Project Update", date="Mon, 10 Mar 2025 09:00:00 +0000"),
            _make_email(subject="Re: Project Update", date="Mon, 10 Mar 2025 10:00:00 +0000"),
            _make_email(subject="Different Topic", date="Mon, 10 Mar 2025 11:00:00 +0000"),
        ]
        digest = self.s.generate_digest(emails, period="daily", reference_date="2025-03-10")
        normalized = [s.lower().replace("re: ", "") for s in digest.top_subjects]
        # After normalization, "project update" should appear only once
        assert normalized.count("project update") <= 1

    def test_invalid_reference_date_uses_now(self):
        # Should not raise; falls back to datetime.now()
        digest = self.s.generate_digest(_period_emails(), reference_date="bad-date")
        assert isinstance(digest, EmailDigest)

    def test_weekly_digest(self):
        digest = self.s.generate_digest(
            _period_emails(), period="weekly", reference_date="2025-03-10"
        )
        assert digest.total_emails == 5

    def test_monthly_digest(self):
        digest = self.s.generate_digest(
            _period_emails(), period="monthly", reference_date="2025-03-15"
        )
        assert digest.total_emails == 5

    def test_thread_count(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-03-10"
        )
        # t1, t2, t3, t4
        assert digest.total_threads == 4

    def test_no_emails_in_period(self):
        digest = self.s.generate_digest(
            _period_emails(), period="daily", reference_date="2025-01-01"
        )
        assert digest.total_emails == 0


# ---------------------------------------------------------------------------
# summarize_threads
# ---------------------------------------------------------------------------

class TestSummarizeThreads:
    def setup_method(self):
        self.s = EmailSummarizer()

    def _thread_emails(self):
        return [
            _make_email(sender="Alice <alice@a.com>", subject="Discussion",
                        date="Mon, 10 Mar 2025 09:00:00 +0000", thread_id="t1", email_id="e1",
                        body="What do you think?"),
            _make_email(sender="Bob <bob@b.com>", subject="Re: Discussion",
                        date="Mon, 10 Mar 2025 10:00:00 +0000", thread_id="t1", email_id="e2",
                        body="Please review and confirm."),
            _make_email(sender="Alice <alice@a.com>", subject="Re: Discussion",
                        date="Mon, 10 Mar 2025 11:00:00 +0000", thread_id="t1", email_id="e3",
                        body="Confirmed."),
            # Single-message thread (should be excluded)
            _make_email(sender="Carol <carol@c.com>", subject="Solo",
                        date="Mon, 10 Mar 2025 12:00:00 +0000", thread_id="t2", email_id="e4"),
        ]

    def test_single_message_threads_excluded(self):
        summaries = self.s.summarize_threads(self._thread_emails())
        thread_ids = [s.thread_id for s in summaries]
        assert "t2" not in thread_ids

    def test_thread_summary_fields(self):
        summaries = self.s.summarize_threads(self._thread_emails())
        assert len(summaries) == 1
        ts = summaries[0]
        assert ts.thread_id == "t1"
        assert ts.subject == "Discussion"
        assert ts.message_count == 3
        assert len(ts.participants) == 2
        assert ts.has_question is True  # "What do you think?"
        assert ts.has_action_item is True  # "Please review and confirm"

    def test_last_sender(self):
        summaries = self.s.summarize_threads(self._thread_emails())
        assert summaries[0].last_sender == "alice@a.com"

    def test_date_range_formatted(self):
        summaries = self.s.summarize_threads(self._thread_emails())
        assert "Mar 10" in summaries[0].date_range

    def test_snippet_truncated(self):
        long_body = "x" * 300
        emails = [
            _make_email(thread_id="t1", email_id="e1", body="short"),
            _make_email(thread_id="t1", email_id="e2", body=long_body,
                        date="Tue, 11 Mar 2025 10:00:00 +0000"),
        ]
        summaries = self.s.summarize_threads(emails)
        assert len(summaries[0].snippet) <= 150

    def test_limit(self):
        # Build multiple 2-message threads
        emails = []
        for i in range(10):
            tid = f"t{i}"
            emails.append(_make_email(thread_id=tid, email_id=f"e{i}a",
                                       date="Mon, 10 Mar 2025 09:00:00 +0000"))
            emails.append(_make_email(thread_id=tid, email_id=f"e{i}b",
                                       date="Mon, 10 Mar 2025 10:00:00 +0000"))
        summaries = self.s.summarize_threads(emails, limit=3)
        assert len(summaries) == 3

    def test_sorted_by_message_count(self):
        emails = [
            _make_email(thread_id="big", email_id="b1"),
            _make_email(thread_id="big", email_id="b2",
                        date="Mon, 10 Mar 2025 10:00:00 +0000"),
            _make_email(thread_id="big", email_id="b3",
                        date="Mon, 10 Mar 2025 11:00:00 +0000"),
            _make_email(thread_id="small", email_id="s1"),
            _make_email(thread_id="small", email_id="s2",
                        date="Mon, 10 Mar 2025 12:00:00 +0000"),
        ]
        summaries = self.s.summarize_threads(emails)
        assert summaries[0].message_count >= summaries[1].message_count

    def test_empty_input(self):
        assert self.s.summarize_threads([]) == []


# ---------------------------------------------------------------------------
# get_sender_summary
# ---------------------------------------------------------------------------

class TestGetSenderSummary:
    def setup_method(self):
        self.s = EmailSummarizer()

    def test_basic(self):
        emails = [
            _make_email(sender="Alice <alice@a.com>", subject="S1",
                        date="Mon, 10 Mar 2025 09:00:00 +0000", category="work"),
            _make_email(sender="Alice <alice@a.com>", subject="S2",
                        date="Tue, 11 Mar 2025 10:00:00 +0000", category="personal"),
            _make_email(sender="Bob <bob@b.com>", subject="S3",
                        date="Wed, 12 Mar 2025 11:00:00 +0000"),
        ]
        result = self.s.get_sender_summary(emails, "alice")
        assert result["total"] == 2
        assert result["first_seen"] == "2025-03-10"
        assert result["last_seen"] == "2025-03-11"
        assert "work" in result["categories"]
        assert len(result["recent_subjects"]) == 2

    def test_not_found(self):
        result = self.s.get_sender_summary([], "nobody")
        assert result["total"] == 0

    def test_case_insensitive(self):
        emails = [_make_email(sender="ALICE <ALICE@A.COM>")]
        result = self.s.get_sender_summary(emails, "alice")
        assert result["total"] == 1

    def test_avg_per_week(self):
        emails = [
            _make_email(sender="a@b.com", date="Mon, 03 Mar 2025 09:00:00 +0000"),
            _make_email(sender="a@b.com", date="Mon, 10 Mar 2025 09:00:00 +0000"),
            _make_email(sender="a@b.com", date="Mon, 17 Mar 2025 09:00:00 +0000"),
        ]
        result = self.s.get_sender_summary(emails, "a@b.com")
        # Span = 14 days = 2 weeks, 3 emails => 1.5
        assert result["avg_per_week"] == 1.5

    def test_recent_subjects_max_five(self):
        emails = [
            _make_email(sender="a@b.com", subject=f"Sub {i}",
                        date=f"Mon, {10+i} Mar 2025 09:00:00 +0000")
            for i in range(8)
        ]
        result = self.s.get_sender_summary(emails, "a@b.com")
        assert len(result["recent_subjects"]) <= 5

    def test_no_dates_returns_na(self):
        emails = [_make_email(sender="a@b.com", date="")]
        result = self.s.get_sender_summary(emails, "a@b.com")
        assert result["first_seen"] == "N/A"
        assert result["last_seen"] == "N/A"
