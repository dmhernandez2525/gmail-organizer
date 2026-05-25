"""Tests for gmail_organizer.duplicates -- DuplicateDetector and dataclasses."""

import time
import pytest
from gmail_organizer.duplicates import DuplicateDetector, DuplicateGroup, ThreadGroup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_ms(offset_seconds=0):
    """Return an epoch-millisecond string offset from a fixed base time."""
    base = 1700000000  # Nov 2023
    return str(int((base + offset_seconds) * 1000))


def _make_email(
    email_id="msg1",
    thread_id="t1",
    message_id="<abc@example.com>",
    from_addr="alice@example.com",
    subject="Hello",
    internal_date=None,
    size_estimate=1000,
    label_ids=None,
    to_addr=None,
):
    """Build a Gmail-API-style email dict."""
    headers = [
        {"name": "Message-ID", "value": message_id},
        {"name": "From", "value": from_addr},
        {"name": "Subject", "value": subject},
    ]
    if to_addr:
        headers.append({"name": "To", "value": to_addr})

    return {
        "email_id": email_id,
        "threadId": thread_id,
        "internalDate": internal_date or _ts_ms(),
        "sizeEstimate": size_estimate,
        "labelIds": label_ids or [],
        "payload": {"headers": headers},
    }


# ---------------------------------------------------------------------------
# DuplicateGroup / ThreadGroup dataclass properties
# ---------------------------------------------------------------------------

class TestDuplicateGroup:
    def test_count(self):
        g = DuplicateGroup(emails=[{"sizeEstimate": 100}, {"sizeEstimate": 200}])
        assert g.count == 2

    def test_removable_count(self):
        g = DuplicateGroup(emails=[{}, {}, {}])
        assert g.removable_count == 2

    def test_removable_count_single(self):
        g = DuplicateGroup(emails=[{}])
        assert g.removable_count == 0

    def test_removable_count_empty(self):
        g = DuplicateGroup(emails=[])
        assert g.removable_count == 0

    def test_space_savings_bytes(self):
        keep = {"sizeEstimate": 500}
        other = {"sizeEstimate": 500}
        g = DuplicateGroup(emails=[keep, other], keep_email=keep)
        assert g.space_savings_bytes == 500

    def test_space_savings_no_keep(self):
        g = DuplicateGroup(emails=[{"sizeEstimate": 100}])
        assert g.space_savings_bytes == 0


class TestThreadGroup:
    def test_count_and_size(self):
        emails = [
            {"sizeEstimate": 100},
            {"sizeEstimate": 200},
            {"sizeEstimate": 300},
        ]
        g = ThreadGroup(thread_id="t1", emails=emails, subject="Hello")
        assert g.count == 3
        assert g.total_size_bytes == 600


# ---------------------------------------------------------------------------
# DuplicateDetector -- exact ID duplicates
# ---------------------------------------------------------------------------

class TestExactIdDuplicates:
    def test_detects_same_message_id(self):
        detector = DuplicateDetector()
        emails = [
            _make_email(email_id="a", message_id="<dup@example.com>"),
            _make_email(email_id="b", message_id="<dup@example.com>"),
        ]
        groups = detector.find_duplicates(emails)
        exact = [g for g in groups if g.reason == "exact_id"]
        assert len(exact) == 1
        assert exact[0].count == 2

    def test_no_duplicates_when_unique_ids(self):
        detector = DuplicateDetector()
        emails = [
            _make_email(email_id="a", message_id="<one@example.com>"),
            _make_email(email_id="b", message_id="<two@example.com>"),
        ]
        groups = detector.find_duplicates(emails)
        exact = [g for g in groups if g.reason == "exact_id"]
        assert len(exact) == 0

    def test_message_id_normalized(self):
        """Angle brackets and whitespace are stripped before comparison."""
        detector = DuplicateDetector()
        emails = [
            _make_email(email_id="a", message_id="<DUP@Example.com>"),
            _make_email(email_id="b", message_id="  dup@example.com  "),
        ]
        groups = detector.find_duplicates(emails)
        exact = [g for g in groups if g.reason == "exact_id"]
        assert len(exact) == 1


# ---------------------------------------------------------------------------
# DuplicateDetector -- similar content duplicates
# ---------------------------------------------------------------------------

