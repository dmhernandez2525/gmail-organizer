"""
Sender reputation scoring module.

Calculates reputation scores for email senders based on multiple signals
including frequency, reply rate, authentication pass rate, relationship age,
and read rate. Supports first-time sender detection and sender categorization.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import re


@dataclass
class SenderProfile:
    """Profile representing a sender's reputation and history."""

    sender_email: str
    sender_name: str = ""
    domain: str = ""
    reputation_score: float = 50.0
    reputation_level: str = "unknown"
    total_emails: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    reply_rate: float = 0.0
    read_rate: float = 0.0
    avg_emails_per_week: float = 0.0
    is_automated: bool = False

    def __post_init__(self):
        if not self.domain and self.sender_email:
            parts = self.sender_email.split("@")
            if len(parts) == 2:
                self.domain = parts[1].lower()


class SenderReputation:
    """
    Calculates and manages reputation scores for email senders.

    Reputation is computed from multiple signals:
    - Email frequency (consistent senders score higher than spammy ones)
    - Reply rate from user (high reply rate indicates trust)
    - SPF/DKIM authentication pass rate
    - Age of relationship (longer relationships score higher)
    - Read rate (emails that are read indicate relevance)
    """

    # Reputation level thresholds
    TRUSTED_THRESHOLD = 70
    NEUTRAL_THRESHOLD = 40
    SUSPICIOUS_THRESHOLD = 20

    # Weight factors for scoring components
    WEIGHT_FREQUENCY = 0.15
    WEIGHT_REPLY_RATE = 0.25
    WEIGHT_AUTH = 0.15
    WEIGHT_AGE = 0.20
    WEIGHT_READ_RATE = 0.25

    # Patterns indicating automated senders
    AUTOMATED_PATTERNS = [
        r"^no-?reply@",
        r"^noreply@",
        r"^do-?not-?reply@",
        r"^notifications?@",
        r"^alerts?@",
        r"^updates?@",
        r"^mailer-daemon@",
        r"^postmaster@",
        r"^bounce[s]?@",
        r"^auto@",
        r"^system@",
        r"^newsletter@",
        r"^digest@",
        r"^info@",
        r"^support@",
        r"^news@",
    ]

    def __init__(self):
        self._sender_history: Dict[str, List[Dict]] = defaultdict(list)

    def analyze_senders(
        self, emails: List[Dict], user_email: str = ""
    ) -> List[SenderProfile]:
        """
        Analyze a list of emails and produce reputation profiles for each sender.

        Args:
            emails: List of email dicts with keys like 'from', 'date', 'labels',
                    'headers', 'replied', 'read', etc.
            user_email: The user's own email address, used to determine replies.

        Returns:
            List of SenderProfile instances sorted by reputation score descending.
        """
        sender_data = self._aggregate_sender_data(emails, user_email)
        profiles = []

        for sender_email, data in sender_data.items():
            profile = self._build_profile(sender_email, data)
            profiles.append(profile)

        profiles.sort(key=lambda p: p.reputation_score, reverse=True)
        return profiles

    def get_first_time_senders(
        self, emails: List[Dict], lookback_days: int = 30
    ) -> List[Dict]:
        """
        Identify senders who sent their first email within the lookback period.

        Args:
            emails: List of email dicts.
            lookback_days: Number of days to look back for first-time senders.

        Returns:
            List of dicts with 'sender_email', 'sender_name', 'domain',
            'first_email_date', and 'email_count' for first-time senders.
        """
        cutoff = datetime.now() - timedelta(days=lookback_days)
        sender_first_seen: Dict[str, Tuple[datetime, str, int]] = {}

        for email in emails:
            sender_email = self._extract_email(email.get("sender", email.get("from", "")))
            if not sender_email:
                continue

            sender_name = self._extract_name(email.get("sender", email.get("from", "")))
            email_date = self._parse_date(email.get("date", ""))
            if not email_date:
                continue

            if sender_email not in sender_first_seen:
                sender_first_seen[sender_email] = (email_date, sender_name, 1)
            else:
                existing_date, existing_name, count = sender_first_seen[sender_email]
                if email_date < existing_date:
                    sender_first_seen[sender_email] = (
                        email_date,
                        sender_name,
                        count + 1,
                    )
                else:
                    sender_first_seen[sender_email] = (
                        existing_date,
                        existing_name,
                        count + 1,
                    )

        first_time_senders = []
        for sender_email, (first_date, name, count) in sender_first_seen.items():
            if first_date >= cutoff:
                domain = ""
                parts = sender_email.split("@")
                if len(parts) == 2:
                    domain = parts[1].lower()

                first_time_senders.append(
                    {
                        "sender_email": sender_email,
                        "sender_name": name,
                        "domain": domain,
                        "first_email_date": first_date,
                        "email_count": count,
                    }
                )

        first_time_senders.sort(key=lambda x: x["first_email_date"], reverse=True)
        return first_time_senders

    def get_reputation_stats(self, profiles: List[SenderProfile]) -> Dict:
        """
        Compute aggregate statistics from a list of sender profiles.

        Args:
            profiles: List of SenderProfile instances.

        Returns:
            Dict with keys:
            - total_senders: int
            - by_level: dict mapping level to count
            - avg_reputation_score: float
            - automated_count: int
            - top_senders: list of top 10 senders by reputation
            - suspicious_senders: list of senders below suspicious threshold
            - avg_reply_rate: float
            - avg_read_rate: float
        """
        if not profiles:
            return {
                "total_senders": 0,
                "by_level": {
                    "trusted": 0,
                    "neutral": 0,
                    "suspicious": 0,
                    "unknown": 0,
                },
                "avg_reputation_score": 0.0,
                "automated_count": 0,
                "top_senders": [],
                "suspicious_senders": [],
                "avg_reply_rate": 0.0,
                "avg_read_rate": 0.0,
            }

        by_level = defaultdict(int)
        total_score = 0.0
        automated_count = 0
        total_reply_rate = 0.0
        total_read_rate = 0.0

        for profile in profiles:
            by_level[profile.reputation_level] += 1
            total_score += profile.reputation_score
            total_reply_rate += profile.reply_rate
            total_read_rate += profile.read_rate
            if profile.is_automated:
                automated_count += 1

        total = len(profiles)
        sorted_profiles = sorted(
            profiles, key=lambda p: p.reputation_score, reverse=True
        )

        top_senders = [
            {
                "sender_email": p.sender_email,
                "sender_name": p.sender_name,
                "reputation_score": round(p.reputation_score, 1),
                "reputation_level": p.reputation_level,
            }
            for p in sorted_profiles[:10]
        ]

        suspicious_senders = [
            {
                "sender_email": p.sender_email,
                "sender_name": p.sender_name,
                "reputation_score": round(p.reputation_score, 1),
                "domain": p.domain,
                "total_emails": p.total_emails,
            }
            for p in profiles
            if p.reputation_score < self.SUSPICIOUS_THRESHOLD
        ]

        return {
            "total_senders": total,
            "by_level": {
                "trusted": by_level.get("trusted", 0),
                "neutral": by_level.get("neutral", 0),
                "suspicious": by_level.get("suspicious", 0),
                "unknown": by_level.get("unknown", 0),
            },
            "avg_reputation_score": round(total_score / total, 1),
            "automated_count": automated_count,
            "top_senders": top_senders,
            "suspicious_senders": suspicious_senders,
            "avg_reply_rate": round(total_reply_rate / total, 3),
            "avg_read_rate": round(total_read_rate / total, 3),
        }

    def _aggregate_sender_data(
        self, emails: List[Dict], user_email: str
    ) -> Dict[str, Dict]:
        """Group emails by sender and compute per-sender statistics."""
        sender_data: Dict[str, Dict] = {}

        for email in emails:
            sender_email = self._extract_email(email.get("sender", email.get("from", "")))
            if not sender_email:
                continue

            if sender_email not in sender_data:
                sender_data[sender_email] = {
                    "sender_name": self._extract_name(email.get("sender", email.get("from", ""))),
                    "emails": [],
                    "dates": [],
                    "replied_count": 0,
                    "read_count": 0,
                    "total_count": 0,
                    "auth_pass_count": 0,
                    "auth_total_count": 0,
                }

            data = sender_data[sender_email]
            data["emails"].append(email)
            data["total_count"] += 1

            email_date = self._parse_date(email.get("date", ""))
            if email_date:
                data["dates"].append(email_date)

            if email.get("replied", False):
                data["replied_count"] += 1

            if email.get("read", False) or email.get("is_read", False):
                data["read_count"] += 1

            # Check authentication headers
            auth_result = self._check_authentication(email)
            if auth_result is not None:
                data["auth_total_count"] += 1
                if auth_result:
                    data["auth_pass_count"] += 1

        # Also check if user replied by looking at "to" field referencing sender
        if user_email:
            self._detect_replies_from_sent(emails, sender_data, user_email)

        return sender_data

    def _detect_replies_from_sent(
        self, emails: List[Dict], sender_data: Dict[str, Dict], user_email: str
    ):
        """
        Detect replies by checking if the user sent emails to known senders.
        Looks at emails where the from field matches user_email.
        """
        for email in emails:
            from_email = self._extract_email(email.get("sender", email.get("from", "")))
            if from_email and from_email.lower() == user_email.lower():
                to_field = email.get("to", "")
                to_emails = self._extract_all_emails(to_field)
                for to_email in to_emails:
                    if to_email in sender_data:
                        sender_data[to_email]["replied_count"] += 1

    def _build_profile(self, sender_email: str, data: Dict) -> SenderProfile:
        """Build a SenderProfile from aggregated sender data."""
        dates = sorted(data["dates"]) if data["dates"] else []
        first_seen = dates[0] if dates else None
        last_seen = dates[-1] if dates else None
        total = data["total_count"]

        # Calculate rates
        reply_rate = data["replied_count"] / total if total > 0 else 0.0
        read_rate = data["read_count"] / total if total > 0 else 0.0

        # Calculate frequency
        avg_per_week = self._calc_avg_per_week(dates)

        # Calculate individual score components
        frequency_score = self._score_frequency(avg_per_week, total)
        reply_score = self._score_reply_rate(reply_rate)
        auth_score = self._score_authentication(data)
        age_score = self._score_relationship_age(first_seen)
        read_score = self._score_read_rate(read_rate)

        # Weighted reputation score
        reputation_score = (
            self.WEIGHT_FREQUENCY * frequency_score
            + self.WEIGHT_REPLY_RATE * reply_score
            + self.WEIGHT_AUTH * auth_score
            + self.WEIGHT_AGE * age_score
            + self.WEIGHT_READ_RATE * read_score
        )

        # Clamp to 0-100
        reputation_score = max(0.0, min(100.0, reputation_score))

        # Determine level
        reputation_level = self._determine_level(reputation_score)

        # Detect automation
        is_automated = self._is_automated_sender(sender_email, data)

        profile = SenderProfile(
            sender_email=sender_email,
            sender_name=data.get("sender_name", ""),
            reputation_score=round(reputation_score, 1),
            reputation_level=reputation_level,
            total_emails=total,
            first_seen=first_seen,
            last_seen=last_seen,
            reply_rate=round(reply_rate, 3),
            read_rate=round(read_rate, 3),
            avg_emails_per_week=round(avg_per_week, 2),
            is_automated=is_automated,
        )

        return profile

    def _score_frequency(self, avg_per_week: float, total: int) -> float:
        """
        Score based on email frequency.

        Moderate, consistent frequency is ideal. Very high frequency
        (potential spam) or very low frequency (unknown sender) score lower.
        """
        if total == 0:
            return 0.0

        if avg_per_week <= 0:
            return 20.0

        # Sweet spot is 1-5 emails per week
        if 0.5 <= avg_per_week <= 5.0:
            return 80.0 + min(20.0, total * 2.0)
        elif 5.0 < avg_per_week <= 15.0:
            # Moderately high - could be mailing list
            return 60.0
        elif avg_per_week > 15.0:
            # Very high frequency - likely spam or aggressive automation
            return max(10.0, 50.0 - (avg_per_week - 15.0) * 2.0)
        else:
            # Very low frequency
            return 40.0 + min(30.0, total * 5.0)

    def _score_reply_rate(self, reply_rate: float) -> float:
        """
        Score based on how often the user replies to this sender.
        Higher reply rate indicates a trusted, engaged relationship.
        """
        # Scale: 0% replies = 20, 50%+ replies = 100
        return min(100.0, 20.0 + reply_rate * 160.0)

    def _score_authentication(self, data: Dict) -> float:
        """
        Score based on SPF/DKIM authentication pass rate.
        No auth data defaults to a neutral score.
        """
        if data["auth_total_count"] == 0:
            return 50.0  # Neutral if no auth data available

        pass_rate = data["auth_pass_count"] / data["auth_total_count"]
        # 100% pass = 100 score, 0% pass = 0 score
        return pass_rate * 100.0

    # Age score tiers: (max_days, base_score, multiplier, offset)
    # Score = base_score + (age_days - offset) * multiplier
    _AGE_SCORE_TIERS = [
        (0, 10.0, 0, 0),       # age_days <= 0: return 10.0
        (7, 20.0, 3.0, 0),     # age_days < 7: return 20.0 + age_days * 3.0
        (30, 40.0, 1.5, 7),    # age_days < 30: return 40.0 + (age_days - 7) * 1.5
        (90, 75.0, 0.3, 30),   # age_days < 90: return 75.0 + (age_days - 30) * 0.3
        (365, 90.0, 0.02, 90), # age_days < 365: return 90.0 + min(5.0, (age_days - 90) * 0.02)
    ]

    def _score_relationship_age(self, first_seen: Optional[datetime]) -> float:
        """
        Score based on how long the sender has been known.
        Longer relationships indicate more trust.
        """
        if first_seen is None:
            return 30.0

        age_days = (datetime.now() - first_seen).days

        for max_days, base, mult, offset in self._AGE_SCORE_TIERS:
            if age_days <= max_days if max_days == 0 else age_days < max_days:
                score = base + (age_days - offset) * mult
                # Cap the 365-day tier at 5.0 additional points
                if max_days == 365:
                    score = base + min(5.0, (age_days - offset) * mult)
                return score
        return 100.0

    def _score_read_rate(self, read_rate: float) -> float:
        """
        Score based on how often the user reads emails from this sender.
        Higher read rate indicates relevance and engagement.
        """
        # Scale: 0% read = 10, 100% read = 100
        return 10.0 + read_rate * 90.0

    def _determine_level(self, score: float) -> str:
        """Categorize sender based on reputation score."""
        if score >= self.TRUSTED_THRESHOLD:
            return "trusted"
        elif score >= self.NEUTRAL_THRESHOLD:
            return "neutral"
        elif score >= self.SUSPICIOUS_THRESHOLD:
            return "suspicious"
        else:
            return "unknown"

    def _is_automated_sender(self, sender_email: str, data: Dict) -> bool:
        """
        Detect if a sender is likely automated (newsletters, notifications, etc.).
        Uses email patterns and behavioral signals.
        """
        email_lower = sender_email.lower()

        # Check against known automated patterns
        for pattern in self.AUTOMATED_PATTERNS:
            if re.match(pattern, email_lower):
                return True

        # Behavioral heuristic: very consistent timing or very high volume
        # with zero replies suggests automation
        if data["total_count"] >= 10 and data["replied_count"] == 0:
            avg_per_week = self._calc_avg_per_week(data["dates"])
            if avg_per_week > 3.0:
                return True

        return False

    def _calc_avg_per_week(self, dates: List[datetime]) -> float:
        """Calculate average emails per week from a list of dates."""
        if len(dates) < 2:
            return float(len(dates))

        sorted_dates = sorted(dates)
        span = (sorted_dates[-1] - sorted_dates[0]).days
        if span <= 0:
            return float(len(dates))

        weeks = span / 7.0
        if weeks < 1.0:
            weeks = 1.0

        return len(dates) / weeks

    def _check_authentication(self, email: Dict) -> Optional[bool]:
        """
        Check SPF/DKIM authentication results from email headers.

        Returns True if passed, False if failed, None if no auth data found.
        """
        headers = email.get("headers", {})

        # Check Authentication-Results header
        auth_results = headers.get("Authentication-Results", "")
        if not auth_results:
            auth_results = headers.get("authentication-results", "")

        if not auth_results:
            # Check individual SPF/DKIM headers
            spf = headers.get("Received-SPF", "") or headers.get("received-spf", "")
            dkim = (
                headers.get("DKIM-Signature", "")
                or headers.get("dkim-signature", "")
            )
            if not spf and not dkim:
                return None
            if spf:
                return "pass" in spf.lower()
            return True if dkim else None

        auth_lower = auth_results.lower()
        spf_pass = "spf=pass" in auth_lower
        dkim_pass = "dkim=pass" in auth_lower

        spf_fail = "spf=fail" in auth_lower or "spf=softfail" in auth_lower
        dkim_fail = "dkim=fail" in auth_lower

        if spf_pass or dkim_pass:
            return True
        if spf_fail or dkim_fail:
            return False

        return None

    def _extract_email(self, from_field: str) -> str:
        """Extract email address from a From header value."""
        if not from_field:
            return ""

        # Try to find email in angle brackets: "Name <email@domain.com>"
        match = re.search(r"<([^>]+)>", from_field)
        if match:
            return match.group(1).lower().strip()

        # Try bare email address
        match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", from_field)
        if match:
            return match.group(0).lower().strip()

        return from_field.strip().lower()

    def _extract_name(self, from_field: str) -> str:
        """Extract display name from a From header value."""
        if not from_field:
            return ""

        # "Name <email>" format
        match = re.match(r"^(.+?)\s*<[^>]+>", from_field)
        if match:
            name = match.group(1).strip().strip('"').strip("'")
            return name

        return ""

    def _extract_all_emails(self, field: str) -> List[str]:
        """Extract all email addresses from a header field (To, Cc, etc.)."""
        if not field:
            return []

        emails = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", field)
        return [e.lower() for e in emails]

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string into a datetime object."""
        if not date_str:
            return None

        if isinstance(date_str, datetime):
            return date_str

        # Common email date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S",
        ]

        # Strip trailing timezone name in parentheses like "(UTC)"
        cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", date_str.strip())

        for fmt in formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
                # Convert to naive datetime for consistent comparison
                return dt.replace(tzinfo=None)
            except (ValueError, TypeError):
                continue

        return None
