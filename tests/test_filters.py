"""Tests for gmail_organizer.filters -- SmartFilterGenerator and FilterRule."""

import pytest
from gmail_organizer.filters import FilterRule, SmartFilterGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_email(sender="", subject="", category="", body_preview=""):
    """Build a minimal email dict used by the filter module."""
    return {
        "sender": sender,
        "subject": subject,
        "category": category,
        "body_preview": body_preview,
    }


# ---------------------------------------------------------------------------
# FilterRule serialization
# ---------------------------------------------------------------------------

class TestFilterRule:
    def test_to_gmail_filter_with_label_id(self):
        rule = FilterRule(
            criteria={"from": "alice@example.com"},
            action_label="Updates",
            label_id="Label_42",
        )
        result = rule.to_gmail_filter()
        assert result["criteria"] == {"from": "alice@example.com"}
        assert result["action"]["addLabelIds"] == ["Label_42"]

    def test_to_gmail_filter_without_label_id(self):
        rule = FilterRule(
            criteria={"subject": "invoice"},
            action_label="Finance",
        )
        result = rule.to_gmail_filter()
        assert result["criteria"] == {"subject": "invoice"}
        assert "addLabelIds" not in result["action"]

    def test_to_dict(self):
        rule = FilterRule(
            criteria={"from": "bob@example.com"},
            action_label="Promo",
            description="Emails from Bob",
            match_count=5,
        )
        d = rule.to_dict()
        assert d["criteria"] == {"from": "bob@example.com"}
        assert d["action_label"] == "Promo"
        assert d["description"] == "Emails from Bob"
        assert d["match_count"] == 5


# ---------------------------------------------------------------------------
# SmartFilterGenerator internals
# ---------------------------------------------------------------------------

class TestSmartFilterGeneratorHelpers:
    @pytest.fixture
    def gen(self):
        return SmartFilterGenerator()

    def test_extract_email_angle_brackets(self, gen):
        assert gen._extract_email("Alice <alice@example.com>") == "alice@example.com"

    def test_extract_email_plain(self, gen):
        assert gen._extract_email("BOB@Example.COM") == "bob@example.com"

    def test_extract_email_no_at(self, gen):
        assert gen._extract_email("localname") == "localname"

    def test_extract_domain(self, gen):
        assert gen._extract_domain("Alice <alice@example.com>") == "example.com"

    def test_extract_domain_plain(self, gen):
        assert gen._extract_domain("alice@sub.example.com") == "sub.example.com"

    def test_extract_domain_no_at(self, gen):
        assert gen._extract_domain("localname") == ""


# ---------------------------------------------------------------------------
# _matches_criteria
# ---------------------------------------------------------------------------

class TestMatchesCriteria:
    @pytest.fixture
    def gen(self):
        return SmartFilterGenerator()

    def test_from_exact_match(self, gen):
        email = _make_email(sender="Alice <alice@example.com>")
        assert gen._matches_criteria(email, {"from": "alice@example.com"}) is True

    def test_from_no_match(self, gen):
        email = _make_email(sender="Alice <alice@example.com>")
        assert gen._matches_criteria(email, {"from": "bob@example.com"}) is False

    def test_from_domain_match(self, gen):
        email = _make_email(sender="alice@corp.io")
        assert gen._matches_criteria(email, {"from": "@corp.io"}) is True

    def test_from_domain_no_match(self, gen):
        email = _make_email(sender="alice@other.io")
        assert gen._matches_criteria(email, {"from": "@corp.io"}) is False

    def test_subject_match(self, gen):
        email = _make_email(subject="Your weekly newsletter")
        assert gen._matches_criteria(email, {"subject": "newsletter"}) is True

    def test_subject_no_match(self, gen):
        email = _make_email(subject="Hello world")
        assert gen._matches_criteria(email, {"subject": "newsletter"}) is False

    def test_has_the_word_in_body(self, gen):
        email = _make_email(subject="Hi", body_preview="Please see the invoice attached")
        assert gen._matches_criteria(email, {"hasTheWord": "invoice"}) is True

    def test_has_the_word_in_subject(self, gen):
        email = _make_email(subject="Invoice due today", body_preview="")
        assert gen._matches_criteria(email, {"hasTheWord": "invoice"}) is True

    def test_has_the_word_not_found(self, gen):
        email = _make_email(subject="Hello", body_preview="World")
        assert gen._matches_criteria(email, {"hasTheWord": "invoice"}) is False

    def test_empty_criteria_matches_all(self, gen):
        email = _make_email(sender="x@y.com", subject="anything")
        assert gen._matches_criteria(email, {}) is True


