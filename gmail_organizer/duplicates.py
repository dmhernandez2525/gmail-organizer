"""
Feature 7: Duplicate/Thread Cleanup

Detects duplicate emails, groups them into clusters, and provides
cleanup recommendations with space savings estimates.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


@dataclass
class DuplicateGroup:
    """A cluster of duplicate or near-duplicate emails."""
    emails: List[Dict] = field(default_factory=list)
    reason: str = ""  # "exact_id", "similar_content", "same_thread"
    keep_email: Optional[Dict] = None  # Recommended email to keep

    @property
    def count(self) -> int:
        return len(self.emails)

    @property
    def removable_count(self) -> int:
        return max(0, self.count - 1)

    @property
    def space_savings_bytes(self) -> int:
        """Estimate bytes saved by removing duplicates (keeping one)."""
        if not self.emails or not self.keep_email:
            return 0
        total = sum(self._estimate_size(e) for e in self.emails)
        keep_size = self._estimate_size(self.keep_email)
        return total - keep_size

    @staticmethod
    def _estimate_size(email: Dict) -> int:
        """Estimate email size in bytes from sizeEstimate or payload."""
        return email.get("sizeEstimate", 0)


@dataclass
class ThreadGroup:
    """A group of emails belonging to the same thread."""
    thread_id: str = ""
    emails: List[Dict] = field(default_factory=list)
    subject: str = ""
    participant_count: int = 0

    @property
    def count(self) -> int:
        return len(self.emails)

    @property
    def total_size_bytes(self) -> int:
        return sum(e.get("sizeEstimate", 0) for e in self.emails)


class DuplicateDetector:
    """Detects duplicate emails and provides cleanup recommendations."""

    # Threshold for fuzzy subject similarity (0.0 to 1.0)
    SUBJECT_SIMILARITY_THRESHOLD = 0.85
    # Maximum time difference for fuzzy date matching
    DATE_PROXIMITY_SECONDS = 60

    def find_duplicates(self, emails: List[Dict]) -> List[DuplicateGroup]:
        """
        Find duplicate email clusters using multiple detection strategies.

        Args:
            emails: List of email message dicts (Gmail API format with
                     id, threadId, payload.headers, sizeEstimate, etc.)

        Returns:
            List of DuplicateGroup instances, each containing a cluster
            of duplicate emails with a reason and keep recommendation.
        """
        groups: List[DuplicateGroup] = []

        # Strategy 1: Exact Message-ID duplicates
        exact_groups = self._find_exact_id_duplicates(emails)
        groups.extend(exact_groups)

        # Collect IDs already grouped to avoid double-counting
        grouped_ids = set()
        for group in groups:
            for email in group.emails:
                grouped_ids.add(email.get("email_id"))

        # Strategy 2: Similar content duplicates (subject + sender + date)
        remaining = [e for e in emails if e.get("email_id") not in grouped_ids]
        similar_groups = self._find_similar_content_duplicates(remaining)
        groups.extend(similar_groups)

        for group in similar_groups:
            for email in group.emails:
                grouped_ids.add(email.get("email_id"))

        # Strategy 3: Same thread duplicates (same threadId, same Message-ID
        # content forwarded or re-sent within a thread)
        remaining = [e for e in emails if e.get("email_id") not in grouped_ids]
        thread_dup_groups = self._find_thread_duplicates(remaining)
        groups.extend(thread_dup_groups)

        return groups

    def find_large_threads(
        self, emails: List[Dict], min_size: int = 10
    ) -> List[ThreadGroup]:
        """
        Find threads that exceed the minimum message count.

        Args:
            emails: List of email message dicts.
            min_size: Minimum number of messages to qualify as a large thread.

        Returns:
            List of ThreadGroup instances sorted by message count descending.
        """
        threads: Dict[str, List[Dict]] = defaultdict(list)

        for email in emails:
            thread_id = email.get("threadId", "")
            if thread_id:
                threads[thread_id].append(email)

        large_threads: List[ThreadGroup] = []
        for thread_id, thread_emails in threads.items():
            if len(thread_emails) >= min_size:
                subject = self._get_thread_subject(thread_emails)
                participants = self._get_participant_count(thread_emails)
                group = ThreadGroup(
                    thread_id=thread_id,
                    emails=sorted(
                        thread_emails,
                        key=lambda e: self._get_internal_date(e),
                    ),
                    subject=subject,
                    participant_count=participants,
                )
                large_threads.append(group)

        large_threads.sort(key=lambda t: t.count, reverse=True)
        return large_threads

    def get_cleanup_stats(
        self,
        duplicates: List[DuplicateGroup],
        threads: List[ThreadGroup],
    ) -> Dict:
        """
        Calculate cleanup statistics and potential space savings.

        Args:
            duplicates: List of DuplicateGroup from find_duplicates().
            threads: List of ThreadGroup from find_large_threads().

        Returns:
            Dictionary with cleanup statistics including counts,
            space savings, and per-category breakdowns.
        """
        total_duplicates = sum(g.removable_count for g in duplicates)
        total_space_savings = sum(g.space_savings_bytes for g in duplicates)

        # Breakdown by reason
        by_reason: Dict[str, Dict] = defaultdict(
            lambda: {"count": 0, "space_bytes": 0}
        )
        for group in duplicates:
            by_reason[group.reason]["count"] += group.removable_count
            by_reason[group.reason]["space_bytes"] += group.space_savings_bytes

        # Thread stats
        total_thread_messages = sum(t.count for t in threads)
        total_thread_size = sum(t.total_size_bytes for t in threads)

        return {
            "duplicate_groups": len(duplicates),
            "total_removable_duplicates": total_duplicates,
            "space_savings_bytes": total_space_savings,
            "space_savings_mb": round(total_space_savings / (1024 * 1024), 2),
            "breakdown_by_reason": dict(by_reason),
            "large_threads": len(threads),
            "large_thread_total_messages": total_thread_messages,
            "large_thread_total_size_bytes": total_thread_size,
            "large_thread_total_size_mb": round(
                total_thread_size / (1024 * 1024), 2
            ),
            "recommendations": self._generate_recommendations(
                duplicates, threads
            ),
        }

    # -------------------------------------------------------------------------
    # Private detection methods
    # -------------------------------------------------------------------------

    def _find_exact_id_duplicates(
        self, emails: List[Dict]
    ) -> List[DuplicateGroup]:
        """Find emails with identical Message-ID headers."""
        message_id_map: Dict[str, List[Dict]] = defaultdict(list)

        for email in emails:
            msg_id = self._get_header(email, "Message-ID") or self._get_header(
                email, "Message-Id"
            )
            if msg_id:
                # Normalize Message-ID (strip whitespace, angle brackets)
                normalized = msg_id.strip().strip("<>").lower()
                if normalized:
                    message_id_map[normalized].append(email)

        groups: List[DuplicateGroup] = []
        for msg_id, dupes in message_id_map.items():
            if len(dupes) > 1:
                keep = self._select_keep_email(dupes)
                groups.append(
                    DuplicateGroup(
                        emails=dupes,
                        reason="exact_id",
                        keep_email=keep,
                    )
                )

        return groups

    def _find_similar_content_duplicates(
        self, emails: List[Dict]
    ) -> List[DuplicateGroup]:
        """Find emails with similar subject + sender + date."""
        # Build candidate pairs using sender as a grouping key
        sender_map: Dict[str, List[Dict]] = defaultdict(list)
        for email in emails:
            sender = self._normalize_sender(
                self._get_header(email, "From") or ""
            )
            if sender:
                sender_map[sender].append(email)

        groups: List[DuplicateGroup] = []
        processed_ids: set = set()

        for sender, sender_emails in sender_map.items():
            if len(sender_emails) < 2:
                continue

            # Compare all pairs within the same sender
            clusters = self._cluster_similar_emails(sender_emails)
            for cluster in clusters:
                cluster_ids = {e.get("email_id") for e in cluster}
                if cluster_ids & processed_ids:
                    continue
                if len(cluster) > 1:
                    keep = self._select_keep_email(cluster)
                    groups.append(
                        DuplicateGroup(
                            emails=cluster,
                            reason="similar_content",
                            keep_email=keep,
                        )
                    )
                    processed_ids.update(cluster_ids)

        return groups

    def _find_thread_duplicates(
        self, emails: List[Dict]
    ) -> List[DuplicateGroup]:
        """
        Find duplicates within the same thread where the same content
        appears multiple times (e.g., quoted replies that are also
        stored as separate messages).
        """
        thread_map: Dict[str, List[Dict]] = defaultdict(list)
        for email in emails:
            thread_id = email.get("threadId", "")
            if thread_id:
                thread_map[thread_id].append(email)

        groups: List[DuplicateGroup] = []
        for thread_id, thread_emails in thread_map.items():
            if len(thread_emails) < 2:
                continue

            # Within a thread, look for emails with nearly identical subjects
            # and very close timestamps (likely re-deliveries or duplicates)
            clusters = self._cluster_thread_duplicates(thread_emails)
            for cluster in clusters:
                if len(cluster) > 1:
                    keep = self._select_keep_email(cluster)
                    groups.append(
                        DuplicateGroup(
                            emails=cluster,
                            reason="same_thread",
                            keep_email=keep,
                        )
                    )

        return groups

    def _cluster_similar_emails(
        self, emails: List[Dict]
    ) -> List[List[Dict]]:
        """Cluster emails by subject similarity and date proximity."""
        n = len(emails)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                if self._are_similar(emails[i], emails[j]):
                    union(i, j)

        clusters_map: Dict[int, List[Dict]] = defaultdict(list)
        for i in range(n):
            clusters_map[find(i)].append(emails[i])

        return [c for c in clusters_map.values() if len(c) > 1]

    def _cluster_thread_duplicates(
        self, emails: List[Dict]
    ) -> List[List[Dict]]:
        """
        Within a thread, cluster emails that have the same normalized subject
        and are sent within a very short time window (likely duplicates).
        """
        n = len(emails)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                subj_i = self._normalize_subject(
                    self._get_header(emails[i], "Subject") or ""
                )
                subj_j = self._normalize_subject(
                    self._get_header(emails[j], "Subject") or ""
                )
                if subj_i == subj_j and subj_i:
                    date_i = self._get_internal_date(emails[i])
                    date_j = self._get_internal_date(emails[j])
                    if date_i and date_j:
                        diff = abs((date_i - date_j).total_seconds())
                        if diff <= self.DATE_PROXIMITY_SECONDS:
                            union(i, j)

        clusters_map: Dict[int, List[Dict]] = defaultdict(list)
        for i in range(n):
            clusters_map[find(i)].append(emails[i])

        return [c for c in clusters_map.values() if len(c) > 1]

    def _are_similar(self, email_a: Dict, email_b: Dict) -> bool:
        """Check if two emails are similar enough to be considered duplicates."""
        subj_a = self._get_header(email_a, "Subject") or ""
        subj_b = self._get_header(email_b, "Subject") or ""

        # Compare normalized subjects
        norm_a = self._normalize_subject(subj_a)
        norm_b = self._normalize_subject(subj_b)

        if not norm_a or not norm_b:
            return False

        similarity = self._subject_similarity(norm_a, norm_b)
        if similarity < self.SUBJECT_SIMILARITY_THRESHOLD:
            return False

        # Check date proximity
        date_a = self._get_internal_date(email_a)
        date_b = self._get_internal_date(email_b)
        if date_a and date_b:
            diff = abs((date_a - date_b).total_seconds())
            if diff > self.DATE_PROXIMITY_SECONDS:
                return False

        return True

    # -------------------------------------------------------------------------
    # Keep-email selection
    # -------------------------------------------------------------------------

    def _select_keep_email(self, emails: List[Dict]) -> Dict:
        """
        Select the best email to keep from a group of duplicates.

        Priority:
        1. Emails in INBOX (label)
        2. Emails that are unread (more likely user hasn't processed yet)
        3. Largest email (most complete content / attachments)
        4. Most recent email (freshest metadata)
        """
        if not emails:
            return {}

        def score(email: Dict) -> Tuple:
            labels = email.get("labelIds", [])
            in_inbox = 1 if "INBOX" in labels else 0
            is_unread = 1 if "UNREAD" in labels else 0
            size = email.get("sizeEstimate", 0)
            date = self._get_internal_date(email) or datetime.min
            return (in_inbox, is_unread, size, date)

        return max(emails, key=score)

    # -------------------------------------------------------------------------
    # Recommendations
    # -------------------------------------------------------------------------

    def _generate_recommendations(
        self,
        duplicates: List[DuplicateGroup],
        threads: List[ThreadGroup],
    ) -> List[str]:
        """Generate human-readable cleanup recommendations."""
        recommendations: List[str] = []

        if duplicates:
            total = sum(g.removable_count for g in duplicates)
            recommendations.append(
                f"Found {len(duplicates)} duplicate groups with "
                f"{total} removable messages."
            )

            exact = [g for g in duplicates if g.reason == "exact_id"]
            if exact:
                count = sum(g.removable_count for g in exact)
                recommendations.append(
                    f"  - {count} exact Message-ID duplicates "
                    f"(safe to remove)."
                )

            similar = [g for g in duplicates if g.reason == "similar_content"]
            if similar:
                count = sum(g.removable_count for g in similar)
                recommendations.append(
                    f"  - {count} similar-content duplicates "
                    f"(review before removing)."
                )

            thread_dups = [g for g in duplicates if g.reason == "same_thread"]
            if thread_dups:
                count = sum(g.removable_count for g in thread_dups)
                recommendations.append(
                    f"  - {count} same-thread duplicates "
                    f"(likely safe to archive)."
                )

        if threads:
            recommendations.append(
                f"Found {len(threads)} large threads "
                f"(10+ messages each)."
            )
            biggest = threads[0] if threads else None
            if biggest:
                recommendations.append(
                    f"  - Largest thread: \"{biggest.subject}\" "
                    f"with {biggest.count} messages "
                    f"({biggest.participant_count} participants)."
                )

        if not duplicates and not threads:
            recommendations.append(
                "No significant duplicates or large threads found."
            )

        return recommendations

    # -------------------------------------------------------------------------
    # Utility / header extraction methods
    # -------------------------------------------------------------------------

    def _get_header(self, email: Dict, header_name: str) -> Optional[str]:
        """Extract a header value from an email's payload."""
        payload = email.get("payload", {})
        headers = payload.get("headers", [])
        for header in headers:
            if header.get("name", "").lower() == header_name.lower():
                return header.get("value", "")
        return None

    def _get_internal_date(self, email: Dict) -> Optional[datetime]:
        """Get the internalDate as a datetime object."""
        internal_date = email.get("internalDate")
        if internal_date:
            try:
                # Gmail API returns internalDate as milliseconds since epoch
                ts = int(internal_date) / 1000.0
                return datetime.utcfromtimestamp(ts)
            except (ValueError, TypeError, OSError):
                pass
        return None

    def _normalize_subject(self, subject: str) -> str:
        """
        Normalize a subject line by removing Re:/Fwd: prefixes,
        extra whitespace, and converting to lowercase.
        """
        # Remove common prefixes (Re:, Fwd:, Fw:) including nested ones
        normalized = re.sub(
            r"^(\s*(re|fwd?|fw)\s*:\s*)+", "", subject, flags=re.IGNORECASE
        )
        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip().lower()
        return normalized

    def _normalize_sender(self, sender: str) -> str:
        """Extract and normalize email address from a From header."""
        # Try to extract email from "Name <email>" format
        match = re.search(r"<([^>]+)>", sender)
        if match:
            return match.group(1).strip().lower()
        # Might be just an email address
        sender = sender.strip().lower()
        if "@" in sender:
            return sender
        return ""

    def _subject_similarity(self, a: str, b: str) -> float:
        """
        Calculate similarity between two normalized subject strings
        using character-level bigram overlap (Dice coefficient).
        """
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0

        bigrams_a = set(self._get_bigrams(a))
        bigrams_b = set(self._get_bigrams(b))

        if not bigrams_a or not bigrams_b:
            return 0.0

        intersection = bigrams_a & bigrams_b
        return (2.0 * len(intersection)) / (
            len(bigrams_a) + len(bigrams_b)
        )

    @staticmethod
    def _get_bigrams(text: str) -> List[str]:
        """Generate character bigrams from text."""
        return [text[i : i + 2] for i in range(len(text) - 1)]

    def _get_thread_subject(self, emails: List[Dict]) -> str:
        """Get the subject line for a thread (from the earliest email)."""
        earliest = None
        earliest_date = None

        for email in emails:
            date = self._get_internal_date(email)
            if date and (earliest_date is None or date < earliest_date):
                earliest_date = date
                earliest = email

        if earliest:
            return self._get_header(earliest, "Subject") or "(no subject)"
        if emails:
            return self._get_header(emails[0], "Subject") or "(no subject)"
        return "(no subject)"

    def _get_participant_count(self, emails: List[Dict]) -> int:
        """Count unique participants (senders) in a thread."""
        participants: set = set()
        for email in emails:
            sender = self._normalize_sender(
                self._get_header(email, "From") or ""
            )
            if sender:
                participants.add(sender)
            # Also count To and Cc recipients
            for field in ("To", "Cc"):
                value = self._get_header(email, field) or ""
                for addr in self._extract_addresses(value):
                    participants.add(addr)
        return len(participants)

    def _extract_addresses(self, header_value: str) -> List[str]:
        """Extract all email addresses from a header value (To, Cc, etc.)."""
        addresses: List[str] = []
        # Find all email-like patterns
        matches = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", header_value)
        for match in matches:
            addresses.append(match.lower())
        return addresses
