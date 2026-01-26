# Gmail Organizer Helper - macOS Native App

A native macOS menubar application that provides a streamlined interface for Gmail Organizer's email processing capabilities. Features parallel multi-worker processing with embedded terminals for maximum efficiency.

## Overview

The Gmail Organizer Helper is a Swift-based macOS application that:
- Lives in your menubar for quick access
- Displays synced Gmail accounts at a glance
- Launches AI-powered email analysis with one click
- Uses parallel Haiku workers for fast, cost-effective processing
- Shows all worker output in organized, tabbed terminals

## Features

### 1. Native macOS Menubar App
- **Always accessible** - Click the envelope icon in your menubar
- **Google-style UI** - Clean, familiar interface with navigation sidebar
- **5-tab layout** - Home, Process, Results, Automation, Settings

### 2. Parallel Processing Architecture
The app uses multiple Claude AI workers running in parallel:

| Phase | Worker | Model | Purpose |
|-------|--------|-------|---------|
| 1 | Data Indexer | Haiku | Create email indexes for parallel access |
| 2 | Thread Analyzers (1-4) | Haiku | Map conversations, detect response needs |
| 3 | Sender Analyzer | Haiku | Build sender reputation scores |
| 4 | Temporal Analyzer | Haiku | Detect time-based patterns |
| 5 | Content Analyzer | Haiku | Extract topics and action items |
| 6 | Anomaly Detector | Haiku | Find conflicts and issues |
| 7 | Smart Categorizer | Sonnet | Aggregate results, create categories |
| 8 | Label Executor | Sonnet | Apply labels via Gmail API |
| 9 | Summary Generator | Sonnet | Create executive summary |

**Why this architecture?**
- **Cost-effective**: Haiku workers (~80% of work) cost 10x less than Sonnet
- **Fast**: Parallel workers utilize all CPU cores
- **Accurate**: Sonnet handles final decisions requiring reasoning
- **Organized**: All output in one window with tabbed terminals

### 3. Embedded Terminal View
Instead of spawning multiple Terminal.app windows:
- **Tabbed interface** - One window, multiple color-coded tabs
- **Real-time output** - See each worker's progress live
- **Status sidebar** - Visual progress for all workers
- **Stop control** - Cancel all workers with one click

### 4. Analysis Types
Choose from multiple analysis modes:

| Type | Description | Best For |
|------|-------------|----------|
| Full Analysis | Complete 10-phase analysis | First-time inbox organization |
| Thread Analysis | Focus on conversation mapping | Finding dropped threads |
| Action Items | Extract tasks and deadlines | Productivity review |
| Sender Reputation | Build relationship scores | Contact prioritization |
| Pattern Detection | Find anomalies and trends | Inbox health check |

