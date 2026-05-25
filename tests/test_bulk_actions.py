"""Tests for gmail_organizer.bulk_actions module."""

import pytest
from unittest.mock import MagicMock, call
from googleapiclient.errors import HttpError

from gmail_organizer.bulk_actions import BulkActionEngine, filter_emails


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_service():
    """Gmail API service mock with batchModify, labels.list, labels.create."""
    service = MagicMock()
    # batchModify chain
    service.users.return_value.messages.return_value.batchModify.return_value.execute.return_value = None
    # labels().list() chain
    service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        "labels": [
            {"id": "Label_1", "name": "Work"},
            {"id": "Label_2", "name": "Personal"},
        ]
    }
    # labels().create() chain
    service.users.return_value.labels.return_value.create.return_value.execute.return_value = {
        "id": "Label_NEW",
        "name": "NewLabel",
    }
    return service


@pytest.fixture
def engine(mock_service):
    return BulkActionEngine(service=mock_service)


@pytest.fixture
def engine_no_service():
    return BulkActionEngine(service=None)


@pytest.fixture
def sample_emails():
    """A small list of email dicts used by filter_emails tests."""
    return [
        {
            "email_id": "1",
            "sender": "alice@example.com",
            "subject": "Project Update",
            "category": "Work",
            "labels": ["INBOX", "UNREAD"],
            "date": "2026-03-20T10:00:00Z",
            "has_attachment": True,
        },
        {
            "email_id": "2",
            "sender": "bob@shop.com",
            "subject": "Your receipt",
            "category": "Shopping",
            "labels": ["INBOX"],
            "date": "2026-03-22T08:00:00Z",
            "has_attachment": False,
        },
        {
            "email_id": "3",
            "sender": "alice@example.com",
            "subject": "Meeting notes",
            "category": "Work",
            "labels": ["INBOX", "UNREAD", "IMPORTANT"],
            "date": "2026-03-25T14:30:00Z",
            "has_attachment": False,
        },
        {
            "email_id": "4",
            "sender": "noreply@social.com",
            "subject": "You have a new follower",
            "category": "Social",
            "labels": ["INBOX"],
            "date": "2026-03-18T06:00:00Z",
            "has_attachment": False,
        },
    ]


# ---------------------------------------------------------------------------
# BulkActionEngine -- no service
# ---------------------------------------------------------------------------

class TestBulkActionEngineNoService:
    """When engine has no Gmail service, operations should fail gracefully."""

    def test_apply_label_no_service(self, engine_no_service):
        result = engine_no_service.apply_label(["m1", "m2"], "Label_1")
        assert result["success"] == 0
        assert result["failed"] == 2
        assert "error" in result

    def test_archive_no_service(self, engine_no_service):
        result = engine_no_service.archive(["m1"])
        assert result["failed"] == 1

    def test_get_or_create_label_no_service(self, engine_no_service):
        assert engine_no_service.get_or_create_label("Test") is None

    def test_list_labels_no_service(self, engine_no_service):
        assert engine_no_service.list_labels() == []


# ---------------------------------------------------------------------------
# BulkActionEngine -- with service
# ---------------------------------------------------------------------------

