# Architecture

## Overview

Gmail Organizer is a Streamlit-based application that uses AI to classify and organize emails across multiple Gmail accounts. The architecture centers around a thread-safe `SyncManager` that enables parallel account syncing with a non-blocking UI.

## System Diagram

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)               │
│  ┌──────────┬─────────┬─────────┬────────┬────────┐│
│  │Dashboard │ Analyze │ Process │Results │Settings││
│  └──────────┴─────────┴─────────┴────────┴────────┘│
│         │                                            │
│    ┌────▼─────────────────────────────────────────┐ │
│    │              Sidebar                          │ │
│    │  Account list + badges + sync buttons        │ │
│    └────┬─────────────────────────────────────────┘ │
└─────────┼───────────────────────────────────────────┘
          │
    ┌─────▼──────────────────────────────────────┐
    │         SyncManager (session_state)         │
    │  ┌──────────────────────────────────────┐  │
    │  │ _statuses: Dict[name, SyncStatus]    │  │
    │  │ _services: Dict[name, (svc, email)]  │  │
    │  │ _lock: threading.Lock                │  │
    │  └──────────────────────────────────────┘  │
    │              │                              │
    │   ┌──────────┼────────────────┐            │
    │   │          │                │            │
    │   ▼          ▼                ▼            │
    │ Thread-1   Thread-2       Thread-N         │
    │ (account1) (account2)    (accountN)        │
    └────┬─────────┬────────────────┬────────────┘
         │         │                │
    ┌────▼─────────▼────────────────▼────────────┐
    │           GmailOperations                   │
    │   sync_emails() → fetch_emails()            │
    │   Gmail History API (incremental)           │
    │   Batch API (50 per request)                │
    └────────────────┬───────────────────────────┘
                     │
    ┌────────────────▼───────────────────────────┐
    │              Disk Storage                    │
    │  .sync-state/sync_state_{email}.json        │
    │  .email-cache/{email}_{query}/batch_*.jsonl │
    └─────────────────────────────────────────────┘
```

## Core Components

### SyncManager (`gmail_organizer/sync_manager.py`)

Thread-safe orchestrator stored in `st.session_state`. Manages parallel syncing for all registered accounts.

**Key design decisions:**
- Each account gets its own daemon thread (won't block app shutdown)
- `threading.Lock` protects all reads/writes to shared state
- Gmail API rate limits are per-user, so parallel syncs don't interfere
- Workers update mutable `SyncStatus` objects in the shared dict
- `get_emails()` falls back to loading from `.sync-state/` files on disk

**API:**
```
SyncManager
├── register_account(name, service, email)     # Register for syncing
├── start_sync(account_name, query="")         # Launch background thread
├── start_all_syncs(query="")                  # Launch all in parallel
├── get_status(account_name) -> SyncStatus     # Thread-safe status read
├── get_all_statuses() -> Dict                 # All statuses
├── is_any_syncing() -> bool                   # Check if any active
├── get_emails(account_name) -> List[Dict]     # Memory or disk fallback
└── _sync_worker(name, service, email, query)  # Background thread target
```

**SyncStatus fields:**
- `state`: idle | syncing | complete | error
- `progress`, `total`, `message`: Real-time progress
- `emails_data`: List of email dicts (full data in memory)
- `error`: Error message if failed
- `last_sync_time`: ISO timestamp of last successful sync

### GmailOperations (`gmail_organizer/operations.py`)

Gmail API wrapper with two fetch strategies:

1. **Full sync** (`fetch_emails`): Paginated fetch with checkpoint-based resume
2. **Incremental sync** (`sync_emails`): Uses Gmail History API for delta updates

**Checkpoint system** (`.email-cache/`):
- Directory-based storage with append-only JSONL batch files
- `index.json` tracks fetched IDs
- `batch_NNNN.jsonl` files store email data
- Never deleted - allows resuming interrupted fetches

**Sync state** (`.sync-state/`):
- Stores Gmail `historyId` after each sync
- Stores full email database as JSON dict
- Used for incremental sync on subsequent runs
- Never deleted - provides instant access to email data

### App UI (`app.py`)

Seven-tab Streamlit interface with sidebar controls.

**Tabs:**
1. **Dashboard** - Account overview, sync status cards, "Sync All" button
2. **Analytics** - Email volume/time charts, hourly/weekly patterns, top senders/domains
3. **Search** - TF-IDF semantic search with relevance ranking and find-similar
4. **Smart Filters** - Pattern detection, filter suggestions, bulk create, existing filter management
5. **Unsubscribe** - Subscription detection, frequency analysis, one-click unsubscribe
6. **Bulk Actions** - Multi-criteria filter + batch Gmail operations with progress
4. **Priority** - Multi-signal priority scoring with configurable thresholds
6. **Analyze** - Pattern analysis using already-synced data
7. **Process** - Classification using synced data (Claude Code or API)
8. **Results** - Multi-account results with search/filter
9. **Settings** - Classification method, sync config, data management

**Auto-refresh mechanism:**
```python
# At end of main():
if sync_mgr.is_any_syncing():
    time.sleep(2)
    st.rerun()
