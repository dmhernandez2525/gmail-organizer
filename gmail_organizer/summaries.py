"""Email summary generator for digest-style overviews of inbox activity."""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class EmailDigest:
    """A summary digest for a time period."""

    period_start: str
    period_end: str
    total_emails: int = 0
    total_threads: int = 0
    top_senders: List[Tuple[str, int]] = field(default_factory=list)
    top_subjects: List[str] = field(default_factory=list)
    category_breakdown: Dict[str, int] = field(default_factory=dict)
    highlights: List[Dict] = field(default_factory=list)
    action_items: List[Dict] = field(default_factory=list)
    trending_topics: List[Tuple[str, int]] = field(default_factory=list)
    busiest_hour: int = 0
    response_needed: int = 0


@dataclass
class ThreadSummary:
    """Summary of an email thread/conversation."""

    thread_id: str
    subject: str
    participants: List[str] = field(default_factory=list)
    message_count: int = 0
    date_range: str = ""
    last_sender: str = ""
    has_question: bool = False
    has_action_item: bool = False
    snippet: str = ""


class EmailSummarizer:
    """Generate digest summaries and thread overviews from email data."""

    ACTION_PATTERNS = [
        re.compile(r"\bplease\b.*\b(review|approve|send|update|confirm)\b", re.IGNORECASE),
        re.compile(r"\bneed(?:s|ed)?\s+(?:you|your)\b", re.IGNORECASE),
        re.compile(r"\baction\s+(?:required|needed|item)\b", re.IGNORECASE),
        re.compile(r"\bby\s+(?:end\s+of|eod|cob|tomorrow|monday|tuesday|wednesday|thursday|friday)\b", re.IGNORECASE),
        re.compile(r"\bdeadline\b", re.IGNORECASE),
        re.compile(r"\burgent(?:ly)?\b", re.IGNORECASE),
        re.compile(r"\basap\b", re.IGNORECASE),
    ]

    HIGHLIGHT_PATTERNS = [
        re.compile(r"\bimportant\b", re.IGNORECASE),
        re.compile(r"\bannounce(?:ment)?\b", re.IGNORECASE),
        re.compile(r"\bupdate(?:s)?\b", re.IGNORECASE),
        re.compile(r"\bmeeting\b", re.IGNORECASE),
        re.compile(r"\binvit(?:e|ation)\b", re.IGNORECASE),
        re.compile(r"\bconfirm(?:ation|ed)?\b", re.IGNORECASE),
    ]

    STOP_WORDS = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'has',
        'her', 'was', 'one', 'our', 'out', 'his', 'had', 'new', 'now', 'way',
        'may', 'day', 'too', 'use', 'how', 'its', 'let', 'get', 'got', 'did',
        'she', 'him', 'have', 'this', 'that', 'with', 'they', 'been', 'from',
        'your', 'will', 'more', 'when', 'what', 'some', 'than', 'them', 'into',
        'just', 'only', 'also', 'very', 'here', 'were', 'said', 'each', 'which',
        'their', 'about', 'would', 'there', 'could', 'other', 'after', 'these',
        'email', 'mail', 'sent', 'message', 'please', 'thanks', 'thank', 'regards',
        'hello', 'dear', 'best', 'kind', 'sincerely', 'cheers', 'fyi', 'fwd',
    }

    def generate_digest(
        self,
        emails: List[Dict],
        period: str = "daily",
        reference_date: Optional[str] = None,
    ) -> EmailDigest:
        """Generate a digest summary for a given time period.

        Args:
            emails: List of email dicts with 'date', 'sender', 'subject',
                    'body'/'snippet', 'threadId', 'labels', 'category' fields.
            period: One of "daily", "weekly", "monthly", or "custom".
            reference_date: ISO date string (YYYY-MM-DD) for the period end.
                           Defaults to today.

        Returns:
            An EmailDigest dataclass with the period summary.
        """
        now = datetime.now()
        if reference_date:
            try:
                now = datetime.strptime(reference_date, "%Y-%m-%d")
            except ValueError:
                pass

        period_start, period_end = self._get_period_range(now, period)
        period_emails = self._filter_by_date(emails, period_start, period_end)

        if not period_emails:
            return EmailDigest(
                period_start=period_start.strftime("%Y-%m-%d"),
                period_end=period_end.strftime("%Y-%m-%d"),
            )

        # Top senders
        sender_counts = Counter()
        for email in period_emails:
            sender = self._extract_sender(email)
            if sender:
                sender_counts[sender] += 1
        top_senders = sender_counts.most_common(10)

        # Thread count
        threads = set(e.get("threadId", e.get("id", "")) for e in period_emails)

        # Category breakdown
        category_counts = Counter()
        for email in period_emails:
            cat = email.get("category", "uncategorized")
            category_counts[cat] += 1

        # Highlights
        highlights = self._extract_highlights(period_emails)

        # Action items
        action_items = self._extract_action_items(period_emails)

        # Trending topics
        trending = self._extract_trending_topics(period_emails)

        # Busiest hour
        hour_counts = Counter()
        for email in period_emails:
            dt = self._parse_date(email.get("date", ""))
            if dt:
                hour_counts[dt.hour] += 1
        busiest_hour = hour_counts.most_common(1)[0][0] if hour_counts else 0

        # Response needed (questions directed at user)
        response_needed = len([
            e for e in period_emails
            if self._needs_response(e)
        ])

        # Top subjects (unique, most recent)
        seen_subjects = set()
        top_subjects = []
        for email in sorted(period_emails, key=lambda e: self._parse_date(e.get("date", "")) or datetime.min, reverse=True):
            subj = email.get("subject", "").strip()
            subj_normalized = re.sub(r"^(re|fwd|fw):\s*", "", subj, flags=re.IGNORECASE).strip().lower()
            if subj_normalized and subj_normalized not in seen_subjects:
                seen_subjects.add(subj_normalized)
                top_subjects.append(subj)
                if len(top_subjects) >= 10:
                    break

        return EmailDigest(
            period_start=period_start.strftime("%Y-%m-%d"),
            period_end=period_end.strftime("%Y-%m-%d"),
            total_emails=len(period_emails),
            total_threads=len(threads),
            top_senders=top_senders,
            top_subjects=top_subjects,
            category_breakdown=dict(category_counts.most_common()),
            highlights=highlights[:10],
            action_items=action_items[:10],
            trending_topics=trending[:10],
            busiest_hour=busiest_hour,
            response_needed=response_needed,
        )

    def summarize_threads(self, emails: List[Dict], limit: int = 20) -> List[ThreadSummary]:
        """Summarize email threads showing conversation overviews.

        Args:
            emails: List of email dicts with threadId, subject, sender/from, date.
            limit: Maximum number of thread summaries to return.

        Returns:
            List of ThreadSummary instances, sorted by recency.
        """
        threads: Dict[str, List[Dict]] = defaultdict(list)
        for email in emails:
            thread_id = email.get("threadId", email.get("id", ""))
            if thread_id:
                threads[thread_id].append(email)

        summaries = []
        for thread_id, thread_emails in threads.items():
            if len(thread_emails) < 2:
                continue

            sorted_emails = sorted(
                thread_emails,
                key=lambda e: self._parse_date(e.get("date", "")) or datetime.min
            )

            first = sorted_emails[0]
            last = sorted_emails[-1]

            participants = list(set(
                self._extract_sender(e) for e in sorted_emails
                if self._extract_sender(e)
            ))

            first_date = self._parse_date(first.get("date", ""))
            last_date = self._parse_date(last.get("date", ""))
            date_range = ""
            if first_date and last_date:
                date_range = f"{first_date.strftime('%b %d')} - {last_date.strftime('%b %d')}"

            combined_text = " ".join(
                (e.get("subject", "") or "") + " " + (e.get("snippet") or e.get("body") or "")
                for e in sorted_emails
            )

            summary = ThreadSummary(
                thread_id=thread_id,
                subject=first.get("subject", "(no subject)"),
                participants=participants,
                message_count=len(sorted_emails),
                date_range=date_range,
                last_sender=self._extract_sender(last),
                has_question="?" in combined_text,
                has_action_item=any(p.search(combined_text) for p in self.ACTION_PATTERNS),
                snippet=last.get("snippet", last.get("body", ""))[:150],
            )
            summaries.append(summary)

        # Sort by most recent last message
        summaries.sort(
            key=lambda s: s.message_count, reverse=True
        )

        return summaries[:limit]

    def get_sender_summary(self, emails: List[Dict], sender: str) -> Dict:
        """Get a summary of all emails from a specific sender.

        Args:
            emails: List of email dicts.
            sender: Sender email address or name to filter by.

        Returns:
            Dict with sender statistics and recent subjects.
        """
        sender_lower = sender.lower()
        sender_emails = [
            e for e in emails
            if sender_lower in self._extract_sender(e).lower()
        ]

        if not sender_emails:
            return {"sender": sender, "total": 0}

        dates = [
            self._parse_date(e.get("date", ""))
            for e in sender_emails
        ]
        dates = [d for d in dates if d]

        subjects = [e.get("subject", "") for e in sender_emails]
        categories = Counter(e.get("category", "uncategorized") for e in sender_emails)

        return {
            "sender": sender,
            "total": len(sender_emails),
            "first_seen": min(dates).strftime("%Y-%m-%d") if dates else "N/A",
            "last_seen": max(dates).strftime("%Y-%m-%d") if dates else "N/A",
            "recent_subjects": subjects[:5],
            "categories": dict(categories.most_common()),
            "avg_per_week": self._calc_weekly_avg(dates),
        }

    def _get_period_range(
        self, reference: datetime, period: str
    ) -> Tuple[datetime, datetime]:
        """Calculate the start and end datetime for a period."""
        if period == "daily":
            start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == "weekly":
            start = reference - timedelta(days=reference.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif period == "monthly":
            start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if reference.month == 12:
                end = start.replace(year=reference.year + 1, month=1)
            else:
                end = start.replace(month=reference.month + 1)
        else:
            # Default to last 7 days
            end = reference
            start = reference - timedelta(days=7)
        return start, end

    def _filter_by_date(
        self, emails: List[Dict], start: datetime, end: datetime
    ) -> List[Dict]:
        """Filter emails to those within the date range."""
        filtered = []
        for email in emails:
            dt = self._parse_date(email.get("date", ""))
            if dt and start <= dt <= end:
                filtered.append(email)
        return filtered

    def _extract_highlights(self, emails: List[Dict]) -> List[Dict]:
        """Extract highlighted/important emails from the list."""
        highlights = []
        for email in emails:
            subject = email.get("subject", "")
            body = email.get("snippet", email.get("body", ""))
            combined = f"{subject} {body}"
            labels = email.get("labels", [])

            score = 0
            if "IMPORTANT" in labels or "STARRED" in labels:
                score += 3
            for pattern in self.HIGHLIGHT_PATTERNS:
                if pattern.search(combined):
                    score += 1

            if score >= 2:
                highlights.append({
                    "subject": subject,
                    "sender": self._extract_sender(email),
                    "date": email.get("date", ""),
                    "score": score,
                    "snippet": body[:100] if body else "",
                })

        highlights.sort(key=lambda h: h["score"], reverse=True)
        return highlights

    def _extract_action_items(self, emails: List[Dict]) -> List[Dict]:
        """Find emails containing action items or tasks."""
        items = []
        for email in emails:
            subject = email.get("subject", "")
            body = email.get("snippet", email.get("body", ""))
            combined = f"{subject} {body}"

            matching_patterns = []
            for pattern in self.ACTION_PATTERNS:
                match = pattern.search(combined)
                if match:
                    matching_patterns.append(match.group(0))

            if matching_patterns:
                items.append({
                    "subject": subject,
                    "sender": self._extract_sender(email),
                    "date": email.get("date", ""),
                    "actions": matching_patterns[:3],
                    "snippet": body[:100] if body else "",
                })

        return items

    def _extract_trending_topics(
        self, emails: List[Dict], top_n: int = 10
    ) -> List[Tuple[str, int]]:
        """Extract trending topics/keywords from email subjects."""
        word_counts = Counter()

        for email in emails:
            subject = email.get("subject", "").lower()
            # Remove Re:/Fwd: prefixes
            subject = re.sub(r"^(re|fwd|fw):\s*", "", subject, flags=re.IGNORECASE)
            words = re.findall(r"\b[a-z]{4,}\b", subject)
            significant = [w for w in words if w not in self.STOP_WORDS]
            word_counts.update(significant)

        return word_counts.most_common(top_n)

    def _needs_response(self, email: Dict) -> bool:
        """Check if an email likely needs a response."""
        subject = email.get("subject", "") or ""
        body = email.get("snippet") or email.get("body") or ""
        combined = f"{subject} {body}"

        # Check for direct questions
        if "?" in subject:
            return True

        # Check for action patterns
        for pattern in self.ACTION_PATTERNS:
            if pattern.search(combined):
                return True

        return False

    def _extract_sender(self, email: Dict) -> str:
        """Extract sender email/name from email dict."""
        sender = email.get("sender", email.get("from", ""))
        match = re.search(r"<([^>]+)>", sender)
        if match:
            return match.group(1).lower()
        if "@" in sender:
            return sender.strip().lower()
        return sender.strip()

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string into datetime."""
        if not date_str:
            return None

        if isinstance(date_str, datetime):
            return date_str

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S",
        ]

        cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", date_str.strip())
        for fmt in formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.replace(tzinfo=None)
            except (ValueError, TypeError):
                continue

        return None

    def _calc_weekly_avg(self, dates: List[datetime]) -> float:
        """Calculate average emails per week from date list."""
        if len(dates) < 2:
            return float(len(dates))
        sorted_dates = sorted(dates)
        span = (sorted_dates[-1] - sorted_dates[0]).days
        if span <= 0:
            return float(len(dates))
        weeks = max(1.0, span / 7.0)
        return round(len(dates) / weeks, 1)
