"""Tests for calendar_integration module."""

import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from gmail_organizer.calendar_integration import (
    CalendarDay,
    CalendarEvent,
    EmailCalendar,
    _ics_escape,
)


# ---------------------------------------------------------------------------
# CalendarEvent dataclass
# ---------------------------------------------------------------------------

class TestCalendarEvent:
    def test_auto_generated_event_id(self):
        event = CalendarEvent()
        assert len(event.event_id) == 8

    def test_custom_event_id_preserved(self):
        event = CalendarEvent(event_id="custom123")
        assert event.event_id == "custom123"

    def test_end_time_defaults_to_one_hour_after_start(self):
        start = datetime(2026, 3, 28, 10, 0)
        event = CalendarEvent(start_time=start)
        assert event.end_time == start + timedelta(hours=1)

    def test_end_time_not_overridden_when_provided(self):
        start = datetime(2026, 3, 28, 10, 0)
        end = datetime(2026, 3, 28, 12, 0)
        event = CalendarEvent(start_time=start, end_time=end)
        assert event.end_time == end

    def test_to_ics_timed_event(self):
        start = datetime(2026, 3, 28, 14, 30)
        end = datetime(2026, 3, 28, 15, 30)
        event = CalendarEvent(
            event_id="abc",
            title="Team Sync",
            start_time=start,
            end_time=end,
            all_day=False,
            location="Room A",
            description="Weekly sync",
            event_type="meeting",
        )
        ics = event.to_ics()
        assert "BEGIN:VEVENT" in ics
        assert "END:VEVENT" in ics
        assert "SUMMARY:Team Sync" in ics
        assert "DTSTART:20260328T143000" in ics
        assert "DTEND:20260328T153000" in ics
        assert "LOCATION:Room A" in ics
        assert "DESCRIPTION:Weekly sync" in ics
        assert "CATEGORIES:meeting" in ics

    def test_to_ics_all_day_event(self):
        start = datetime(2026, 4, 1)
        end = datetime(2026, 4, 2)
        event = CalendarEvent(
            event_id="d1",
            title="Conference",
            start_time=start,
            end_time=end,
            all_day=True,
            event_type="travel",
        )
        ics = event.to_ics()
        assert "DTSTART;VALUE=DATE:20260401" in ics
        assert "DTEND;VALUE=DATE:20260402" in ics

    def test_to_ics_no_start_time(self):
        event = CalendarEvent(event_id="x", title="No time")
        ics = event.to_ics()
        assert "DTSTART" not in ics

    def test_to_ics_no_description_or_location(self):
        event = CalendarEvent(
            event_id="z",
            title="Minimal",
            start_time=datetime(2026, 5, 1, 9, 0),
            all_day=False,
            event_type="reminder",
        )
        ics = event.to_ics()
        assert "DESCRIPTION" not in ics
        assert "LOCATION" not in ics


# ---------------------------------------------------------------------------
# CalendarDay dataclass
# ---------------------------------------------------------------------------

class TestCalendarDay:
    def test_empty_day(self):
        day = CalendarDay(date=datetime(2026, 3, 28))
        assert day.has_events is False
        assert day.event_count == 0

    def test_day_with_events(self):
        event = CalendarEvent(title="Standup")
        day = CalendarDay(date=datetime(2026, 3, 28), events=[event])
        assert day.has_events is True
        assert day.event_count == 1


# ---------------------------------------------------------------------------
# _ics_escape helper
# ---------------------------------------------------------------------------

class TestIcsEscape:
    def test_escapes_backslash(self):
        assert _ics_escape("a\\b") == "a\\\\b"

    def test_escapes_comma_and_semicolon(self):
        assert _ics_escape("a,b;c") == "a\\,b\\;c"

    def test_escapes_newlines(self):
        assert _ics_escape("line1\nline2") == "line1\\nline2"
        assert _ics_escape("line1\r\nline2") == "line1\\nline2"
        assert _ics_escape("line1\rline2") == "line1\\nline2"


# ---------------------------------------------------------------------------
# EmailCalendar
# ---------------------------------------------------------------------------

