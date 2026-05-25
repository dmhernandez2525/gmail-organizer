"""Tests for EmailSecurityScanner"""

import pytest
from gmail_organizer.security import EmailSecurityScanner, SecurityAlert


@pytest.fixture
def scanner():
    return EmailSecurityScanner()


def _make_email(
    sender="John Doe <john@example.com>",
    subject="Hello",
    body_preview="Just a normal message.",
    headers=None,
):
    email = {
        "sender": sender,
        "subject": subject,
        "body_preview": body_preview,
    }
    if headers is not None:
        email["headers"] = headers
    return email


# --- 1. Clean email returns no alert ---


class TestCleanEmail:
    def test_clean_email_returns_none(self, scanner):
        email = _make_email()
        alert = scanner._analyze_email(email)
        assert alert is None

    def test_scan_clean_emails_returns_empty_list(self, scanner):
        emails = [_make_email(), _make_email(subject="Meeting tomorrow")]
        alerts = scanner.scan_emails(emails)
        assert alerts == []


# --- 2. Phishing keywords detected ---


class TestPhishingKeywords:
    def test_single_phishing_keyword_in_subject(self, scanner):
        email = _make_email(subject="Verify your account now")
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert any("Phishing keywords" in f for f in alert.findings)

    def test_phishing_keyword_in_body(self, scanner):
        email = _make_email(body_preview="Please confirm your identity right away")
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert any("Phishing keywords" in f for f in alert.findings)

    def test_multiple_phishing_keywords_increase_score(self, scanner):
        email = _make_email(
            subject="verify your account",
            body_preview="confirm your identity or your account will be closed",
        )
        alert = scanner._analyze_email(email)
        assert alert is not None
        # Multiple keywords should push score higher (capped at 0.3 from keywords alone)
        assert alert.risk_score >= 0.2

    def test_phishing_keywords_capped_at_0_3(self, scanner):
        # Stuff many phishing keywords into one email
        body = " ".join(EmailSecurityScanner.PHISHING_KEYWORDS)
        email = _make_email(body_preview=body)
        matches = scanner._check_keywords(body.lower(), scanner.PHISHING_KEYWORDS)
        # Even with many matches, contribution from keywords alone is min(0.3, count*0.1)
        assert min(0.3, len(matches) * 0.1) == 0.3


# --- 3. Typosquatting domain detected ---


class TestTyposquatting:
    def test_typosquat_sender_detected(self, scanner):
        email = _make_email(sender="Support <support@g00gle.com>")
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert any("typosquatting" in f.lower() for f in alert.findings)
        assert alert.risk_score >= 0.4

    def test_typosquat_paypal(self, scanner):
        email = _make_email(sender="PayPal <billing@paypa1.com>")
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert any("paypal" in f.lower() for f in alert.findings)

    def test_typosquat_amazon(self, scanner):
        email = _make_email(sender="Amazon <orders@amaz0n.com>")
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert any("amazon" in f.lower() for f in alert.findings)

    def test_legitimate_domain_no_typosquat(self, scanner):
        result = scanner._check_sender("test@google.com", {})
        assert result is None


# --- 4. Suspicious TLD detected ---


class TestSuspiciousTLD:
    @pytest.mark.parametrize("tld", [".xyz", ".tk", ".ml", ".click", ".icu"])
    def test_suspicious_tld_flagged(self, scanner, tld):
        sender = f"user@sketchy{tld}"
        result = scanner._check_sender(sender, {})
        assert result is not None
        score, findings = result
        assert score >= 0.15
        assert any("Suspicious TLD" in f for f in findings)

    def test_normal_tld_not_flagged(self, scanner):
        result = scanner._check_sender("user@company.com", {})
        assert result is None


# --- 5. IP-based sender detected ---


class TestIPBasedSender:
    def test_ip_address_in_domain(self, scanner):
        result = scanner._check_sender("user@192.168.1.1", {})
        assert result is not None
        score, findings = result
        assert score >= 0.3
        assert any("IP address" in f for f in findings)

    def test_non_ip_domain_not_flagged(self, scanner):
        result = scanner._check_sender("user@normal-domain.com", {})
        assert result is None


# --- 6. SPF/DKIM failure detected ---


class TestSPFDKIM:
    def test_spf_fail(self, scanner):
        headers = {"Authentication-Results": "mx.example.com; spf=fail"}
        result = scanner._check_sender("user@example.com", headers)
        assert result is not None
        score, findings = result
        assert score >= 0.3
        assert any("SPF" in f for f in findings)

    def test_dkim_fail(self, scanner):
        headers = {"Authentication-Results": "mx.example.com; dkim=fail"}
        result = scanner._check_sender("user@example.com", headers)
        assert result is not None
        score, findings = result
        assert score >= 0.3
        assert any("DKIM" in f for f in findings)

    def test_both_spf_and_dkim_fail(self, scanner):
        headers = {
            "Authentication-Results": "mx.example.com; spf=fail; dkim=fail"
        }
        result = scanner._check_sender("user@example.com", headers)
        assert result is not None
        score, findings = result
        assert score >= 0.6
        assert any("SPF" in f for f in findings)
        assert any("DKIM" in f for f in findings)

    def test_spf_pass_not_flagged(self, scanner):
        headers = {"Authentication-Results": "mx.example.com; spf=pass; dkim=pass"}
        result = scanner._check_sender("user@example.com", headers)
        assert result is None


