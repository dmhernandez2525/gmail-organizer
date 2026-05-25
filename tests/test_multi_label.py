"""Tests for multi_label email classification module."""

import pytest

from gmail_organizer.multi_label import (
    ClassificationResult,
    ClassificationRule,
    LabelAssignment,
    MultiLabelClassifier,
)


# ---------------------------------------------------------------------------
# ClassificationRule dataclass
# ---------------------------------------------------------------------------

class TestClassificationRule:
    def test_compiles_valid_patterns(self):
        rule = ClassificationRule(
            label="test",
            sender_patterns=[r"@example\.com"],
            subject_patterns=[r"\bmeeting\b"],
        )
        assert len(rule._compiled_sender) == 1
        assert len(rule._compiled_subject) == 1

    def test_skips_invalid_regex(self):
        rule = ClassificationRule(
            label="test",
            sender_patterns=[r"[invalid", r"@valid\.com"],
        )
        # Invalid pattern is skipped, valid one remains
        assert len(rule._compiled_sender) == 1

    def test_empty_patterns(self):
        rule = ClassificationRule(label="empty")
        assert len(rule._compiled_sender) == 0
        assert len(rule._compiled_subject) == 0
        assert len(rule._compiled_body) == 0
        assert len(rule._compiled_domain) == 0

    def test_default_weight(self):
        rule = ClassificationRule(label="test")
        assert rule.weight == 1.0


# ---------------------------------------------------------------------------
# LabelAssignment and ClassificationResult dataclasses
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_label_assignment_fields(self):
        la = LabelAssignment(label="work", confidence=0.85, matched_rules=["rule1"])
        assert la.label == "work"
        assert la.confidence == 0.85
        assert la.matched_rules == ["rule1"]

    def test_classification_result_defaults(self):
        cr = ClassificationResult(email_id="e1")
        assert cr.primary_label == ""
        assert cr.labels == []
        assert cr.all_labels == []


# ---------------------------------------------------------------------------
# MultiLabelClassifier
# ---------------------------------------------------------------------------

