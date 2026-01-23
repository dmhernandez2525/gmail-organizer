"""Priority Inbox - score and rank emails by importance"""

import re
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from email.utils import parsedate_to_datetime


class PriorityScorer:
    """Score emails by importance using multiple signals"""

    DEFAULT_WEIGHTS = {
        'sender_frequency': 0.15,     # How often sender emails you
        'sender_reply_rate': 0.20,    # How often you reply to this sender
        'recency': 0.10,             # How recent the email is
        'subject_urgency': 0.20,     # Urgency keywords in subject
        'is_direct': 0.15,           # Sent directly to you (not CC/BCC)
        'has_question': 0.10,        # Contains question marks
        'thread_length': 0.05,       # Part of active thread
        'vip_sender': 0.05           # Sender is in VIP list
    }

    URGENCY_KEYWORDS = {
        'high': ['urgent', 'asap', 'immediately', 'critical', 'emergency',
                 'deadline', 'today', 'tonight', 'now', 'action required',
                 'time sensitive', 'priority', 'important'],
        'medium': ['soon', 'reminder', 'follow up', 'following up',
                   'tomorrow', 'this week', 'please respond', 'waiting',
                   'pending', 'overdue', 'schedule', 'meeting', 'interview'],
        'low': ['fyi', 'no rush', 'when you get a chance', 'newsletter',
                'digest', 'weekly', 'monthly', 'update', 'announcement']
    }

    def __init__(self, config_dir: str = ".sync-state"):
        self.config_dir = config_dir
        self._config = self._load_config()
        self._sender_stats: Dict[str, Dict] = {}

    def _load_config(self) -> Dict:
        """Load priority configuration"""
        config_file = os.path.join(self.config_dir, "priority_config.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            'weights': self.DEFAULT_WEIGHTS.copy(),
            'vip_senders': [],
            'low_priority_senders': [],
            'thresholds': {'high': 0.7, 'medium': 0.4}
        }

    def save_config(self):
        """Save priority configuration"""
        os.makedirs(self.config_dir, exist_ok=True)
        config_file = os.path.join(self.config_dir, "priority_config.json")
        with open(config_file, 'w') as f:
            json.dump(self._config, f, indent=2)

    @property
    def vip_senders(self) -> List[str]:
        return self._config.get('vip_senders', [])

    @vip_senders.setter
    def vip_senders(self, senders: List[str]):
        self._config['vip_senders'] = senders
        self.save_config()

    @property
    def low_priority_senders(self) -> List[str]:
        return self._config.get('low_priority_senders', [])

    @low_priority_senders.setter
    def low_priority_senders(self, senders: List[str]):
        self._config['low_priority_senders'] = senders
        self.save_config()

    @property
    def thresholds(self) -> Dict[str, float]:
        return self._config.get('thresholds', {'high': 0.7, 'medium': 0.4})

    @thresholds.setter
    def thresholds(self, values: Dict[str, float]):
        self._config['thresholds'] = values
        self.save_config()

    def _build_sender_stats(self, emails: List[Dict]):
        """Pre-compute sender statistics for scoring"""
        sender_counts = Counter()
        sender_replied = Counter()
        user_sent = set()

        for email in emails:
            sender = self._extract_email(email.get('sender', ''))
            labels = email.get('labels', [])

            if 'SENT' in labels:
                # Track who user sends to
                to = email.get('to', '')
                if to:
                    to_email = self._extract_email(to)
                    user_sent.add(to_email)
                    sender_replied[to_email] += 1
            else:
                sender_counts[sender] += 1

        # Build stats dict
        self._sender_stats = {}
        max_count = max(sender_counts.values()) if sender_counts else 1
        for sender, count in sender_counts.items():
            self._sender_stats[sender] = {
                'frequency': count / max_count,  # Normalized 0-1
                'reply_rate': min(sender_replied.get(sender, 0) / max(count, 1), 1.0),
                'total_emails': count
            }

    def score_emails(self, emails: List[Dict],
                     user_email: str = "") -> List[Tuple[Dict, float, str]]:
        """
        Score all emails by priority.

        Args:
            emails: List of email dicts
            user_email: User's email for direct-to detection

        Returns:
            List of (email, score, priority_level) tuples sorted by score desc
        """
        # Build sender stats first
        self._build_sender_stats(emails)

        results = []
        for email in emails:
            score = self._score_email(email, user_email)
            level = self._get_priority_level(score)
            results.append((email, score, level))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _score_email(self, email: Dict, user_email: str = "") -> float:
        """Score a single email (0-1)"""
        weights = self._config.get('weights', self.DEFAULT_WEIGHTS)
        score = 0.0

        sender = self._extract_email(email.get('sender', ''))
        subject = email.get('subject', '').lower()
        labels = email.get('labels', [])

        # Skip sent emails
        if 'SENT' in labels:
            return 0.0

        # VIP/Low priority overrides
        if sender in [s.lower() for s in self._config.get('vip_senders', [])]:
            score += weights.get('vip_sender', 0.05)
        if sender in [s.lower() for s in self._config.get('low_priority_senders', [])]:
            return 0.1  # Force low priority

        # Sender frequency signal
        stats = self._sender_stats.get(sender, {})
        freq = stats.get('frequency', 0)
        # Moderate frequency is better (not too many, not too few)
        freq_score = 1.0 - abs(freq - 0.3) if freq > 0 else 0
        score += weights.get('sender_frequency', 0.15) * freq_score

        # Reply rate signal (high reply rate = important sender)
        reply_rate = stats.get('reply_rate', 0)
        score += weights.get('sender_reply_rate', 0.20) * reply_rate

        # Recency signal
        recency = self._recency_score(email.get('date', ''))
        score += weights.get('recency', 0.10) * recency

        # Subject urgency
        urgency = self._urgency_score(subject)
        score += weights.get('subject_urgency', 0.20) * urgency

        # Direct-to signal
        if user_email:
            to_field = email.get('to', '').lower()
            if user_email.lower() in to_field:
                score += weights.get('is_direct', 0.15)

        # Question signal
        if '?' in subject:
            score += weights.get('has_question', 0.10)

        # Thread signal (presence of Re: or Fwd:)
        if subject.startswith('re:') or 'thread' in labels:
            score += weights.get('thread_length', 0.05) * 0.5

        return min(score, 1.0)

    def _urgency_score(self, subject: str) -> float:
        """Score subject urgency (0-1)"""
        subject_lower = subject.lower()

        for keyword in self.URGENCY_KEYWORDS['high']:
            if keyword in subject_lower:
                return 1.0

        for keyword in self.URGENCY_KEYWORDS['medium']:
            if keyword in subject_lower:
                return 0.6

        for keyword in self.URGENCY_KEYWORDS['low']:
            if keyword in subject_lower:
                return 0.1

        return 0.3  # Neutral

    def _recency_score(self, date_str: str) -> float:
        """Score recency (1.0 = today, 0.0 = 30+ days ago)"""
        if not date_str:
            return 0.0
        try:
            dt = parsedate_to_datetime(date_str).replace(tzinfo=None)
            days_ago = (datetime.now() - dt).days
            if days_ago <= 0:
                return 1.0
            elif days_ago <= 1:
                return 0.9
            elif days_ago <= 3:
                return 0.7
            elif days_ago <= 7:
                return 0.5
            elif days_ago <= 14:
                return 0.3
            elif days_ago <= 30:
                return 0.1
            else:
                return 0.0
        except Exception:
            return 0.0

    def _extract_email(self, sender: str) -> str:
        """Extract email from sender string"""
        match = re.search(r'<(.+?)>', sender)
        if match:
            return match.group(1).lower()
        if '@' in sender:
            return sender.strip().lower()
        return sender.lower()

    def _get_priority_level(self, score: float) -> str:
        """Convert score to priority level"""
        thresholds = self.thresholds
        if score >= thresholds.get('high', 0.7):
            return 'high'
        elif score >= thresholds.get('medium', 0.4):
            return 'medium'
        else:
            return 'low'

    def get_priority_stats(self, scored_emails: List[Tuple]) -> Dict:
        """Get priority distribution stats"""
        levels = Counter()
        for _, score, level in scored_emails:
            levels[level] += 1

        return {
            'high': levels.get('high', 0),
            'medium': levels.get('medium', 0),
            'low': levels.get('low', 0),
            'total': len(scored_emails)
        }
