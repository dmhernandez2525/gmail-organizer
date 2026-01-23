"""Theme management for Gmail Organizer UI."""

from typing import Dict, Optional


# Theme definitions with colors and CSS
THEMES: Dict[str, Dict] = {
    "default": {
        "name": "Default Light",
        "description": "Clean light theme with blue accents",
        "primaryColor": "#1f77b4",
        "backgroundColor": "#ffffff",
        "secondaryBackgroundColor": "#f0f2f6",
        "textColor": "#262730",
        "font": "sans serif",
        "css": "",
    },
    "dark": {
        "name": "Dark Mode",
        "description": "Dark theme for reduced eye strain",
        "primaryColor": "#4da6ff",
        "backgroundColor": "#0e1117",
        "secondaryBackgroundColor": "#262730",
        "textColor": "#fafafa",
        "font": "sans serif",
        "css": """
            .stApp {
                background-color: #0e1117;
            }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, p, span, label {
                color: #fafafa !important;
            }
            .stSelectbox label, .stRadio label, .stSlider label,
            .stTextInput label, .stNumberInput label {
                color: #fafafa !important;
            }
            [data-testid="stSidebar"] {
                background-color: #1a1d24;
            }
            [data-testid="stHeader"] {
                background-color: #0e1117;
            }
            .stTabs [data-baseweb="tab-list"] {
                background-color: #1a1d24;
                border-radius: 8px;
            }
            .stTabs [data-baseweb="tab"] {
                color: #b0b8c4;
            }
            .stTabs [aria-selected="true"] {
                color: #4da6ff !important;
            }
            [data-testid="stMetric"] {
                background-color: #1a1d24;
                border-radius: 8px;
                padding: 12px;
            }
            .stDataFrame {
                background-color: #1a1d24;
            }
            [data-testid="stExpander"] {
                background-color: #1a1d24;
                border-color: #333;
            }
            div[data-testid="stMarkdownContainer"] p {
                color: #fafafa;
            }
        """,
    },
    "midnight": {
        "name": "Midnight Blue",
        "description": "Deep blue dark theme",
        "primaryColor": "#6c9fff",
        "backgroundColor": "#0a1628",
        "secondaryBackgroundColor": "#162238",
        "textColor": "#e8edf5",
        "font": "sans serif",
        "css": """
            .stApp {
                background-color: #0a1628;
            }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, p, span, label {
                color: #e8edf5 !important;
            }
            .stSelectbox label, .stRadio label, .stSlider label,
            .stTextInput label, .stNumberInput label {
                color: #e8edf5 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #0f1d33;
            }
            [data-testid="stHeader"] {
                background-color: #0a1628;
            }
            .stTabs [data-baseweb="tab-list"] {
                background-color: #0f1d33;
                border-radius: 8px;
            }
            .stTabs [data-baseweb="tab"] {
                color: #8899b3;
            }
            .stTabs [aria-selected="true"] {
                color: #6c9fff !important;
            }
            [data-testid="stMetric"] {
                background-color: #162238;
                border-radius: 8px;
                padding: 12px;
            }
            [data-testid="stExpander"] {
                background-color: #162238;
                border-color: #2a3a55;
            }
        """,
    },
    "solarized": {
        "name": "Solarized",
        "description": "Warm solarized color scheme",
        "primaryColor": "#268bd2",
        "backgroundColor": "#fdf6e3",
        "secondaryBackgroundColor": "#eee8d5",
        "textColor": "#657b83",
        "font": "sans serif",
        "css": """
            .stApp {
                background-color: #fdf6e3;
            }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, p, span, label {
                color: #657b83 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #eee8d5;
            }
            [data-testid="stHeader"] {
                background-color: #fdf6e3;
            }
            [data-testid="stMetric"] {
                background-color: #eee8d5;
                border-radius: 8px;
                padding: 12px;
            }
            h1, h2, h3 {
                color: #073642 !important;
            }
        """,
    },
    "nord": {
        "name": "Nord",
        "description": "Arctic-inspired color palette",
        "primaryColor": "#88c0d0",
        "backgroundColor": "#2e3440",
        "secondaryBackgroundColor": "#3b4252",
        "textColor": "#eceff4",
        "font": "sans serif",
        "css": """
            .stApp {
                background-color: #2e3440;
            }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, p, span, label {
                color: #eceff4 !important;
            }
            .stSelectbox label, .stRadio label, .stSlider label,
            .stTextInput label, .stNumberInput label {
                color: #eceff4 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #3b4252;
            }
            [data-testid="stHeader"] {
                background-color: #2e3440;
            }
            .stTabs [data-baseweb="tab-list"] {
                background-color: #3b4252;
                border-radius: 8px;
            }
            .stTabs [data-baseweb="tab"] {
                color: #d8dee9;
            }
            .stTabs [aria-selected="true"] {
                color: #88c0d0 !important;
            }
            [data-testid="stMetric"] {
                background-color: #3b4252;
                border-radius: 8px;
                padding: 12px;
            }
            [data-testid="stExpander"] {
                background-color: #3b4252;
                border-color: #4c566a;
            }
        """,
    },
    "high_contrast": {
        "name": "High Contrast",
        "description": "Maximum readability with strong contrast",
        "primaryColor": "#ffcc00",
        "backgroundColor": "#000000",
        "secondaryBackgroundColor": "#1a1a1a",
        "textColor": "#ffffff",
        "font": "sans serif",
        "css": """
            .stApp {
                background-color: #000000;
            }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6, p, span, label {
                color: #ffffff !important;
            }
            .stSelectbox label, .stRadio label, .stSlider label,
            .stTextInput label, .stNumberInput label {
                color: #ffffff !important;
            }
            [data-testid="stSidebar"] {
                background-color: #0d0d0d;
                border-right: 2px solid #ffcc00;
            }
            [data-testid="stHeader"] {
                background-color: #000000;
            }
            .stTabs [data-baseweb="tab-list"] {
                background-color: #1a1a1a;
            }
            .stTabs [aria-selected="true"] {
                color: #ffcc00 !important;
                border-bottom-color: #ffcc00 !important;
            }
            [data-testid="stMetric"] {
                background-color: #1a1a1a;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 12px;
            }
            [data-testid="stExpander"] {
                background-color: #1a1a1a;
                border-color: #444;
            }
            a {
                color: #ffcc00 !important;
            }
        """,
    },
}


