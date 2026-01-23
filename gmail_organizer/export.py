"""Email data export module.

Exports email data in various formats including CSV, JSON, and MBOX.
Supports filtered subsets and generates export summary statistics.
"""

import csv
import json
import os
import io
from datetime import datetime
from typing import Dict, List, Optional
from collections import Counter


class EmailExporter:
    """Exports email data in various formats."""

    DEFAULT_EXPORT_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".exports"
    )

    DEFAULT_CSV_FIELDS = ["sender", "subject", "date", "category", "labels"]

    def __init__(self, export_dir: str = None):
        """Initialize the EmailExporter.

        Args:
            export_dir: Directory for export files. Defaults to .exports/ in project root.
        """
        self.export_dir = export_dir or self.DEFAULT_EXPORT_DIR
        os.makedirs(self.export_dir, exist_ok=True)

    def _resolve_filepath(self, filepath: str) -> str:
        """Resolve filepath, using export_dir as base if path is relative.

        Ensures the resolved path stays within export_dir to prevent
        path traversal attacks.

        Args:
            filepath: The target file path.

        Returns:
            Absolute file path within export_dir.

        Raises:
            ValueError: If the resolved path escapes export_dir.
        """
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.export_dir, filepath)
        # Resolve any ".." components and check containment
        resolved = os.path.realpath(filepath)
        export_real = os.path.realpath(self.export_dir)
        if not resolved.startswith(export_real + os.sep) and resolved != export_real:
            raise ValueError(
                f"Path '{filepath}' resolves outside export directory"
            )
        parent_dir = os.path.dirname(resolved)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        return resolved

    def _sanitize_csv_value(self, value: str) -> str:
        """Sanitize a value to prevent CSV injection.

        Prefixes values starting with formula characters (=, +, -, @, |)
        with a single quote to prevent execution in spreadsheet applications.

        Args:
            value: The cell value to sanitize.

        Returns:
            Sanitized value safe for CSV export.
        """
        if value and value[0] in ('=', '+', '-', '@', '|'):
            return "'" + value
        return value

    def filter_emails(
        self,
        emails: List[Dict],
        category: str = None,
        sender: str = None,
        date_from: str = None,
        date_to: str = None,
    ) -> List[Dict]:
        """Filter emails by category, sender, or date range.

        Args:
            emails: List of email dictionaries.
            category: Filter by category name.
            sender: Filter by sender (substring match, case-insensitive).
            date_from: Filter emails on or after this date (ISO format YYYY-MM-DD).
            date_to: Filter emails on or before this date (ISO format YYYY-MM-DD).

        Returns:
            Filtered list of email dictionaries.
        """
        filtered = list(emails)

        if category:
            filtered = [
                e for e in filtered
                if e.get("category", "").lower() == category.lower()
            ]

        if sender:
            sender_lower = sender.lower()
            filtered = [
                e for e in filtered
                if sender_lower in e.get("sender", "").lower()
            ]

        if date_from:
            filtered = [
                e for e in filtered
                if self._parse_date(e.get("date", "")) >= self._parse_date(date_from)
            ]

        if date_to:
            filtered = [
                e for e in filtered
                if self._parse_date(e.get("date", "")) <= self._parse_date(date_to)
            ]

        return filtered

    def _parse_date(self, date_str: str) -> datetime:
        """Parse a date string, trying multiple formats.

        Args:
            date_str: Date string to parse.

        Returns:
            Parsed datetime object, or datetime.min if parsing fails.
        """
        if not date_str:
            return datetime.min

        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %z",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue

        return datetime.min

    def export_csv(
        self,
        emails: List[Dict],
        filepath: str,
        fields: List[str] = None,
    ) -> str:
        """Export emails to CSV format.

        Args:
            emails: List of email dictionaries.
            filepath: Output file path (relative to export_dir or absolute).
            fields: List of field names to include. Defaults to DEFAULT_CSV_FIELDS.

        Returns:
            Absolute path of the created CSV file.
        """
        filepath = self._resolve_filepath(filepath)
        fields = fields or self.DEFAULT_CSV_FIELDS

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for email in emails:
                row = {}
                for field in fields:
                    value = email.get(field, "")
                    if isinstance(value, list):
                        value = "; ".join(str(v) for v in value)
                    row[field] = self._sanitize_csv_value(str(value))
                writer.writerow(row)

        return filepath

    def export_json(
        self,
        emails: List[Dict],
        filepath: str,
        pretty: bool = True,
    ) -> str:
        """Export emails to JSON format.

        Args:
            emails: List of email dictionaries.
            filepath: Output file path (relative to export_dir or absolute).
            pretty: Whether to format JSON with indentation.

        Returns:
            Absolute path of the created JSON file.
        """
        filepath = self._resolve_filepath(filepath)

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total_emails": len(emails),
            "emails": emails,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(export_data, f, ensure_ascii=False, default=str)

        return filepath

    def export_mbox(self, emails: List[Dict], filepath: str) -> str:
        """Export emails to MBOX format.

        Creates a text-based MBOX file using the standard From_ line separator.
        Each message is separated by a blank line followed by a From_ line.

        Args:
            emails: List of email dictionaries.
            filepath: Output file path (relative to export_dir or absolute).

        Returns:
            Absolute path of the created MBOX file.
        """
        filepath = self._resolve_filepath(filepath)

        with open(filepath, "w", encoding="utf-8") as f:
            for email in emails:
                sender = email.get("sender", "unknown@unknown.com")
                # Extract email address from "Name <email>" format
                sender_addr = self._extract_email_address(sender)
                date_str = email.get("date", "")
                mbox_date = self._format_mbox_date(date_str)

                # From_ line (note the space after "From")
                f.write("From {} {}\n".format(sender_addr, mbox_date))

                # Headers (sanitize to prevent header injection via newlines)
                f.write("From: {}\n".format(self._sanitize_header(email.get("sender", ""))))
                f.write("To: {}\n".format(self._sanitize_header(email.get("to", ""))))
                f.write("Subject: {}\n".format(self._sanitize_header(email.get("subject", ""))))
                f.write("Date: {}\n".format(self._sanitize_header(date_str)))

                if email.get("message_id"):
                    f.write("Message-ID: {}\n".format(email["message_id"]))

                if email.get("labels"):
                    labels = email["labels"]
                    if isinstance(labels, list):
                        labels = ", ".join(labels)
                    f.write("X-Gmail-Labels: {}\n".format(labels))

                if email.get("category"):
                    f.write("X-Category: {}\n".format(email["category"]))

                # Blank line separating headers from body
                f.write("\n")

                # Body - escape any lines starting with "From "
                body = email.get("body", email.get("snippet", ""))
                if body:
                    for line in body.splitlines():
                        if line.startswith("From "):
                            f.write(">" + line + "\n")
                        else:
                            f.write(line + "\n")

                # Blank line after message
                f.write("\n")

        return filepath

    def _sanitize_header(self, value: str) -> str:
        """Remove newlines from header values to prevent header injection."""
        return value.replace('\r', '').replace('\n', ' ')

    def _extract_email_address(self, sender: str) -> str:
        """Extract email address from a sender string.

        Handles formats like:
            - "user@example.com"
            - "Display Name <user@example.com>"

        Args:
            sender: Sender string.

        Returns:
            The extracted email address.
        """
        if "<" in sender and ">" in sender:
            start = sender.index("<") + 1
            end = sender.index(">")
            return sender[start:end]
        return sender.strip()

    def _format_mbox_date(self, date_str: str) -> str:
        """Format a date string for the MBOX From_ line.

        The MBOX format uses asctime format: "Day Mon DD HH:MM:SS YYYY"

        Args:
            date_str: Date string to format.

        Returns:
            Formatted date string for MBOX From_ line.
        """
        dt = self._parse_date(date_str)
        if dt == datetime.min:
            dt = datetime.now()
        return dt.strftime("%a %b %d %H:%M:%S %Y")

    def export_summary(self, emails: List[Dict]) -> Dict:
        """Generate summary statistics for a list of emails.

        Args:
            emails: List of email dictionaries.

        Returns:
            Dictionary containing summary statistics:
                - total_emails: Total number of emails
                - categories: Counter of emails per category
                - top_senders: Top 10 senders by email count
                - date_range: Dict with earliest and latest dates
                - labels: Counter of label occurrences
                - avg_subject_length: Average length of subject lines
        """
        if not emails:
            return {
                "total_emails": 0,
                "categories": {},
                "top_senders": [],
                "date_range": {"earliest": None, "latest": None},
                "labels": {},
                "avg_subject_length": 0,
            }

        categories = Counter()
        senders = Counter()
        labels = Counter()
        dates = []
        subject_lengths = []

        for email in emails:
            # Categories
            category = email.get("category", "uncategorized")
            categories[category] += 1

            # Senders
            sender = email.get("sender", "unknown")
            senders[sender] += 1

            # Labels
            email_labels = email.get("labels", [])
            if isinstance(email_labels, str):
                email_labels = [email_labels]
            for label in email_labels:
                labels[label] += 1

            # Dates
            date_str = email.get("date", "")
            if date_str:
                parsed = self._parse_date(date_str)
                if parsed != datetime.min:
                    dates.append(parsed)

            # Subject lengths
            subject = email.get("subject", "")
            subject_lengths.append(len(subject))

        # Date range
        date_range = {"earliest": None, "latest": None}
        if dates:
            date_range["earliest"] = min(dates).isoformat()
            date_range["latest"] = max(dates).isoformat()

        # Average subject length
        avg_subject_length = (
            sum(subject_lengths) / len(subject_lengths)
            if subject_lengths
            else 0
        )

        return {
            "total_emails": len(emails),
            "categories": dict(categories.most_common()),
            "top_senders": senders.most_common(10),
            "date_range": date_range,
            "labels": dict(labels.most_common()),
            "avg_subject_length": round(avg_subject_length, 1),
        }

    def get_export_size_estimate(self, emails: List[Dict], format: str) -> int:
        """Estimate the file size of an export in bytes.

        Provides an approximation of the output file size without
        actually writing to disk.

        Args:
            emails: List of email dictionaries.
            format: Export format - one of "csv", "json", or "mbox".

        Returns:
            Estimated file size in bytes.

        Raises:
            ValueError: If format is not recognized.
        """
        if not emails:
            return 0

        format_lower = format.lower()

        if format_lower == "csv":
            return self._estimate_csv_size(emails)
        elif format_lower == "json":
            return self._estimate_json_size(emails)
        elif format_lower == "mbox":
            return self._estimate_mbox_size(emails)
        else:
            raise ValueError(
                "Unsupported format '{}'. Use 'csv', 'json', or 'mbox'.".format(format)
            )

    def _estimate_csv_size(self, emails: List[Dict]) -> int:
        """Estimate CSV export size in bytes."""
        buf = io.StringIO()
        fields = self.DEFAULT_CSV_FIELDS
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()

        # Estimate from a sample (up to 10 emails) then extrapolate
        sample_size = min(10, len(emails))
        for email in emails[:sample_size]:
            row = {}
            for field in fields:
                value = email.get(field, "")
                if isinstance(value, list):
                    value = "; ".join(str(v) for v in value)
                row[field] = value
            writer.writerow(row)

        sample_bytes = len(buf.getvalue().encode("utf-8"))
        header_size = len(",".join(fields).encode("utf-8")) + 1

        if sample_size > 0:
            avg_row_size = (sample_bytes - header_size) / sample_size
            return int(header_size + avg_row_size * len(emails))
        return header_size

    def _estimate_json_size(self, emails: List[Dict]) -> int:
        """Estimate JSON export size in bytes."""
        # Estimate using a sample
        sample_size = min(5, len(emails))
        if sample_size == 0:
            return 0

        sample_data = {
            "exported_at": datetime.now().isoformat(),
            "total_emails": len(emails),
            "emails": emails[:sample_size],
        }
        sample_json = json.dumps(sample_data, indent=2, ensure_ascii=False, default=str)
        sample_bytes = len(sample_json.encode("utf-8"))

        # Subtract wrapper overhead, calculate per-email size, extrapolate
        wrapper_overhead = 100  # approximate overhead for metadata
        email_bytes = sample_bytes - wrapper_overhead
        avg_email_size = email_bytes / sample_size

        return int(wrapper_overhead + avg_email_size * len(emails))

    def _estimate_mbox_size(self, emails: List[Dict]) -> int:
        """Estimate MBOX export size in bytes."""
        total = 0
        sample_size = min(10, len(emails))

        for email in emails[:sample_size]:
            # From_ line
            total += 50
            # Headers (From, To, Subject, Date, etc.)
            total += len(email.get("sender", "").encode("utf-8")) + 10
            total += len(email.get("to", "").encode("utf-8")) + 10
            total += len(email.get("subject", "").encode("utf-8")) + 15
            total += len(email.get("date", "").encode("utf-8")) + 10
            # Body
            body = email.get("body", email.get("snippet", ""))
            total += len(body.encode("utf-8")) if body else 0
            # Separators
            total += 5

        if sample_size > 0:
            avg_size = total / sample_size
            return int(avg_size * len(emails))
        return 0