```
- Polls every 2 seconds while any sync is active
- Stops automatically when all syncs complete
- Works with any Streamlit version (no fragment dependency)

### SmartFilterGenerator (`gmail_organizer/filters.py`)

Analyzes classified email patterns to discover and create Gmail filters automatically.

**Pattern detection strategies:**
1. **Sender patterns** - Identifies senders that consistently map to a category
2. **Domain patterns** - Finds domains with multiple senders in the same category
3. **Subject keyword patterns** - Discovers subject line keywords indicating categories

**API:**
```
SmartFilterGenerator
├── analyze_patterns(emails, min_frequency)    # Discover filter-worthy patterns
├── preview_filter(rule, emails)               # Preview which emails would match
├── create_filter(rule)                        # Create filter via Gmail API
├── list_existing_filters()                    # List current Gmail filters
├── delete_filter(filter_id)                   # Remove a Gmail filter
└── _deduplicate_rules(rules)                  # Remove overlapping rules
```

**FilterRule fields:**
- `criteria`: Dict with `from`, `subject`, or `hasTheWord` keys
- `action_label`: Gmail label name to apply
- `label_id`: Gmail label ID (resolved before creation)
- `description`: Human-readable rule explanation
- `match_count`: Number of emails matching this pattern

**Gmail filter creation flow:**
1. Analyze patterns from classified emails
2. User previews matched emails per filter
3. Label is created if it doesn't exist (`_get_or_create_label`)
4. Filter created via `users.settings.filters.create` API

### SearchIndex (`gmail_organizer/search.py`)

Pure Python TF-IDF search engine for email content.

**Algorithm:**
1. **Tokenization**: Splits text, removes stop words, normalizes
2. **TF-IDF Vectorization**: Augmented term frequency * smoothed IDF
3. **Cosine Similarity**: Sparse vector dot product for relevance scoring
4. **Field Weighting**: Subject (3x), Sender (2x), Body (1x)
5. **Subject Boosting**: Exact query matches in subject get 2x score boost

**API:**
```
SearchIndex
├── build_index(emails)                       # Build TF-IDF index
├── search(query, filters...)                 # Search with relevance ranking
├── find_similar(email, limit)                # Find similar emails
├── get_suggestions(partial_query)            # Autocomplete suggestions
├── document_count                            # Number of indexed docs
└── vocabulary_size                           # Number of unique terms
```

**Performance:** Indexes 80,000+ emails in seconds. Pure Python, no external ML dependencies.

### UnsubscribeManager (`gmail_organizer/unsubscribe.py`)

Detects email subscriptions and provides unsubscribe capabilities.

**Detection strategies:**
1. **List-Unsubscribe header** - Standard email header for automated unsubscribe
2. **Body URL patterns** - Finds unsubscribe/opt-out URLs in email content
3. **Marketing domain detection** - Known ESP domains (Mailchimp, SendGrid, etc.)
4. **Sender pattern analysis** - Newsletter-like naming patterns
5. **Automated subject detection** - Repeated prefixes, numbered issues

**API:**
```
UnsubscribeManager
├── detect_subscriptions(emails)              # Scan emails for subscriptions
├── unsubscribe_via_email(subscription)       # Send unsubscribe email via Gmail API
├── mark_unsubscribed(sender_email)           # Manually mark as unsubscribed
├── ignore_subscription(sender_email)         # Hide from future scans
├── get_subscription_stats(subscriptions)     # Summary statistics
└── get_unsubscribe_candidates(subscriptions) # Recommended unsubscribes
```

**State persistence:** Stores unsubscribe/ignore state in `.sync-state/unsubscribe_state.json`

## Data Flow

```
User clicks "Sync All"
        │
        ▼
