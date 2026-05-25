"""Tests for gmail_organizer/mobile.py -- PWA support and mobile layout helpers."""

import struct
import zlib
from pathlib import Path

import pytest

from gmail_organizer.mobile import (
    MOBILE_COMPACT_CSS,
    PWA_HEAD_HTML,
    MobileLayoutHelper,
    _create_png,
    generate_pwa_icons,
)


# ---------------------------------------------------------------------------
# _create_png
# ---------------------------------------------------------------------------

class TestCreatePng:
    def test_returns_bytes(self):
        result = _create_png(1, 1, (0, 0, 0))
        assert isinstance(result, bytes)

    def test_starts_with_png_signature(self):
        result = _create_png(2, 2, (255, 0, 0))
        assert result[:8] == b'\x89PNG\r\n\x1a\n'

    def test_contains_ihdr_idat_iend_chunks(self):
        result = _create_png(4, 4, (31, 119, 180))
        assert b'IHDR' in result
        assert b'IDAT' in result
        assert b'IEND' in result

    def test_different_sizes_produce_different_lengths(self):
        small = _create_png(1, 1, (0, 0, 0))
        large = _create_png(10, 10, (0, 0, 0))
        assert len(large) > len(small)

    def test_ihdr_encodes_dimensions(self):
        width, height = 16, 8
        result = _create_png(width, height, (0, 0, 0))
        # IHDR data starts right after the chunk length (4 bytes) and 'IHDR' tag (4 bytes)
        ihdr_start = result.index(b'IHDR') + 4
        w, h = struct.unpack('>II', result[ihdr_start:ihdr_start + 8])
        assert w == width
        assert h == height

    def test_color_tuple_accepted(self):
        # Just verifying various color tuples do not raise
        _create_png(1, 1, (0, 0, 0))
        _create_png(1, 1, (255, 255, 255))
        _create_png(1, 1, (128, 64, 32))


# ---------------------------------------------------------------------------
# generate_pwa_icons
# ---------------------------------------------------------------------------

