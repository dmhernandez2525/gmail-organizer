"""
Storage analysis module for Gmail Organizer.

Analyzes email storage usage, breaks down consumption by various dimensions,
identifies largest emails, and provides cleanup recommendations.
"""

from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
from email.utils import parseaddr
from typing import Dict, List, Tuple


@dataclass
class StorageReport:
    """Report containing storage usage analysis results."""

    total_size_bytes: int = 0
    total_size_mb: float = 0.0
    by_sender: List[Tuple[str, int]] = field(default_factory=list)
    by_domain: List[Tuple[str, int]] = field(default_factory=list)
    by_label: Dict[str, int] = field(default_factory=dict)
    by_year: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    avg_email_size_kb: float = 0.0
    largest_emails: List[Dict] = field(default_factory=list)
    emails_with_attachments: int = 0


class StorageAnalyzer:
    """Analyzes email storage usage and provides cleanup recommendations."""

    # Threshold constants for cleanup suggestions
    LARGE_EMAIL_THRESHOLD_MB = 5.0
    LARGE_SENDER_THRESHOLD_MB = 50.0
    OLD_EMAIL_YEARS = 3
    ATTACHMENT_RATIO_THRESHOLD = 0.5

    def analyze_storage(self, emails: List[Dict]) -> StorageReport:
        """
        Analyze storage usage across all provided emails.

        Args:
            emails: List of email message dicts, each potentially containing
                    'sizeEstimate', 'payload' (with headers), 'labelIds',
                    'internalDate', and other Gmail API fields.

        Returns:
            A StorageReport dataclass with full breakdown of storage usage.
        """
        if not emails:
            return StorageReport()

        total_size = 0
        sender_sizes: Dict[str, int] = defaultdict(int)
        domain_sizes: Dict[str, int] = defaultdict(int)
        label_sizes: Dict[str, int] = defaultdict(int)
        year_sizes: Dict[str, int] = defaultdict(int)
        category_sizes: Dict[str, int] = defaultdict(int)
        emails_with_attachments = 0

        for email in emails:
            size = email.get("sizeEstimate", 0)
            total_size += size

            # Extract sender
            sender = self._extract_sender(email)
            if sender:
                sender_sizes[sender] += size
                domain = self._extract_domain(sender)
                if domain:
                    domain_sizes[domain] += size

            # Extract labels
            labels = email.get("labelIds", [])
            for label in labels:
                label_sizes[label] += size

            # Extract category from labels
            category = self._extract_category(labels)
            category_sizes[category] += size

            # Extract year from internalDate
            year = self._extract_year(email)
            if year:
                year_sizes[year] += size

            # Check for attachments
            if self._has_attachments(email):
                emails_with_attachments += 1

        # Sort senders and domains by size descending
        sorted_senders = sorted(sender_sizes.items(), key=lambda x: x[1], reverse=True)
        sorted_domains = sorted(domain_sizes.items(), key=lambda x: x[1], reverse=True)

        # Get largest emails
        largest = self.get_largest_emails(emails)

        # Build report
        report = StorageReport(
            total_size_bytes=total_size,
            total_size_mb=total_size / (1024 * 1024),
            by_sender=sorted_senders[:50],
            by_domain=sorted_domains[:50],
            by_label=dict(sorted(label_sizes.items(), key=lambda x: x[1], reverse=True)),
            by_year=dict(sorted(year_sizes.items(), key=lambda x: x[0])),
            by_category=dict(sorted(category_sizes.items(), key=lambda x: x[1], reverse=True)),
            avg_email_size_kb=(total_size / len(emails) / 1024) if emails else 0.0,
            largest_emails=largest,
            emails_with_attachments=emails_with_attachments,
        )

        return report

    def get_largest_emails(self, emails: List[Dict], limit: int = 20) -> List[Dict]:
        """
        Find the largest emails by size.

        Args:
            emails: List of email message dicts.
            limit: Maximum number of results to return.

        Returns:
            List of dicts with email summary info, sorted by size descending.
        """
        if not emails:
            return []

        email_sizes = []
        for email in emails:
            size = email.get("sizeEstimate", 0)
            sender = self._extract_sender(email)
            subject = self._extract_subject(email)
            date = self._extract_date_str(email)
            msg_id = email.get("email_id", "")

            email_sizes.append({
                "id": msg_id,
                "sender": sender,
                "subject": subject,
                "date": date,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "has_attachments": self._has_attachments(email),
            })

        email_sizes.sort(key=lambda x: x["size_bytes"], reverse=True)
        return email_sizes[:limit]

    def get_cleanup_suggestions(self, report: StorageReport) -> List[str]:
        """
        Generate actionable cleanup recommendations based on the storage report.

        Args:
            report: A completed StorageReport from analyze_storage().

        Returns:
            List of human-readable suggestion strings.
        """
        suggestions = []

        if not report.total_size_bytes:
            return ["No emails to analyze. Storage appears empty."]

        # Suggestion: large emails with attachments
        large_emails = [
            e for e in report.largest_emails
            if e["size_mb"] >= self.LARGE_EMAIL_THRESHOLD_MB
        ]
        if large_emails:
            total_large_mb = sum(e["size_mb"] for e in large_emails)
            suggestions.append(
                f"Found {len(large_emails)} emails larger than "
                f"{self.LARGE_EMAIL_THRESHOLD_MB} MB (total: {total_large_mb:.1f} MB). "
                f"Consider downloading attachments and removing these emails."
            )

        # Suggestion: top storage-consuming senders
        if report.by_sender:
            top_sender, top_sender_size = report.by_sender[0]
            top_sender_mb = top_sender_size / (1024 * 1024)
            if top_sender_mb >= self.LARGE_SENDER_THRESHOLD_MB:
                suggestions.append(
                    f"The sender '{top_sender}' uses {top_sender_mb:.1f} MB of storage. "
                    f"Consider unsubscribing or bulk-deleting old messages from this sender."
                )

        # Suggestion: high-volume senders (top 5 using significant storage)
        heavy_senders = [
            (sender, size) for sender, size in report.by_sender[:10]
            if size / (1024 * 1024) >= 10.0
        ]
        if len(heavy_senders) > 1:
            total_heavy_mb = sum(s / (1024 * 1024) for _, s in heavy_senders)
            pct = (total_heavy_mb / report.total_size_mb * 100) if report.total_size_mb else 0
            suggestions.append(
                f"Top {len(heavy_senders)} senders consume {total_heavy_mb:.1f} MB "
                f"({pct:.0f}% of total storage). Review these for bulk cleanup opportunities."
            )

        # Suggestion: old emails
        current_year = datetime.now().year
        old_years_size = sum(
            size for year_str, size in report.by_year.items()
            if self._parse_year_int(year_str) and
            (current_year - self._parse_year_int(year_str)) >= self.OLD_EMAIL_YEARS
        )
        if old_years_size:
            old_mb = old_years_size / (1024 * 1024)
            pct = (old_mb / report.total_size_mb * 100) if report.total_size_mb else 0
            suggestions.append(
                f"Emails older than {self.OLD_EMAIL_YEARS} years use {old_mb:.1f} MB "
                f"({pct:.0f}% of storage). Consider archiving or deleting old messages."
            )

        # Suggestion: attachments ratio
        if report.emails_with_attachments:
            total_emails = (
                report.total_size_bytes / (report.avg_email_size_kb * 1024)
                if report.avg_email_size_kb else 0
            )
            if total_emails > 0:
                attachment_ratio = report.emails_with_attachments / total_emails
                if attachment_ratio >= self.ATTACHMENT_RATIO_THRESHOLD:
                    suggestions.append(
                        f"{report.emails_with_attachments} emails contain attachments "
                        f"({attachment_ratio * 100:.0f}% of all emails). "
                        f"Downloading and removing attachments can significantly reduce storage."
                    )

        # Suggestion: promotional/social categories
        promo_size = report.by_category.get("PROMOTIONS", 0)
        social_size = report.by_category.get("SOCIAL", 0)
        junk_size = promo_size + social_size
        if junk_size:
            junk_mb = junk_size / (1024 * 1024)
            if junk_mb >= 10.0:
                suggestions.append(
                    f"Promotional and social emails use {junk_mb:.1f} MB. "
                    f"Consider bulk-deleting these categories or setting up auto-delete filters."
                )

        # Suggestion: trash and spam
        trash_size = report.by_label.get("TRASH", 0)
        spam_size = report.by_label.get("SPAM", 0)
        recoverable = trash_size + spam_size
        if recoverable:
            recoverable_mb = recoverable / (1024 * 1024)
            if recoverable_mb >= 1.0:
                suggestions.append(
                    f"Trash and spam contain {recoverable_mb:.1f} MB. "
                    f"Empty trash and spam to immediately reclaim this space."
                )

        # Suggestion: domain-level cleanup
        if report.by_domain:
            top_domain, top_domain_size = report.by_domain[0]
            top_domain_mb = top_domain_size / (1024 * 1024)
            if top_domain_mb >= self.LARGE_SENDER_THRESHOLD_MB:
                suggestions.append(
                    f"The domain '{top_domain}' uses {top_domain_mb:.1f} MB. "
                    f"Consider reviewing all senders from this domain for cleanup."
                )

        # General summary suggestion
        if report.total_size_mb >= 100:
            suggestions.append(
                f"Total email storage is {report.total_size_mb:.1f} MB. "
                f"Average email size is {report.avg_email_size_kb:.1f} KB. "
                f"Focus on large emails and top senders for maximum impact."
            )

        if not suggestions:
            suggestions.append(
                "Storage usage appears reasonable. No immediate cleanup actions needed."
            )

        return suggestions

    def _extract_sender(self, email: Dict) -> str:
        """Extract the sender email address from an email message dict."""
        payload = email.get("payload", {})
        headers = payload.get("headers", [])
        for header in headers:
            if header.get("name", "").lower() == "from":
                value = header.get("value", "")
                _, addr = parseaddr(value)
                return addr if addr else value
        return ""

    def _extract_subject(self, email: Dict) -> str:
        """Extract the subject from an email message dict."""
        payload = email.get("payload", {})
        headers = payload.get("headers", [])
        for header in headers:
            if header.get("name", "").lower() == "subject":
                return header.get("value", "(no subject)")
        return "(no subject)"

    def _extract_domain(self, sender: str) -> str:
        """Extract the domain portion of an email address."""
        if "@" in sender:
            return sender.split("@", 1)[1].lower()
        return ""

    def _extract_category(self, labels: List[str]) -> str:
        """Determine the category from Gmail label IDs."""
        category_labels = {
            "CATEGORY_PRIMARY": "PRIMARY",
            "CATEGORY_SOCIAL": "SOCIAL",
            "CATEGORY_PROMOTIONS": "PROMOTIONS",
            "CATEGORY_UPDATES": "UPDATES",
            "CATEGORY_FORUMS": "FORUMS",
        }
        for label in labels:
            if label in category_labels:
                return category_labels[label]
        return "UNCATEGORIZED"

    def _extract_year(self, email: Dict) -> str:
        """Extract the year from the email's internalDate (epoch ms)."""
        internal_date = email.get("internalDate")
        if internal_date:
            try:
                timestamp = int(internal_date) / 1000
                dt = datetime.fromtimestamp(timestamp)
                return str(dt.year)
            except (ValueError, TypeError, OSError):
                pass
        return ""

    def _extract_date_str(self, email: Dict) -> str:
        """Extract a human-readable date string from the email."""
        internal_date = email.get("internalDate")
        if internal_date:
            try:
                timestamp = int(internal_date) / 1000
                dt = datetime.fromtimestamp(timestamp)
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError, OSError):
                pass
        # Fallback to Date header
        payload = email.get("payload", {})
        headers = payload.get("headers", [])
        for header in headers:
            if header.get("name", "").lower() == "date":
                return header.get("value", "")
        return ""

    def _has_attachments(self, email: Dict) -> bool:
        """Check if the email has attachments based on payload structure."""
        payload = email.get("payload", {})
        parts = payload.get("parts", [])
        for part in parts:
            disposition = part.get("headers", [])
            # Check Content-Disposition header
            for header in disposition:
                if (header.get("name", "").lower() == "content-disposition"
                        and "attachment" in header.get("value", "").lower()):
                    return True
            # Check for attachment body
            body = part.get("body", {})
            if body.get("attachmentId"):
                return True
            # Recurse into nested parts
            nested_parts = part.get("parts", [])
            if nested_parts:
                nested_email = {"payload": {"parts": nested_parts}}
                if self._has_attachments(nested_email):
                    return True
        return False

    def _parse_year_int(self, year_str: str) -> int:
        """Safely parse a year string to int, returning 0 on failure."""
        try:
            return int(year_str)
        except (ValueError, TypeError):
            return 0