class TestEmailCalendar:
    def _make_email(self, email_id="e1", subject="", body="",
                    sender="alice@example.com", date=""):
        return {
            "email_id": email_id,
            "subject": subject,
            "body": body,
            "sender": sender,
            "date": date,
        }

    # --- extract_events ---

    def test_extract_meeting_event(self):
        cal = EmailCalendar()
        email = self._make_email(
            subject="Team standup at 3pm",
            body="Let's sync tomorrow at 3pm in Room B",
        )
        events = cal.extract_events([email])
        assert len(events) == 1
        assert events[0].event_type == "meeting"
        assert events[0].source_email_id == "e1"

    def test_extract_deadline_event(self):
        cal = EmailCalendar()
        email = self._make_email(
            email_id="e2",
            subject="Project deadline January 15",
            body="Please submit by the deadline on January 15",
        )
        events = cal.extract_events([email])
        assert len(events) == 1
        assert events[0].event_type == "deadline"
        assert events[0].start_time.month == 1
        assert events[0].start_time.day == 15

    def test_extract_travel_event(self):
        cal = EmailCalendar()
        email = self._make_email(
            email_id="e3",
            subject="Your flight itinerary",
            body="Flight departure on 03/15/2026. Boarding at gate C12.",
        )
        events = cal.extract_events([email])
        assert len(events) == 1
        assert events[0].event_type == "travel"

    def test_extract_reminder_event(self):
        cal = EmailCalendar()
        email = self._make_email(
            email_id="e4",
            subject="Reminder: don't forget tomorrow",
            body="Heads up, your appointment is coming up tomorrow.",
        )
        events = cal.extract_events([email])
        assert len(events) >= 1

    def test_extract_appointment_event(self):
        cal = EmailCalendar()
        email = self._make_email(
            email_id="e5",
            subject="Your appointment is confirmed for Jan 20",
            body="Consultation session scheduled for January 20 at 2pm.",
        )
        events = cal.extract_events([email])
        assert len(events) == 1
        assert events[0].event_type == "appointment"

    def test_skips_duplicate_email_ids(self):
        cal = EmailCalendar()
        email = self._make_email(
            subject="Meeting tomorrow at 10am",
            body="Standup sync",
        )
        events1 = cal.extract_events([email])
        events2 = cal.extract_events([email])
        assert len(events1) >= 1
        assert len(events2) == 0

    def test_skips_low_confidence(self):
        cal = EmailCalendar()
        email = self._make_email(
            email_id="low",
            subject="Hello there",
            body="Just wanted to say hi. No events here.",
        )
        events = cal.extract_events([email])
        assert len(events) == 0

    def test_skips_email_without_detectable_date(self):
        cal = EmailCalendar()
        email = self._make_email(
            email_id="nodate",
            subject="Team meeting sync standup",
            body="Let's have a huddle sometime",
        )
        events = cal.extract_events([email])
        # No date detected, so event should be skipped
        assert len(events) == 0

    def test_extract_all_day_event_when_no_time(self):
        cal = EmailCalendar()
        email = self._make_email(
            email_id="allday",
            subject="Deadline submission on January 10",
            body="Due date is January 10",
        )
        events = cal.extract_events([email])
        assert len(events) == 1
        assert events[0].all_day is True

    # --- get_events ---

    def test_get_events_date_range(self):
        cal = EmailCalendar()
        start = datetime(2026, 1, 1)
        end = datetime(2026, 12, 31)
        # Manually add events
        cal._events = [
            CalendarEvent(
                event_id="a", title="A",
                start_time=datetime(2026, 3, 15),
                event_type="meeting",
            ),
            CalendarEvent(
                event_id="b", title="B",
                start_time=datetime(2025, 6, 1),
                event_type="meeting",
            ),
        ]
        result = cal.get_events(start, end)
        assert len(result) == 1
        assert result[0].event_id == "a"

    def test_get_events_defaults(self):
        cal = EmailCalendar()
        # Should not raise with defaults
        result = cal.get_events()
        assert isinstance(result, list)

    def test_get_events_sorted_by_start_time(self):
        cal = EmailCalendar()
        cal._events = [
            CalendarEvent(event_id="late", start_time=datetime(2026, 6, 20), event_type="meeting"),
            CalendarEvent(event_id="early", start_time=datetime(2026, 6, 5), event_type="meeting"),
        ]
        result = cal.get_events(datetime(2026, 6, 1), datetime(2026, 6, 30))
        assert result[0].event_id == "early"
        assert result[1].event_id == "late"

    # --- get_events_by_type ---

    def test_get_events_by_type(self):
        cal = EmailCalendar()
        cal._events = [
            CalendarEvent(event_id="m1", event_type="meeting"),
            CalendarEvent(event_id="d1", event_type="deadline"),
            CalendarEvent(event_id="m2", event_type="meeting"),
        ]
        meetings = cal.get_events_by_type("meeting")
        assert len(meetings) == 2
        deadlines = cal.get_events_by_type("deadline")
        assert len(deadlines) == 1

    # --- get_calendar_month ---

    def test_get_calendar_month(self):
        cal = EmailCalendar()
        cal._events = [
            CalendarEvent(
                event_id="x",
                start_time=datetime(2026, 3, 15, 10, 0),
                event_type="meeting",
            ),
        ]
        days = cal.get_calendar_month(2026, 3)
        assert len(days) == 31  # March has 31 days
        march_15 = days[14]  # 0-indexed, day 15 is index 14
        assert march_15.has_events is True
        assert march_15.event_count == 1

    def test_get_calendar_month_february(self):
        cal = EmailCalendar()
        days = cal.get_calendar_month(2026, 2)
        assert len(days) == 28

    # --- get_upcoming_events ---

    def test_get_upcoming_events(self):
        cal = EmailCalendar()
        now = datetime.now()
        cal._events = [
            CalendarEvent(
                event_id="soon",
                start_time=now + timedelta(days=2),
                event_type="meeting",
            ),
            CalendarEvent(
                event_id="far",
                start_time=now + timedelta(days=30),
                event_type="meeting",
            ),
        ]
        upcoming = cal.get_upcoming_events(days=7)
        assert len(upcoming) == 1
        assert upcoming[0].event_id == "soon"

    # --- get_event_stats ---

    def test_get_event_stats(self):
        cal = EmailCalendar()
        cal._events = [
            CalendarEvent(
                event_id="a",
                start_time=datetime(2026, 3, 28, 10, 0),
                event_type="meeting",
            ),
            CalendarEvent(
                event_id="b",
                start_time=datetime(2026, 3, 28, 14, 0),
                event_type="meeting",
            ),
            CalendarEvent(
                event_id="c",
                start_time=datetime(2026, 3, 29, 9, 0),
                event_type="deadline",
            ),
        ]
        stats = cal.get_event_stats()
        assert stats["total_events"] == 3
        assert stats["events_by_type"]["meeting"] == 2
        assert stats["events_by_type"]["deadline"] == 1
        assert stats["busiest_day"] == "Saturday"  # 2026-03-28 is Saturday

    def test_get_event_stats_empty(self):
        cal = EmailCalendar()
        stats = cal.get_event_stats()
        assert stats["total_events"] == 0
        assert stats["busiest_day"] == "N/A"

    # --- export_ics ---

    def test_export_ics_all_events(self):
        cal = EmailCalendar()
        cal._events = [
            CalendarEvent(
                event_id="ev1",
                title="Test",
                start_time=datetime(2026, 5, 1, 9, 0),
                event_type="meeting",
            ),
        ]
        ics = cal.export_ics()
        assert "BEGIN:VCALENDAR" in ics
        assert "END:VCALENDAR" in ics
        assert "BEGIN:VEVENT" in ics
        assert "SUMMARY:Test" in ics

    def test_export_ics_specific_events(self):
        cal = EmailCalendar()
        event = CalendarEvent(
            event_id="ev2",
            title="Specific",
            start_time=datetime(2026, 6, 1, 10, 0),
            event_type="deadline",
        )
        ics = cal.export_ics([event])
        assert "SUMMARY:Specific" in ics

    def test_export_ics_empty(self):
        cal = EmailCalendar()
        ics = cal.export_ics()
        assert "BEGIN:VCALENDAR" in ics
        assert "END:VCALENDAR" in ics
        assert "VEVENT" not in ics

    # --- remove_event ---

    def test_remove_event_found(self):
        cal = EmailCalendar()
        cal._events = [
            CalendarEvent(event_id="keep", event_type="meeting"),
            CalendarEvent(event_id="drop", event_type="deadline"),
        ]
        removed = cal.remove_event("drop")
        assert removed is True
        assert len(cal._events) == 1
        assert cal._events[0].event_id == "keep"

    def test_remove_event_not_found(self):
        cal = EmailCalendar()
        cal._events = [CalendarEvent(event_id="keep", event_type="meeting")]
        removed = cal.remove_event("nonexistent")
        assert removed is False

    # --- clear_events ---

    def test_clear_events(self):
        cal = EmailCalendar()
        cal._events = [CalendarEvent(event_id="a", event_type="meeting")]
        cal._processed_email_ids = {"e1"}
        cal.clear_events()
        assert len(cal._events) == 0
        assert len(cal._processed_email_ids) == 0

    # --- _detect_event_type ---

    def test_detect_meeting_type(self):
        cal = EmailCalendar()
        etype, conf = cal._detect_event_type("Let's have a standup sync")
        assert etype == "meeting"
        assert conf > 0

    def test_detect_no_match(self):
        cal = EmailCalendar()
        etype, conf = cal._detect_event_type("random text with nothing relevant")
        assert etype == ""
        assert conf == 0.0

    # --- _parse_date ---

    def test_parse_date_today(self):
        cal = EmailCalendar()
        result = cal._parse_date("meeting today", "")
        assert result is not None
        assert result.date() == datetime.now().date()

    def test_parse_date_tomorrow(self):
        cal = EmailCalendar()
        result = cal._parse_date("see you tomorrow", "")
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        assert result is not None
        assert result.date() == tomorrow

    def test_parse_date_tonight(self):
        cal = EmailCalendar()
        result = cal._parse_date("tonight at 8", "")
        assert result is not None
        assert result.hour == 20

    def test_parse_date_next_day_name(self):
        cal = EmailCalendar()
        result = cal._parse_date("next Monday at 9am", "")
        assert result is not None
        assert result.weekday() == 0  # Monday

    def test_parse_date_this_day_name(self):
        cal = EmailCalendar()
        result = cal._parse_date("this Friday", "")
        assert result is not None
        assert result.weekday() == 4  # Friday

    def test_parse_date_month_name(self):
        cal = EmailCalendar()
        result = cal._parse_date("January 15", "")
        assert result is not None
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_month_name_with_year(self):
        cal = EmailCalendar()
        result = cal._parse_date("Feb 20, 2027", "")
        assert result is not None
        assert result.month == 2
        assert result.day == 20
        assert result.year == 2027

    def test_parse_date_numeric(self):
        cal = EmailCalendar()
        result = cal._parse_date("deadline 03/15/2026", "")
        assert result is not None
        assert result.month == 3
        assert result.day == 15
        assert result.year == 2026

    def test_parse_date_numeric_two_digit_year(self):
        cal = EmailCalendar()
        result = cal._parse_date("due 06/01/26", "")
        assert result is not None
        assert result.year == 2026

    def test_parse_date_fallback_email_date(self):
        cal = EmailCalendar()
        result = cal._parse_date("no date in text", "2026-03-28")
        assert result is not None
        assert result.year == 2026

    def test_parse_date_invalid_returns_none(self):
        cal = EmailCalendar()
        result = cal._parse_date("no dates here at all", "")
        assert result is None

    def test_parse_date_invalid_numeric(self):
        cal = EmailCalendar()
        # Month 13 is invalid
        result = cal._parse_date("13/45/2026", "")
        assert result is None

    # --- _parse_time ---

    def test_parse_time_at_pm(self):
        cal = EmailCalendar()
        result = cal._parse_time("meeting at 3pm")
        assert result == (15, 0)

    def test_parse_time_at_am(self):
        cal = EmailCalendar()
        result = cal._parse_time("call at 9am")
        assert result == (9, 0)

    def test_parse_time_with_minutes(self):
        cal = EmailCalendar()
        result = cal._parse_time("at 2:30 PM")
        assert result == (14, 30)

    def test_parse_time_12pm(self):
        cal = EmailCalendar()
        result = cal._parse_time("at 12pm")
        assert result == (12, 0)

    def test_parse_time_12am(self):
        cal = EmailCalendar()
        result = cal._parse_time("at 12am")
        assert result == (0, 0)

    def test_parse_time_colon_format(self):
        cal = EmailCalendar()
        result = cal._parse_time("starts 3:00 PM sharp")
        assert result == (15, 0)

    def test_parse_time_24h_format(self):
        cal = EmailCalendar()
        result = cal._parse_time("meeting 15:00 sharp")
        assert result == (15, 0)

    def test_parse_time_none_when_no_time(self):
        cal = EmailCalendar()
        result = cal._parse_time("no time information here")
        assert result is None

    # --- _parse_location ---

    def test_parse_location_zoom(self):
        cal = EmailCalendar()
        result = cal._parse_location("Join on Zoom")
        assert "zoom" in result.lower() or "Zoom" in result

    def test_parse_location_teams(self):
        cal = EmailCalendar()
        result = cal._parse_location("Meeting on Teams")
        assert "teams" in result.lower() or "Teams" in result

    def test_parse_location_url(self):
        cal = EmailCalendar()
        result = cal._parse_location("Join here: https://zoom.us/j/12345")
        assert "zoom" in result.lower()

    def test_parse_location_empty(self):
        cal = EmailCalendar()
        result = cal._parse_location("no location mentioned")
        assert result == ""

    # --- _generate_title ---

    def test_generate_title_strips_re_prefix(self):
        cal = EmailCalendar()
        assert cal._generate_title("Re: Team Sync", "meeting") == "Team Sync"

    def test_generate_title_strips_fwd_prefix(self):
        cal = EmailCalendar()
        assert cal._generate_title("Fwd: Invitation", "meeting") == "Invitation"

    def test_generate_title_truncates_long_subject(self):
        cal = EmailCalendar()
        long_subject = "A" * 100
        title = cal._generate_title(long_subject, "meeting")
        assert len(title) == 80
        assert title.endswith("...")

    def test_generate_title_fallback_for_empty_subject(self):
        cal = EmailCalendar()
        assert cal._generate_title("", "meeting") == "Meeting"
        assert cal._generate_title("", "deadline") == "Deadline"
        assert cal._generate_title("", "travel") == "Travel"
        assert cal._generate_title("", "unknown_type") == "Event"

    def test_generate_title_strips_fw_prefix(self):
        cal = EmailCalendar()
        assert cal._generate_title("FW: Budget Update", "deadline") == "Budget Update"
