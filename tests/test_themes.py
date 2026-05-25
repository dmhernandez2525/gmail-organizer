"""Tests for the theme management module."""

import pytest

from gmail_organizer.themes import THEMES, ThemeManager


class TestThemesDict:
    """Tests for the THEMES module-level dictionary."""

    def test_themes_not_empty(self):
        assert len(THEMES) > 0

    def test_default_theme_exists(self):
        assert "default" in THEMES

    def test_dark_theme_exists(self):
        assert "dark" in THEMES

    def test_all_themes_have_required_keys(self):
        required = {
            "name",
            "description",
            "primaryColor",
            "backgroundColor",
            "secondaryBackgroundColor",
            "textColor",
            "font",
            "css",
        }
        for theme_name, theme_data in THEMES.items():
            missing = required - set(theme_data.keys())
            assert not missing, f"Theme '{theme_name}' missing keys: {missing}"

    def test_default_theme_has_no_css(self):
        assert THEMES["default"]["css"] == ""

    def test_dark_theme_has_css(self):
        assert len(THEMES["dark"]["css"].strip()) > 0

    @pytest.mark.parametrize("theme_name", list(THEMES.keys()))
    def test_color_values_are_hex(self, theme_name):
        theme = THEMES[theme_name]
        for key in ("primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor"):
            val = theme[key]
            assert val.startswith("#"), f"{theme_name}.{key} = {val!r} is not hex"

    @pytest.mark.parametrize("theme_name", [
        "default", "dark", "midnight", "solarized", "nord", "high_contrast"
    ])
    def test_expected_themes_present(self, theme_name):
        assert theme_name in THEMES


class TestThemeManagerGetThemeNames:
    """Tests for ThemeManager.get_theme_names."""

    def test_returns_all_keys(self):
        mgr = ThemeManager()
        names = mgr.get_theme_names()
        assert set(names) == set(THEMES.keys())

    def test_returns_list(self):
        mgr = ThemeManager()
        assert isinstance(mgr.get_theme_names(), list)


class TestThemeManagerGetTheme:
    """Tests for ThemeManager.get_theme."""

    def test_returns_dict_for_valid_theme(self):
        mgr = ThemeManager()
        theme = mgr.get_theme("default")
        assert isinstance(theme, dict)
        assert theme["name"] == "Default Light"

    def test_returns_none_for_unknown_theme(self):
        mgr = ThemeManager()
        assert mgr.get_theme("nonexistent") is None

    def test_returns_correct_theme_data(self):
        mgr = ThemeManager()
        theme = mgr.get_theme("dark")
        assert theme["primaryColor"] == "#4da6ff"
        assert theme["backgroundColor"] == "#0e1117"


class TestThemeManagerGetThemeCss:
    """Tests for ThemeManager.get_theme_css."""

    def test_returns_css_for_dark(self):
        mgr = ThemeManager()
        css = mgr.get_theme_css("dark")
        assert ".stApp" in css

    def test_returns_empty_for_default(self):
        mgr = ThemeManager()
        css = mgr.get_theme_css("default")
        assert css == ""

    def test_returns_empty_for_unknown(self):
        mgr = ThemeManager()
        css = mgr.get_theme_css("nonexistent")
        assert css == ""


class TestThemeManagerApplyThemeCss:
    """Tests for ThemeManager.apply_theme_css."""

    def test_wraps_css_in_style_tag(self):
        mgr = ThemeManager()
        result = mgr.apply_theme_css("dark")
        assert result.startswith("<style>")
        assert result.endswith("</style>")
        assert ".stApp" in result

    def test_empty_for_default(self):
        mgr = ThemeManager()
        result = mgr.apply_theme_css("default")
        assert result == ""

    def test_empty_for_unknown(self):
        mgr = ThemeManager()
        result = mgr.apply_theme_css("nonexistent")
        assert result == ""


class TestThemeManagerGetThemePreview:
    """Tests for ThemeManager.get_theme_preview."""

    def test_preview_for_valid_theme(self):
        mgr = ThemeManager()
        preview = mgr.get_theme_preview("dark")
        assert preview["name"] == "Dark Mode"
        assert preview["description"] == "Dark theme for reduced eye strain"
        assert preview["primary"] == "#4da6ff"
        assert preview["background"] == "#0e1117"
        assert preview["secondary"] == "#262730"
        assert preview["text"] == "#fafafa"

    def test_preview_for_unknown_returns_defaults(self):
        mgr = ThemeManager()
        preview = mgr.get_theme_preview("nonexistent")
        assert preview["name"] == "nonexistent"
        assert preview["description"] == ""
        assert preview["primary"] == "#000"
        assert preview["background"] == "#fff"
        assert preview["secondary"] == "#eee"
        assert preview["text"] == "#000"

    @pytest.mark.parametrize("theme_name", list(THEMES.keys()))
    def test_preview_has_all_fields(self, theme_name):
        mgr = ThemeManager()
        preview = mgr.get_theme_preview(theme_name)
        assert "name" in preview
        assert "description" in preview
        assert "primary" in preview
        assert "background" in preview
        assert "secondary" in preview
        assert "text" in preview


class TestThemeManagerUsesModuleThemes:
    """Verify ThemeManager references the module-level THEMES dict."""

    def test_themes_attribute_matches_module(self):
        mgr = ThemeManager()
        assert mgr.themes is THEMES
