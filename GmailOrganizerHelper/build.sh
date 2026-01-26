#!/bin/zsh
# Build Gmail Organizer Helper menubar app

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Gmail Organizer Helper"
APP_PATH="$HOME/Desktop/${APP_NAME}.app"
BUILD_DIR="$SCRIPT_DIR/build"
SOURCES_DIR="$SCRIPT_DIR/Sources"

echo "Building Gmail Organizer Helper..."

# Clean previous build
rm -rf "$BUILD_DIR"
rm -rf "$APP_PATH"
mkdir -p "$BUILD_DIR"

# Collect all Swift source files (order matters - dependencies first)
SWIFT_FILES=(
    "$SOURCES_DIR/Utils.swift"
    "$SOURCES_DIR/ResultsManager.swift"
    "$SOURCES_DIR/PromptTemplates.swift"
    "$SOURCES_DIR/EmbeddedTerminal.swift"
    "$SOURCES_DIR/ProcessingManager.swift"
    "$SOURCES_DIR/WorkerManager.swift"
    "$SOURCES_DIR/ProcessingPanel.swift"
    "$SOURCES_DIR/MainPanel.swift"
    "$SOURCES_DIR/AppDelegate.swift"
    "$SOURCES_DIR/main.swift"
)

echo "Compiling ${#SWIFT_FILES[@]} source files..."

# Compile Swift
swiftc -o "$BUILD_DIR/GmailOrganizerHelper" \
    -O \
    -target arm64-apple-macosx12.0 \
    -sdk $(xcrun --show-sdk-path) \
    -framework Cocoa \
    -framework UserNotifications \
    "${SWIFT_FILES[@]}"

echo "Creating app bundle..."

# Create app bundle structure
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Copy executable
cp "$BUILD_DIR/GmailOrganizerHelper" "$APP_PATH/Contents/MacOS/"

# Create Info.plist
cat > "$APP_PATH/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>GmailOrganizerHelper</string>
    <key>CFBundleIdentifier</key>
    <string>com.gmail-organizer.helper</string>
    <key>CFBundleName</key>
    <string>Gmail Organizer Helper</string>
    <key>CFBundleDisplayName</key>
    <string>Gmail Organizer Helper</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.productivity</string>
    <key>CFBundleURLTypes</key>
    <array>
        <dict>
            <key>CFBundleURLName</key>
            <string>com.gmail-organizer.helper</string>
            <key>CFBundleURLSchemes</key>
            <array>
                <string>gmailorganizer</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
EOF

# Touch the app
touch "$APP_PATH"

# Code sign with entitlements (ad-hoc signing for local use)
echo "Code signing app..."
codesign --force --deep --sign - --entitlements "$SCRIPT_DIR/entitlements.plist" "$APP_PATH"

echo ""
echo "Build successful!"
echo "   App created at: $APP_PATH"
echo ""
echo "To run: open '$APP_PATH'"
echo ""
echo "URL Scheme examples:"
echo "   gmailorganizer://process/accountname  - Process specific account"
echo "   gmailorganizer://process-all          - Process all accounts"
echo "   gmailorganizer://open                 - Open web interface"