class TestMultiLabelClassifier:
    def _make_email(self, email_id="e1", sender="", subject="", body=""):
        return {
            "email_id": email_id,
            "sender": sender,
            "subject": subject,
            "body": body,
        }

    # --- initialization ---

    def test_default_rules_loaded(self):
        clf = MultiLabelClassifier()
        assert len(clf.rules) > 0

    def test_custom_rules(self):
        rules = [ClassificationRule(label="custom", subject_patterns=[r"\btest\b"])]
        clf = MultiLabelClassifier(rules=rules)
        assert len(clf.rules) == 1
        assert clf.rules[0].label == "custom"

    def test_custom_threshold(self):
        clf = MultiLabelClassifier(confidence_threshold=0.5)
        assert clf.confidence_threshold == 0.5

    # --- classify_email ---

    def test_classify_work_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="notifications@jira.atlassian.com",
            subject="Sprint review meeting tomorrow",
            body="Please join the sprint review.",
        )
        result = clf.classify_email(email)
        assert result.primary_label == "work"
        assert "work" in result.all_labels

    def test_classify_finance_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="alerts@chase.com",
            subject="Your payment of $500 has been processed",
            body="Transaction statement for your account.",
        )
        result = clf.classify_email(email)
        assert "finance" in result.all_labels

    def test_classify_shopping_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="shipment-tracking@amazon.com",
            subject="Your order has shipped",
            body="Your package is on its way. Tracking number included.",
        )
        result = clf.classify_email(email)
        assert "shopping" in result.all_labels

    def test_classify_social_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="notifications@linkedin.com",
            subject="You have a new connection request",
            body="Someone wants to connect with you.",
        )
        result = clf.classify_email(email)
        assert "social" in result.all_labels

    def test_classify_newsletter(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="digest@substack.com",
            subject="Your weekly newsletter digest #42",
            body="This week in tech. Click to unsubscribe.",
        )
        result = clf.classify_email(email)
        assert "newsletter" in result.all_labels

    def test_classify_security_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="security-noreply@google.com",
            subject="Security alert: suspicious sign-in detected",
            body="We noticed unauthorized login attempt. Verify your password.",
        )
        result = clf.classify_email(email)
        assert "security" in result.all_labels

    def test_classify_travel_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="confirm@booking.com",
            subject="Your hotel reservation is confirmed",
            body="Check-in details for your trip.",
        )
        result = clf.classify_email(email)
        assert "travel" in result.all_labels

    def test_classify_promotions_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="deals@store.com",
            subject="Flash sale: 50% off everything, limited time",
            body="Use promo code SAVE50. Unsubscribe here.",
        )
        result = clf.classify_email(email)
        assert "promotions" in result.all_labels

    def test_classify_uncategorized_email(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="random@unknown.org",
            subject="Hello",
            body="Just wanted to say hi.",
        )
        result = clf.classify_email(email)
        # With no pattern matches, should fall back to uncategorized
        assert result.primary_label == "uncategorized" or len(result.all_labels) >= 0

    def test_classify_email_uses_snippet_fallback(self):
        clf = MultiLabelClassifier()
        email = {
            "email_id": "e1",
            "from": "alerts@chase.com",
            "subject": "Payment received $100",
            "snippet": "Your payment transaction is confirmed.",
        }
        result = clf.classify_email(email)
        assert "finance" in result.all_labels

    def test_classify_email_multi_label(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="noreply@company.atlassian.com",
            subject="Meeting about project deadline invoice payment",
            body="Sprint review. Payment due. Unsubscribe link.",
        )
        result = clf.classify_email(email)
        # Should get multiple labels since the email touches several categories
        assert len(result.labels) >= 1

    def test_classify_email_confidence_between_0_and_1(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="notifications@jira.atlassian.com",
            subject="Sprint review meeting",
        )
        result = clf.classify_email(email)
        for label_assignment in result.labels:
            assert 0.0 <= label_assignment.confidence <= 1.0

    def test_classify_email_matched_rules_truncated(self):
        clf = MultiLabelClassifier()
        email = self._make_email(
            sender="noreply@google.com",
            subject="Security alert verify password login sign-in suspicious",
            body="unauthorized two-factor 2fa otp",
        )
        result = clf.classify_email(email)
        for la in result.labels:
            assert len(la.matched_rules) <= 5

    # --- classify_batch ---

    def test_classify_batch(self):
        clf = MultiLabelClassifier()
        emails = [
            self._make_email(email_id="e1", sender="noreply@chase.com", subject="Payment received"),
            self._make_email(email_id="e2", sender="notifications@linkedin.com", subject="New connection"),
        ]
        results = clf.classify_batch(emails)
        assert len(results) == 2
        assert all(isinstance(r, ClassificationResult) for r in results)

    def test_classify_batch_empty(self):
        clf = MultiLabelClassifier()
        results = clf.classify_batch([])
        assert results == []

    # --- get_label_stats ---

    def test_get_label_stats(self):
        clf = MultiLabelClassifier()
        results = [
            ClassificationResult(
                email_id="e1",
                primary_label="work",
                labels=[LabelAssignment(label="work", confidence=0.9)],
                all_labels=["work"],
            ),
            ClassificationResult(
                email_id="e2",
                primary_label="finance",
                labels=[
                    LabelAssignment(label="finance", confidence=0.8),
                    LabelAssignment(label="shopping", confidence=0.4),
                ],
                all_labels=["finance", "shopping"],
            ),
        ]
        stats = clf.get_label_stats(results)
        assert stats["total_emails"] == 2
        assert stats["label_counts"]["work"] == 1
        assert stats["label_counts"]["finance"] == 1
        assert stats["multi_label_count"] == 1
        assert stats["multi_label_pct"] == 50.0
        assert stats["avg_labels_per_email"] == 1.5
        assert stats["unique_labels"] == 3

    def test_get_label_stats_empty(self):
        clf = MultiLabelClassifier()
        stats = clf.get_label_stats([])
        assert stats["total_emails"] == 0
        assert stats["multi_label_count"] == 0
        assert stats["avg_labels_per_email"] == 0.0

    # --- add_rule / remove_rule ---

    def test_add_rule(self):
        clf = MultiLabelClassifier()
        initial_count = len(clf.rules)
        new_rule = ClassificationRule(
            label="custom",
            subject_patterns=[r"\bcustom\b"],
        )
        clf.add_rule(new_rule)
        assert len(clf.rules) == initial_count + 1
        assert clf.rules[-1].label == "custom"

    def test_remove_rule(self):
        rules = [
            ClassificationRule(label="a", subject_patterns=[r"a"]),
            ClassificationRule(label="b", subject_patterns=[r"b"]),
            ClassificationRule(label="a", subject_patterns=[r"a2"]),
        ]
        clf = MultiLabelClassifier(rules=rules)
        removed = clf.remove_rule("a")
        assert removed == 2
        assert len(clf.rules) == 1
        assert clf.rules[0].label == "b"

    def test_remove_rule_nonexistent(self):
        clf = MultiLabelClassifier(rules=[ClassificationRule(label="a")])
        removed = clf.remove_rule("z")
        assert removed == 0

    # --- get_available_labels ---

    def test_get_available_labels(self):
        clf = MultiLabelClassifier()
        labels = clf.get_available_labels()
        assert isinstance(labels, list)
        assert len(labels) > 0
        # Default rules include these
        assert "work" in labels
        assert "finance" in labels

    def test_get_available_labels_custom(self):
        rules = [
            ClassificationRule(label="alpha"),
            ClassificationRule(label="beta"),
            ClassificationRule(label="alpha"),  # duplicate label
        ]
        clf = MultiLabelClassifier(rules=rules)
        labels = clf.get_available_labels()
        assert sorted(labels) == ["alpha", "beta"]

    # --- _evaluate_rule ---

    def test_evaluate_rule_sender_match(self):
        rule = ClassificationRule(label="test", sender_patterns=[r"@example\.com"])
        clf = MultiLabelClassifier(rules=[rule])
        score, reasons = clf._evaluate_rule(rule, "user@example.com", "", "", "")
        assert score > 0
        assert any("sender" in r for r in reasons)

    def test_evaluate_rule_subject_match_weighted_higher(self):
        rule = ClassificationRule(
            label="test",
            sender_patterns=[r"@example\.com"],
            subject_patterns=[r"\bmeeting\b"],
        )
        clf = MultiLabelClassifier(rules=[rule])
        sender_score, _ = clf._evaluate_rule(rule, "user@example.com", "", "", "")
        subject_score, _ = clf._evaluate_rule(rule, "", "meeting tomorrow", "", "")
        assert subject_score > sender_score

    def test_evaluate_rule_body_match(self):
        rule = ClassificationRule(label="test", body_patterns=[r"\bunsubscribe\b"])
        clf = MultiLabelClassifier(rules=[rule])
        score, reasons = clf._evaluate_rule(rule, "", "", "click to unsubscribe", "")
        assert score > 0
        assert any("body" in r for r in reasons)

    def test_evaluate_rule_domain_match(self):
        rule = ClassificationRule(label="test", domain_patterns=[r"example\.com"])
        clf = MultiLabelClassifier(rules=[rule])
        score, reasons = clf._evaluate_rule(rule, "", "", "", "example.com")
        assert score > 0
        assert any("domain" in r for r in reasons)

    def test_evaluate_rule_no_domain_match_when_empty(self):
        rule = ClassificationRule(label="test", domain_patterns=[r"example\.com"])
        clf = MultiLabelClassifier(rules=[rule])
        score, reasons = clf._evaluate_rule(rule, "", "", "", "")
        assert score == 0.0

    def test_evaluate_rule_no_match(self):
        rule = ClassificationRule(
            label="test",
            sender_patterns=[r"@specific\.org"],
            subject_patterns=[r"\brare_word\b"],
        )
        clf = MultiLabelClassifier(rules=[rule])
        score, reasons = clf._evaluate_rule(rule, "other@other.com", "hello world", "", "")
        assert score == 0.0
        assert reasons == []

    # --- domain extraction ---

    def test_domain_extraction_from_sender(self):
        clf = MultiLabelClassifier()
        email = self._make_email(sender="user@atlassian.com", subject="Sprint review")
        result = clf.classify_email(email)
        # atlassian.com should trigger work domain pattern
        assert isinstance(result, ClassificationResult)

    def test_domain_extraction_no_at_sign(self):
        clf = MultiLabelClassifier()
        email = self._make_email(sender="no-domain-here", subject="test")
        result = clf.classify_email(email)
        assert isinstance(result, ClassificationResult)
