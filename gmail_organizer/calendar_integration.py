"""Calendar integration for detecting and managing email-based events."""

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CalendarEvent:
    """An event detected from or associated with an email."""

    event_id: str = ""
    title: str = ""
    description: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: bool = False
    location: str = ""
    source_email_id: str = ""
    source_subject: str = ""
    source_sender: str = ""
    event_type: str = ""  # meeting, deadline, reminder, travel, appointment
    confidence: float = 0.0

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())[:8]
        if self.start_time and not self.end_time:
            self.end_time = self.start_time + timedelta(hours=1)

    def to_ics(self) -> str:
        """Generate ICS (iCalendar) formatted string for this event.

        Returns:
            ICS VEVENT block as a string.
        """
        lines = [
            "BEGIN:VEVENT",
            f"UID:{self.event_id}@gmail-organizer",
            f"SUMMARY:{_ics_escape(self.title)}",
        ]

        if self.start_time:
            if self.all_day:
                lines.append(f"DTSTART;VALUE=DATE:{self.start_time.strftime('%Y%m%d')}")
                if self.end_time:
                    lines.append(f"DTEND;VALUE=DATE:{self.end_time.strftime('%Y%m%d')}")
            else:
                lines.append(f"DTSTART:{self.start_time.strftime('%Y%m%dT%H%M%S')}")
                if self.end_time:
                    lines.append(f"DTEND:{self.end_time.strftime('%Y%m%dT%H%M%S')}")

        if self.description:
            lines.append(f"DESCRIPTION:{_ics_escape(self.description)}")
        if self.location:
            lines.append(f"LOCATION:{_ics_escape(self.location)}")

        lines.append(f"CATEGORIES:{self.event_type}")
        lines.append(f"CREATED:{datetime.now().strftime('%Y%m%dT%H%M%S')}")
        lines.append("END:VEVENT")

        return "\r\n".join(lines)


@dataclass
class CalendarDay:
    """Represents a single day on the calendar."""

    date: datetime
    events: List[CalendarEvent] = field(default_factory=list)

    @property
    def has_events(self) -> bool:
        return len(self.events) > 0

    @property
    def event_count(self) -> int:
        return len(self.events)


def _ics_escape(text: str) -> str:
    """Escape special characters for ICS format."""
    text = text.replace("\\", "\\\\")
    text = text.replace(",", "\\,")
    text = text.replace(";", "\\;")
    text = text.replace("\r\n", "\\n")
    text = text.replace("\r", "\\n")
    text = text.replace("\n", "\\n")
    return text


# Patterns for detecting event-related content
EVENT_PATTERNS = {
    "meeting": [
        re.compile(r"\b(meeting|standup|stand-up|sync|huddle|call|conference)\b", re.I),
        re.compile(r"\b(1:1|one-on-one|check-in|check in|touchbase)\b", re.I),
        re.compile(r"\b(scrum|retro|retrospective|sprint review|planning)\b", re.I),
    ],
    "deadline": [
        re.compile(r"\b(deadline|due|due date|submission|submit by)\b", re.I),
        re.compile(r"\b(expires?|expiration|last day|final day)\b", re.I),
        re.compile(r"\b(end of|close of|cutoff|cut-off)\b", re.I),
    ],
    "reminder": [
        re.compile(r"\b(reminder|don'?t forget|remember to|heads up)\b", re.I),
        re.compile(r"\b(upcoming|coming up|approaching|soon)\b", re.I),
        re.compile(r"\b(follow.?up|action required|action needed)\b", re.I),
    ],
    "travel": [
        re.compile(r"\b(flight|boarding|departure|arrival|gate)\b", re.I),
        re.compile(r"\b(check-?in|checkout|reservation|booking)\b", re.I),
        re.compile(r"\b(itinerary|trip|travel|hotel)\b", re.I),
    ],
    "appointment": [
        re.compile(r"\b(appointment|scheduled|booked|confirmed)\b", re.I),
        re.compile(r"\b(consultation|session|visit|exam)\b", re.I),
        re.compile(r"\b(interview|demo|presentation|webinar)\b", re.I),
    ],
}

# Time-related patterns
TIME_PATTERNS = [
    # "at 3pm", "at 3:00 PM"
    re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)\b"),
    # "3:00 PM", "15:00"
    re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?\b"),
    # "from 2pm to 3pm"
    re.compile(r"\bfrom\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|-)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I),
]

# Date-related patterns
DATE_PATTERNS = [
    # "January 15", "Jan 15, 2025"
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?\b",
        re.I
    ),
    # "1/15/2025", "01-15-2025"
    re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b"),
    # "tomorrow", "today", "next Monday"
    re.compile(r"\b(today|tomorrow|tonight)\b", re.I),
    re.compile(r"\bnext\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", re.I),
    # "this Monday", "this Friday"
    re.compile(r"\bthis\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", re.I),
]

# Month name to number mapping
MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
}

# Day name to weekday number mapping
DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

