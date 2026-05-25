"""Tests for gmail_organizer.storage module."""

import time
import pytest
from datetime import datetime

from gmail_organizer.storage import StorageAnalyzer, StorageReport


@pytest.fixture
def analyzer():
    """Create a StorageAnalyzer instance."""
    return StorageAnalyzer()


def _make_email(
    sender="user@example.com",
    subject="Test Subject",
    size=1024,
    labels=None,
    year=2024,
    has_attachment=False,
):
    """Helper to build a realistic email dict matching the Gmail API structure."""
    # Convert year to epoch milliseconds (Jan 1 of that year)
    dt = datetime(year, 6, 15, 12, 0, 0)
    internal_date = str(int(dt.timestamp() * 1000))

    parts = []
    if has_attachment:
        parts.append({
            "mimeType": "application/pdf",
            "body": {"attachmentId": "ATT_12345", "size": 500},
            "headers": [
                {"name": "Content-Disposition", "value": "attachment; filename=\"doc.pdf\""}
            ],
        })
    else:
        parts.append({
            "mimeType": "text/plain",
            "body": {"size": size},
            "headers": [],
        })

    return {
        "email_id": f"msg_{id(subject)}",
        "sizeEstimate": size,
        "internalDate": internal_date,
        "labelIds": labels or ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": f"Display Name <{sender}>"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": dt.strftime("%Y-%m-%d")},
            ],
            "parts": parts,
        },
    }


@pytest.fixture
def sample_emails():
    """Return a varied list of sample emails."""
    return [
        _make_email(sender="alice@example.com", subject="Project update", size=5000, labels=["INBOX", "CATEGORY_PRIMARY"], year=2024),
        _make_email(sender="alice@example.com", subject="Follow up", size=3000, labels=["INBOX", "CATEGORY_PRIMARY"], year=2024),
        _make_email(sender="bob@other.org", subject="Meeting notes", size=10000, labels=["INBOX", "CATEGORY_UPDATES"], year=2023),
        _make_email(sender="promo@shop.com", subject="Big Sale", size=2000, labels=["CATEGORY_PROMOTIONS"], year=2022),
        _make_email(sender="social@network.com", subject="New follower", size=1500, labels=["CATEGORY_SOCIAL"], year=2020, has_attachment=True),
    ]


# ---------------------------------------------------------------------------
# analyze_storage
# ---------------------------------------------------------------------------