SyncManager.start_all_syncs()
        │
        ├─── Thread: account1 → ops.sync_emails() → .sync-state/
        ├─── Thread: account2 → ops.sync_emails() → .sync-state/
        └─── Thread: accountN → ops.sync_emails() → .sync-state/
                                                        │
                                                        ▼
Analyze tab: sync_mgr.get_emails() ◄── memory OR .sync-state/ disk
        │
        ▼
Process tab: reads same data → classifies → applies labels
        │
        ▼
Results tab: reads processing_results from session_state
```

**Data never re-fetched:** The Analyze and Process tabs read from `sync_mgr.get_emails()` which returns data from memory (if synced in current session) or loads from `.sync-state/` files on disk (if from a previous session).

## Data Persistence Guarantees

| Storage | Purpose | Deleted? |
|---------|---------|----------|
| `.sync-state/sync_state_{email}.json` | Full email database + historyId | Never |
| `.email-cache/{email}_{query}/` | Checkpoint for interrupted fetches | Never |
| `credentials/token_{name}.pickle` | OAuth tokens | Only on account removal |
| `.claude-processing/` | Temporary export for Claude Code | After processing |

## Thread Safety Model

```
Main Thread (Streamlit)          Worker Threads
─────────────────────           ──────────────
render_sidebar()                _sync_worker():
  get_all_statuses()  ◄─lock──►  status.state = "syncing"
  get_emails()        ◄─lock──►  status.progress = N
  start_sync()        ◄─lock──►  status.emails_data = [...]
                                  status.state = "complete"