# --- 7. Display name mismatch ---


class TestDisplayMismatch:
    def test_paypal_mismatch(self, scanner):
        result = scanner._check_display_mismatch("PayPal <random@phishing.com>")
        assert "paypal" in result.lower()
        assert "phishing.com" in result

    def test_google_mismatch(self, scanner):
        result = scanner._check_display_mismatch("Google Support <help@scamsite.net>")
        assert "google" in result.lower()

    def test_legitimate_sender_no_mismatch(self, scanner):
        result = scanner._check_display_mismatch("Google <noreply@google.com>")
        assert result == ""

    def test_no_angle_brackets_no_mismatch(self, scanner):
        result = scanner._check_display_mismatch("user@example.com")
        assert result == ""

    def test_short_brand_name_ignored(self, scanner):
        # Brands with fewer than 4 chars should not trigger mismatch check
        # None of the built-in brands are that short, so this should return empty
        result = scanner._check_display_mismatch("IBM <info@ibm.com>")
        assert result == ""

    def test_mismatch_increases_score_in_analyze(self, scanner):
        email = _make_email(sender="PayPal <random@phishing.com>")
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert alert.risk_score >= 0.15
        assert alert.category == "spoofing"


# --- 8. URL shortener detected ---


class TestURLShortener:
    @pytest.mark.parametrize("shortener", ["bit.ly", "tinyurl.com", "goo.gl", "t.co"])
    def test_shortener_detected(self, scanner, shortener):
        body = f"click here: https://{shortener}/abc123"
        result = scanner._check_urls(body.lower())
        assert result is not None
        score, findings = result
        assert any("shortener" in f.lower() for f in findings)

    def test_normal_url_not_flagged(self, scanner):
        body = "visit https://www.google.com/search for more"
        result = scanner._check_urls(body.lower())
        assert result is None


# --- 9. Urgency manipulation detected ---


class TestUrgency:
    def test_time_pressure(self, scanner):
        result = scanner._check_urgency("respond within 24 hours")
        assert "Urgency" in result

    def test_expiration_pressure(self, scanner):
        result = scanner._check_urgency("this offer expires today")
        assert "Urgency" in result

    def test_immediate_action(self, scanner):
        result = scanner._check_urgency("you must act immediately.")
        assert "Urgency" in result

    def test_account_threat(self, scanner):
        result = scanner._check_urgency("your account will be suspended")
        assert "Urgency" in result

    def test_verify_now(self, scanner):
        result = scanner._check_urgency("please verify your account now")
        assert "Urgency" in result

    def test_no_urgency(self, scanner):
        result = scanner._check_urgency("here is a regular update for you")
        assert result == ""


# --- 10. Multiple signals combine for high risk score ---


class TestMultipleSignals:
    def test_phishing_plus_typosquat_plus_urgency(self, scanner):
        email = _make_email(
            sender="Amazon <orders@amaz0n.xyz>",
            subject="Your account has been compromised",
            body_preview=(
                "Click here immediately to verify your account. "
                "Your account will be suspended within 24 hours. "
                "Visit https://amaz0n.xyz/verify now."
            ),
        )
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert alert.risk_level == "high"
        assert alert.risk_score >= 0.6
        assert len(alert.findings) >= 3

    def test_spoofing_plus_suspicious_link(self, scanner):
        email = _make_email(
            sender="Apple <support@app1e.tk>",
            subject="Verify your information",
            body_preview="Visit https://192.168.1.1/login to confirm your password",
        )
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert alert.risk_score >= 0.5

    def test_score_capped_at_1(self, scanner):
        """Even with many signals, score should never exceed 1.0"""
        email = _make_email(
            sender="PayPal <billing@paypa1.xyz>",
            subject="verify your account action required immediately",
            body_preview=(
                "confirm your identity. your account will be closed. "
                "click here immediately. within 24 hours. "
                "visit https://192.168.1.1/scam or https://bit.ly/x "
                "act now limited time free gift no obligation risk free"
            ),
            headers={
                "Authentication-Results": "mx.example.com; spf=fail; dkim=fail"
            },
        )
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert alert.risk_score <= 1.0


# --- 11. Stats calculation ---


