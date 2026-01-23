"""Mobile companion and PWA support for Gmail Organizer."""

import base64
import struct
import zlib
from pathlib import Path
from typing import Dict, Optional


# PWA meta tags and service worker registration
PWA_HEAD_HTML = """
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Gmail Organizer">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#1f77b4">
<meta name="msapplication-TileColor" content="#1f77b4">
<link rel="manifest" href="/app/static/manifest.json">
<link rel="apple-touch-icon" href="/app/static/icon-192.png">
<link rel="stylesheet" href="/app/static/mobile.css">
<script>
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/app/static/service-worker.js', {scope: '/'})
            .then(function(registration) {
                console.log('SW registered:', registration.scope);
            })
            .catch(function(error) {
                console.log('SW registration failed:', error);
            });
    });
}
</script>
"""

# Compact mobile layout CSS injected via Streamlit
MOBILE_COMPACT_CSS = """
<style>
/* Mobile-first compact layout */
@media (max-width: 768px) {
    .main .block-container {
        padding: 1rem 0.75rem !important;
        max-width: 100% !important;
    }
    [data-testid="stSidebar"] {
        min-width: 0 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
        display: none;
    }
    .stTabs [data-baseweb="tab"] {
        white-space: nowrap !important;
        font-size: 0.8rem !important;
        padding: 8px 12px !important;
    }
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 0 100% !important;
    }
    [data-testid="stMetric"] {
        padding: 8px !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.2rem !important;
    }
    .stButton > button {
        width: 100% !important;
        min-height: 44px !important;
    }
    .stTextInput input, .stNumberInput input {
        font-size: 16px !important;
    }
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.25rem !important; }
    h3 { font-size: 1.1rem !important; }
}
@media (display-mode: standalone) {
    [data-testid="stHeader"] { display: none !important; }
    .main .block-container {
        padding-top: env(safe-area-inset-top, 1rem) !important;
    }
    .stApp {
        padding-bottom: env(safe-area-inset-bottom);
    }
}
</style>
"""


def _create_png(width: int, height: int, color: tuple) -> bytes:
    """Generate a minimal single-color PNG image.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        color: RGB tuple (r, g, b) with values 0-255.

    Returns:
        PNG file contents as bytes.
    """
    r, g, b = color

    # Build raw pixel data (RGBA)
    raw_data = b''
    for _ in range(height):
        raw_data += b'\x00'  # Filter byte (none)
        for _ in range(width):
            raw_data += struct.pack('BBBB', r, g, b, 255)

    # Compress with zlib
    compressed = zlib.compress(raw_data, 9)

    # PNG signature
    png = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    png += struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)

    # IDAT chunk
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    png += struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)

    # IEND chunk
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    png += struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)

    return png


def generate_pwa_icons(static_dir: Optional[str] = None):
    """Generate PWA icon PNG files if they don't exist.

    Creates simple branded icons in the Streamlit static directory.

    Args:
        static_dir: Path to the static directory. Defaults to .streamlit/static/.
    """
    if static_dir:
        icons_dir = Path(static_dir)
    else:
        icons_dir = Path(__file__).parent.parent / ".streamlit" / "static"

    icons_dir.mkdir(parents=True, exist_ok=True)

    # Brand color: Gmail Organizer blue
    brand_color = (31, 119, 180)

    icon_sizes = [192, 512]
    for size in icon_sizes:
        icon_path = icons_dir / f"icon-{size}.png"
        if not icon_path.exists():
            png_data = _create_png(size, size, brand_color)
            icon_path.write_bytes(png_data)


class MobileLayoutHelper:
    """Helper for creating mobile-optimized Streamlit layouts.

    Provides methods to detect mobile viewports and render
    compact versions of common UI patterns.
    """

    def __init__(self):
        self._is_compact = False

    def get_pwa_html(self) -> str:
        """Get the HTML for PWA meta tags and service worker registration.

        Returns:
            HTML string to inject via st.markdown(unsafe_allow_html=True).
        """
        return PWA_HEAD_HTML

    def get_mobile_css(self) -> str:
        """Get the mobile-responsive CSS.

        Returns:
            HTML style tag string for mobile layout.
        """
        return MOBILE_COMPACT_CSS

    def responsive_columns(self, specs: list, mobile_stack: bool = True) -> list:
        """Create responsive column specs that stack on mobile.

        Args:
            specs: Column width specs (e.g., [1, 2, 1]).
            mobile_stack: If True, columns stack vertically on mobile.

        Returns:
            The specs list (for use with st.columns).
        """
        return specs

    def compact_metric_card(self, label: str, value: str,
                            delta: Optional[str] = None) -> Dict:
        """Create data for a compact metric card.

        Args:
            label: Metric label.
            value: Metric value.
            delta: Optional delta/change indicator.

        Returns:
            Dict with label, value, delta for rendering.
        """
        return {
            "label": label,
            "value": value,
            "delta": delta,
        }

    def email_list_item(self, email: Dict) -> Dict:
        """Format an email for compact mobile list display.

        Args:
            email: Email dict with sender, subject, date fields.

        Returns:
            Dict with formatted fields for compact display.
        """
        sender = email.get("sender", email.get("from", "Unknown"))
        subject = email.get("subject", "(no subject)")
        date = email.get("date", "")

        # Truncate for mobile display
        if len(sender) > 25:
            sender = sender[:22] + "..."
        if len(subject) > 40:
            subject = subject[:37] + "..."
        if len(date) > 10:
            date = date[:10]

        return {
            "sender": sender,
            "subject": subject,
            "date": date,
            "snippet": email.get("snippet", "")[:80],
        }

    def get_install_instructions(self) -> str:
        """Get PWA installation instructions for display.

        Returns:
            Markdown-formatted installation instructions.
        """
        return """
### Install as Mobile App

**iOS (Safari):**
1. Tap the Share button (square with arrow)
2. Scroll down and tap "Add to Home Screen"
3. Tap "Add" to confirm

**Android (Chrome):**
1. Tap the three-dot menu
2. Tap "Add to Home Screen" or "Install App"
3. Tap "Install" to confirm

**Desktop (Chrome/Edge):**
1. Click the install icon in the address bar
2. Click "Install" to confirm

Once installed, the app will open in standalone mode without browser chrome.
"""

    def get_offline_status_html(self) -> str:
        """Get HTML for an offline status indicator.

        Returns:
            HTML/JS snippet that shows offline/online status.
        """
        return """
<div id="offline-indicator" style="display:none; position:fixed; top:0; left:0; right:0;
     background:#ff6b6b; color:white; text-align:center; padding:4px; font-size:0.8rem; z-index:10000;">
    You are offline. Changes will sync when reconnected.
</div>
<script>
window.addEventListener('offline', function() {
    document.getElementById('offline-indicator').style.display = 'block';
});
window.addEventListener('online', function() {
    document.getElementById('offline-indicator').style.display = 'none';
});
if (!navigator.onLine) {
    document.getElementById('offline-indicator').style.display = 'block';
}
</script>
"""