```

All access to `_statuses` and `_services` dicts goes through `self._lock`. The Streamlit main thread reads status snapshots for rendering, while worker threads update their own status objects.

## Performance Characteristics

| Operation | Speed | Notes |
|-----------|-------|-------|
| First full sync | ~1,500 emails/min | Batch API, 50/request, 2s delay |
| Incremental sync | Seconds | Gmail History API delta |
| Load from disk | Instant | JSON parse of sync state file |
| Classification (API) | ~500 emails/min | Claude Haiku, sender+subject only |
| Classification (CLI) | ~1,000 emails/min | Claude Code, full context |

## Key Differences from Previous Architecture

| Before | After |
|--------|-------|
| Single account at a time | All accounts sync in parallel |
| Analyze re-fetches emails | Uses already-synced data |
| Process re-fetches emails | Uses already-synced data |
| analysis_results is single value | Per-account dict |
| suggested_categories is single value | Per-account dict |
| No sync progress visibility | Real-time progress in sidebar + dashboard |
| Checkpoint deleted on completion | Never deleted |
| Tab switching resets progress | Background threads continue regardless |
| 4 tabs | 5 tabs (Dashboard added) |
| 120s initial quota wait | Removed (unnecessary) |
| 10s batch delay | 2s batch delay (safe, faster) |
| Metadata-only fetch | Full email fetch (body included) |

---

## macOS Native Helper App Architecture

### Overview

The Gmail Organizer Helper is a native Swift macOS application that provides a menubar interface for email processing. It uses a parallel multi-worker architecture for efficient, cost-effective AI analysis.

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Gmail Organizer Helper (Swift)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────┐      ┌─────────────────────────────────────────────┐   │
│  │  Menubar   │      │              MainPanel                       │   │
│  │   Icon     │─────▶│  ┌─────┬────────┬────────┬──────┬────────┐  │   │
│  │    ✉️      │      │  │Home │Process │Results │Auto  │Settings│  │   │
│  └────────────┘      │  └─────┴────────┴────────┴──────┴────────┘  │   │
│                      │           │                                   │   │
│                      │    ┌──────┴──────┐                           │   │
│                      │    ▼             ▼                           │   │
│                      │  Single       Parallel                        │   │
│                      │  Thread       Processing                      │   │
│                      └─────────────────────────────────────────────┘   │
│                                         │                               │
│                            ┌────────────┴────────────┐                 │
│                            ▼                         ▼                 │
│  ┌────────────────────────────────┐  ┌────────────────────────────┐   │
│  │     ProcessingPanel             │  │      Terminal.app          │   │
│  │  ┌───────────────────────────┐ │  │   (Single Thread Mode)     │   │
│  │  │    TabbedTerminalView     │ │  └────────────────────────────┘   │
│  │  │  ┌────┬────┬────┬────┐   │ │                                    │
│  │  │  │ W1 │ W2 │ W3 │ W4 │   │ │                                    │
│  │  │  └────┴────┴────┴────┘   │ │                                    │
│  │  │  Color-coded tabs         │ │                                    │
│  │  └───────────────────────────┘ │                                    │
│  │  ┌───────────────────────────┐ │                                    │
│  │  │    Status Sidebar         │ │                                    │
│  │  │  Progress: ████████░░ 80% │ │                                    │
│  │  │  Workers:                 │ │                                    │
│  │  │  ● Indexer     [Done]    │ │                                    │
│  │  │  ● Threads     [Running] │ │                                    │
│  │  │  ○ Sender      [Pending] │ │                                    │
│  │  └───────────────────────────┘ │                                    │
│  └────────────────────────────────┘                                    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           WorkerManager                                   │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                         ProcessingJob                               │  │
│  │  • id, accountEmail, accountName                                   │  │
│  │  • syncStatePath, resultsDir, totalEmails                          │  │
│  │  • workers: [WorkerInfo]                                           │  │
│  │  • onWorkerStatusChanged, onJobComplete                            │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│       ┌────────────────────────────┼────────────────────────────┐        │
│       │            │               │               │            │        │
│       ▼            ▼               ▼               ▼            ▼        │
│  ┌─────────┐ ┌─────────┐    ┌─────────┐    ┌─────────┐   ┌─────────┐   │
│  │Worker 1 │ │Worker 2 │    │Worker 3 │    │Worker 4 │   │Worker 9 │   │
│  │ Haiku   │ │ Haiku   │    │ Haiku   │    │ Haiku   │   │ Sonnet  │   │
│  │Indexer  │ │Threads  │    │Sender   │    │Temporal │   │Summary  │   │
│  └────┬────┘ └────┬────┘    └────┬────┘    └────┬────┘   └────┬────┘   │
│       │           │              │              │              │        │
│       └───────────┴──────────────┴──────────────┴──────────────┘        │
│                                    │                                      │
│                          ┌─────────┴─────────┐                           │
│                          ▼                   ▼                           │
│                   ┌────────────┐      ┌────────────┐                    │
│                   │Claude Haiku│      │Claude      │                    │
│                   │ (cheap)    │      │Sonnet      │                    │
│                   │~80% of work│      │(reasoning) │                    │
│                   └────────────┘      └────────────┘                    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            Data Layer                                     │
│                                                                           │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐ │
│  │    .sync-state/     │  │    .processing/     │  │.processing-      │ │
│  │                     │  │                     │  │  results/        │ │
│  │ sync_state_         │  │ {account}/          │  │                  │ │
│  │  {email}.json       │  │  01_indexer.md      │  │ {email}_         │ │
│  │                     │  │  02_thread_0.md     │  │  latest.json     │ │
│  │ • Full email DB     │  │  03_sender.md       │  │                  │ │
│  │ • Gmail historyId   │  │  ...                │  │ • Thread analysis│ │
│  │ • Last sync time    │  │                     │  │ • Sender scores  │ │
│  │                     │  │ (Worker prompts)    │  │ • Health score   │ │
│  └─────────────────────┘  └─────────────────────┘  └──────────────────┘ │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

### Helper App Components

#### MainPanelController (`MainPanel.swift`)

Main window with Google-style UI:
- **Navigation sidebar** - 5 tabs with icons
- **Content area** - Tab-specific content
- **Account cards** - Show sync status, email counts
- **Parallel processing toggle** - Switch between modes

**Key properties:**
- `accounts: [AccountInfo]` - Discovered Gmail accounts
- `selectedAnalysisType: AnalysisType` - Current analysis mode
- `useParallelProcessing: Bool` - Processing mode toggle
- `accountsLoaded: Bool` - Deferred loading for permissions

#### ProcessingPanelController (`ProcessingPanel.swift`)

Dedicated window for parallel processing:
- **Header** - Account info, stop button
- **Status sidebar** - Progress bar, worker list
- **Terminal container** - Tabbed terminal views

#### TabbedTerminalView (`EmbeddedTerminal.swift`)

Container for multiple terminal outputs:
- **Tab bar** - Color-coded worker tabs
- **Content area** - Active terminal view
- **Status indicators** - Per-tab running/complete status

**Tab colors by phase:**
```swift
static let tabColors: [NSColor] = [
    .systemBlue,    // Phase 1
    .systemGreen,   // Phase 2
    .systemOrange,  // Phase 3
    .systemPurple,  // Phase 4
    .systemPink,    // Phase 5
    .systemTeal,    // Phase 6
    .systemYellow,  // Phase 7
    .systemIndigo   // Phase 8-9
]
```

#### TerminalOutputView (`EmbeddedTerminal.swift`)

Individual terminal display:
- **Process management** - Runs shell commands
- **Output display** - Monospace text with colors
- **Auto-scroll** - Follows output
- **Callbacks** - `onProcessComplete`, `onOutputReceived`

#### WorkerManager (`WorkerManager.swift`)

Orchestrates parallel processing jobs:

**ProcessingJob:**
- Tracks account being processed
- Manages worker list and status
- Collects results from all workers

**Worker types:**
| ID | Name | Phase | Model | Purpose |
|----|------|-------|-------|---------|
| `indexer` | Data Indexer | 1 | Haiku | Create indexes |
| `thread_N` | Thread Analyzer N | 2 | Haiku | Map conversations |
| `sender` | Sender Analyzer | 3 | Haiku | Reputation scoring |
| `temporal` | Temporal Analyzer | 4 | Haiku | Time patterns |
| `content` | Content Analyzer | 5 | Haiku | Topics, actions |
| `anomaly` | Anomaly Detector | 6 | Haiku | Find issues |
| `categorizer` | Smart Categorizer | 7 | Sonnet | Aggregate, categorize |
| `executor` | Label Executor | 8 | Sonnet | Apply Gmail labels |
| `summary` | Summary Generator | 9 | Sonnet | Executive summary |

**Concurrency model:**
```swift
// Max workers = CPU cores - 2 (leave headroom)
let cores = ProcessInfo.processInfo.activeProcessorCount
self.maxConcurrentWorkers = max(2, cores - 2)
```

### Data Flow (Parallel Processing)

```
User clicks "Process" with Parallel toggle ON
                    │
                    ▼
        ProcessingPanelController
                    │
                    ▼
   WorkerManager.createJob(account)
                    │
   ┌────────────────┼────────────────┐
   │                │                │
   ▼                ▼                ▼
