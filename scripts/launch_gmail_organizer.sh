#!/bin/bash

# Gmail Organizer Launcher
# Double-click this to launch the app

# Get the directory where this script is located, then go to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$DIR"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping Gmail Organizer..."

    # Kill Streamlit process if running
    if [ ! -z "$STREAMLIT_PID" ]; then
        kill $STREAMLIT_PID 2>/dev/null
        sleep 1
    fi

    # Make sure port 8501 is freed
    lsof -ti:8501 | xargs kill -9 2>/dev/null

    echo "✓ Server stopped"
    exit 0
}

# Trap Ctrl+C and script exit
trap cleanup INT TERM EXIT

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Error: .env file not found"
    echo "Please run setup first!"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if Anthropic API key is set
if ! grep -q "ANTHROPIC_API_KEY=sk-" .env; then
    echo "⚠️  Error: ANTHROPIC_API_KEY not set in .env"
    echo ""
    echo "Please add your Anthropic API key:"
    echo "1. Get key from: https://console.anthropic.com/settings/keys"
    echo "2. Edit .env file and add: ANTHROPIC_API_KEY=sk-your-key-here"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if client_secret.json exists
if [ ! -f "client_secret.json" ]; then
    echo "⚠️  Warning: client_secret.json not found"
    echo "You'll need Google OAuth credentials to authenticate accounts"
    echo ""
fi

echo "====================================="
echo "  📧 Gmail Organizer"
echo "====================================="
echo ""
echo "Starting server..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Use full path to streamlit if venv exists, otherwise use system streamlit
if [ -f "venv/bin/streamlit" ]; then
    STREAMLIT_CMD="./venv/bin/streamlit"
else
    STREAMLIT_CMD="streamlit"
fi

# Auto-restart loop
RESTART_COUNT=0
BROWSER_OPENED=false

while true; do
    # Start Streamlit in the background
    $STREAMLIT_CMD run app.py --server.headless true --server.port 8501 &
    STREAMLIT_PID=$!

    # Wait for server to start
    echo "Waiting for server to start..."
    sleep 3

    # Check if Streamlit is still running
    if ! ps -p $STREAMLIT_PID > /dev/null; then
        echo "❌ Failed to start server"
        echo ""
        echo "Try running manually:"
        echo "  cd $DIR"
        echo "  streamlit run app.py"
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo "✓ Server started!"

    # Open browser only on first start
    if [ "$BROWSER_OPENED" = false ]; then
        echo ""
        echo "Opening in browser..."

        # Open in Chrome (or default browser if Chrome not found)
        if [ -d "/Applications/Google Chrome.app" ]; then
            open -a "Google Chrome" http://localhost:8501
        elif [ -d "/Applications/Brave Browser.app" ]; then
            open -a "Brave Browser" http://localhost:8501
        else
            open http://localhost:8501
        fi

        BROWSER_OPENED=true

        echo ""
        echo "====================================="
        echo "  Gmail Organizer is running!"
        echo "====================================="
        echo ""
        echo "Access at: http://localhost:8501"
        echo ""
        echo "Press Ctrl+C to stop the server"
        echo "Auto-restart enabled ♻️"
        echo ""
    fi

    # Monitor the process
    wait $STREAMLIT_PID
    EXIT_CODE=$?

    # If we get here, Streamlit has stopped
    RESTART_COUNT=$((RESTART_COUNT + 1))

    # Log to file
    LOG_DIR="$DIR/logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/gmail_organizer_$(date +%Y%m%d).log"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - launcher - WARNING - Streamlit stopped unexpectedly (exit code: $EXIT_CODE, restart #$RESTART_COUNT)" >> "$LOG_FILE"

    echo ""
    echo "⚠️  Streamlit stopped unexpectedly (exit code: $EXIT_CODE)"
    echo "🔄 Auto-restarting... (attempt #$RESTART_COUNT)"
    echo ""

    # Brief pause before restart to avoid rapid restart loops
    sleep 2
done
