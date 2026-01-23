"""Unsubscribe Manager - detect subscriptions and manage unsubscribes"""

import re
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from googleapiclient.errors import HttpError


class Subscription:
    """Represents a detected email subscription"""

    def __init__(self, sender_email: str, sender_name: str = "",
                 unsubscribe_link: str = "", unsubscribe_email: str = "",
                 frequency: int = 0, last_received: str = "",
                 first_received: str = "", category: str = ""):
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.unsubscribe_link = unsubscribe_link  # HTTP URL
        self.unsubscribe_email = unsubscribe_email  # mailto: address
        self.frequency = frequency  # Total email count
        self.last_received = last_received
        self.first_received = first_received
        self.category = category
        self.domain = sender_email.split('@')[1] if '@' in sender_email else ""
        self.unsubscribed = False
        self.unsubscribe_date = ""

    @property
    def has_unsubscribe(self) -> bool:
        """Whether this subscription has an unsubscribe mechanism"""
        return bool(self.unsubscribe_link or self.unsubscribe_email)

    @property
    def emails_per_week(self) -> float:
        """Calculate average emails per week"""
        if not self.first_received or not self.last_received:
            return 0.0
        try:
            first = datetime.fromisoformat(self.first_received)
            last = datetime.fromisoformat(self.last_received)
            days = max((last - first).days, 1)
            weeks = days / 7.0
            return round(self.frequency / max(weeks, 0.14), 1)  # min 1 day
        except (ValueError, TypeError):
            return 0.0

    def to_dict(self) -> Dict:
        """Serialize subscription data"""
        return {
            'sender_email': self.sender_email,
            'sender_name': self.sender_name,
            'unsubscribe_link': self.unsubscribe_link,
            'unsubscribe_email': self.unsubscribe_email,
            'frequency': self.frequency,
            'last_received': self.last_received,
            'first_received': self.first_received,
            'category': self.category,
            'domain': self.domain,
            'emails_per_week': self.emails_per_week,
            'unsubscribed': self.unsubscribed,
            'unsubscribe_date': self.unsubscribe_date,
            'has_unsubscribe': self.has_unsubscribe
        }