Worker 1        Worker 2         Worker N
(Haiku)         (Haiku)          (Sonnet)
   │                │                │
   ▼                ▼                ▼
.processing/    .processing/    .processing/
01_indexer.md   02_thread.md    09_summary.md
   │                │                │
   ▼                ▼                ▼
Claude Code     Claude Code     Claude Code
--model haiku   --model haiku   --model sonnet
   │                │                │
   └────────────────┼────────────────┘
                    │
                    ▼
           .processing-results/
           {email}_latest.json
```

### Cost Optimization

The parallel architecture optimizes costs by using:

| Model | Cost | Used For | % of Work |
|-------|------|----------|-----------|
| Haiku | $0.25/1M input | Data gathering, analysis | ~80% |
| Sonnet | $3/1M input | Decision making, labeling | ~20% |

**Estimated cost per inbox:**
- 1,000 emails: ~$0.02
- 10,000 emails: ~$0.15
- 100,000 emails: ~$1.20

### File Persistence

| File | Purpose | Created By | Read By |
|------|---------|------------|---------|
| `.sync-state/sync_state_{email}.json` | Email database | Web app | Helper app |
| `.processing/{account}/XX_worker.md` | Worker prompts | Helper app | Claude Code |
| `.processing-results/{email}_latest.json` | Analysis results | Claude Code | Both apps |

### Thread Safety

The Helper app uses different threading models:

**Single-thread mode:**
- Launches Terminal.app with AppleScript
- Uses fallback shell script if AppleScript fails
- Window positioned center-screen

**Parallel mode:**
- `WorkerManager` tracks active workers
- `maxConcurrentWorkers` limits parallelism
- UI updates via main thread callbacks
- Each `TerminalOutputView` has its own Process
