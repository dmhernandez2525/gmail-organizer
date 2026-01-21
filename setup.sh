#!/bin/bash

# Gmail Organizer Setup Script

echo "====================================="
echo "  Gmail Organizer - Setup"
echo "====================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Anthropic API key"
    echo ""
else
    echo "✓ .env file exists"
fi

# Check if client_secret.json exists
if [ ! -f "client_secret.json" ]; then
    echo ""
    echo "⚠️  client_secret.json not found"
    echo ""
    echo "Please download OAuth credentials from Google Cloud Console:"
    echo "1. Go to: https://console.cloud.google.com/"
    echo "2. Enable Gmail API"
    echo "3. Create OAuth 2.0 credentials (Desktop app)"
    echo "4. Download and save as client_secret.json"
    echo ""
else
    echo "✓ client_secret.json found"
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error installing dependencies"
    exit 1
fi

echo ""
echo "====================================="
echo "  Setup Complete!"
echo "====================================="
echo ""
echo "Next steps:"
echo "1. Edit .env and add your Anthropic API key"
echo "2. Make sure client_secret.json is in this directory"
echo "3. Create a clickable app (see CREATE_MACOS_APP.md)"
echo "4. Or run directly:"
echo ""
echo "   Easy:    ./launch_gmail_organizer.sh"
echo "   Web UI:  streamlit run frontend.py"
echo "   CLI:     python main.py"
echo ""