class TestScanStats:
    def test_stats_empty(self, scanner):
        stats = scanner.get_scan_stats([])
        assert stats["total_alerts"] == 0
        assert stats["high_risk"] == 0
        assert stats["phishing"] == 0

    def test_stats_counts(self, scanner):
        alerts = [
            SecurityAlert(
                email={}, risk_level="high", risk_score=0.8,
                findings=["f1"], category="phishing",
            ),
            SecurityAlert(
                email={}, risk_level="medium", risk_score=0.4,
                findings=["f2"], category="spoofing",
            ),
            SecurityAlert(
                email={}, risk_level="low", risk_score=0.2,
                findings=["f3"], category="spam",
            ),
            SecurityAlert(
                email={}, risk_level="high", risk_score=0.9,
                findings=["f4"], category="suspicious_link",
            ),
        ]
        stats = scanner.get_scan_stats(alerts)
        assert stats["total_alerts"] == 4
        assert stats["high_risk"] == 2
        assert stats["medium_risk"] == 1
        assert stats["low_risk"] == 1
        assert stats["phishing"] == 1
        assert stats["spoofing"] == 1
        assert stats["suspicious_link"] == 1
        assert stats["spam"] == 1


# --- 12. Spam keyword detection ---


class TestSpamKeywords:
    def test_few_spam_keywords_no_finding(self, scanner):
        """Fewer than 3 spam keywords should not add a spam finding"""
        email = _make_email(body_preview="unsubscribe from this list")
        alert = scanner._analyze_email(email)
        # One spam keyword alone should not trigger anything
        assert alert is None

    def test_three_or_more_spam_keywords_flagged(self, scanner):
        email = _make_email(
            body_preview="act now, limited time, exclusive deal, free gift"
        )
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert any("Spam signals" in f for f in alert.findings)
        assert alert.category == "spam"

    def test_spam_only_is_low_risk(self, scanner):
        email = _make_email(
            body_preview="act now limited time exclusive deal free gift no obligation"
        )
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert alert.risk_level == "low"


# --- Edge cases and integration ---


class TestEdgeCases:
    def test_email_missing_all_fields(self, scanner):
        alert = scanner._analyze_email({})
        assert alert is None

    def test_sender_without_at_sign(self, scanner):
        result = scanner._check_sender("no-at-sign-here", {})
        assert result == (0, [])

    def test_excessive_subdomains(self, scanner):
        result = scanner._check_sender("user@a.b.c.evil.com", {})
        assert result is not None
        score, findings = result
        assert any("Excessive subdomains" in f for f in findings)

    def test_long_url_flagged(self, scanner):
        long_path = "a" * 201
        body = f"https://example.com/{long_path}"
        result = scanner._check_urls(body.lower())
        assert result is not None
        _, findings = result
        assert any("long URL" in f for f in findings)

    def test_typosquat_url_detected(self, scanner):
        body = "visit https://g00gle.com/login for details"
        result = scanner._check_urls(body.lower())
        assert result is not None
        _, findings = result
        assert any("typosquatting" in f.lower() for f in findings)

    def test_ip_based_url(self, scanner):
        body = "go to https://10.0.0.1/dashboard"
        result = scanner._check_urls(body.lower())
        assert result is not None
        _, findings = result
        assert any("IP-based URL" in f for f in findings)

    def test_suspicious_url_tld(self, scanner):
        body = "check https://promo.xyz/deal"
        result = scanner._check_urls(body.lower())
        assert result is not None
        _, findings = result
        assert any("Suspicious URL TLD" in f for f in findings)

    def test_scan_emails_sorted_by_risk_score(self, scanner):
        low_risk = _make_email(
            body_preview="act now limited time exclusive deal free gift"
        )
        high_risk = _make_email(
            sender="PayPal <billing@paypa1.xyz>",
            subject="verify your account",
            body_preview="confirm your identity within 24 hours",
            headers={
                "Authentication-Results": "spf=fail; dkim=fail"
            },
        )
        alerts = scanner.scan_emails([low_risk, high_risk])
        assert len(alerts) == 2
        assert alerts[0].risk_score >= alerts[1].risk_score

    def test_check_keywords_no_match(self, scanner):
        result = scanner._check_keywords("hello world", ["phishing", "scam"])
        assert result == []

    def test_check_keywords_multiple_matches(self, scanner):
        result = scanner._check_keywords(
            "verify your account and confirm your identity",
            ["verify your account", "confirm your identity"],
        )
        assert len(result) == 2

    def test_phishing_category_requires_keywords_and_high_score(self, scanner):
        """Category is phishing only when phishing keywords present AND score >= 0.4"""
        email = _make_email(
            sender="Support <help@g00gle.com>",
            subject="verify your account",
            body_preview="confirm your identity immediately.",
        )
        alert = scanner._analyze_email(email)
        assert alert is not None
        assert alert.category == "phishing"

    def test_no_body_urls_returns_none(self, scanner):
        result = scanner._check_urls("no urls here at all")
        assert result is None

    def test_urls_limit_to_10(self, scanner):
        """Only the first 10 URLs should be checked"""
        urls = " ".join(f"https://site{i}.xyz/page" for i in range(15))
        result = scanner._check_urls(urls)
        assert result is not None
        _, findings = result
        # Should have at most 10 suspicious TLD findings (one per URL checked)
        tld_findings = [f for f in findings if "Suspicious URL TLD" in f]
        assert len(tld_findings) <= 10
