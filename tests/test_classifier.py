"""Tests for EmailClassifier."""

import pytest
from unittest.mock import MagicMock, patch

from gmail_organizer.classifier import EmailClassifier
from gmail_organizer.config import CATEGORIES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_anthropic():
    """Patch anthropic.Anthropic so no real API calls are made."""
    with patch("gmail_organizer.classifier.anthropic.Anthropic") as MockClient:
        client_instance = MagicMock()
        MockClient.return_value = client_instance
        yield MockClient, client_instance


@pytest.fixture
def classifier(mock_anthropic):
    """Return an EmailClassifier with a mocked Anthropic client."""
    return EmailClassifier(api_key="test-key-123")


@pytest.fixture
def make_api_response():
    """Factory for creating mock API responses."""

    def _make(text, stop_reason="end_turn"):
        response = MagicMock()
        content_block = MagicMock()
        content_block.text = text
        response.content = [content_block]
        response.stop_reason = stop_reason
        return response

    return _make


# ---------------------------------------------------------------------------
# __init__ tests
# ---------------------------------------------------------------------------


class TestInit:
    def test_raises_without_api_key(self):
        with patch("gmail_organizer.classifier.ANTHROPIC_API_KEY", None):
            with patch("gmail_organizer.classifier.anthropic.Anthropic"):
                with pytest.raises(ValueError, match="API key"):
                    EmailClassifier(api_key=None)

    def test_creates_client_with_key(self, mock_anthropic):
        MockClient, _ = mock_anthropic
        EmailClassifier(api_key="my-key")
        MockClient.assert_called_once_with(api_key="my-key")

    def test_all_categories_populated(self, classifier):
        assert len(classifier.all_categories) > 0
        assert "subscriptions" in classifier.all_categories
        assert "applications" in classifier.all_categories


# ---------------------------------------------------------------------------
# classify_email tests
# ---------------------------------------------------------------------------


class TestClassifyEmail:
    def test_returns_valid_category(self, classifier, mock_anthropic, make_api_response):
        _, client = mock_anthropic
        client.messages.create.return_value = make_api_response("subscriptions")

        category, confidence = classifier.classify_email(
            subject="Weekly Newsletter",
            sender="news@example.com",
        )
        assert category == "subscriptions"
        assert confidence == 0.9

    def test_with_body_preview_uses_full_prompt(self, classifier, mock_anthropic, make_api_response):
        _, client = mock_anthropic
        client.messages.create.return_value = make_api_response("finance")

        category, confidence = classifier.classify_email(
            subject="Your receipt",
            sender="billing@stripe.com",
            body_preview="Payment of $49.99 processed on March 1.",
        )
        assert category == "finance"
        # Verify the prompt included body_preview content
        call_args = client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "Payment of $49.99" in prompt_text

    def test_without_body_uses_short_prompt(self, classifier, mock_anthropic, make_api_response):
        _, client = mock_anthropic
        client.messages.create.return_value = make_api_response("applications")

        classifier.classify_email(
            subject="Application received",
            sender="jobs@company.com",
        )
        call_args = client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        # Short prompt does not contain "Body Preview"
        assert "Body Preview" not in prompt_text
        assert "Category (respond with one word only):" in prompt_text

    def test_confidence_lower_when_not_end_turn(self, classifier, mock_anthropic, make_api_response):
        _, client = mock_anthropic
        client.messages.create.return_value = make_api_response(
            "saved", stop_reason="max_tokens"
        )
        _, confidence = classifier.classify_email("Test", "test@test.com")
        assert confidence == 0.7

    def test_handles_api_error_gracefully(self, classifier, mock_anthropic):
        _, client = mock_anthropic
        client.messages.create.side_effect = Exception("API timeout")

        category, confidence = classifier.classify_email(
            subject="Something",
            sender="someone@example.com",
        )
        assert category == "saved"
        assert confidence == 0.0  # Error fallback signals failure

    def test_fuzzy_matches_invalid_category(self, classifier, mock_anthropic, make_api_response):
        _, client = mock_anthropic
        # API returns "job/applications" which is not a valid key
        client.messages.create.return_value = make_api_response("job/applications")

        category, _ = classifier.classify_email("Job app", "hr@co.com")
        assert category == "applications"


# ---------------------------------------------------------------------------
# _fuzzy_match_category tests
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    def test_matches_partial_name(self, classifier):
        assert classifier._fuzzy_match_category("subscriptions stuff") == "subscriptions"

    def test_matches_substring(self, classifier):
        # "finance" is a valid category; "my finance email" contains it
        assert classifier._fuzzy_match_category("my finance email") == "finance"

    def test_returns_saved_for_unknown(self, classifier):
        assert classifier._fuzzy_match_category("xyzzy_garbage_text") == "saved"

    def test_case_insensitive(self, classifier):
        result = classifier._fuzzy_match_category("SOCIAL")
        assert result == "social"


# ---------------------------------------------------------------------------
# classify_batch tests
# ---------------------------------------------------------------------------


class TestClassifyBatch:
    def test_processes_all_emails(self, classifier, mock_anthropic, make_api_response):
        _, client = mock_anthropic
        client.messages.create.return_value = make_api_response("updates")

        emails = [
            {"subject": f"Update #{i}", "sender": "svc@example.com", "email_id": str(i)}
            for i in range(5)
        ]
        results = classifier.classify_batch(emails)

        assert len(results) == 5
        for r in results:
            assert r["category"] == "updates"
            assert "confidence" in r

    def test_batch_omits_body_preview(self, classifier, mock_anthropic, make_api_response):
        _, client = mock_anthropic
        client.messages.create.return_value = make_api_response("saved")

        emails = [
            {
                "subject": "Test",
                "sender": "a@b.com",
                "body_preview": "This should be ignored in batch mode",
            }
        ]
        classifier.classify_batch(emails)

        call_args = client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "This should be ignored" not in prompt_text


# ---------------------------------------------------------------------------
# get_category_info tests
# ---------------------------------------------------------------------------


class TestGetCategoryInfo:
    def test_known_category(self, classifier):
        info = classifier.get_category_info("subscriptions")
        assert info["name"] == "Subscriptions"
        assert "color" in info

    def test_job_search_category(self, classifier):
        info = classifier.get_category_info("applications")
        assert info["name"] == "Job/Applications"

    def test_unknown_category(self, classifier):
        info = classifier.get_category_info("nonexistent_category")
        assert info["name"] == "Unknown"
        assert info["color"] == "#cccccc"