class UnsubscribeManager:
    """Detect subscriptions and manage unsubscribes"""

    # Common newsletter/marketing patterns
    NEWSLETTER_PATTERNS = [
        r'newsletter', r'digest', r'weekly', r'daily', r'monthly',
        r'update', r'bulletin', r'roundup', r'recap', r'brief',
        r'noreply', r'no-reply', r'notifications?', r'alerts?',
        r'marketing', r'promo', r'offers?', r'deals?', r'discount',
        r'subscribe', r'unsubscribe', r'list-unsubscribe'
    ]

    # Domains that are almost always newsletters/marketing
    MARKETING_DOMAINS = {
        'mailchimp.com', 'sendgrid.net', 'constantcontact.com',
        'campaign-archive.com', 'createsend.com', 'mailgun.org',
        'amazonses.com', 'postmarkapp.com', 'mandrillapp.com',
        'sparkpostmail.com', 'sailthru.com', 'exacttarget.com',
        'responsys.net', 'hubspot.com', 'marketo.com',
        'salesforce.com', 'pardot.com', 'eloqua.com'
    }

    def __init__(self, service=None, state_dir: str = ".sync-state"):
        self.service = service
        self.state_dir = state_dir
        self._unsubscribe_state = self._load_state()

    def _load_state(self) -> Dict:
        """Load unsubscribe state from disk"""
        state_file = os.path.join(self.state_dir, "unsubscribe_state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {'unsubscribed': {}, 'ignored': []}

    def _save_state(self):
        """Save unsubscribe state to disk"""
        os.makedirs(self.state_dir, exist_ok=True)
        state_file = os.path.join(self.state_dir, "unsubscribe_state.json")
        with open(state_file, 'w') as f:
            json.dump(self._unsubscribe_state, f, indent=2)

    def detect_subscriptions(self, emails: List[Dict]) -> List[Subscription]:
        """
        Analyze emails to detect subscriptions.

        Identifies subscriptions by:
        1. List-Unsubscribe header presence
        2. Unsubscribe links in email body
        3. Newsletter/marketing sender patterns
        4. High-frequency senders

        Args:
            emails: List of email dicts with sender, headers, body_preview fields

        Returns:
            List of Subscription objects sorted by frequency (highest first)
        """
        sender_data = defaultdict(lambda: {
            'emails': [],
            'unsubscribe_links': set(),
            'unsubscribe_emails': set(),
            'sender_names': Counter(),
            'categories': Counter(),
            'dates': []
        })

        for email in emails:
            sender = email.get('sender', '')
            if not sender:
                continue

            sender_email = self._extract_email(sender)
            sender_name = self._extract_name(sender)

            if not sender_email or '@' not in sender_email:
                continue

            data = sender_data[sender_email]
            data['emails'].append(email)
            if sender_name:
                data['sender_names'][sender_name] += 1

            # Check for List-Unsubscribe header
            headers = email.get('headers', {})
            list_unsub = headers.get('List-Unsubscribe', '')
            if list_unsub:
                links = self._parse_list_unsubscribe(list_unsub)
                for link in links:
                    if link.startswith('http'):
                        data['unsubscribe_links'].add(link)
                    elif link.startswith('mailto:'):
                        data['unsubscribe_emails'].add(link[7:])

            # Check body for unsubscribe links
            body = email.get('body_preview', '')
            if body:
                body_links = self._find_unsubscribe_in_body(body)
                data['unsubscribe_links'].update(body_links)

            # Track dates
            date_str = email.get('date', '')
            if date_str:
                parsed = self._parse_date(date_str)
                if parsed:
                    data['dates'].append(parsed)

            # Track categories
            category = email.get('category', '')
            if category:
                data['categories'][category] += 1

        # Build subscription list
        subscriptions = []
        for sender_email, data in sender_data.items():
            # Determine if this is likely a subscription
            is_subscription = self._is_likely_subscription(sender_email, data)
            if not is_subscription:
                continue

            # Get most common sender name
            sender_name = ""
            if data['sender_names']:
                sender_name = data['sender_names'].most_common(1)[0][0]

            # Get unsubscribe info
            unsub_link = next(iter(data['unsubscribe_links']), "")
            unsub_email = next(iter(data['unsubscribe_emails']), "")

            # Get date range
            dates = sorted(data['dates'])
            first = dates[0].isoformat() if dates else ""
            last = dates[-1].isoformat() if dates else ""

            # Get primary category
            category = ""
            if data['categories']:
                category = data['categories'].most_common(1)[0][0]

            sub = Subscription(
                sender_email=sender_email,
                sender_name=sender_name,
                unsubscribe_link=unsub_link,
                unsubscribe_email=unsub_email,
                frequency=len(data['emails']),
                first_received=first,
                last_received=last,
                category=category
            )

            # Check if already unsubscribed
            if sender_email in self._unsubscribe_state.get('unsubscribed', {}):
                sub.unsubscribed = True
                sub.unsubscribe_date = self._unsubscribe_state['unsubscribed'][sender_email]

            subscriptions.append(sub)

        # Sort by frequency (most emails first)
        subscriptions.sort(key=lambda s: s.frequency, reverse=True)
        return subscriptions

    def _is_likely_subscription(self, sender_email: str, data: Dict) -> bool:
        """Determine if a sender is likely a subscription/newsletter"""
        # Has unsubscribe mechanism = definitely a subscription
        if data['unsubscribe_links'] or data['unsubscribe_emails']:
            return True

        # Check if sender domain is a known marketing platform
        domain = sender_email.split('@')[1] if '@' in sender_email else ""
        if domain in self.MARKETING_DOMAINS:
            return True

        # Check sender email for newsletter patterns
        for pattern in self.NEWSLETTER_PATTERNS:
            if re.search(pattern, sender_email, re.IGNORECASE):
                return True

        # High frequency from automated senders (5+ emails)
        if len(data['emails']) >= 5:
            # Check if subjects look automated (similar patterns)
            subjects = [e.get('subject', '') for e in data['emails']]
            if self._subjects_look_automated(subjects):
                return True

        return False

    def _subjects_look_automated(self, subjects: List[str]) -> bool:
        """Check if subjects follow automated patterns"""
        if len(subjects) < 3:
            return False

        # Check for common prefixes
        if len(subjects) >= 3:
            prefix_len = 0
            for i in range(min(30, min(len(s) for s in subjects if s))):
                chars = set(s[i].lower() for s in subjects if len(s) > i)
                if len(chars) == 1:
                    prefix_len += 1
                else:
                    break
            if prefix_len >= 5:
                return True

        # Check for number/date patterns (e.g., "Weekly Digest #123")
        number_pattern = sum(1 for s in subjects if re.search(r'#\d+|\d{1,2}/\d{1,2}', s))
        if number_pattern >= len(subjects) * 0.5:
            return True

        return False

    def _parse_list_unsubscribe(self, header: str) -> List[str]:
        """Parse List-Unsubscribe header value"""
        # Format: <url1>, <mailto:addr>, <url2>
        links = re.findall(r'<([^>]+)>', header)
        return links

    def _find_unsubscribe_in_body(self, body: str) -> List[str]:
        """Find unsubscribe URLs in email body"""
        links = []
        # Look for URLs near "unsubscribe" text
        patterns = [
            r'https?://[^\s<>"\']+unsubscribe[^\s<>"\']*',
            r'https?://[^\s<>"\']+opt.?out[^\s<>"\']*',
            r'https?://[^\s<>"\']+remove[^\s<>"\']*list[^\s<>"\']*',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            links.extend(matches)

        return links[:3]  # Limit to avoid noise

    def _extract_email(self, sender: str) -> str:
        """Extract email address from sender string"""
        match = re.search(r'<(.+?)>', sender)
        if match:
            return match.group(1).lower()
        if '@' in sender:
            return sender.strip().lower()
        return sender.lower()

    def _extract_name(self, sender: str) -> str:
        """Extract display name from sender string"""
        match = re.match(r'^"?([^"<]+)"?\s*<', sender)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string"""
        try:
            return parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%d %b %Y %H:%M:%S'):
                try:
                    return datetime.strptime(date_str[:20], fmt)
                except Exception:
                    continue
        return None

    def unsubscribe_via_email(self, subscription: Subscription) -> bool:
        """
        Unsubscribe by sending email to the List-Unsubscribe address.

        Uses Gmail API to send an unsubscribe email.
        """
        if not self.service or not subscription.unsubscribe_email:
            return False

        try:
            import base64
            from email.mime.text import MIMEText

            unsub_addr = subscription.unsubscribe_email
            # Handle subject in mailto link
            subject = "Unsubscribe"
            if '?' in unsub_addr:
                addr_part, params = unsub_addr.split('?', 1)
                unsub_addr = addr_part
                for param in params.split('&'):
                    if param.lower().startswith('subject='):
                        subject = param.split('=', 1)[1]

            message = MIMEText("Please unsubscribe me from this mailing list.")
            message['to'] = unsub_addr
            message['subject'] = subject

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            body = {'raw': raw}

            self.service.users().messages().send(
                userId='me', body=body
            ).execute()

            # Mark as unsubscribed
            self._mark_unsubscribed(subscription.sender_email)
            subscription.unsubscribed = True
            subscription.unsubscribe_date = datetime.now().isoformat()
            return True

        except (HttpError, Exception) as e:
            print(f"Error sending unsubscribe email: {e}")
            return False

    def mark_unsubscribed(self, sender_email: str):
        """Manually mark a subscription as unsubscribed"""
        self._mark_unsubscribed(sender_email)

    def _mark_unsubscribed(self, sender_email: str):
        """Internal: mark subscription as unsubscribed and persist"""
        self._unsubscribe_state.setdefault('unsubscribed', {})
        self._unsubscribe_state['unsubscribed'][sender_email] = datetime.now().isoformat()
        self._save_state()

    def ignore_subscription(self, sender_email: str):
        """Mark a subscription as ignored (not shown in suggestions)"""
        self._unsubscribe_state.setdefault('ignored', [])
        if sender_email not in self._unsubscribe_state['ignored']:
            self._unsubscribe_state['ignored'].append(sender_email)
            self._save_state()

    def get_subscription_stats(self, subscriptions: List[Subscription]) -> Dict:
        """Get summary statistics about subscriptions"""
        active = [s for s in subscriptions if not s.unsubscribed]
        with_unsub = [s for s in active if s.has_unsubscribe]
        total_emails = sum(s.frequency for s in active)

        # Group by domain
        domain_counts = Counter()
        for s in active:
            domain_counts[s.domain] += 1

        # Categorize by frequency
        daily = [s for s in active if s.emails_per_week >= 5]
        weekly = [s for s in active if 0.8 <= s.emails_per_week < 5]
        monthly = [s for s in active if 0 < s.emails_per_week < 0.8]

        return {
            'total_subscriptions': len(active),
            'with_unsubscribe': len(with_unsub),
            'without_unsubscribe': len(active) - len(with_unsub),
            'total_emails': total_emails,
            'already_unsubscribed': len([s for s in subscriptions if s.unsubscribed]),
            'top_domains': domain_counts.most_common(10),
            'daily_senders': len(daily),
            'weekly_senders': len(weekly),
            'monthly_senders': len(monthly),
            'avg_per_week': round(
                sum(s.emails_per_week for s in active) / max(len(active), 1), 1
            )
        }

    def get_unsubscribe_candidates(self, subscriptions: List[Subscription],
                                    min_frequency: int = 5) -> List[Subscription]:
        """
        Get subscriptions recommended for unsubscribing.

        Prioritizes by:
        1. Has unsubscribe mechanism
        2. High frequency
        3. Never opened/replied (if data available)
        """
        candidates = []
        ignored = set(self._unsubscribe_state.get('ignored', []))

        for sub in subscriptions:
            if sub.unsubscribed:
                continue
            if sub.sender_email in ignored:
                continue
            if sub.frequency < min_frequency:
                continue
            if sub.has_unsubscribe:
                candidates.append(sub)

        # Sort by frequency (most annoying first)
        candidates.sort(key=lambda s: s.frequency, reverse=True)
        return candidates
