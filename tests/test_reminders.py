"""Tests for gmail_organizer/reminders.py - FollowUpDetector."""

from datetime import datetime, timedelta, timezone

import pytest

from gmail_organizer.reminders import FollowUpDetector, FollowUpItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_email(
    *,
    email_id="msg1",
    thread_id="thread1",
    sender="someone@example.com",
    to="me@example.com",
    subject="Hello",
    body="",
    days_ago=0,
    labels=None,
):
    """Build a minimal email dict with a date N days in the past."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": email_id,
        "threadId": thread_id,
        "sender": sender,
        "from": sender,
        "to": to,
        "subject": subject,
        "body": body,
        "snippet": body,
        "date": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "labelIds": labels or ["INBOX"],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detector():
    return FollowUpDetector()


# ---------------------------------------------------------------------------
# detect_follow_ups: question detection
# ---------------------------------------------------------------------------

class TestQuestionDetection:
    """Emails with questions should be flagged."""

    def test_question_mark_in_subject(self, detector):
        email = _make_email(subject="Can we meet tomorrow?", days_ago=1)
        results = detector.detect_follow_ups([email])
        assert len(results) == 1
        assert results[0].reason == "question"

    def test_question_pattern_in_body(self, detector):
        email = _make_email(body="Could you send me the report?", days_ago=2)
        results = detector.detect_follow_ups([email])
        assert len(results) == 1
        assert results[0].reason in ("question", "action_item")

    def test_no_question_no_flag(self, detector):
        email = _make_email(subject="FYI: system maintenance", body="Just a heads up.", days_ago=1)
        results = detector.detect_follow_ups([email])
        assert len(results) == 0


# ---------------------------------------------------------------------------
# detect_follow_ups: action item detection
# ---------------------------------------------------------------------------

class TestActionItemDetection:
    """Emails with action items should be flagged."""

    def test_action_item_with_please_and_deadline(self, detector):
        email = _make_email(
            body="Please submit the form by Friday. The deadline is strict.",
            days_ago=2,
        )
        results = detector.detect_follow_ups([email])
        assert len(results) == 1
        assert results[0].reason == "action_item"

    def test_action_item_urgent_asap(self, detector):
        email = _make_email(
            body="Please handle this ASAP. It is urgent.",
            days_ago=1,
        )
        results = detector.detect_follow_ups([email])
        assert len(results) == 1
        assert results[0].reason == "action_item"

    def test_single_pattern_not_enough(self, detector):
        """Action items require at least 2 pattern matches to reduce false positives."""
        email = _make_email(body="Please let me know.", days_ago=1)
        results = detector.detect_follow_ups([email])
        # "please" alone is only 1 match; needs 2
        # May or may not flag depending on question patterns in body
        for item in results:
            if item.reason == "action_item":
                pytest.fail("Single 'please' should not trigger action_item alone")


# ---------------------------------------------------------------------------
# detect_follow_ups: awaiting reply detection
# ---------------------------------------------------------------------------

class TestAwaitingReplyDetection:
    """Emails sent by user without a reply should be flagged."""

    def test_sent_email_no_reply(self, detector):
        user = "me@example.com"
        sent = _make_email(
            sender=user,
            to="them@example.com",
            subject="Following up",
            days_ago=5,
            thread_id="t1",
        )
        results = detector.detect_follow_ups([sent], user_email=user)
        assert len(results) == 1
        assert results[0].reason == "awaiting_reply"

    def test_sent_email_with_reply_not_flagged(self, detector):
        user = "me@example.com"
        sent = _make_email(
            email_id="s1",
            sender=user,
            to="them@example.com",
            subject="Question",
            days_ago=5,
            thread_id="t1",
        )
        reply = _make_email(
            email_id="r1",
            sender="them@example.com",
            to=user,
            subject="Re: Question",
            days_ago=3,
            thread_id="t1",
        )
        results = detector.detect_follow_ups([sent, reply], user_email=user)
        # The sent message should not be flagged because a reply exists
        awaiting = [r for r in results if r.reason == "awaiting_reply"]
        assert len(awaiting) == 0

    def test_no_user_email_skips_awaiting_reply(self, detector):
        sent = _make_email(sender="me@example.com", days_ago=5)
        results = detector.detect_follow_ups([sent], user_email="")
        awaiting = [r for r in results if r.reason == "awaiting_reply"]
        assert len(awaiting) == 0


# ---------------------------------------------------------------------------
# Urgency determination
# ---------------------------------------------------------------------------

class TestUrgencyDetermination:
    """Tests for urgency classification based on age and keywords."""

    def test_overdue_after_seven_days(self, detector):
        email = _make_email(subject="Can you help?", body="Question here?", days_ago=10)
        results = detector.detect_follow_ups([email])
        assert len(results) >= 1
        assert results[0].urgency == "overdue"

    def test_soon_three_to_seven_days(self, detector):
        email = _make_email(subject="Are you available?", days_ago=4)
        results = detector.detect_follow_ups([email])
        assert len(results) >= 1
        assert results[0].urgency == "soon"

    def test_later_under_three_days(self, detector):
        email = _make_email(subject="Quick question?", days_ago=1)
        results = detector.detect_follow_ups([email])
        assert len(results) >= 1
        assert results[0].urgency == "later"

    def test_urgent_keyword_bumps_soon_to_overdue(self, detector):
        email = _make_email(
            body="Please respond urgently. Action required.",
            days_ago=4,  # normally "soon"
        )
        results = detector.detect_follow_ups([email])
        assert len(results) >= 1
        assert results[0].urgency == "overdue"

    def test_urgent_keyword_bumps_later_to_soon(self, detector):
        email = _make_email(
            body="Please handle this ASAP. Need your help.",
            days_ago=1,  # normally "later"
        )
        results = detector.detect_follow_ups([email])
        assert len(results) >= 1
        assert results[0].urgency == "soon"


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestSorting:
    """Follow-ups should be sorted by urgency, then days_waiting descending."""

    def test_overdue_comes_before_soon(self, detector):
        overdue_email = _make_email(
            email_id="old", subject="Where is the report?", days_ago=10, thread_id="t1"
        )
        soon_email = _make_email(
            email_id="recent", subject="Can we chat?", days_ago=4, thread_id="t2"
        )
        results = detector.detect_follow_ups([soon_email, overdue_email])
        assert len(results) >= 2
        assert results[0].urgency == "overdue"

    def test_same_urgency_sorted_by_days_desc(self, detector):
        email_a = _make_email(
            email_id="a", subject="Question 1?", days_ago=1, thread_id="t1"
        )
        email_b = _make_email(
            email_id="b", subject="Question 2?", days_ago=2, thread_id="t2"
        )
        results = detector.detect_follow_ups([email_a, email_b])
        later_items = [r for r in results if r.urgency == "later"]
        if len(later_items) >= 2:
            assert later_items[0].days_waiting >= later_items[1].days_waiting


# ---------------------------------------------------------------------------
# get_follow_up_stats
# ---------------------------------------------------------------------------

class TestGetFollowUpStats:
    """Tests for summary statistics."""

    def test_empty_items(self, detector):
        stats = detector.get_follow_up_stats([])
        assert stats["total"] == 0
        assert stats["average_days_waiting"] == 0.0
        assert stats["oldest_days"] == 0

    def test_counts_by_urgency(self, detector):
        items = [
            FollowUpItem(email={}, reason="question", urgency="overdue", days_waiting=10, suggested_action="Reply."),
            FollowUpItem(email={}, reason="action_item", urgency="soon", days_waiting=5, suggested_action="Act."),
            FollowUpItem(email={}, reason="question", urgency="later", days_waiting=1, suggested_action="Reply."),
        ]
        stats = detector.get_follow_up_stats(items)
        assert stats["total"] == 3
        assert stats["by_urgency"]["overdue"] == 1
        assert stats["by_urgency"]["soon"] == 1
        assert stats["by_urgency"]["later"] == 1

    def test_counts_by_reason(self, detector):
        items = [
            FollowUpItem(email={}, reason="question", urgency="later", days_waiting=1, suggested_action="Reply."),
            FollowUpItem(email={}, reason="question", urgency="later", days_waiting=2, suggested_action="Reply."),
            FollowUpItem(email={}, reason="awaiting_reply", urgency="soon", days_waiting=5, suggested_action="Follow up."),
        ]
        stats = detector.get_follow_up_stats(items)
        assert stats["by_reason"]["question"] == 2
        assert stats["by_reason"]["awaiting_reply"] == 1
        assert stats["by_reason"]["action_item"] == 0

    def test_average_days_waiting(self, detector):
        items = [
            FollowUpItem(email={}, reason="question", urgency="later", days_waiting=2, suggested_action="Reply."),
            FollowUpItem(email={}, reason="question", urgency="later", days_waiting=8, suggested_action="Reply."),
        ]
        stats = detector.get_follow_up_stats(items)
        assert stats["average_days_waiting"] == 5.0

    def test_oldest_days(self, detector):
        items = [
            FollowUpItem(email={}, reason="question", urgency="later", days_waiting=3, suggested_action="Reply."),
            FollowUpItem(email={}, reason="question", urgency="overdue", days_waiting=15, suggested_action="Reply."),
        ]
        stats = detector.get_follow_up_stats(items)
        assert stats["oldest_days"] == 15


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

class TestDateParsing:
    """Tests for internal date parsing in FollowUpDetector."""

    def test_iso_format(self, detector):
        email = _make_email(days_ago=0)
        dt = detector._parse_date(email)
        assert dt.tzinfo is not None

    def test_unix_timestamp_millis(self, detector):
        ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        email = {"date": ts}
        dt = detector._parse_date(email)
        assert dt.year == datetime.now(timezone.utc).year

    def test_unix_timestamp_string(self, detector):
        ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        email = {"date": ts}
        dt = detector._parse_date(email)
        assert dt.tzinfo is not None

    def test_rfc2822_format(self, detector):
        email = {"date": "Mon, 20 Mar 2026 10:00:00 +0000"}
        dt = detector._parse_date(email)
        assert dt.year == 2026

    def test_missing_date_returns_now(self, detector):
        dt = detector._parse_date({})
        now = datetime.now(timezone.utc)
        # Should be very close to now
        assert abs((now - dt).total_seconds()) < 5

    def test_internal_date_fallback(self, detector):
        ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        email = {"internalDate": ts}
        dt = detector._parse_date(email)
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# Sender extraction
# ---------------------------------------------------------------------------

class TestSenderExtraction:
    """Tests for _get_sender and _is_from_user."""

    def test_plain_email(self, detector):
        email = {"from": "user@example.com"}
        assert detector._get_sender(email) == "user@example.com"

    def test_name_angle_bracket_format(self, detector):
        email = {"from": "John Doe <john@example.com>"}
        assert detector._get_sender(email) == "john@example.com"

    def test_sender_field_preferred(self, detector):
        email = {"sender": "primary@example.com", "from": "fallback@example.com"}
        assert detector._get_sender(email) == "primary@example.com"

    def test_is_from_user_true(self, detector):
        assert detector._is_from_user("me@test.com", "me@test.com") is True

    def test_is_from_user_case_insensitive(self, detector):
        assert detector._is_from_user("Me@Test.com", "me@test.com") is True

    def test_is_from_user_false(self, detector):
        assert detector._is_from_user("other@test.com", "me@test.com") is False

    def test_is_from_user_empty(self, detector):
        assert detector._is_from_user("", "me@test.com") is False
        assert detector._is_from_user("me@test.com", "") is False


# ---------------------------------------------------------------------------
# Suggested action text
# ---------------------------------------------------------------------------

class TestSuggestedAction:
    """Tests for _suggest_action_item_response variations."""

    def test_deadline_suggestion(self, detector):
        result = detector._suggest_action_item_response("Submit by Monday please")
        assert "deadline" in result.lower()

    def test_urgent_suggestion(self, detector):
        result = detector._suggest_action_item_response("This is urgent")
        assert "urgently" in result.lower()

    def test_review_suggestion(self, detector):
        result = detector._suggest_action_item_response("Please review the PR")
        assert "review" in result.lower()

    def test_approval_suggestion(self, detector):
        result = detector._suggest_action_item_response("Need your approval on this")
        assert "approval" in result.lower()

    def test_update_suggestion(self, detector):
        result = detector._suggest_action_item_response("Please provide an update")
        assert "update" in result.lower()

    def test_generic_suggestion(self, detector):
        result = detector._suggest_action_item_response("Something else entirely")
        assert "action item" in result.lower()