# Location patterns
LOCATION_PATTERNS = [
    re.compile(r"\b(?:at|in|location:?|room:?|venue:?)\s+([A-Z][A-Za-z0-9\s,.-]+?)(?:\.|$|\n)", re.M),
    re.compile(r"\b(zoom|teams|google meet|webex|skype|hangouts)\b", re.I),
    re.compile(r"(https?://\S*(?:zoom|teams|meet|webex)\S*)", re.I),
]


class EmailCalendar:
    """Detect calendar events from emails and manage a calendar view.

    Parses email subjects and bodies for event-like content including
    meetings, deadlines, reminders, travel, and appointments.
    """

    def __init__(self):
        self._events: List[CalendarEvent] = []
        self._processed_email_ids: Set[str] = set()

    def extract_events(self, emails: List[Dict]) -> List[CalendarEvent]:
        """Extract calendar events from a list of emails.

        Args:
            emails: List of email dicts with 'id', 'subject', 'sender'/'from',
                   'body'/'snippet', 'date' fields.

        Returns:
            List of newly detected CalendarEvent instances.
        """
        new_events = []

        for email in emails:
            email_id = email.get("email_id", "")
            if email_id in self._processed_email_ids:
                continue

            self._processed_email_ids.add(email_id)

            subject = email.get("subject", "")
            body = email.get("body", email.get("snippet", ""))
            sender = email.get("sender", email.get("from", ""))
            date_str = email.get("date", "")

            text = f"{subject} {body}"

            # Detect event type
            event_type, confidence = self._detect_event_type(text)
            if not event_type or confidence < 0.3:
                continue

            # Parse date and time from the email content
            event_date = self._parse_date(text, date_str)
            event_time = self._parse_time(text)
            location = self._parse_location(text)

            # Build start_time
            start_time = None
            all_day = True
            if event_date:
                if event_time:
                    hour, minute = event_time
                    start_time = event_date.replace(hour=hour, minute=minute)
                    all_day = False
                else:
                    start_time = event_date
                    all_day = True

            # Skip events without a discernible date
            if not start_time:
                continue

            # Create the event
            event = CalendarEvent(
                title=self._generate_title(subject, event_type),
                description=f"From: {sender}\nSubject: {subject}",
                start_time=start_time,
                all_day=all_day,
                location=location,
                source_email_id=email_id,
                source_subject=subject,
                source_sender=sender,
                event_type=event_type,
                confidence=confidence,
            )

            new_events.append(event)
            self._events.append(event)

        return new_events

    def get_events(self, start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> List[CalendarEvent]:
        """Get events within a date range.

        Args:
            start_date: Start of range (inclusive). Defaults to today.
            end_date: End of range (inclusive). Defaults to 30 days from start.

        Returns:
            List of CalendarEvent instances within the range, sorted by start_time.
        """
        if start_date is None:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if end_date is None:
            end_date = start_date + timedelta(days=30)

        filtered = [
            e for e in self._events
            if e.start_time and start_date <= e.start_time <= end_date
        ]
        return sorted(filtered, key=lambda e: e.start_time)

    def get_events_by_type(self, event_type: str) -> List[CalendarEvent]:
        """Get all events of a specific type.

        Args:
            event_type: One of 'meeting', 'deadline', 'reminder', 'travel', 'appointment'.

        Returns:
            List of matching CalendarEvent instances.
        """
        return [e for e in self._events if e.event_type == event_type]

    def get_calendar_month(self, year: int, month: int) -> List[CalendarDay]:
        """Get a calendar month view with events.

        Args:
            year: Calendar year.
            month: Calendar month (1-12).

        Returns:
            List of CalendarDay instances for each day of the month.
        """
        import calendar
        _, num_days = calendar.monthrange(year, month)

        days = []
        for day in range(1, num_days + 1):
            date = datetime(year, month, day)
            day_events = [
                e for e in self._events
                if e.start_time and e.start_time.year == year
                and e.start_time.month == month
                and e.start_time.day == day
            ]
            days.append(CalendarDay(date=date, events=day_events))

        return days

    def get_upcoming_events(self, days: int = 7) -> List[CalendarEvent]:
        """Get upcoming events within the next N days.

        Args:
            days: Number of days to look ahead.

        Returns:
            Sorted list of upcoming events.
        """
        now = datetime.now()
        end = now + timedelta(days=days)
        return self.get_events(now, end)

    def get_event_stats(self) -> Dict:
        """Get calendar event statistics.

        Returns:
            Dict with total_events, events_by_type, upcoming_count, busiest_day.
        """
        type_counts = defaultdict(int)
        day_counts = defaultdict(int)

        for event in self._events:
            type_counts[event.event_type] += 1
            if event.start_time:
                day_key = event.start_time.strftime("%A")
                day_counts[day_key] += 1

        busiest_day = max(day_counts, key=day_counts.get) if day_counts else "N/A"
        upcoming = self.get_upcoming_events(7)

        return {
            "total_events": len(self._events),
            "events_by_type": dict(type_counts),
            "upcoming_count": len(upcoming),
            "busiest_day": busiest_day,
            "day_distribution": dict(day_counts),
        }

    def export_ics(self, events: Optional[List[CalendarEvent]] = None) -> str:
        """Export events to ICS (iCalendar) format.

        Args:
            events: Events to export. Defaults to all events.

        Returns:
            Complete ICS file content as a string.
        """
        if events is None:
            events = self._events

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Gmail Organizer//Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:Gmail Organizer Events",
        ]

        for event in events:
            lines.append(event.to_ics())

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    def remove_event(self, event_id: str) -> bool:
        """Remove an event by ID.

        Args:
            event_id: The event ID to remove.

        Returns:
            True if the event was found and removed.
        """
        before = len(self._events)
        self._events = [e for e in self._events if e.event_id != event_id]
        return len(self._events) < before

    def clear_events(self):
        """Remove all detected events."""
        self._events = []
        self._processed_email_ids = set()

    def _detect_event_type(self, text: str) -> Tuple[str, float]:
        """Detect the event type from email text.

        Returns:
            Tuple of (event_type, confidence) or ("", 0.0) if no match.
        """
        scores: Dict[str, float] = {}

        for event_type, patterns in EVENT_PATTERNS.items():
            match_count = 0
            for pattern in patterns:
                if pattern.search(text):
                    match_count += 1
            if match_count > 0:
                scores[event_type] = match_count / len(patterns)

        if not scores:
            return "", 0.0

        best_type = max(scores, key=scores.get)
        return best_type, round(scores[best_type], 2)

    def _parse_date(self, text: str, email_date_str: str = "") -> Optional[datetime]:
        """Parse a date from text.

        Args:
            text: Text to search for date patterns.
            email_date_str: Fallback email date string.

        Returns:
            Parsed datetime or None.
        """
        now = datetime.now()

        # Check for relative dates first
        if re.search(r"\btoday\b", text, re.I):
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if re.search(r"\btomorrow\b", text, re.I):
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if re.search(r"\btonight\b", text, re.I):
            return now.replace(hour=20, minute=0, second=0, microsecond=0)

        # Check for "next Monday" etc
        next_day_match = re.search(
            r"\bnext\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
            text, re.I
        )
        if next_day_match:
            target_day = DAY_MAP[next_day_match.group(1).lower()]
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Check for "this Monday" etc
        this_day_match = re.search(
            r"\bthis\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
            text, re.I
        )
        if this_day_match:
            target_day = DAY_MAP[this_day_match.group(1).lower()]
            days_ahead = target_day - now.weekday()
            if days_ahead < 0:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Check for "January 15" or "Jan 15, 2025"
        month_match = re.search(
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December|"
            r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?\b",
            text, re.I
        )
        if month_match:
            month = MONTH_MAP[month_match.group(1).lower()]
            day = int(month_match.group(2))
            year = int(month_match.group(3)) if month_match.group(3) else now.year
            try:
                return datetime(year, month, day)
            except ValueError:
                pass

        # Check for numeric dates "1/15/2025"
        numeric_match = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b", text)
        if numeric_match:
            month = int(numeric_match.group(1))
            day = int(numeric_match.group(2))
            year = int(numeric_match.group(3))
            if year < 100:
                year += 2000
            try:
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(year, month, day)
            except ValueError:
                pass

        # Fallback: try to parse email date for context
        if email_date_str:
            try:
                # Common email date formats
                for fmt in ["%a, %d %b %Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        return datetime.strptime(email_date_str[:len(fmt) + 5], fmt)
                    except (ValueError, IndexError):
                        continue
            except Exception:
                pass

        return None

    def _parse_time(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse a time from text.

        Returns:
            Tuple of (hour, minute) in 24-hour format, or None.
        """
        # "at 3pm", "at 3:00 PM"
        at_match = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)\b", text)
        if at_match:
            hour = int(at_match.group(1))
            minute = int(at_match.group(2)) if at_match.group(2) else 0
            ampm = at_match.group(3).lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)

        # "3:00 PM"
        time_match = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b", text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            ampm = time_match.group(3).lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)

        # 24-hour format "15:00"
        h24_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        if h24_match:
            hour = int(h24_match.group(1))
            minute = int(h24_match.group(2))
            # Avoid matching things like "1:1" or version numbers
            if hour >= 7:  # Reasonable meeting hours
                return (hour, minute)

        return None

    def _parse_location(self, text: str) -> str:
        """Parse a location or meeting link from text.

        Returns:
            Location string or empty string.
        """
        # Check for video call links first
        for pattern in LOCATION_PATTERNS:
            match = pattern.search(text)
            if match:
                location = match.group(1) if match.lastindex else match.group(0)
                return location.strip()[:100]

        return ""

    def _generate_title(self, subject: str, event_type: str) -> str:
        """Generate a calendar event title from email subject.

        Args:
            subject: Email subject line.
            event_type: Detected event type.

        Returns:
            Clean title string.
        """
        # Remove common prefixes
        title = re.sub(r"^(Re:|Fwd?:|FW:)\s*", "", subject, flags=re.I).strip()

        # Truncate if too long
        if len(title) > 80:
            title = title[:77] + "..."

        if not title:
            type_labels = {
                "meeting": "Meeting",
                "deadline": "Deadline",
                "reminder": "Reminder",
                "travel": "Travel",
                "appointment": "Appointment",
            }
            title = type_labels.get(event_type, "Event")

        return title