class TestSimilarContentDuplicates:
    def test_same_sender_similar_subject_close_date(self):
        detector = DuplicateDetector()
        base_ts = _ts_ms(0)
        close_ts = _ts_ms(30)  # 30 seconds apart
        emails = [
            _make_email(
                email_id="a",
                message_id="<u1@example.com>",
                from_addr="alice@example.com",
                subject="Project status report",
                internal_date=base_ts,
            ),
            _make_email(
                email_id="b",
                message_id="<u2@example.com>",
                from_addr="alice@example.com",
                subject="Project status report",
                internal_date=close_ts,
            ),
        ]
        groups = detector.find_duplicates(emails)
        similar = [g for g in groups if g.reason == "similar_content"]
        assert len(similar) >= 1

    def test_different_senders_not_grouped(self):
        detector = DuplicateDetector()
        base_ts = _ts_ms(0)
        emails = [
            _make_email(
                email_id="a",
                message_id="<u1@example.com>",
                from_addr="alice@example.com",
                subject="Same subject line",
                internal_date=base_ts,
            ),
            _make_email(
                email_id="b",
                message_id="<u2@example.com>",
                from_addr="bob@example.com",
                subject="Same subject line",
                internal_date=base_ts,
            ),
        ]
        groups = detector.find_duplicates(emails)
        similar = [g for g in groups if g.reason == "similar_content"]
        assert len(similar) == 0


# ---------------------------------------------------------------------------
# DuplicateDetector -- thread duplicates
# ---------------------------------------------------------------------------

class TestThreadDuplicates:
    def test_same_thread_same_subject_close_timestamp(self):
        detector = DuplicateDetector()
        base_ts = _ts_ms(0)
        close_ts = _ts_ms(10)
        emails = [
            _make_email(
                email_id="a",
                thread_id="thread-1",
                message_id="<t1@example.com>",
                from_addr="alice@example.com",
                subject="Discussion topic",
                internal_date=base_ts,
            ),
            _make_email(
                email_id="b",
                thread_id="thread-1",
                message_id="<t2@example.com>",
                from_addr="bob@example.com",
                subject="Discussion topic",
                internal_date=close_ts,
            ),
        ]
        # These won't be caught by exact_id or similar_content (different senders),
        # so they fall through to thread duplicate detection.
        groups = detector.find_duplicates(emails)
        thread_dups = [g for g in groups if g.reason == "same_thread"]
        assert len(thread_dups) >= 1

    def test_same_thread_different_subjects_not_grouped(self):
        detector = DuplicateDetector()
        base_ts = _ts_ms(0)
        emails = [
            _make_email(
                email_id="a",
                thread_id="thread-1",
                message_id="<t1@example.com>",
                subject="Topic A is very different",
                internal_date=base_ts,
            ),
            _make_email(
                email_id="b",
                thread_id="thread-1",
                message_id="<t2@example.com>",
                subject="Completely unrelated subject matter",
                internal_date=base_ts,
            ),
        ]
        groups = detector.find_duplicates(emails)
        thread_dups = [g for g in groups if g.reason == "same_thread"]
        assert len(thread_dups) == 0


# ---------------------------------------------------------------------------
# find_large_threads
# ---------------------------------------------------------------------------

class TestFindLargeThreads:
    def test_thread_at_min_size(self):
        detector = DuplicateDetector()
        emails = [
            _make_email(
                email_id=f"m{i}",
                thread_id="big-thread",
                message_id=f"<m{i}@example.com>",
                subject="Long thread",
                internal_date=_ts_ms(i * 100),
                size_estimate=500,
            )
            for i in range(10)
        ]
        threads = detector.find_large_threads(emails, min_size=10)
        assert len(threads) == 1
        assert threads[0].count == 10
        assert threads[0].total_size_bytes == 5000

    def test_thread_below_min_size_excluded(self):
        detector = DuplicateDetector()
        emails = [
            _make_email(email_id=f"m{i}", thread_id="small-thread",
                        message_id=f"<m{i}@ex.com>", internal_date=_ts_ms(i))
            for i in range(5)
        ]
        threads = detector.find_large_threads(emails, min_size=10)
        assert len(threads) == 0

    def test_custom_min_size(self):
        detector = DuplicateDetector()
        emails = [
            _make_email(email_id=f"m{i}", thread_id="t1",
                        message_id=f"<m{i}@ex.com>", internal_date=_ts_ms(i * 10))
            for i in range(3)
        ]
        threads = detector.find_large_threads(emails, min_size=3)
        assert len(threads) == 1

    def test_sorted_by_count_descending(self):
        detector = DuplicateDetector()
        emails = []
        for i in range(5):
            emails.append(
                _make_email(email_id=f"a{i}", thread_id="big",
                            message_id=f"<a{i}@ex.com>", internal_date=_ts_ms(i))
            )
        for i in range(3):
            emails.append(
                _make_email(email_id=f"b{i}", thread_id="small",
                            message_id=f"<b{i}@ex.com>", internal_date=_ts_ms(i))
            )
        threads = detector.find_large_threads(emails, min_size=3)
        assert threads[0].count >= threads[-1].count


