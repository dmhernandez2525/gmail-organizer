"""Tests for GmailOrganizer in gmail_organizer/main.py."""

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_organizer():
    """Create a GmailOrganizer with mocked dependencies (auth, classifier)."""
    with patch("gmail_organizer.main.GmailAuthManager") as MockAuth, \
         patch("gmail_organizer.main.EmailClassifier") as MockClassifier:
        from gmail_organizer.main import GmailOrganizer

        organizer = GmailOrganizer()
        organizer._mock_auth_cls = MockAuth
        organizer._mock_classifier_cls = MockClassifier
    return organizer


def _sample_emails(count=3):
    """Return a list of sample email dicts."""
    return [
        {
            "email_id": f"msg_{i}",
            "subject": f"Test Subject {i}",
            "sender": f"sender{i}@example.com",
            "body_preview": f"Body preview {i}",
            "snippet": f"Snippet {i}",
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# authenticate_accounts
# ---------------------------------------------------------------------------

class TestAuthenticateAccounts:
    def test_loads_specific_accounts(self):
        organizer = _make_organizer()
        organizer.auth_manager.authenticate_account.return_value = (
            MagicMock(),  # service
            "alice@gmail.com",  # email
            "personal",  # name
        )

        organizer.authenticate_accounts(["personal"])

        organizer.auth_manager.authenticate_account.assert_called_once_with("personal")
        assert "personal" in organizer.accounts
        assert organizer.accounts["personal"]["email"] == "alice@gmail.com"

    def test_loads_all_accounts_when_names_none(self):
        organizer = _make_organizer()
        organizer.auth_manager.load_all_accounts.return_value = {
            "personal": (MagicMock(), "alice@gmail.com"),
            "work": (MagicMock(), "bob@company.com"),
        }

        organizer.authenticate_accounts(None)

        organizer.auth_manager.load_all_accounts.assert_called_once()
        assert "personal" in organizer.accounts
        assert "work" in organizer.accounts
        assert organizer.accounts["work"]["email"] == "bob@company.com"

    def test_handles_auth_failure_gracefully(self):
        organizer = _make_organizer()
        organizer.auth_manager.authenticate_account.side_effect = Exception("Token expired")

        organizer.authenticate_accounts(["broken_account"])

        # Should not crash; account should not be added
        assert "broken_account" not in organizer.accounts


# ---------------------------------------------------------------------------
# process_account
# ---------------------------------------------------------------------------

class TestProcessAccount:
    def _setup_organizer_with_account(self):
        """Return an organizer with one pre-loaded account and mocked ops."""
        organizer = _make_organizer()
        mock_service = MagicMock()
        organizer.accounts["personal"] = {
            "service": mock_service,
            "email": "alice@gmail.com",
        }
        return organizer, mock_service

    @patch("gmail_organizer.main.GmailOperations")
    def test_full_pipeline(self, MockOps):
        organizer, mock_service = self._setup_organizer_with_account()

        # Mock operations
        mock_ops = MockOps.return_value
        mock_ops.create_all_labels.return_value = {
            "subscriptions": "Label_1",
            "finance": "Label_2",
        }
        mock_ops.get_email_count.return_value = 3
        mock_ops.fetch_emails.return_value = _sample_emails(3)
        mock_ops.apply_label_to_email.return_value = True

        # Mock classifier to assign categories
        organizer.classifier.classify_batch.return_value = [
            {**e, "category": "subscriptions", "confidence": 0.9}
            for e in _sample_emails(3)
        ]
        organizer.classifier.get_category_info.return_value = {
            "name": "Subscriptions",
            "description": "Newsletters",
            "color": "#cca6ac",
        }

        organizer.process_account("personal", max_emails=10, query="in:inbox")

        # Verify pipeline was called
        MockOps.assert_called_once_with(mock_service, "alice@gmail.com")
        mock_ops.create_all_labels.assert_called_once()
        mock_ops.fetch_emails.assert_called_once()
        mock_ops.apply_label_to_email.assert_called()
        assert mock_ops.apply_label_to_email.call_count == 3

        # Results should be stored
        assert "personal" in organizer.results
        assert organizer.results["personal"]["total_processed"] == 3
        assert organizer.results["personal"]["total_labeled"] == 3

    def test_handles_missing_account(self):
        organizer = _make_organizer()
        # Should print a message and return without error
        organizer.process_account("nonexistent")
        assert "nonexistent" not in organizer.results

    @patch("gmail_organizer.main.GmailOperations")
    def test_aborts_when_labels_fail(self, MockOps):
        organizer, _ = self._setup_organizer_with_account()
        mock_ops = MockOps.return_value
        mock_ops.create_all_labels.return_value = {}

        organizer.process_account("personal")

        # Should not attempt to fetch emails if labels fail
        mock_ops.fetch_emails.assert_not_called()

    @patch("gmail_organizer.main.GmailOperations")
    def test_handles_no_emails(self, MockOps):
        organizer, _ = self._setup_organizer_with_account()
        mock_ops = MockOps.return_value
        mock_ops.create_all_labels.return_value = {"subscriptions": "Label_1"}
        mock_ops.get_email_count.return_value = 0
        mock_ops.fetch_emails.return_value = []

        organizer.process_account("personal")

        # Should not attempt classification
        organizer.classifier.classify_batch.assert_not_called()


# ---------------------------------------------------------------------------
# _print_account_summary
# ---------------------------------------------------------------------------

class TestPrintAccountSummary:
    def test_formats_output(self, capsys):
        organizer = _make_organizer()
        organizer.results["personal"] = {
            "email": "alice@gmail.com",
            "total_processed": 50,
            "total_labeled": 48,
            "category_counts": {"subscriptions": 30, "finance": 18},
        }
        organizer.classifier.get_category_info.side_effect = lambda key: {
            "subscriptions": {"name": "Subscriptions", "description": "", "color": ""},
            "finance": {"name": "Finance", "description": "", "color": ""},
        }.get(key, {"name": "Unknown", "description": "", "color": ""})

        organizer._print_account_summary("personal")

        captured = capsys.readouterr().out
        assert "alice@gmail.com" in captured
        assert "50" in captured
        assert "48" in captured
        assert "Subscriptions" in captured
        assert "Finance" in captured

    def test_no_result_does_nothing(self, capsys):
        organizer = _make_organizer()
        organizer._print_account_summary("nonexistent")
        captured = capsys.readouterr().out
        # Should produce no summary output (the method returns early)
        assert "SUMMARY" not in captured


# ---------------------------------------------------------------------------
# print_final_summary
# ---------------------------------------------------------------------------

class TestPrintFinalSummary:
    def test_combines_all_results(self, capsys):
        organizer = _make_organizer()
        organizer.results["personal"] = {
            "email": "alice@gmail.com",
            "total_processed": 40,
            "total_labeled": 38,
            "category_counts": {"subscriptions": 20, "finance": 18},
        }
        organizer.results["work"] = {
            "email": "bob@company.com",
            "total_processed": 60,
            "total_labeled": 55,
            "category_counts": {"subscriptions": 10, "updates": 45},
        }
        organizer.classifier.get_category_info.side_effect = lambda key: {
            "subscriptions": {"name": "Subscriptions", "description": "", "color": ""},
            "finance": {"name": "Finance", "description": "", "color": ""},
            "updates": {"name": "Updates", "description": "", "color": ""},
        }.get(key, {"name": "Unknown", "description": "", "color": ""})

        organizer.print_final_summary()

        captured = capsys.readouterr().out
        assert "FINAL SUMMARY" in captured
        assert "Accounts processed: 2" in captured
        assert "Total emails processed: 100" in captured
        assert "Total labels applied: 93" in captured
        assert "Subscriptions" in captured
        assert "Finance" in captured
        assert "Updates" in captured

    def test_no_results_does_nothing(self, capsys):
        organizer = _make_organizer()
        organizer.print_final_summary()
        captured = capsys.readouterr().out
        assert "FINAL SUMMARY" not in captured