### 5. Delayed Permission Handling
- Permission prompts appear when you click "Load Accounts"
- Clear explanation of why access is needed
- No surprise permission dialogs on app launch

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Gmail Organizer Helper                        │
│                     (Swift macOS App)                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌────────────────────────────────────────────┐  │
│  │ Menubar  │  │              Main Panel                     │  │
│  │  Icon    │  │  ┌────────┬────────┬────────┬──────────┐   │  │
│  │    ✉     │─▶│  │  Home  │Process │Results │Settings  │   │  │
│  └──────────┘  │  └────────┴────────┴────────┴──────────┘   │  │
│                │                    │                         │  │
│                │         ┌──────────┴──────────┐             │  │
│                │         ▼                     ▼             │  │
│                │  ┌─────────────┐    ┌──────────────────┐   │  │
│                │  │Single-Thread│    │ Parallel Panel   │   │  │
│                │  │  (Legacy)   │    │ ┌──────────────┐ │   │  │
│                │  │  Terminal   │    │ │ Worker Tabs  │ │   │  │
│                │  │   Window    │    │ │ ┌──┬──┬──┐   │ │   │  │
│                │  └─────────────┘    │ │ │W1│W2│W3│   │ │   │  │
│                │                      │ │ └──┴──┴──┘   │ │   │  │
│                │                      │ └──────────────┘ │   │  │
│                │                      │ ┌──────────────┐ │   │  │
│                │                      │ │ Status Bar   │ │   │  │
│                │                      │ │ Progress: ██░│ │   │  │
│                │                      │ └──────────────┘ │   │  │
│                │                      └──────────────────┘   │  │
│                └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     WorkerManager                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ProcessingJob                                               │ │
│  │  • accountEmail, totalEmails                               │ │
│  │  • workers: [WorkerInfo]                                   │ │
│  │  • results: [String: Any]                                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│   ┌──────────────────────────┼────────────────────────┐         │
│   │                          │                        │         │
│   ▼                          ▼                        ▼         │
│ ┌──────────┐            ┌──────────┐            ┌──────────┐   │
│ │ Worker 1 │            │ Worker 2 │            │ Worker N │   │
│ │ (Haiku)  │            │ (Haiku)  │            │ (Sonnet) │   │
│ │ Indexer  │            │ Threads  │            │ Summary  │   │
│ └────┬─────┘            └────┬─────┘            └────┬─────┘   │
│      │                       │                       │         │
│      └───────────────────────┼───────────────────────┘         │
│                              ▼                                  │
│                    ┌──────────────────┐                        │
│                    │   Claude Code    │                        │
│                    │  CLI (Terminal)  │                        │
│                    └────────┬─────────┘                        │
│                              │                                  │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  .sync-state/   │  │ .processing/    │  │.processing-     │ │
│  │ sync_state_     │  │ account_        │  │  results/       │ │
│  │ {email}.json    │  │ {type}.md       │  │ account_        │ │
│  │                 │  │ (prompts)       │  │ latest.json     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## File Structure

```
GmailOrganizerHelper/
├── Sources/
│   ├── main.swift              # App entry point
│   ├── AppDelegate.swift       # NSApplication delegate
│   ├── MainPanel.swift         # Main window with 5-tab UI
│   ├── ProcessingPanel.swift   # Parallel processing window
│   ├── EmbeddedTerminal.swift  # Terminal view + tabbed container
│   ├── WorkerManager.swift     # Parallel job orchestration
│   ├── ProcessingManager.swift # Legacy single-thread processing
│   ├── PromptTemplates.swift   # Comprehensive analysis prompts
│   ├── ResultsManager.swift    # JSON results storage
│   └── Utils.swift             # Path helpers, notifications, shell
├── build.sh                    # Build script (creates .app bundle)
├── entitlements.plist          # macOS permissions
└── README.md                   # This file
```

## Building

### Prerequisites
- macOS 12.0+ (Monterey or later)
- Xcode Command Line Tools
- Claude Code CLI installed (`~/.local/bin/claude`)

### Build & Run

```bash
cd GmailOrganizerHelper
./build.sh
open ~/Desktop/Gmail\ Organizer\ Helper.app
```

The build script:
1. Compiles all Swift sources with optimizations
2. Creates an app bundle at `~/Desktop/Gmail Organizer Helper.app`
3. Code signs with entitlements for file access
4. Outputs URL scheme examples

### URL Schemes

The app registers the `gmailorganizer://` URL scheme:

```bash
# Process a specific account
open "gmailorganizer://process/accountname"

# Process all accounts
open "gmailorganizer://process-all"

# Open web interface
open "gmailorganizer://open"
```

## Usage

### First Launch

1. Click the envelope icon in your menubar
2. Click "Load Accounts" to scan for synced Gmail data
3. Grant folder access permission when prompted

### Processing Emails

1. Go to the **Process** tab
2. Toggle **Parallel Processing** ON (recommended)
3. Select an analysis type (Full Analysis for comprehensive results)
4. Click **Process** on any account
5. Watch progress in the Processing Panel

### Understanding the Processing Panel

The Processing Panel shows:
- **Header**: Account being processed, estimated time
- **Status Sidebar**:
  - Progress bar (overall completion)
  - Worker list with status indicators:
    - Gray = Pending
    - Blue = Running
    - Green = Complete
    - Red = Error
