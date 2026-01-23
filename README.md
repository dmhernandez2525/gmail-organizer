# 📧 Gmail Organizer

AI-powered email management system that automatically categorizes and organizes emails across multiple Gmail accounts using Claude AI.

![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Gmail API](https://img.shields.io/badge/Gmail-API-red)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B)

**[View Website](https://gmail-organizer-site.onrender.com)** | **[Deploy Your Own](#-deploy)**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/dmhernandez2525/gmail-organizer)

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

### 1. Parallel Multi-Account Syncing
- **All accounts sync simultaneously** via background threads
- Non-blocking UI: switch tabs/accounts without stopping syncs
- Real-time progress bars and status badges per account
- Gmail API rate limits are per-user, so parallel syncs don't interfere
- Incremental sync after first full fetch (seconds instead of hours)
- Data persisted to disk and **never deleted**

### 2. AI-Powered Analysis
- Scans your entire inbox (inbox, sent, archives)
- Discovers patterns in your email usage
- Suggests categories based on YOUR actual emails
- Prioritizes job search emails if configured
- Uses already-synced data (no re-fetching)

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
- **Parallel Multi-Account Sync**: All accounts sync simultaneously via daemon threads
- **Non-Blocking UI**: Switch tabs/accounts freely while syncs run in background
- **Data Never Deleted**: `.sync-state/` and `.email-cache/` persist across restarts
- **Pagination Support**: Process unlimited emails (Gmail API handles 500/batch)
- **Batch API**: Fetches 50 emails per HTTP request (50x faster)
- **Partial Batch Recovery**: Saves successful emails even when some fail
- **Comprehensive Logging**: All actions logged to `logs/` folder
- **Email Count Accuracy**: Uses Gmail Profile API for exact totals
- **Progress Tracking**: Real-time progress bars and status badges per account
- **Checkpoint System**: Resumes from where it left off after interruption
- **Rate Limit Handling**: Exponential backoff with smart retries
- **Disk Fallback**: Loads email data from disk if not in memory

### 6. Bulk Actions

Batch operations on filtered email selections:

- **Multi-Criteria Filters**: Select by sender, category, label, subject, date range
- **12 Actions**: Label, archive, trash, star, mark read/unread, mark important, mark spam
- **Batch API**: Uses Gmail batchModify for fast bulk operations (1000 per request)
- **Progress Tracking**: Real-time progress bars for large operations
- **Safety Checks**: Confirmation required for destructive actions (trash, spam)
- **Label Management**: Create new labels or use existing ones

### 7. Semantic Search

Search emails by meaning using TF-IDF relevance ranking:

- **TF-IDF Index**: Builds a search index from subjects, senders, and body previews
- **Relevance Ranking**: Results ranked by cosine similarity with score display
- **Subject Boosting**: Exact matches in subject lines are prioritized
- **Advanced Filters**: Filter by sender, category, date range
- **Find Similar**: Discover emails similar to a selected result
- **Zero Dependencies**: Pure Python implementation, no ML libraries required

### 7. Unsubscribe Manager

Detect and manage newsletter/marketing subscriptions:

- **Auto-Detection**: Identifies subscriptions via List-Unsubscribe headers, body links, sender patterns
- **Frequency Analysis**: Shows emails/week from each sender
- **One-Click Unsubscribe**: Open unsubscribe links or send unsubscribe emails via Gmail API
- **Subscription Stats**: Total subscriptions, daily/weekly/monthly breakdown, top domains
- **Status Tracking**: Track which subscriptions you've already unsubscribed from
- **Smart Filtering**: Filter by frequency, unsubscribe availability, or status

### 7. Smart Filters

Automatically discover email patterns and create Gmail filters:

- **Sender Patterns**: Identifies senders that consistently map to a category
- **Domain Patterns**: Finds domains with multiple senders in the same category
- **Subject Keywords**: Discovers subject line keywords indicating categories
- **Preview**: See which emails each filter would match before creating
- **Bulk Create**: Select multiple filters and create them all at once
- **Manage Existing**: View and delete existing Gmail filters
- **Auto-Label**: Creates Gmail labels automatically if they don't exist

**How it works:**
1. Classify your emails first (Process tab)
2. Go to Smart Filters tab and click "Analyze Patterns"
3. Review suggested filters with match counts
4. Preview matched emails for each filter
5. Create individually or in bulk

## 🚀 Getting Started

### Prerequisites

- macOS (for .app launcher)
- Python 3.11+
- Gmail account(s)
- Anthropic API key OR Claude Code CLI

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/dmhernandez2525/gmail-organizer.git
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

#### Option 1: Launch Script

```bash
cd gmail-organizer
./scripts/launch_gmail_organizer.sh
```

#### Option 2: Streamlit Direct

```bash
source venv/bin/activate
streamlit run app.py
```

#### Option 3: Python Package

```bash
pip install -e .
gmail-organizer
```

### First-Time Setup

1. **Add Gmail Account**
   - Click "Add Gmail Account" in sidebar
   - Name your account (e.g., "personal", "work")
   - Browser opens for Google OAuth
   - Grant permissions
   - Account saved for future use

2. **Sync Emails** (Dashboard tab)
   - Click "Sync All Accounts" to sync all at once
   - Or click individual sync buttons per account
   - Syncs run in background threads - switch tabs freely
   - Progress bars and status badges update in real-time
   - Data persists to disk and loads automatically on restart

3. **Analyze Inbox** (Analyze tab)
   - Uses already-synced data (no re-fetching)
   - Select account and configure analysis options
   - Click "Analyze Patterns"
   - Review AI-suggested categories

4. **Process Emails** (Process tab)

   **If using Claude Code CLI:**
   - Select account (uses synced data)
   - Click "Step 1: Export & Launch Claude Code"
   - Terminal opens automatically
   - Wait for completion, click "Step 2: Apply Results"

   **If using Anthropic API:**
   - Go to Settings, uncheck "Use Claude Code"
   - Select account, click "Start Processing"

5. **Check Results** (Results tab)
   - Multi-account results with search/filter
   - Category breakdown charts
   - View classified emails

## 📁 Project Structure

```
gmail-organizer/
├── gmail_organizer/          # Python package
│   ├── __init__.py           # Package exports
│   ├── auth.py               # Multi-account OAuth manager
│   ├── operations.py         # Gmail API operations + incremental sync
│   ├── sync_manager.py       # Thread-safe parallel sync manager
│   ├── classifier.py         # AI classification with Anthropic
│   ├── analyzer.py           # Inbox pattern analysis
│   ├── claude_integration.py # Claude Code CLI integration
│   ├── filters.py            # Smart filter pattern detection & creation
│   ├── unsubscribe.py        # Subscription detection & unsubscribe management
│   ├── search.py             # TF-IDF semantic search engine
│   ├── bulk_actions.py       # Batch Gmail operations engine
│   ├── config.py             # Category definitions
│   ├── logger.py             # Logging configuration
│   └── main.py               # CLI entry point
├── scripts/                  # Launcher scripts
│   ├── launch_gmail_organizer.sh
│   └── GmailOrganizer.applescript
├── website/                  # React portfolio site
│   ├── src/
│   ├── public/
│   └── package.json
├── tests/                    # Test suite
├── app.py                    # Streamlit web interface
├── pyproject.toml            # Python project configuration
├── requirements.txt          # Python dependencies
├── render.yaml               # Render deployment config
└── README.md
```

**Git-ignored (local only):**
- `.env` - API keys
- `credentials/` - Gmail OAuth tokens
- `client_secret.json` - Google OAuth credentials
- `.claude-processing/` - Email exports for Claude Code
- `.email-cache/` - Checkpoint files
- `.sync-state/` - Incremental sync state
- `logs/` - Application logs
- `venv/` - Python virtual environment

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

- **Local only**: Email data stored locally in `.sync-state/` and `.email-cache/` (git-ignored)
- **No external storage**: Emails never sent to external servers (except Anthropic API for classification)
- **Local processing**: All syncing and analysis happens locally
- **OAuth tokens**: Stored in `credentials/` folder (git-ignored)
- **API keys**: Never committed to git (via .gitignore)
- **Email exports**: Files in `.claude-processing/` (git-ignored)
- **Logs**: Contain no email content, only metadata and counts
- **Data persistence**: Synced email data is never deleted from disk

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

## 🚀 Deploy

### Deploy Documentation Website

Click the Render button at the top to deploy the documentation website, or manually:

```bash
# The website is located in /website
cd website
npm install
npm run build
# Deploy the dist/ folder to any static host
```

### Self-Hosted Processing

The email processing runs locally on your machine for privacy. Clone the repo and follow the [Getting Started](#-getting-started) section above.

## 🗺️ Roadmap

- [x] **Core Classification** - AI-powered email categorization
- [x] **Incremental Sync** - Gmail History API integration
- [x] **Checkpoint System** - Resumable batch processing
- [x] **Multi-Account Support** - Manage 5+ Gmail accounts
- [x] **Parallel Syncing** - All accounts sync simultaneously via background threads
- [x] **Non-Blocking UI** - Switch tabs/accounts without stopping syncs
- [x] **Data Persistence** - Email data never deleted, loads from disk on restart
- [x] **5-Tab Dashboard UI** - Dashboard, Analyze, Process, Results, Settings
- [x] **Smart Filters** - Auto-generate Gmail filters from sender/domain/subject patterns with bulk create and preview
- [x] **Analytics Dashboard** - Email volume over time, hourly/weekly patterns, sender/domain breakdown, inbox growth charts
- [ ] **Mobile Companion** - iOS/Android notification app
- [ ] **Calendar Integration** - Auto-schedule from email context

## 🤝 Contributing

This is a personal project, but suggestions and feedback are welcome!

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Gmail API by Google
- [Streamlit](https://streamlit.io/) for the UI
- Claude Code CLI for local processing

## 📧 Contact

For questions or issues, please open a GitHub issue.

---

**Made with ❤️ to organize chaos and focus on what matters**
