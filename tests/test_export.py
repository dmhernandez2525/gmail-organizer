"""Tests for gmail_organizer.export module."""

import csv
import json
import os
import pytest

from gmail_organizer.export import EmailExporter


@pytest.fixture
def exporter(tmp_path):
    """Create an EmailExporter with a temporary export directory."""
    return EmailExporter(export_dir=str(tmp_path))


@pytest.fixture
def sample_emails():
    """Return a list of sample email dicts for testing."""
    return [
        {
            "sender": "Alice <alice@example.com>",
            "subject": "Hello World",
            "date": "2024-01-15",
            "category": "primary",
            "labels": ["INBOX", "IMPORTANT"],
            "to": "bob@example.com",
            "body": "This is the body of email one.",
            "message_id": "<msg1@example.com>",
            "snippet": "This is the body...",
        },
        {
            "sender": "bob@example.com",
            "subject": "Re: Hello World",
            "date": "2024-02-20",
            "category": "primary",
            "labels": ["INBOX"],
            "to": "alice@example.com",
            "body": "Reply body here.\nFrom someone else.",
            "message_id": "<msg2@example.com>",
            "snippet": "Reply body...",
        },
        {
            "sender": "promo@shop.com",
            "subject": "Sale Alert!",
            "date": "2024-03-10",
            "category": "promotions",
            "labels": ["CATEGORY_PROMOTIONS"],
            "to": "alice@example.com",
            "body": "50% off everything!",
            "snippet": "50% off...",
        },
    ]


# ---------------------------------------------------------------------------
# Path traversal prevention
# ---------------------------------------------------------------------------


class TestResolveFilepath:
    def test_relative_path_stays_in_export_dir(self, exporter, tmp_path):
        resolved = exporter._resolve_filepath("output.csv")
        assert resolved.startswith(str(tmp_path))

    def test_path_traversal_raises_value_error(self, exporter):
        with pytest.raises(ValueError, match="resolves outside export directory"):
            exporter._resolve_filepath("../../../etc/passwd")

    def test_path_traversal_with_dotdot_in_middle(self, exporter):
        with pytest.raises(ValueError, match="resolves outside export directory"):
            exporter._resolve_filepath("subdir/../../../../../../tmp/evil")

    def test_subdirectory_within_export_dir_allowed(self, exporter, tmp_path):
        resolved = exporter._resolve_filepath("subdir/output.csv")
        assert resolved.startswith(str(tmp_path))


# ---------------------------------------------------------------------------
# CSV injection prevention
# ---------------------------------------------------------------------------


class TestSanitizeCsvValue:
    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "|"])
    def test_formula_chars_get_prefixed(self, exporter, prefix):
        value = f"{prefix}cmd('malicious')"
        result = exporter._sanitize_csv_value(value)
        assert result.startswith("'")
        assert result == f"'{value}"

    def test_normal_value_unchanged(self, exporter):
        assert exporter._sanitize_csv_value("hello") == "hello"

    def test_empty_string_unchanged(self, exporter):
        assert exporter._sanitize_csv_value("") == ""

    def test_none_returns_none(self, exporter):
        # _sanitize_csv_value guards on truthiness; None should pass through
        assert exporter._sanitize_csv_value(None) is None


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestExportCsv:
    def test_creates_valid_csv_file(self, exporter, sample_emails, tmp_path):
        path = exporter.export_csv(sample_emails, "test.csv")
        assert os.path.exists(path)

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["subject"] == "Hello World"

    def test_csv_sanitizes_formula_in_subject(self, exporter, tmp_path):
        emails = [{"sender": "x@y.com", "subject": "=cmd()", "date": "", "category": "", "labels": []}]
        path = exporter.export_csv(emails, "injected.csv")

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["subject"].startswith("'")

    def test_csv_custom_fields(self, exporter, sample_emails, tmp_path):
        path = exporter.export_csv(sample_emails, "custom.csv", fields=["sender", "subject"])

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        assert fieldnames == ["sender", "subject"]

    def test_csv_list_field_joined(self, exporter, tmp_path):
        emails = [{"sender": "a@b.com", "subject": "test", "date": "", "category": "", "labels": ["INBOX", "STARRED"]}]
        path = exporter.export_csv(emails, "labels.csv")

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert "INBOX" in row["labels"]
        assert "STARRED" in row["labels"]


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


