# 📧 Gmail Organizer

AI-powered email management system that automatically categorizes and organizes emails across multiple Gmail accounts using Claude AI.

![Gmail Organizer](https://img.shields.io/badge/AI-Claude-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## 🎯 What It Does

Gmail Organizer uses AI to automatically:
- **Analyze** your inbox patterns and suggest relevant categories
- **Classify** emails based on sender, subject, and content
- **Create** Gmail labels automatically
- **Organize** thousands of emails in minutes
- **Support** multiple Gmail accounts simultaneously

### Why It's Useful

**Problem:** Managing multiple Gmail accounts with thousands of emails is overwhelming. Manual organization is time-consuming and inconsistent.

**Solution:** Gmail Organizer uses Claude AI to intelligently categorize your emails, creating a clean, organized inbox in minutes instead of hours.

**Key Benefits:**
- ⚡ **Fast**: Process 80,000+ emails in under 10 minutes
- 💰 **Cost-Effective**: Use free Claude Code CLI or pay-per-use API
- 🎯 **Accurate**: AI understands context and categorizes intelligently
- 🔐 **Private**: All processing happens locally, no data stored
- 🔄 **Multi-Account**: Manage 5+ Gmail accounts from one interface
- 🚀 **Job Search Focused**: Special categories for job hunting

## ✨ Features

### 1. AI-Powered Analysis
- Scans your entire inbox (inbox, sent, archives)
- Discovers patterns in your email usage
- Suggests categories based on YOUR actual emails
- Prioritizes job search emails if configured

### 2. Two Classification Methods

**Method 1: Claude Code CLI (Recommended - FREE)**
- Uses Claude Code CLI installed on your Mac
- Zero API costs
- Full 200K token context window
- Processes emails locally via Terminal
- Saves results to `.claude-processing/`

**Method 2: Anthropic API**
- Direct API integration
- Token-optimized (sender + subject only)
- ~70% token savings vs. full email body
- Pay-per-use pricing

### 3. Smart Categories

**Job Search Categories:**
- 🎯 Interviews
- 📝 Applications
- 💼 Offers
- 📧 Rejections
- 🤝 Networking

**General Categories:**
- 🛒 Shopping/Receipts
- 📰 Newsletters
- 💰 Finance
- 🔔 Notifications
- ⭐ Important
- 📂 Saved (default)

### 4. Incremental Sync (Gmail History API)

**First sync:** Full fetch of all emails (may take hours for large mailboxes)

**Future syncs:** Only fetches NEW emails since last sync (seconds instead of hours!)

How it works:
- Stores Gmail `historyId` after each sync in `.sync-state/`
- Uses Gmail's `history.list` API to detect changes
- Only fetches new/modified emails
- Caches email metadata locally for instant access

Benefits:
- ⚡ **Lightning fast**: Future syncs complete in seconds
- 💾 **Efficient**: No re-downloading 80K+ emails
- 🔄 **Automatic**: App chooses full vs incremental automatically
- 📊 **Resumable**: Checkpoints save progress during full sync

### 5. Powerful Features
- **Pagination Support**: Process unlimited emails (Gmail API handles 500/batch)
- **Batch API**: Fetches 50 emails per HTTP request (50x faster)
- **Partial Batch Recovery**: Saves successful emails even when some fail
- **Auto-Restart**: App automatically recovers from crashes
- **Comprehensive Logging**: All actions logged to `logs/` folder
- **Email Count Accuracy**: Uses Gmail Profile API for exact totals
- **Progress Tracking**: Real-time progress bars and status updates
- **Checkpoint System**: Resumes from where it left off after interruption
- **Rate Limit Handling**: Exponential backoff with smart retries

## 🚀 Getting Started

### Prerequisites

- macOS (for .app launcher)
- Python 3.11+
- Gmail account(s)
- Anthropic API key OR Claude Code CLI

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd gmail-organizer
```

2. **Set up environment**
```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your Anthropic API key
# Get key from: https://console.anthropic.com/settings/keys
nano .env
```

3. **Get Google OAuth credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download as `client_secret.json` to project root
   - Add yourself as a test user in OAuth consent screen

4. **Install dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. **(Optional) Install Claude Code CLI**
```bash
npm install -g @anthropic-ai/claude-code
```

### Usage

#### Option 1: macOS App (Recommended)

Double-click `Gmail Organizer.app` on your Desktop

#### Option 2: Command Line

```bash
cd ~/Desktop/Projects/PersonalProjects/gmail-organizer
./launch_gmail_organizer.sh
```

#### Option 3: Streamlit Direct

```bash
source venv/bin/activate
streamlit run frontend.py
```

### First-Time Setup

1. **Add Gmail Account**
   - Click "➕ Add Gmail Account" in sidebar
   - Name your account (e.g., "personal", "work")
   - Browser opens for Google OAuth
   - Grant permissions
   - Account saved for future use

2. **Analyze Inbox** (Optional but Recommended)
   - Go to "🔍 Analyze First" tab
   - Select account
   - Choose "All Mail" to scan everything
   - Set email count (or use "All")
   - Click "🔍 Analyze Inbox"
   - Review AI-suggested categories

3. **Process Emails**

   **If using Claude Code CLI:**
   - Go to "📥 Process Emails" tab
   - Select account and email count
   - Click "📤 Step 1: Export & Launch Claude Code"
   - Terminal opens automatically
   - Wait for "Classification complete!" message
   - Return to app, click "✅ Step 2: Apply Results"

   **If using Anthropic API:**
   - Go to Settings, uncheck "Use Claude Code"
   - Go to "📥 Process Emails" tab
   - Click "🚀 Start Processing"
   - Watch progress bar

4. **Check Results**
   - Go to "📊 Results" tab
   - View category breakdown
   - See classified emails

## 📁 Project Structure

```
gmail-organizer/
├── .claude-processing/       # Git-ignored: Email exports for Claude Code
├── .email-cache/             # Git-ignored: Checkpoint files for resumable fetching
├── .sync-state/              # Git-ignored: Incremental sync state (historyId, cached emails)
├── .env                       # Git-ignored: API keys
├── .env.example              # Template for environment variables
├── client_secret.json        # Git-ignored: Google OAuth credentials
├── credentials/              # Git-ignored: Saved Gmail OAuth tokens
├── logs/                     # Git-ignored: Application logs
├── venv/                     # Git-ignored: Python virtual environment
├── Gmail Organizer.app       # macOS launcher app
├── launch_gmail_organizer.sh # Launch script with auto-restart
├── requirements.txt          # Python dependencies
├── frontend.py              # Streamlit web interface
├── gmail_auth.py            # Multi-account OAuth manager
├── gmail_operations.py      # Gmail API operations + incremental sync
├── email_classifier.py      # AI classification with Anthropic
├── email_analyzer.py        # Inbox pattern analysis
├── claude_code_integration.py # Claude Code CLI integration
├── config.py                # Category definitions
├── logger.py                # Logging configuration
└── README.md                # This file
```

## ⚙️ Configuration

### Settings Tab Options

1. **AI Classification Method**
   - Use Claude Code CLI (free, recommended)
   - Use Anthropic API (paid, but token-optimized)

2. **Incremental Sync (Gmail History API)**
   - Enable incremental sync: ON (default, recommended)
   - View sync state info for each account
   - See last sync time and cached email count

3. **Token Optimization**
   - Include email body: OFF (default, saves 70% tokens)
   - Include email body: ON (slightly better accuracy, costs more)

4. **API Configuration**
   - Verify Anthropic API key is set
   - View connection status

### Environment Variables

```bash
# Required for API method
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional
API_KEY=your-custom-key
```

### Categories Customization

Edit `config.py` to add/remove categories:

```python
CATEGORIES = {
    'job_search': {
        'interviews': {
            'name': 'Interviews',
            'description': 'Interview invitations and scheduling',
            'color': '#FF6B6B'
        },
        # ... more categories
    }
}
```

## 🔒 Privacy & Security

- **No data storage**: Emails never stored on external servers
- **Local processing**: All classification happens locally or via Anthropic API
- **OAuth tokens**: Stored encrypted in `credentials/` folder
- **API keys**: Never committed to git (via .gitignore)
- **Email exports**: Temporary files in `.claude-processing/` (git-ignored)
- **Logs**: Contain no email content, only metadata and counts

## 📊 Performance

- **Email Count**: Unlimited (pagination support)
- **Full Sync Speed**: ~100 emails/minute (with Gmail API rate limiting)
- **Incremental Sync Speed**: Seconds (only fetches new emails!)
- **Classification Speed**: ~500 emails/minute with Claude Code
- **Accuracy**: 90-95% with sender + subject only
- **Cost**:
  - Claude Code: $0 (free)
  - Anthropic API: ~$0.20 per 1,000 emails (with optimization)

### Gmail API Limits
| Limit | Value |
|-------|-------|
| Per-user quota | 15,000 units/minute |
| `messages.get` cost | 5 units each |
| Max fetches/minute | ~3,000 messages |
| Batch size | 50 (Google recommended) |

The app handles rate limits automatically with exponential backoff and checkpoint recovery.

## 🛠️ Troubleshooting

### App won't start
- Check Terminal for errors
- Verify `venv/` is created: `ls venv/`
- Reinstall dependencies: `pip install -r requirements.txt`

### "Connection error" in browser
- Streamlit may have crashed
- Check logs: `tail -f logs/gmail_organizer_*.log`
- Auto-restart should recover within 2 seconds

### OAuth errors
- Delete credentials: `rm -rf credentials/`
- Re-authenticate account
- Verify you're a test user in Google Cloud Console

### Claude Code not detected
- Install: `npm install -g @anthropic-ai/claude-code`
- Verify: `which claude`
- Restart app

### Low accuracy
- Enable "Include email body" in Settings (costs more tokens)
- Review and edit categories in `config.py`
- Use "Analyze First" to discover better categories

## 🤝 Contributing

This is a personal project, but suggestions and feedback are welcome!

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Gmail API by Google
- [Streamlit](https://streamlit.io/) for the UI

## 📧 Contact

For questions or issues, please open a GitHub issue.

---

**Made with ❤️ to organize chaos and focus on what matters**
