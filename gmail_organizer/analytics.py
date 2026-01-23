"""Email analytics engine for insights and trends"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from email.utils import parsedate_to_datetime
import re


class EmailAnalytics:
    """Analyze email data for insights, trends, and patterns"""

    def __init__(self, emails: List[Dict]):
        self.emails = emails
        self._parsed_dates = None
        self._senders = None
        self._domains = None

    def _parse_dates(self) -> List[Tuple[Dict, datetime]]:
        """Parse email dates, caching results"""
        if self._parsed_dates is not None:
            return self._parsed_dates

        parsed = []
        for email in self.emails:
            date_str = email.get('date', '')
            if not date_str:
                continue
            try:
                dt = parsedate_to_datetime(date_str)
                parsed.append((email, dt))
            except Exception:
                # Try common fallback formats
                for fmt in ('%Y-%m-%d %H:%M:%S', '%d %b %Y %H:%M:%S'):
                    try:
                        dt = datetime.strptime(date_str[:20], fmt)
                        parsed.append((email, dt))
                        break
                    except Exception:
                        continue

        self._parsed_dates = sorted(parsed, key=lambda x: x[1])
        return self._parsed_dates

    def _extract_sender_email(self, sender: str) -> str:
        """Extract email address from sender string"""
        match = re.search(r'<(.+?)>', sender)
        if match:
            return match.group(1).lower()
        if '@' in sender:
            return sender.strip().lower()
        return sender.lower()

    def _extract_domain(self, sender: str) -> str:
        """Extract domain from sender"""
        email_addr = self._extract_sender_email(sender)
        if '@' in email_addr:
            return email_addr.split('@')[1]
        return email_addr

    def get_volume_over_time(self, granularity: str = "daily") -> Dict[str, int]:
        """
        Get email volume over time.

        Args:
            granularity: "daily", "weekly", or "monthly"

        Returns:
            Dict mapping date strings to counts
        """
        parsed = self._parse_dates()
        if not parsed:
            return {}

        counts = Counter()
        for email, dt in parsed:
            if granularity == "daily":
                key = dt.strftime('%Y-%m-%d')
            elif granularity == "weekly":
                # Start of week (Monday)
                start = dt - timedelta(days=dt.weekday())
                key = start.strftime('%Y-%m-%d')
            elif granularity == "monthly":
                key = dt.strftime('%Y-%m')
            else:
                key = dt.strftime('%Y-%m-%d')
            counts[key] += 1

        return dict(sorted(counts.items()))

    def get_hourly_distribution(self) -> Dict[int, int]:
        """Get email count by hour of day (0-23)"""
        parsed = self._parse_dates()
        counts = Counter()
        for email, dt in parsed:
            counts[dt.hour] += 1
        # Fill all hours
        return {h: counts.get(h, 0) for h in range(24)}

    def get_day_of_week_distribution(self) -> Dict[str, int]:
        """Get email count by day of week"""
        parsed = self._parse_dates()
        counts = Counter()
        for email, dt in parsed:
            counts[dt.strftime('%A')] += 1

        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return {d: counts.get(d, 0) for d in days_order}

    def get_top_senders(self, limit: int = 20) -> List[Tuple[str, int]]:
        """Get top senders by volume"""
        counts = Counter()
        for email in self.emails:
            sender = email.get('sender', '')
            if sender:
                counts[self._extract_sender_email(sender)] += 1
        return counts.most_common(limit)

    def get_top_domains(self, limit: int = 20) -> List[Tuple[str, int]]:
        """Get top sender domains by volume"""
        counts = Counter()
        for email in self.emails:
            sender = email.get('sender', '')
            if sender:
                domain = self._extract_domain(sender)
                if domain:
                    counts[domain] += 1
        return counts.most_common(limit)

    def get_inbox_growth_rate(self) -> Dict[str, int]:
        """Get cumulative email count over time (monthly)"""
        volume = self.get_volume_over_time("monthly")
        cumulative = {}
        total = 0
        for month, count in sorted(volume.items()):
            total += count
            cumulative[month] = total
        return cumulative

    def get_response_patterns(self) -> Dict[str, any]:
        """Analyze sent vs received patterns"""
        sent = 0
        received = 0
        for email in self.emails:
            labels = email.get('labels', [])
            if 'SENT' in labels:
                sent += 1
            else:
                received += 1

        return {
            'sent': sent,
            'received': received,
            'ratio': round(sent / max(received, 1), 2),
            'total': len(self.emails)
        }

    def get_label_distribution(self) -> Dict[str, int]:
        """Get distribution of Gmail labels"""
        counts = Counter()
        for email in self.emails:
            for label in email.get('labels', []):
                counts[label] += 1
        return dict(counts.most_common(30))

    def get_date_range(self) -> Dict[str, str]:
        """Get the date range of synced emails"""
        parsed = self._parse_dates()
        if not parsed:
            return {'oldest': 'N/A', 'newest': 'N/A', 'span_days': 0}

        oldest = parsed[0][1]
        newest = parsed[-1][1]
        span = (newest - oldest).days

        return {
            'oldest': oldest.strftime('%Y-%m-%d'),
            'newest': newest.strftime('%Y-%m-%d'),
            'span_days': span
        }

    def get_busiest_periods(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get the busiest days by email volume"""
        volume = self.get_volume_over_time("daily")
        sorted_days = sorted(volume.items(), key=lambda x: x[1], reverse=True)
        return sorted_days[:top_n]

    def get_quiet_periods(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Get the quietest days by email volume"""
        volume = self.get_volume_over_time("daily")
        sorted_days = sorted(volume.items(), key=lambda x: x[1])
        return sorted_days[:top_n]

    def get_monthly_stats(self) -> List[Dict]:
        """Get per-month statistics"""
        parsed = self._parse_dates()
        if not parsed:
            return []

        monthly = defaultdict(list)
        for email, dt in parsed:
            key = dt.strftime('%Y-%m')
            monthly[key].append(email)

        stats = []
        for month, emails in sorted(monthly.items()):
            senders = set()
            for e in emails:
                sender = e.get('sender', '')
                if sender:
                    senders.add(self._extract_sender_email(sender))

            stats.append({
                'month': month,
                'count': len(emails),
                'unique_senders': len(senders),
                'avg_per_day': round(len(emails) / 30, 1)
            })

        return stats

    def get_summary(self) -> Dict:
        """Get a comprehensive summary of all analytics"""
        date_range = self.get_date_range()
        response = self.get_response_patterns()

        return {
            'total_emails': len(self.emails),
            'date_range': date_range,
            'unique_senders': len(set(
                self._extract_sender_email(e.get('sender', ''))
                for e in self.emails if e.get('sender')
            )),
            'unique_domains': len(set(
                self._extract_domain(e.get('sender', ''))
                for e in self.emails if e.get('sender')
            )),
            'sent': response['sent'],
            'received': response['received'],
            'avg_per_day': round(len(self.emails) / max(date_range['span_days'], 1), 1),
        }