class ThemeManager:
    """Manages theme selection and application for the Streamlit app."""

    def __init__(self):
        self.themes = THEMES

    def get_theme_names(self):
        """Get list of available theme names."""
        return list(self.themes.keys())

    def get_theme(self, name: str) -> Optional[Dict]:
        """Get theme configuration by name."""
        return self.themes.get(name)

    def get_theme_css(self, name: str) -> str:
        """Get the CSS for a theme."""
        theme = self.themes.get(name)
        if theme:
            return theme.get("css", "")
        return ""

    def apply_theme_css(self, name: str) -> str:
        """Generate the full CSS style tag for a theme.

        Args:
            name: Theme name to apply.

        Returns:
            HTML style tag string to inject via st.markdown.
        """
        css = self.get_theme_css(name)
        if not css:
            return ""

        return f"<style>{css}</style>"

    def get_theme_preview(self, name: str) -> Dict:
        """Get theme preview colors for display.

        Args:
            name: Theme name.

        Returns:
            Dict with color values for preview.
        """
        theme = self.themes.get(name, {})
        return {
            "name": theme.get("name", name),
            "description": theme.get("description", ""),
            "primary": theme.get("primaryColor", "#000"),
            "background": theme.get("backgroundColor", "#fff"),
            "secondary": theme.get("secondaryBackgroundColor", "#eee"),
            "text": theme.get("textColor", "#000"),
        }