class TestGeneratePwaIcons:
    def test_creates_icons_in_specified_directory(self, tmp_path):
        generate_pwa_icons(static_dir=str(tmp_path))
        assert (tmp_path / "icon-192.png").exists()
        assert (tmp_path / "icon-512.png").exists()

    def test_icon_files_are_valid_png(self, tmp_path):
        generate_pwa_icons(static_dir=str(tmp_path))
        for size in [192, 512]:
            data = (tmp_path / f"icon-{size}.png").read_bytes()
            assert data[:8] == b'\x89PNG\r\n\x1a\n'

    def test_does_not_overwrite_existing_icons(self, tmp_path):
        # Write dummy files first
        for size in [192, 512]:
            (tmp_path / f"icon-{size}.png").write_bytes(b"existing")

        generate_pwa_icons(static_dir=str(tmp_path))

        for size in [192, 512]:
            assert (tmp_path / f"icon-{size}.png").read_bytes() == b"existing"

    def test_creates_subdirectory_if_missing(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        generate_pwa_icons(static_dir=str(nested))
        assert nested.exists()
        assert (nested / "icon-192.png").exists()

    def test_default_static_dir_when_none(self, tmp_path, monkeypatch):
        # Patch Path so the default resolves to tmp_path
        fake_parent = tmp_path / "gmail_organizer"
        fake_parent.mkdir()
        fake_static = tmp_path / ".streamlit" / "static"

        import gmail_organizer.mobile as mobile_mod
        original_file = mobile_mod.__file__
        monkeypatch.setattr(mobile_mod, "__file__", str(fake_parent / "mobile.py"))
        try:
            generate_pwa_icons(static_dir=None)
            assert fake_static.exists()
            assert (fake_static / "icon-192.png").exists()
        finally:
            monkeypatch.setattr(mobile_mod, "__file__", original_file)


# ---------------------------------------------------------------------------
# MobileLayoutHelper -- basics
# ---------------------------------------------------------------------------

class TestMobileLayoutHelperInit:
    def test_initial_compact_flag_is_false(self):
        helper = MobileLayoutHelper()
        assert helper._is_compact is False

    def test_get_pwa_html_returns_pwa_head(self):
        helper = MobileLayoutHelper()
        assert helper.get_pwa_html() == PWA_HEAD_HTML

    def test_get_mobile_css_returns_compact_css(self):
        helper = MobileLayoutHelper()
        assert helper.get_mobile_css() == MOBILE_COMPACT_CSS


# ---------------------------------------------------------------------------
# MobileLayoutHelper.responsive_columns
# ---------------------------------------------------------------------------

class TestResponsiveColumns:
    def test_returns_specs_unchanged(self):
        helper = MobileLayoutHelper()
        specs = [1, 2, 1]
        assert helper.responsive_columns(specs) == [1, 2, 1]

    def test_with_mobile_stack_false(self):
        helper = MobileLayoutHelper()
        specs = [3, 3]
        assert helper.responsive_columns(specs, mobile_stack=False) == [3, 3]

    def test_empty_specs(self):
        helper = MobileLayoutHelper()
        assert helper.responsive_columns([]) == []


# ---------------------------------------------------------------------------
# MobileLayoutHelper.compact_metric_card
# ---------------------------------------------------------------------------

class TestCompactMetricCard:
    def test_returns_dict_with_required_keys(self):
        helper = MobileLayoutHelper()
        result = helper.compact_metric_card("Emails", "1234")
        assert result["label"] == "Emails"
        assert result["value"] == "1234"
        assert result["delta"] is None

    def test_includes_delta_when_provided(self):
        helper = MobileLayoutHelper()
        result = helper.compact_metric_card("Emails", "1234", delta="+10%")
        assert result["delta"] == "+10%"


# ---------------------------------------------------------------------------
# MobileLayoutHelper.email_list_item
# ---------------------------------------------------------------------------

class TestEmailListItem:
    def test_basic_email_formatting(self):
        helper = MobileLayoutHelper()
        email = {
            "sender": "Alice",
            "subject": "Hello",
            "date": "2025-01-01",
            "snippet": "Preview text here",
        }
        result = helper.email_list_item(email)
        assert result["sender"] == "Alice"
        assert result["subject"] == "Hello"
        assert result["date"] == "2025-01-01"
        assert result["snippet"] == "Preview text here"

    def test_truncates_long_sender(self):
        helper = MobileLayoutHelper()
        email = {"sender": "A" * 30, "subject": "Hi", "date": "2025-01-01"}
        result = helper.email_list_item(email)
        assert len(result["sender"]) == 25
        assert result["sender"].endswith("...")

    def test_truncates_long_subject(self):
        helper = MobileLayoutHelper()
        email = {"sender": "Bob", "subject": "S" * 50, "date": "2025-01-01"}
        result = helper.email_list_item(email)
        assert len(result["subject"]) == 40
        assert result["subject"].endswith("...")

    def test_truncates_long_date(self):
        helper = MobileLayoutHelper()
        email = {"sender": "Bob", "subject": "Hi", "date": "2025-01-01T12:00:00Z"}
        result = helper.email_list_item(email)
        assert len(result["date"]) == 10

    def test_truncates_snippet_to_80(self):
        helper = MobileLayoutHelper()
        email = {"sender": "X", "subject": "Y", "date": "Z", "snippet": "W" * 200}
        result = helper.email_list_item(email)
        assert len(result["snippet"]) == 80

    def test_uses_from_field_as_fallback_for_sender(self):
        helper = MobileLayoutHelper()
        email = {"from": "charlie@example.com", "subject": "Test", "date": "2025-01-01"}
        result = helper.email_list_item(email)
        assert result["sender"] == "charlie@example.com"

    def test_defaults_for_missing_fields(self):
        helper = MobileLayoutHelper()
        result = helper.email_list_item({})
        assert result["sender"] == "Unknown"
        assert result["subject"] == "(no subject)"
        assert result["date"] == ""
        assert result["snippet"] == ""

    def test_sender_at_exact_boundary_not_truncated(self):
        helper = MobileLayoutHelper()
        email = {"sender": "A" * 25, "subject": "Hi", "date": "2025-01-01"}
        result = helper.email_list_item(email)
        assert result["sender"] == "A" * 25  # exactly 25, no truncation

    def test_subject_at_exact_boundary_not_truncated(self):
        helper = MobileLayoutHelper()
        email = {"sender": "X", "subject": "B" * 40, "date": "2025-01-01"}
        result = helper.email_list_item(email)
        assert result["subject"] == "B" * 40  # exactly 40, no truncation


# ---------------------------------------------------------------------------
# MobileLayoutHelper.get_install_instructions
# ---------------------------------------------------------------------------

class TestGetInstallInstructions:
    def test_contains_ios_instructions(self):
        helper = MobileLayoutHelper()
        text = helper.get_install_instructions()
        assert "iOS" in text
        assert "Safari" in text

    def test_contains_android_instructions(self):
        helper = MobileLayoutHelper()
        text = helper.get_install_instructions()
        assert "Android" in text
        assert "Chrome" in text

    def test_contains_desktop_instructions(self):
        helper = MobileLayoutHelper()
        text = helper.get_install_instructions()
        assert "Desktop" in text


# ---------------------------------------------------------------------------
# MobileLayoutHelper.get_offline_status_html
# ---------------------------------------------------------------------------

class TestGetOfflineStatusHtml:
    def test_contains_offline_indicator_div(self):
        helper = MobileLayoutHelper()
        html = helper.get_offline_status_html()
        assert 'id="offline-indicator"' in html

    def test_contains_online_and_offline_listeners(self):
        helper = MobileLayoutHelper()
        html = helper.get_offline_status_html()
        assert "addEventListener('offline'" in html
        assert "addEventListener('online'" in html

    def test_contains_navigator_online_check(self):
        helper = MobileLayoutHelper()
        html = helper.get_offline_status_html()
        assert "navigator.onLine" in html


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_pwa_head_html_contains_manifest_link(self):
        assert "manifest.json" in PWA_HEAD_HTML

    def test_pwa_head_html_contains_service_worker_registration(self):
        assert "serviceWorker" in PWA_HEAD_HTML

    def test_mobile_css_contains_media_query(self):
        assert "@media (max-width: 768px)" in MOBILE_COMPACT_CSS

    def test_mobile_css_contains_standalone_mode(self):
        assert "@media (display-mode: standalone)" in MOBILE_COMPACT_CSS