class TestAnalyzeStorage:
    def test_empty_list_returns_empty_report(self, analyzer):
        report = analyzer.analyze_storage([])
        assert isinstance(report, StorageReport)
        assert report.total_size_bytes == 0
        assert report.total_size_mb == 0.0
        assert report.by_sender == []
        assert report.by_domain == []
        assert report.by_label == {}
        assert report.by_year == {}
        assert report.by_category == {}
        assert report.avg_email_size_kb == 0.0
        assert report.largest_emails == []
        assert report.emails_with_attachments == 0

    def test_total_size_calculated_correctly(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        expected_total = 5000 + 3000 + 10000 + 2000 + 1500
        assert report.total_size_bytes == expected_total
        assert report.total_size_mb == pytest.approx(expected_total / (1024 * 1024), rel=1e-3)

    def test_avg_email_size(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        expected_avg = (5000 + 3000 + 10000 + 2000 + 1500) / 5 / 1024
        assert report.avg_email_size_kb == pytest.approx(expected_avg, rel=1e-3)

    def test_by_sender_sorted_descending(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        # alice@example.com has 8000 bytes total, bob@other.org has 10000
        assert len(report.by_sender) > 0
        sizes = [s for _, s in report.by_sender]
        assert sizes == sorted(sizes, reverse=True)

    def test_by_domain_present(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        domains = [d for d, _ in report.by_domain]
        assert "example.com" in domains
        assert "other.org" in domains

    def test_by_label_includes_inbox(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        assert "INBOX" in report.by_label

    def test_by_category_present(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        assert "PRIMARY" in report.by_category
        assert "PROMOTIONS" in report.by_category

    def test_by_year_present(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        assert "2024" in report.by_year
        assert "2023" in report.by_year
        assert "2020" in report.by_year

    def test_emails_with_attachments_counted(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        assert report.emails_with_attachments == 1

    def test_largest_emails_populated(self, analyzer, sample_emails):
        report = analyzer.analyze_storage(sample_emails)
        assert len(report.largest_emails) > 0
        assert report.largest_emails[0]["size_bytes"] >= report.largest_emails[-1]["size_bytes"]


# ---------------------------------------------------------------------------
# get_largest_emails
# ---------------------------------------------------------------------------


class TestGetLargestEmails:
    def test_sorted_by_size_descending(self, analyzer, sample_emails):
        result = analyzer.get_largest_emails(sample_emails)
        sizes = [e["size_bytes"] for e in result]
        assert sizes == sorted(sizes, reverse=True)

    def test_respects_limit(self, analyzer, sample_emails):
        result = analyzer.get_largest_emails(sample_emails, limit=2)
        assert len(result) == 2

    def test_empty_list(self, analyzer):
        result = analyzer.get_largest_emails([])
        assert result == []

    def test_result_contains_expected_fields(self, analyzer, sample_emails):
        result = analyzer.get_largest_emails(sample_emails, limit=1)
        entry = result[0]
        assert "id" in entry
        assert "sender" in entry
        assert "subject" in entry
        assert "date" in entry
        assert "size_bytes" in entry
        assert "size_mb" in entry
        assert "has_attachments" in entry

    def test_largest_email_is_correct(self, analyzer, sample_emails):
        result = analyzer.get_largest_emails(sample_emails, limit=1)
        # bob@other.org has size 10000 which is the largest
        assert result[0]["size_bytes"] == 10000


# ---------------------------------------------------------------------------
# get_cleanup_suggestions
# ---------------------------------------------------------------------------


class TestGetCleanupSuggestions:
    def test_empty_report_returns_empty_message(self, analyzer):
        report = StorageReport()
        suggestions = analyzer.get_cleanup_suggestions(report)
        assert len(suggestions) == 1
        assert "empty" in suggestions[0].lower()

    def test_large_emails_suggestion(self, analyzer):
        report = StorageReport(
            total_size_bytes=100 * 1024 * 1024,
            total_size_mb=100.0,
            largest_emails=[
                {"id": "1", "sender": "big@example.com", "subject": "Huge", "date": "2024-01-01", "size_bytes": 10 * 1024 * 1024, "size_mb": 10.0, "has_attachments": True},
                {"id": "2", "sender": "big@example.com", "subject": "Also huge", "date": "2024-01-02", "size_bytes": 6 * 1024 * 1024, "size_mb": 6.0, "has_attachments": True},
            ],
            avg_email_size_kb=50.0,
        )
        suggestions = analyzer.get_cleanup_suggestions(report)
        large_suggestion = [s for s in suggestions if "larger than" in s]
        assert len(large_suggestion) >= 1

    def test_old_emails_suggestion(self, analyzer):
        current_year = datetime.now().year
        old_year = str(current_year - 4)
        report = StorageReport(
            total_size_bytes=50 * 1024 * 1024,
            total_size_mb=50.0,
            by_year={old_year: 30 * 1024 * 1024, str(current_year): 20 * 1024 * 1024},
            avg_email_size_kb=50.0,
        )
        suggestions = analyzer.get_cleanup_suggestions(report)
        old_suggestion = [s for s in suggestions if "older than" in s]
        assert len(old_suggestion) >= 1

    def test_no_suggestions_when_clean(self, analyzer):
        report = StorageReport(
            total_size_bytes=1000,
            total_size_mb=0.001,
            avg_email_size_kb=1.0,
        )
        suggestions = analyzer.get_cleanup_suggestions(report)
        assert any("reasonable" in s.lower() for s in suggestions)

    def test_trash_spam_suggestion(self, analyzer):
        report = StorageReport(
            total_size_bytes=10 * 1024 * 1024,
            total_size_mb=10.0,
            by_label={"TRASH": 5 * 1024 * 1024, "SPAM": 3 * 1024 * 1024},
            avg_email_size_kb=50.0,
        )
        suggestions = analyzer.get_cleanup_suggestions(report)
        trash_suggestion = [s for s in suggestions if "trash" in s.lower() or "spam" in s.lower()]
        assert len(trash_suggestion) >= 1

    def test_promotional_social_suggestion(self, analyzer):
        report = StorageReport(
            total_size_bytes=50 * 1024 * 1024,
            total_size_mb=50.0,
            by_category={"PROMOTIONS": 8 * 1024 * 1024, "SOCIAL": 5 * 1024 * 1024},
            avg_email_size_kb=50.0,
        )
        suggestions = analyzer.get_cleanup_suggestions(report)
        promo_suggestion = [s for s in suggestions if "promotional" in s.lower() or "social" in s.lower()]
        assert len(promo_suggestion) >= 1


# ---------------------------------------------------------------------------
# Attachment detection
# ---------------------------------------------------------------------------


class TestHasAttachments:
    def test_detects_attachment_by_attachment_id(self, analyzer):
        email = {
            "payload": {
                "parts": [
                    {
                        "body": {"attachmentId": "ATT_123"},
                        "headers": [],
                    }
                ]
            }
        }
        assert analyzer._has_attachments(email) is True

    def test_detects_attachment_by_content_disposition(self, analyzer):
        email = {
            "payload": {
                "parts": [
                    {
                        "body": {},
                        "headers": [
                            {"name": "Content-Disposition", "value": "attachment; filename=\"file.pdf\""}
                        ],
                    }
                ]
            }
        }
        assert analyzer._has_attachments(email) is True

    def test_no_attachment(self, analyzer):
        email = {
            "payload": {
                "parts": [
                    {
                        "body": {"size": 100},
                        "headers": [],
                    }
                ]
            }
        }
        assert analyzer._has_attachments(email) is False

    def test_nested_attachment(self, analyzer):
        email = {
            "payload": {
                "parts": [
                    {
                        "body": {},
                        "headers": [],
                        "parts": [
                            {
                                "body": {"attachmentId": "ATT_NESTED"},
                                "headers": [],
                            }
                        ],
                    }
                ]
            }
        }
        assert analyzer._has_attachments(email) is True

    def test_no_payload(self, analyzer):
        email = {}
        assert analyzer._has_attachments(email) is False


# ---------------------------------------------------------------------------
# Year extraction
# ---------------------------------------------------------------------------


class TestExtractYear:
    def test_valid_internal_date(self, analyzer):
        dt = datetime(2023, 7, 15, 10, 30, 0)
        epoch_ms = str(int(dt.timestamp() * 1000))
        email = {"internalDate": epoch_ms}
        assert analyzer._extract_year(email) == "2023"

    def test_missing_internal_date(self, analyzer):
        email = {}
        assert analyzer._extract_year(email) == ""

    def test_invalid_internal_date(self, analyzer):
        email = {"internalDate": "not-a-number"}
        assert analyzer._extract_year(email) == ""


# ---------------------------------------------------------------------------
# Category extraction
# ---------------------------------------------------------------------------


class TestExtractCategory:
    def test_primary_category(self, analyzer):
        assert analyzer._extract_category(["INBOX", "CATEGORY_PRIMARY"]) == "PRIMARY"

    def test_promotions_category(self, analyzer):
        assert analyzer._extract_category(["CATEGORY_PROMOTIONS"]) == "PROMOTIONS"

    def test_social_category(self, analyzer):
        assert analyzer._extract_category(["CATEGORY_SOCIAL"]) == "SOCIAL"

    def test_no_category_label(self, analyzer):
        assert analyzer._extract_category(["INBOX", "STARRED"]) == "UNCATEGORIZED"

    def test_empty_labels(self, analyzer):
        assert analyzer._extract_category([]) == "UNCATEGORIZED"


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_extract_sender(self, analyzer):
        email = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                ]
            }
        }
        assert analyzer._extract_sender(email) == "alice@example.com"

    def test_extract_sender_no_headers(self, analyzer):
        email = {"payload": {"headers": []}}
        assert analyzer._extract_sender(email) == ""

    def test_extract_domain(self, analyzer):
        assert analyzer._extract_domain("user@example.com") == "example.com"

    def test_extract_domain_no_at(self, analyzer):
        assert analyzer._extract_domain("noemail") == ""

    def test_extract_subject(self, analyzer):
        email = {
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hello World"},
                ]
            }
        }
        assert analyzer._extract_subject(email) == "Hello World"

    def test_extract_subject_missing(self, analyzer):
        email = {"payload": {"headers": []}}
        assert analyzer._extract_subject(email) == "(no subject)"

    def test_extract_date_str(self, analyzer):
        dt = datetime(2024, 3, 15, 10, 0, 0)
        epoch_ms = str(int(dt.timestamp() * 1000))
        email = {"internalDate": epoch_ms}
        assert analyzer._extract_date_str(email) == "2024-03-15"

    def test_extract_date_str_fallback_to_header(self, analyzer):
        email = {
            "payload": {
                "headers": [
                    {"name": "Date", "value": "Mon, 15 Jan 2024 10:00:00 +0000"},
                ]
            }
        }
        assert analyzer._extract_date_str(email) == "Mon, 15 Jan 2024 10:00:00 +0000"

    def test_parse_year_int(self, analyzer):
        assert analyzer._parse_year_int("2024") == 2024
        assert analyzer._parse_year_int("invalid") == 0
        assert analyzer._parse_year_int(None) == 0