class TestExportJson:
    def test_creates_valid_json_file(self, exporter, sample_emails, tmp_path):
        path = exporter.export_json(sample_emails, "test.json")
        assert os.path.exists(path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_emails"] == 3
        assert len(data["emails"]) == 3
        assert "exported_at" in data

    def test_json_pretty_format(self, exporter, sample_emails, tmp_path):
        path = exporter.export_json(sample_emails, "pretty.json", pretty=True)

        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Pretty-printed JSON should have indentation
        assert "\n  " in content

    def test_json_compact_format(self, exporter, sample_emails, tmp_path):
        path = exporter.export_json(sample_emails, "compact.json", pretty=False)

        with open(path, encoding="utf-8") as f:
            content = f.read()
        data = json.loads(content)
        assert data["total_emails"] == 3


# ---------------------------------------------------------------------------
# MBOX export
# ---------------------------------------------------------------------------


class TestExportMbox:
    def test_creates_mbox_with_from_lines(self, exporter, sample_emails, tmp_path):
        path = exporter.export_mbox(sample_emails, "test.mbox")
        assert os.path.exists(path)

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # Each email should have a "From " separator line
        from_lines = [line for line in content.splitlines() if line.startswith("From ")]
        assert len(from_lines) == 3

    def test_mbox_escapes_from_in_body(self, exporter, tmp_path):
        emails = [
            {
                "sender": "test@example.com",
                "subject": "Test",
                "date": "2024-01-01",
                "body": "From someone else\nNormal line",
            }
        ]
        path = exporter.export_mbox(emails, "escaped.mbox")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # Body line starting with "From " should be escaped with >
        assert ">From someone else" in content

    def test_mbox_header_sanitization(self, exporter, tmp_path):
        emails = [
            {
                "sender": "evil@example.com\r\nBcc: victim@example.com",
                "subject": "Injected\nHeader: bad",
                "date": "2024-01-01",
                "body": "test",
            }
        ]
        path = exporter.export_mbox(emails, "sanitized.mbox")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        # The "From:" header line should have newlines replaced with spaces,
        # so the injected Bcc never appears as a separate header line.
        from_header_lines = [l for l in content.splitlines() if l.startswith("From:")]
        assert len(from_header_lines) == 1
        # Injected content should be collapsed into the same line
        assert "Bcc:" in from_header_lines[0]  # Present but neutralized on same line

        # Subject header should also be collapsed to one line
        subject_lines = [l for l in content.splitlines() if l.startswith("Subject:")]
        assert len(subject_lines) == 1
        assert "Header: bad" in subject_lines[0]

        # Verify no standalone "Bcc:" line exists anywhere
        # (the _extract_email_address and _sanitize_header both strip newlines)
        bcc_lines = [l for l in content.splitlines() if l.strip().startswith("Bcc:")]
        assert len(bcc_lines) == 0

    def test_mbox_includes_labels_and_category(self, exporter, sample_emails, tmp_path):
        path = exporter.export_mbox(sample_emails, "labels.mbox")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        assert "X-Gmail-Labels:" in content
        assert "X-Category:" in content

    def test_mbox_includes_message_id(self, exporter, sample_emails, tmp_path):
        path = exporter.export_mbox(sample_emails, "msgid.mbox")

        with open(path, encoding="utf-8") as f:
            content = f.read()

        assert "Message-ID: <msg1@example.com>" in content


# ---------------------------------------------------------------------------
# filter_emails
# ---------------------------------------------------------------------------


class TestFilterEmails:
    def test_filter_by_category(self, exporter, sample_emails):
        result = exporter.filter_emails(sample_emails, category="promotions")
        assert len(result) == 1
        assert result[0]["sender"] == "promo@shop.com"

    def test_filter_by_category_case_insensitive(self, exporter, sample_emails):
        result = exporter.filter_emails(sample_emails, category="PRIMARY")
        assert len(result) == 2

    def test_filter_by_sender(self, exporter, sample_emails):
        result = exporter.filter_emails(sample_emails, sender="alice")
        assert len(result) == 1
        assert "alice" in result[0]["sender"].lower()

    def test_filter_by_sender_case_insensitive(self, exporter, sample_emails):
        result = exporter.filter_emails(sample_emails, sender="ALICE")
        assert len(result) == 1

    def test_filter_by_date_from(self, exporter, sample_emails):
        result = exporter.filter_emails(sample_emails, date_from="2024-02-01")
        assert len(result) == 2

    def test_filter_by_date_to(self, exporter, sample_emails):
        result = exporter.filter_emails(sample_emails, date_to="2024-01-31")
        assert len(result) == 1
        assert result[0]["subject"] == "Hello World"

    def test_filter_by_date_range(self, exporter, sample_emails):
        result = exporter.filter_emails(
            sample_emails, date_from="2024-01-01", date_to="2024-02-28"
        )
        assert len(result) == 2

    def test_filter_no_criteria_returns_all(self, exporter, sample_emails):
        result = exporter.filter_emails(sample_emails)
        assert len(result) == 3

    def test_filter_combined_criteria(self, exporter, sample_emails):
        result = exporter.filter_emails(
            sample_emails, category="primary", sender="alice"
        )
        assert len(result) == 1

    def test_filter_empty_list(self, exporter):
        result = exporter.filter_emails([])
        assert result == []


# ---------------------------------------------------------------------------
# export_summary
# ---------------------------------------------------------------------------


class TestExportSummary:
    def test_summary_empty_list(self, exporter):
        summary = exporter.export_summary([])
        assert summary["total_emails"] == 0
        assert summary["categories"] == {}
        assert summary["top_senders"] == []
        assert summary["date_range"]["earliest"] is None
        assert summary["date_range"]["latest"] is None
        assert summary["avg_subject_length"] == 0

    def test_summary_populated_list(self, exporter, sample_emails):
        summary = exporter.export_summary(sample_emails)
        assert summary["total_emails"] == 3
        assert "primary" in summary["categories"]
        assert summary["categories"]["primary"] == 2
        assert len(summary["top_senders"]) <= 10
        assert summary["date_range"]["earliest"] is not None
        assert summary["date_range"]["latest"] is not None
        assert summary["avg_subject_length"] > 0

    def test_summary_labels_counted(self, exporter, sample_emails):
        summary = exporter.export_summary(sample_emails)
        assert "INBOX" in summary["labels"]
        assert summary["labels"]["INBOX"] == 2

    def test_summary_string_labels_handled(self, exporter):
        emails = [{"sender": "x@y.com", "subject": "test", "labels": "SINGLE_LABEL"}]
        summary = exporter.export_summary(emails)
        assert "SINGLE_LABEL" in summary["labels"]


# ---------------------------------------------------------------------------
# get_export_size_estimate
# ---------------------------------------------------------------------------


class TestGetExportSizeEstimate:
    def test_csv_estimate_returns_positive_int(self, exporter, sample_emails):
        estimate = exporter.get_export_size_estimate(sample_emails, "csv")
        assert isinstance(estimate, int)
        assert estimate > 0

    def test_json_estimate_returns_positive_int(self, exporter, sample_emails):
        estimate = exporter.get_export_size_estimate(sample_emails, "json")
        assert isinstance(estimate, int)
        assert estimate > 0

    def test_mbox_estimate_returns_positive_int(self, exporter, sample_emails):
        estimate = exporter.get_export_size_estimate(sample_emails, "mbox")
        assert isinstance(estimate, int)
        assert estimate > 0

    def test_unknown_format_raises_value_error(self, exporter, sample_emails):
        with pytest.raises(ValueError, match="Unsupported format"):
            exporter.get_export_size_estimate(sample_emails, "xml")

    def test_empty_emails_returns_zero(self, exporter):
        assert exporter.get_export_size_estimate([], "csv") == 0
        assert exporter.get_export_size_estimate([], "json") == 0
        assert exporter.get_export_size_estimate([], "mbox") == 0

    def test_case_insensitive_format(self, exporter, sample_emails):
        estimate = exporter.get_export_size_estimate(sample_emails, "CSV")
        assert isinstance(estimate, int)
        assert estimate > 0


# ---------------------------------------------------------------------------
# _extract_email_address
# ---------------------------------------------------------------------------


class TestExtractEmailAddress:
    def test_name_angle_bracket_format(self, exporter):
        result = exporter._extract_email_address("Alice Smith <alice@example.com>")
        assert result == "alice@example.com"

    def test_plain_email_format(self, exporter):
        result = exporter._extract_email_address("alice@example.com")
        assert result == "alice@example.com"

    def test_email_with_whitespace(self, exporter):
        result = exporter._extract_email_address("  alice@example.com  ")
        assert result == "alice@example.com"


# ---------------------------------------------------------------------------
# _sanitize_header
# ---------------------------------------------------------------------------


class TestSanitizeHeader:
    def test_strips_newlines(self, exporter):
        result = exporter._sanitize_header("Subject\r\nBcc: evil@example.com")
        assert "\n" not in result
        assert "\r" not in result

    def test_normal_header_unchanged(self, exporter):
        result = exporter._sanitize_header("Normal Subject Line")
        assert result == "Normal Subject Line"