# ---------------------------------------------------------------------------
# preview_filter
# ---------------------------------------------------------------------------

class TestPreviewFilter:
    def test_preview_returns_matching_emails(self):
        gen = SmartFilterGenerator()
        rule = FilterRule(criteria={"from": "alice@example.com"}, action_label="Work")
        emails = [
            _make_email(sender="alice@example.com", subject="A"),
            _make_email(sender="bob@other.com", subject="B"),
            _make_email(sender="Alice <alice@example.com>", subject="C"),
        ]
        matches = gen.preview_filter(rule, emails)
        assert len(matches) == 2

    def test_preview_returns_empty_when_nothing_matches(self):
        gen = SmartFilterGenerator()
        rule = FilterRule(criteria={"from": "nobody@void.com"}, action_label="X")
        emails = [_make_email(sender="a@b.com")]
        assert gen.preview_filter(rule, emails) == []


# ---------------------------------------------------------------------------
# analyze_patterns
# ---------------------------------------------------------------------------

class TestAnalyzePatterns:
    @pytest.fixture
    def gen(self):
        return SmartFilterGenerator()

    def test_sender_pattern_above_threshold(self, gen):
        emails = [
            _make_email(sender="noreply@shop.com", subject="Order", category="Shopping")
            for _ in range(5)
        ]
        rules = gen.analyze_patterns(emails, min_frequency=3)
        sender_rules = [r for r in rules if "from" in r.criteria and "@" in r.criteria["from"] and not r.criteria["from"].startswith("@")]
        assert len(sender_rules) >= 1
        assert sender_rules[0].criteria["from"] == "noreply@shop.com"
        assert sender_rules[0].action_label == "Shopping"

    def test_sender_pattern_below_threshold_excluded(self, gen):
        emails = [
            _make_email(sender="rare@example.com", subject="Hi", category="Misc")
            for _ in range(2)
        ]
        rules = gen.analyze_patterns(emails, min_frequency=3)
        sender_rules = [r for r in rules if r.criteria.get("from") == "rare@example.com"]
        assert sender_rules == []

    def test_domain_pattern_multiple_senders(self, gen):
        emails = []
        for i in range(4):
            sender = f"user{i % 2}@bigcorp.com"
            emails.append(_make_email(sender=sender, subject="Report", category="Work"))
        rules = gen.analyze_patterns(emails, min_frequency=3)
        domain_rules = [r for r in rules if r.criteria.get("from", "").startswith("@")]
        assert len(domain_rules) >= 1
        assert domain_rules[0].criteria["from"] == "@bigcorp.com"

    def test_subject_keyword_pattern(self, gen):
        # Keywords need min_frequency * 2 = 6 occurrences at default min_frequency=3
        emails = [
            _make_email(sender=f"s{i}@x.com", subject="Weekly invoice summary", category="Finance")
            for i in range(8)
        ]
        rules = gen.analyze_patterns(emails, min_frequency=3)
        keyword_rules = [r for r in rules if "subject" in r.criteria]
        # "invoice", "weekly", or "summary" should appear as keyword rules
        keyword_values = [r.criteria["subject"] for r in keyword_rules]
        assert len(keyword_rules) >= 1
        # At least one of the significant words should be picked up
        assert any(w in keyword_values for w in ["invoice", "weekly", "summary"])


# ---------------------------------------------------------------------------
# _deduplicate_rules
# ---------------------------------------------------------------------------

class TestDeduplicateRules:
    def test_keeps_highest_match_count(self):
        gen = SmartFilterGenerator()
        rule_low = FilterRule(
            criteria={"from": "a@b.com"}, action_label="X", match_count=2
        )
        rule_high = FilterRule(
            criteria={"from": "a@b.com"}, action_label="X", match_count=10
        )
        result = gen._deduplicate_rules([rule_low, rule_high])
        assert len(result) == 1
        assert result[0].match_count == 10

    def test_different_criteria_preserved(self):
        gen = SmartFilterGenerator()
        rule_a = FilterRule(criteria={"from": "a@b.com"}, action_label="X", match_count=5)
        rule_b = FilterRule(criteria={"from": "c@d.com"}, action_label="X", match_count=3)
        result = gen._deduplicate_rules([rule_a, rule_b])
        assert len(result) == 2

    def test_different_labels_preserved(self):
        gen = SmartFilterGenerator()
        rule_a = FilterRule(criteria={"from": "a@b.com"}, action_label="X", match_count=5)
        rule_b = FilterRule(criteria={"from": "a@b.com"}, action_label="Y", match_count=3)
        result = gen._deduplicate_rules([rule_a, rule_b])
        assert len(result) == 2
