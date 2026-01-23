"""Email Security Scanner - detect phishing, spam, and suspicious emails"""

import re
from collections import Counter
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class SecurityAlert:
    """A security finding for an email"""
    email: Dict
    risk_level: str  # high, medium, low
    risk_score: float  # 0-1
    findings: List[str] = field(default_factory=list)
    category: str = ""  # phishing, spam, spoofing, suspicious_link


class EmailSecurityScanner:
    """Analyze emails for phishing, spam, and security threats"""

    # Known phishing/spam indicators
    PHISHING_KEYWORDS = [
        'verify your account', 'confirm your identity', 'update your payment',
        'suspicious activity', 'account suspended', 'click here immediately',
        'your account will be closed', 'verify your information',
        'security alert', 'unauthorized access', 'confirm your password',
        'reset your password now', 'action required immediately',
        'your account has been compromised', 'limited time offer',
        'you have won', 'congratulations you', 'claim your prize',
        'wire transfer', 'send money', 'bitcoin payment',
        'inheritance fund', 'nigerian prince', 'dear beneficiary'
    ]

    SPAM_KEYWORDS = [
        'unsubscribe', 'opt out', 'no longer wish', 'bulk mail',
        'this is an advertisement', 'not spam', 'legitimate offer',
        'act now', 'limited time', 'exclusive deal', 'free gift',
        'no obligation', 'risk free', 'satisfaction guaranteed',
        'double your', 'earn extra', 'make money fast',
        'work from home', 'be your own boss', 'financial freedom',
        'lose weight', 'enlargement', 'pharmacy', 'viagra', 'cialis'
    ]

    SUSPICIOUS_TLDS = {
        '.xyz', '.top', '.club', '.work', '.click', '.link',
        '.info', '.tk', '.ml', '.ga', '.cf', '.gq',
        '.buzz', '.space', '.site', '.online', '.icu'
    }

    LEGITIMATE_DOMAINS = {
        'google.com', 'gmail.com', 'microsoft.com', 'apple.com',
        'amazon.com', 'facebook.com', 'twitter.com', 'linkedin.com',
        'github.com', 'paypal.com', 'stripe.com', 'slack.com',
        'zoom.us', 'dropbox.com', 'salesforce.com', 'adobe.com'
    }

    # Common domain typosquatting patterns
    TYPOSQUAT_PATTERNS = {
        'google': ['g00gle', 'googie', 'gooogle', 'googl3'],
        'paypal': ['paypa1', 'paypai', 'paypaI', 'peypal'],
        'amazon': ['amaz0n', 'arnazon', 'amazom', 'armazon'],
        'microsoft': ['micr0soft', 'rnicrosoft', 'microsft'],
        'apple': ['appie', 'app1e', 'applle'],
        'facebook': ['faceb00k', 'facebock', 'facebo0k'],
        'netflix': ['netf1ix', 'netfllx', 'netfiix'],
        'bank': ['banlk', 'bannk', 'b4nk']
    }

    def scan_emails(self, emails: List[Dict]) -> List[SecurityAlert]:
        """
        Scan emails for security threats.

        Returns list of SecurityAlert objects sorted by risk score (highest first).
        """
        alerts = []

        for email in emails:
            alert = self._analyze_email(email)
            if alert:
                alerts.append(alert)

        alerts.sort(key=lambda a: a.risk_score, reverse=True)
        return alerts

    def _analyze_email(self, email: Dict) -> SecurityAlert:
        """Analyze a single email for threats"""
        findings = []
        score = 0.0

        sender = email.get('sender', '')
        subject = email.get('subject', '').lower()
        body = email.get('body_preview', '').lower()
        headers = email.get('headers', {})
        full_text = f"{subject} {body}"

        # Check phishing keywords
        phishing_matches = self._check_keywords(full_text, self.PHISHING_KEYWORDS)
        if phishing_matches:
            score += min(0.3, len(phishing_matches) * 0.1)
            findings.append(f"Phishing keywords: {', '.join(phishing_matches[:3])}")

        # Check sender legitimacy
        sender_findings = self._check_sender(sender, headers)
        if sender_findings:
            score += sender_findings[0]
            findings.extend(sender_findings[1])

        # Check URLs in body
        url_findings = self._check_urls(body)
        if url_findings:
            score += url_findings[0]
            findings.extend(url_findings[1])

        # Check for urgency manipulation
        urgency = self._check_urgency(full_text)
        if urgency:
            score += 0.1
            findings.append(urgency)

        # Check for mismatched sender display name vs address
        mismatch = self._check_display_mismatch(sender)
        if mismatch:
            score += 0.15
            findings.append(mismatch)

        # Check spam signals
        spam_matches = self._check_keywords(full_text, self.SPAM_KEYWORDS)
        if len(spam_matches) >= 3:
            score += 0.1
            findings.append(f"Spam signals: {', '.join(spam_matches[:3])}")

        if not findings:
            return None

        score = min(score, 1.0)

        # Determine risk level and category
        if score >= 0.6:
            risk_level = 'high'
        elif score >= 0.3:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        # Determine category
        if phishing_matches and score >= 0.4:
            category = 'phishing'
        elif mismatch or sender_findings:
            category = 'spoofing'
        elif url_findings:
            category = 'suspicious_link'
        else:
            category = 'spam'

        return SecurityAlert(
            email=email,
            risk_level=risk_level,
            risk_score=score,
            findings=findings,
            category=category
        )

    def _check_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Check for keyword matches"""
        matches = []
        for kw in keywords:
            if kw in text:
                matches.append(kw)
        return matches

    def _check_sender(self, sender: str, headers: Dict) -> Tuple:
        """Check sender for suspicious patterns"""
        findings = []
        score = 0.0

        # Extract email address
        email_match = re.search(r'<(.+?)>', sender)
        sender_email = email_match.group(1).lower() if email_match else sender.lower()

        if '@' not in sender_email:
            return (0, [])

        domain = sender_email.split('@')[1]

        # Check for suspicious TLDs
        for tld in self.SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                score += 0.15
                findings.append(f"Suspicious TLD: {tld}")
                break

        # Check for typosquatting
        for legit, typos in self.TYPOSQUAT_PATTERNS.items():
            for typo in typos:
                if typo in domain:
                    score += 0.4
                    findings.append(f"Possible typosquatting: '{domain}' mimics '{legit}'")
                    break

        # Check for very long subdomains (hiding real domain)
        parts = domain.split('.')
        if len(parts) > 3:
            score += 0.1
            findings.append(f"Excessive subdomains in sender: {domain}")

        # Check for numeric IPs in sender
        if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', domain):
            score += 0.3
            findings.append("Sender uses IP address instead of domain")

        # Check SPF/DKIM headers if available
        auth_results = headers.get('Authentication-Results', '')
        if auth_results:
            if 'spf=fail' in auth_results.lower():
                score += 0.3
                findings.append("SPF authentication failed")
            if 'dkim=fail' in auth_results.lower():
                score += 0.3
                findings.append("DKIM authentication failed")

        return (score, findings) if findings else None

    def _check_urls(self, body: str) -> Tuple:
        """Check URLs for suspicious patterns"""
        findings = []
        score = 0.0

        # Find URLs
        urls = re.findall(r'https?://([^\s<>"\']+)', body)

        for url in urls[:10]:  # Limit to first 10 URLs
            domain = url.split('/')[0].lower()

            # Check suspicious TLDs
            for tld in self.SUSPICIOUS_TLDS:
                if domain.endswith(tld):
                    score += 0.1
                    findings.append(f"Suspicious URL TLD: {domain}")
                    break

            # Check for IP-based URLs
            if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', domain):
                score += 0.2
                findings.append(f"IP-based URL: {domain}")

            # Check for very long URLs (obfuscation)
            if len(url) > 200:
                score += 0.05
                findings.append("Unusually long URL detected")

            # Check for URL shorteners
            shorteners = {'bit.ly', 'tinyurl.com', 'goo.gl', 't.co', 'ow.ly',
                         'is.gd', 'buff.ly', 'rebrand.ly'}
            if domain in shorteners:
                score += 0.05
                findings.append(f"URL shortener: {domain}")

            # Check for typosquatting in URLs
            for legit, typos in self.TYPOSQUAT_PATTERNS.items():
                for typo in typos:
                    if typo in domain:
                        score += 0.3
                        findings.append(f"Typosquatting URL: {domain}")
                        break

        return (score, findings) if findings else None

    def _check_urgency(self, text: str) -> str:
        """Check for urgency manipulation tactics"""
        urgency_patterns = [
            (r'within \d+ hours?', 'Time pressure'),
            (r'expires? (today|tonight|in \d+)', 'Expiration pressure'),
            (r'immediate(ly)?[\s,.]', 'Immediate action demanded'),
            (r'(account|access) (will be|has been) (suspended|blocked|closed)',
             'Account threat'),
            (r'(verify|confirm|update).{0,20}(now|immediately|today)',
             'Urgency + action demand'),
        ]

        for pattern, desc in urgency_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return f"Urgency manipulation: {desc}"
        return ""

    def _check_display_mismatch(self, sender: str) -> str:
        """Check if display name mismatches email domain"""
        # Pattern: "PayPal <random@phishing.com>"
        name_match = re.match(r'^"?([^"<]+)"?\s*<(.+?)>', sender)
        if not name_match:
            return ""

        display_name = name_match.group(1).strip().lower()
        email_addr = name_match.group(2).lower()
        email_domain = email_addr.split('@')[1] if '@' in email_addr else ""

        # Check if display name contains a known brand but email is from different domain
        for brand in self.LEGITIMATE_DOMAINS:
            brand_name = brand.split('.')[0]
            if (brand_name in display_name and
                    brand not in email_domain and
                    len(brand_name) >= 4):
                return (f"Display name '{display_name}' mentions {brand_name} "
                        f"but email is from {email_domain}")

        return ""

    def get_scan_stats(self, alerts: List[SecurityAlert]) -> Dict:
        """Get summary statistics of scan results"""
        levels = Counter()
        categories = Counter()

        for alert in alerts:
            levels[alert.risk_level] += 1
            categories[alert.category] += 1

        return {
            'total_alerts': len(alerts),
            'high_risk': levels.get('high', 0),
            'medium_risk': levels.get('medium', 0),
            'low_risk': levels.get('low', 0),
            'phishing': categories.get('phishing', 0),
            'spoofing': categories.get('spoofing', 0),
            'suspicious_link': categories.get('suspicious_link', 0),
            'spam': categories.get('spam', 0)
        }