- **Terminal Tabs**: Click to see output from each worker

## Worker Details

### Phase 1: Data Indexer
Creates index files for parallel access:
- `index_by_thread.json` - Emails grouped by conversation
- `index_by_sender.json` - Emails grouped by sender domain
- `index_by_date.json` - Emails grouped by month
- `email_summary.json` - Basic statistics

### Phase 2: Thread Analyzers
Analyze email conversations:
- Thread status (active, stale, needs response)
- Participant mapping
- Response time calculations
- Split across multiple workers for large inboxes

### Phase 3: Sender Analyzer
Build sender reputation:
- Classification (human, automated, newsletter)
- Relationship scoring (0-100)
- Domain grouping
- VIP and unsubscribe candidates

### Phase 4: Temporal Analyzer
Time-based patterns:
- Volume by day of week
- Volume by hour
- Monthly trends
- Spike detection

### Phase 5: Content Analyzer
Content patterns (sample-based for large inboxes):
- Topic clustering
- Urgency detection
- Action item extraction
- Question identification

### Phase 6: Anomaly Detector
Find potential issues:
- Dropped conversations
- Unanswered important emails
- Volume anomalies
- Potential phishing indicators

### Phase 7: Smart Categorizer
Aggregate and categorize:
- Combine all worker results
- Assign primary/secondary labels
- Calculate priority scores
- Generate label structure

### Phase 8: Label Executor
Apply labels via Gmail API:
- Create labels if needed
- Apply in batches with rate limiting
- Log all actions

### Phase 9: Summary Generator
Create final report:
- Executive summary
- Inbox Health Score (0-100)
- Key findings
- Actionable recommendations

## Results Storage

Results are saved to `.processing-results/`:

```json
{
    "accountEmail": "user@gmail.com",
    "processedAt": "2024-01-24T22:30:00Z",
    "summary": {
        "totalEmails": 45000,
        "totalThreads": 12500,
        "uniqueSenders": 3200
    },
    "threadAnalysis": { ... },
    "senderAnalysis": { ... },
    "temporalAnalysis": { ... },
    "contentAnalysis": { ... },
    "issuesDetected": { ... },
    "categorization": { ... },
    "inboxHealthScore": {
        "overall": 78,
        "organization": 20,
        "responseRate": 18,
        "actionCompletion": 22,
        "communicationBalance": 18
    },
    "recommendations": [ ... ]
}
```

## Troubleshooting

### App not appearing in menubar
- Check System Preferences > Privacy & Security > Accessibility
- Restart the app

### "Load Accounts" shows no accounts
- Ensure you've synced accounts in the web interface first
- Check that `.sync-state/` directory exists in the project

### Terminal not launching
- Verify Claude Code CLI is installed: `which claude`
- Check Terminal has automation permissions in System Preferences

### Permission denied errors
- The app needs folder access - click "Load Accounts" to trigger the prompt
- If denied, go to System Preferences > Privacy & Security > Files and Folders

### Workers failing immediately
- Check Claude Code CLI authentication
- Ensure sufficient disk space for results

## Development

### Adding New Workers

1. Add worker definition in `WorkerManager.createWorkers()`
2. Create prompt generator in `WorkerManager.generatePrompt()`
3. Add specific prompt in `WorkerManager` (e.g., `generateNewWorkerPrompt()`)
4. Update `ProcessingPanel` if UI changes needed

### Modifying Prompts

Edit `PromptTemplates.swift` for the single-threaded prompts, or the `generateXXXPrompt()` methods in `WorkerManager.swift` for parallel workers.

### Building for Release

```bash
# Build with release optimizations
./build.sh

# For distribution, add proper code signing:
codesign --force --deep --sign "Developer ID Application: Your Name" \
    --entitlements entitlements.plist \
    ~/Desktop/Gmail\ Organizer\ Helper.app
```

## License

MIT License - See main project LICENSE file.
