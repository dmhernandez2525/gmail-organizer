"""Follow-up reminder detection for emails needing responses or action."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class FollowUpItem:
    """Represents an email that may need follow-up."""

    email: Dict
    reason: str  # "question", "action_item", "awaiting_reply"
    urgency: str  # "overdue", "soon", "later"
    days_waiting: int
    suggested_action: str


# Patterns indicating a question was asked
QUESTION_PATTERNS = [
    re.compile(r"\?"),
    re.compile(r"\bcan you\b", re.IGNORECASE),
    re.compile(r"\bcould you\b", re.IGNORECASE),
    re.compile(r"\bwould you\b", re.IGNORECASE),
    re.compile(r"\bwill you\b", re.IGNORECASE),
    re.compile(r"\bare you able\b", re.IGNORECASE),
    re.compile(r"\bdo you think\b", re.IGNORECASE),
    re.compile(r"\bwhat do you\b", re.IGNORECASE),
    re.compile(r"\bhow do you\b", re.IGNORECASE),
]

# Patterns indicating action items
ACTION_ITEM_PATTERNS = [
    re.compile(r"\bplease\b", re.IGNORECASE),
    re.compile(r"\bneed you to\b", re.IGNORECASE),
    re.compile(r"\bneed your\b", re.IGNORECASE),
    re.compile(r"\bcan you\b", re.IGNORECASE),
    re.compile(r"\bcould you\b", re.IGNORECASE),
    re.compile(r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    re.compile(r"\bby (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", re.IGNORECASE),
    re.compile(r"\bby \d{1,2}[/\-]\d{1,2}\b", re.IGNORECASE),
    re.compile(r"\bdeadline\b", re.IGNORECASE),
    re.compile(r"\burgent\b", re.IGNORECASE),
    re.compile(r"\basap\b", re.IGNORECASE),
    re.compile(r"\baction required\b", re.IGNORECASE),
    re.compile(r"\baction needed\b", re.IGNORECASE),
    re.compile(r"\bfollow up\b", re.IGNORECASE),
    re.compile(r"\bfollow-up\b", re.IGNORECASE),
    re.compile(r"\breminder\b", re.IGNORECASE),
]

# Keywords that increase urgency scoring
URGENCY_KEYWORDS = [
    re.compile(r"\burgent\b", re.IGNORECASE),
    re.compile(r"\basap\b", re.IGNORECASE),
    re.compile(r"\bimmediately\b", re.IGNORECASE),
    re.compile(r"\bcritical\b", re.IGNORECASE),
    re.compile(r"\bdeadline\b", re.IGNORECASE),
    re.compile(r"\btime.sensitive\b", re.IGNORECASE),
    re.compile(r"\baction required\b", re.IGNORECASE),
    re.compile(r"\boverdue\b", re.IGNORECASE),
]


class FollowUpDetector:
    """Detects emails that may need follow-up responses."""

    def __init__(self):
        self.question_patterns = QUESTION_PATTERNS
        self.action_item_patterns = ACTION_ITEM_PATTERNS
        self.urgency_keywords = URGENCY_KEYWORDS

    def detect_follow_ups(
        self, emails: List[Dict], user_email: str = ""
    ) -> List[FollowUpItem]:
        """Detect emails that may need follow-up responses.

        Args:
            emails: List of email dicts, each containing at minimum:
                - id: message ID
                - threadId: thread ID
                - subject: email subject line
                - body or snippet: email body text
                - date: email date as ISO string or Unix timestamp
                - from: sender email address
                - to: recipient email address(es)
                - labelIds: list of Gmail label IDs (e.g., "SENT", "INBOX")
            user_email: The user's own email address, used to detect
                sent messages awaiting replies.

        Returns:
            List of FollowUpItem instances sorted by urgency then days_waiting.
        """
        follow_ups: List[FollowUpItem] = []

        # Build a set of thread IDs that have replies (for awaiting_reply detection)
        threads_with_replies = self._build_thread_reply_map(emails, user_email)

        for email in emails:
            item = self._check_email(email, user_email, threads_with_replies)
            if item is not None:
                follow_ups.append(item)

        # Sort by urgency priority (overdue first) then by days_waiting descending
        urgency_order = {"overdue": 0, "soon": 1, "later": 2}
        follow_ups.sort(
            key=lambda x: (urgency_order.get(x.urgency, 3), -x.days_waiting)
        )

        return follow_ups

    def get_follow_up_stats(self, items: List[FollowUpItem]) -> Dict:
        """Get summary statistics about follow-up items.

        Args:
            items: List of FollowUpItem instances.

        Returns:
            Dictionary with stats including counts by urgency and reason,
            total count, and average days waiting.
        """
        stats: Dict = {
            "total": len(items),
            "by_urgency": {"overdue": 0, "soon": 0, "later": 0},
            "by_reason": {"question": 0, "action_item": 0, "awaiting_reply": 0},
            "average_days_waiting": 0.0,
            "oldest_days": 0,
        }

        if not items:
            return stats

        total_days = 0
        max_days = 0

        for item in items:
            if item.urgency in stats["by_urgency"]:
                stats["by_urgency"][item.urgency] += 1
            if item.reason in stats["by_reason"]:
                stats["by_reason"][item.reason] += 1
            total_days += item.days_waiting
            if item.days_waiting > max_days:
                max_days = item.days_waiting

        stats["average_days_waiting"] = round(total_days / len(items), 1)
        stats["oldest_days"] = max_days

        return stats

    def _check_email(
        self,
        email: Dict,
        user_email: str,
        threads_with_replies: Dict[str, bool],
    ) -> Optional[FollowUpItem]:
        """Check a single email for follow-up needs.

        Returns a FollowUpItem if follow-up is needed, None otherwise.
        Priority: awaiting_reply > action_item > question.
        """
        days_waiting = self._calculate_days_waiting(email)
        sender = self._get_sender(email)
        is_sent_by_user = self._is_from_user(sender, user_email)

        # Check for awaiting reply (sent by user, no reply in thread)
        if is_sent_by_user and user_email:
            thread_id = email.get("threadId", "")
            if thread_id and not threads_with_replies.get(thread_id, False):
                urgency = self._determine_urgency(email, days_waiting)
                return FollowUpItem(
                    email=email,
                    reason="awaiting_reply",
                    urgency=urgency,
                    days_waiting=days_waiting,
                    suggested_action="Follow up on your sent message that hasn't received a reply.",
                )

        # Only check received emails for questions and action items
        if is_sent_by_user:
            return None

        subject = email.get("subject", "") or ""
        body = email.get("body") or email.get("snippet") or ""
        combined_text = f"{subject} {body}"

        # Check for action items (higher priority than questions)
        if self._has_action_items(combined_text):
            urgency = self._determine_urgency(email, days_waiting)
            return FollowUpItem(
                email=email,
                reason="action_item",
                urgency=urgency,
                days_waiting=days_waiting,
                suggested_action=self._suggest_action_item_response(combined_text),
            )

        # Check for unanswered questions
        if self._has_questions(subject, body):
            urgency = self._determine_urgency(email, days_waiting)
            return FollowUpItem(
                email=email,
                reason="question",
                urgency=urgency,
                days_waiting=days_waiting,
                suggested_action="Reply to the question asked in this email.",
            )

        return None

    def _build_thread_reply_map(
        self, emails: List[Dict], user_email: str
    ) -> Dict[str, bool]:
        """Build a map of threadId -> whether there's a reply from someone else.

        For detecting 'awaiting reply': if the user sent a message and
        no one else replied in the same thread, it's awaiting reply.
        """
        # Group emails by threadId
        threads: Dict[str, List[Dict]] = {}
        for email in emails:
            thread_id = email.get("threadId", "")
            if thread_id:
                if thread_id not in threads:
                    threads[thread_id] = []
                threads[thread_id].append(email)

        # For each thread, check if there's a non-user message after a user message
        reply_map: Dict[str, bool] = {}
        for thread_id, thread_emails in threads.items():
            has_user_sent = False
            has_reply = False

            # Sort by date within thread
            sorted_thread = sorted(
                thread_emails, key=lambda e: self._parse_date(e)
            )

            for email in sorted_thread:
                sender = self._get_sender(email)
                if self._is_from_user(sender, user_email):
                    has_user_sent = True
                elif has_user_sent:
                    # Someone else replied after user sent
                    has_reply = True
                    break

            reply_map[thread_id] = has_reply

        return reply_map

    def _has_questions(self, subject: str, body: str) -> bool:
        """Check if the email contains questions directed at the recipient."""
        # Check subject for question mark
        if "?" in subject:
            return True

        # Check body for question patterns
        for pattern in self.question_patterns:
            if pattern.search(body):
                return True

        return False

    def _has_action_items(self, text: str) -> bool:
        """Check if the email contains action item indicators."""
        match_count = 0
        for pattern in self.action_item_patterns:
            if pattern.search(text):
                match_count += 1
                # Require at least 2 pattern matches to reduce false positives
                if match_count >= 2:
                    return True
        return False

    def _determine_urgency(self, email: Dict, days_waiting: int) -> str:
        """Determine urgency level based on age and keywords.

        Rules:
            - overdue: 7+ days waiting, or contains urgent keywords
            - soon: 3-7 days waiting
            - later: less than 3 days waiting

        Urgent keywords can bump the urgency level up by one tier.
        """
        subject = email.get("subject", "") or ""
        body = email.get("body") or email.get("snippet") or ""
        combined_text = f"{subject} {body}"

        has_urgent_keywords = any(
            p.search(combined_text) for p in self.urgency_keywords
        )

        # Base urgency from days waiting
        if days_waiting >= 7:
            return "overdue"
        elif days_waiting >= 3:
            # Urgent keywords bump from soon to overdue
            if has_urgent_keywords:
                return "overdue"
            return "soon"
        else:
            # Urgent keywords bump from later to soon
            if has_urgent_keywords:
                return "soon"
            return "later"

    def _calculate_days_waiting(self, email: Dict) -> int:
        """Calculate the number of days since the email was received."""
        email_date = self._parse_date(email)
        now = datetime.now(timezone.utc)
        delta = now - email_date
        return max(0, delta.days)

    def _parse_date(self, email: Dict) -> datetime:
        """Parse the email date from various formats."""
        date_value = email.get("date", email.get("internalDate", ""))

        if not date_value:
            return datetime.now(timezone.utc)

        # Handle Unix timestamp in milliseconds (Gmail API internalDate)
        if isinstance(date_value, (int, float)):
            return datetime.fromtimestamp(date_value / 1000, tz=timezone.utc)

        if isinstance(date_value, str):
            # Try as Unix timestamp string (milliseconds)
            if date_value.isdigit():
                return datetime.fromtimestamp(
                    int(date_value) / 1000, tz=timezone.utc
                )

            # Try ISO format
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%a, %d %b %Y %H:%M:%S %z",
                "%d %b %Y %H:%M:%S %z",
            ]:
                try:
                    parsed = datetime.strptime(date_value, fmt)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed
                except ValueError:
                    continue

        # Fallback to now if parsing fails
        return datetime.now(timezone.utc)

    def _get_sender(self, email: Dict) -> str:
        """Extract the sender email address from the email dict."""
        from_field = email.get("sender", email.get("from", ""))
        # Handle "Name <email@example.com>" format
        match = re.search(r"<([^>]+)>", from_field)
        if match:
            return match.group(1).lower()
        return from_field.strip().lower()

    def _is_from_user(self, sender: str, user_email: str) -> bool:
        """Check if the sender matches the user's email."""
        if not user_email or not sender:
            return False
        return sender.lower() == user_email.lower()

    def _suggest_action_item_response(self, text: str) -> str:
        """Generate a suggested action based on the action item content."""
        text_lower = text.lower()

        if any(
            kw in text_lower for kw in ["deadline", "by monday", "by tuesday",
                                         "by wednesday", "by thursday",
                                         "by friday", "by saturday", "by sunday"]
        ):
            return "Complete the requested task before the mentioned deadline."

        if "urgent" in text_lower or "asap" in text_lower:
            return "Respond urgently to this action item request."

        if "review" in text_lower:
            return "Review the attached or referenced material and respond."

        if "approve" in text_lower or "approval" in text_lower:
            return "Provide your approval or feedback as requested."

        if "update" in text_lower:
            return "Provide the requested status update."

        return "Respond to the action item request in this email."