class TestBulkActionEngineWithService:

    def test_apply_label(self, engine, mock_service):
        ids = ["m1", "m2", "m3"]
        result = engine.apply_label(ids, "Label_1")
        assert result["success"] == 3
        assert result["failed"] == 0
        mock_service.users.return_value.messages.return_value.batchModify.assert_called_once()
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["addLabelIds"] == ["Label_1"]

    def test_remove_label(self, engine, mock_service):
        result = engine.remove_label(["m1"], "Label_2")
        assert result["success"] == 1
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["removeLabelIds"] == ["Label_2"]

    def test_archive_removes_inbox(self, engine, mock_service):
        result = engine.archive(["m1", "m2"])
        assert result["success"] == 2
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["removeLabelIds"] == ["INBOX"]

    def test_unarchive_adds_inbox(self, engine, mock_service):
        result = engine.unarchive(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["addLabelIds"] == ["INBOX"]

    def test_mark_read(self, engine, mock_service):
        result = engine.mark_read(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["removeLabelIds"] == ["UNREAD"]

    def test_mark_unread(self, engine, mock_service):
        result = engine.mark_unread(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["addLabelIds"] == ["UNREAD"]

    def test_star(self, engine, mock_service):
        engine.star(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["addLabelIds"] == ["STARRED"]

    def test_unstar(self, engine, mock_service):
        engine.unstar(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["removeLabelIds"] == ["STARRED"]

    def test_mark_important(self, engine, mock_service):
        engine.mark_important(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["addLabelIds"] == ["IMPORTANT"]

    def test_mark_not_important(self, engine, mock_service):
        engine.mark_not_important(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["removeLabelIds"] == ["IMPORTANT"]

    def test_move_to_trash(self, engine, mock_service):
        engine.move_to_trash(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["addLabelIds"] == ["TRASH"]
        assert body[1]["body"]["removeLabelIds"] == ["INBOX"]

    def test_mark_spam(self, engine, mock_service):
        engine.mark_spam(["m1"])
        body = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert body[1]["body"]["addLabelIds"] == ["SPAM"]
        assert body[1]["body"]["removeLabelIds"] == ["INBOX"]

    def test_progress_callback_called(self, engine):
        ids = ["m1", "m2"]
        cb = MagicMock()
        engine.apply_label(ids, "Label_1", progress_callback=cb)
        cb.assert_called()

    def test_http_error_recorded(self, engine, mock_service):
        """If Gmail returns an HttpError, the batch should be counted as failed."""
        resp = MagicMock(status=400, reason="Bad Request")
        mock_service.users.return_value.messages.return_value.batchModify.return_value.execute.side_effect = (
            HttpError(resp, b"error")
        )
        result = engine.apply_label(["m1", "m2"], "Label_1")
        assert result["failed"] == 2
        assert result["success"] == 0
        assert len(result["errors"]) == 1

    def test_batching_over_1000(self, engine, mock_service):
        """Messages exceeding 1000 should be split into multiple API calls."""
        ids = [f"m{i}" for i in range(1500)]
        result = engine.apply_label(ids, "Label_1")
        assert result["success"] == 1500
        assert mock_service.users.return_value.messages.return_value.batchModify.call_count == 2

    def test_batching_progress_callback_multiple_batches(self, engine, mock_service):
        """Progress callback should be invoked once per batch."""
        ids = [f"m{i}" for i in range(2500)]
        cb = MagicMock()
        engine.apply_label(ids, "Label_1", progress_callback=cb)
        assert cb.call_count == 3  # ceil(2500/1000) = 3 batches

    def test_partial_failure(self, engine, mock_service):
        """First batch succeeds, second batch fails."""
        execute_mock = mock_service.users.return_value.messages.return_value.batchModify.return_value.execute
        resp = MagicMock(status=429, reason="Rate Limit")
        execute_mock.side_effect = [None, HttpError(resp, b"rate limit")]
        ids = [f"m{i}" for i in range(1500)]
        result = engine.apply_label(ids, "Label_1")
        assert result["success"] == 1000
        assert result["failed"] == 500


# ---------------------------------------------------------------------------
# BulkActionEngine -- label management
# ---------------------------------------------------------------------------

class TestLabelManagement:

    def test_get_existing_label(self, engine):
        label_id = engine.get_or_create_label("Work")
        assert label_id == "Label_1"

    def test_get_existing_label_case_insensitive(self, engine):
        label_id = engine.get_or_create_label("personal")
        assert label_id == "Label_2"

    def test_create_new_label(self, engine, mock_service):
        label_id = engine.get_or_create_label("NewLabel")
        assert label_id == "Label_NEW"
        mock_service.users.return_value.labels.return_value.create.assert_called_once()

    def test_get_or_create_label_http_error(self, engine, mock_service):
        resp = MagicMock(status=500, reason="Server Error")
        mock_service.users.return_value.labels.return_value.list.return_value.execute.side_effect = (
            HttpError(resp, b"err")
        )
        assert engine.get_or_create_label("Anything") is None

    def test_list_labels(self, engine):
        labels = engine.list_labels()
        assert len(labels) == 2
        assert labels[0]["name"] == "Work"

    def test_list_labels_http_error(self, engine, mock_service):
        resp = MagicMock(status=500, reason="Server Error")
        mock_service.users.return_value.labels.return_value.list.return_value.execute.side_effect = (
            HttpError(resp, b"err")
        )
        assert engine.list_labels() == []


# ---------------------------------------------------------------------------
# filter_emails standalone function
# ---------------------------------------------------------------------------

class TestFilterEmails:

    def test_no_filters_returns_all(self, sample_emails):
        assert len(filter_emails(sample_emails)) == 4

    def test_sender_filter(self, sample_emails):
        result = filter_emails(sample_emails, sender_filter="alice")
        assert len(result) == 2
        assert all("alice" in e["sender"] for e in result)

    def test_sender_filter_case_insensitive(self, sample_emails):
        result = filter_emails(sample_emails, sender_filter="ALICE")
        assert len(result) == 2

    def test_category_filter(self, sample_emails):
        result = filter_emails(sample_emails, category_filter="Work")
        assert len(result) == 2

    def test_category_filter_no_match(self, sample_emails):
        result = filter_emails(sample_emails, category_filter="Finance")
        assert len(result) == 0

    def test_label_filter(self, sample_emails):
        result = filter_emails(sample_emails, label_filter="IMPORTANT")
        assert len(result) == 1
        assert result[0]["email_id"] == "3"

    def test_subject_filter(self, sample_emails):
        result = filter_emails(sample_emails, subject_filter="receipt")
        assert len(result) == 1
        assert result[0]["email_id"] == "2"

    def test_subject_filter_case_insensitive(self, sample_emails):
        result = filter_emails(sample_emails, subject_filter="PROJECT")
        assert len(result) == 1

    def test_date_from(self, sample_emails):
        result = filter_emails(sample_emails, date_from="2026-03-21")
        assert len(result) == 2  # emails 2 and 3

    def test_date_to(self, sample_emails):
        result = filter_emails(sample_emails, date_to="2026-03-20")
        assert len(result) == 2  # emails 1 and 4

    def test_date_range(self, sample_emails):
        result = filter_emails(sample_emails, date_from="2026-03-20", date_to="2026-03-22")
        assert len(result) == 2  # emails 1 and 2

    def test_has_attachment_true(self, sample_emails):
        result = filter_emails(sample_emails, has_attachment=True)
        assert len(result) == 1
        assert result[0]["email_id"] == "1"

    def test_has_attachment_false(self, sample_emails):
        result = filter_emails(sample_emails, has_attachment=False)
        assert len(result) == 3

    def test_is_unread_true(self, sample_emails):
        result = filter_emails(sample_emails, is_unread=True)
        assert len(result) == 2  # emails 1 and 3

    def test_is_unread_false(self, sample_emails):
        result = filter_emails(sample_emails, is_unread=False)
        assert len(result) == 2  # emails 2 and 4

    def test_combined_filters(self, sample_emails):
        result = filter_emails(
            sample_emails,
            sender_filter="alice",
            is_unread=True,
            has_attachment=False,
        )
        assert len(result) == 1
        assert result[0]["email_id"] == "3"

    def test_empty_list(self):
        assert filter_emails([]) == []

    def test_missing_fields_graceful(self):
        """Emails missing optional fields should not crash filters."""
        emails = [{"email_id": "x"}]
        result = filter_emails(emails, sender_filter="test")
        assert result == []
        result2 = filter_emails(emails, is_unread=True)
        assert result2 == []
        result3 = filter_emails(emails, has_attachment=True)
        assert result3 == []