# ---------------------------------------------------------------------------
# get_cleanup_stats
# ---------------------------------------------------------------------------

class TestGetCleanupStats:
    def test_returns_correct_counts(self):
        detector = DuplicateDetector()
        keep = _make_email(email_id="k", size_estimate=1000)
        dup = _make_email(email_id="d", size_estimate=1000)
        group = DuplicateGroup(emails=[keep, dup], reason="exact_id", keep_email=keep)

        threads = []
        stats = detector.get_cleanup_stats([group], threads)

        assert stats["duplicate_groups"] == 1
        assert stats["total_removable_duplicates"] == 1
        assert stats["space_savings_bytes"] == 1000
        assert stats["large_threads"] == 0
        assert "recommendations" in stats

    def test_stats_with_threads(self):
        detector = DuplicateDetector()
        thread_emails = [{"sizeEstimate": 500} for _ in range(12)]
        tg = ThreadGroup(thread_id="t1", emails=thread_emails, subject="Big thread")

        stats = detector.get_cleanup_stats([], [tg])
        assert stats["large_threads"] == 1
        assert stats["large_thread_total_messages"] == 12
        assert stats["large_thread_total_size_bytes"] == 6000


# ---------------------------------------------------------------------------
# _select_keep_email
# ---------------------------------------------------------------------------

class TestSelectKeepEmail:
    def test_prefers_inbox(self):
        detector = DuplicateDetector()
        inbox = _make_email(email_id="a", label_ids=["INBOX"], size_estimate=100)
        archive = _make_email(email_id="b", label_ids=[], size_estimate=200)
        result = detector._select_keep_email([inbox, archive])
        assert result["email_id"] == "a"

    def test_prefers_unread_when_both_inbox(self):
        detector = DuplicateDetector()
        read = _make_email(email_id="a", label_ids=["INBOX"], size_estimate=100)
        unread = _make_email(email_id="b", label_ids=["INBOX", "UNREAD"], size_estimate=100)
        result = detector._select_keep_email([read, unread])
        assert result["email_id"] == "b"

    def test_prefers_largest_when_same_labels(self):
        detector = DuplicateDetector()
        small = _make_email(email_id="a", label_ids=[], size_estimate=100)
        large = _make_email(email_id="b", label_ids=[], size_estimate=5000)
        result = detector._select_keep_email([small, large])
        assert result["email_id"] == "b"

    def test_empty_list_returns_empty_dict(self):
        detector = DuplicateDetector()
        assert detector._select_keep_email([]) == {}


# ---------------------------------------------------------------------------
# _subject_similarity and _normalize_subject
# ---------------------------------------------------------------------------

class TestSubjectSimilarityAndNormalize:
    def test_identical_subjects_return_1(self):
        detector = DuplicateDetector()
        assert detector._subject_similarity("hello world", "hello world") == 1.0

    def test_completely_different_return_low(self):
        detector = DuplicateDetector()
        score = detector._subject_similarity("aaaa", "zzzz")
        assert score == 0.0

    def test_both_empty_strings_return_1(self):
        """Two identical empty strings are equal per the a == b fast path."""
        detector = DuplicateDetector()
        assert detector._subject_similarity("", "") == 1.0

    def test_one_empty_string_returns_0(self):
        detector = DuplicateDetector()
        assert detector._subject_similarity("abc", "") == 0.0
        assert detector._subject_similarity("", "abc") == 0.0

    def test_normalize_strips_re_fwd(self):
        detector = DuplicateDetector()
        assert detector._normalize_subject("Re: Hello") == "hello"
        assert detector._normalize_subject("Fwd: Re: Fwd: Hello") == "hello"
        assert detector._normalize_subject("FW: Status") == "status"

    def test_normalize_collapses_whitespace(self):
        detector = DuplicateDetector()
        assert detector._normalize_subject("  Re:  lots   of   space  ") == "lots of space"
