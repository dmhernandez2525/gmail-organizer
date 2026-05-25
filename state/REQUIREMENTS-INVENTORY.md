# Requirements Inventory

Source: README.md, ARCHITECTURE.md, docs/DEMO_MODE.md, pyproject.toml, render.yaml, codebase inspection

## Core Features

- [ ] REQ-001: [Auth] Multi-account OAuth2 authentication with token persistence (source: README)
- [ ] REQ-002: [Auth] Token refresh when expired (source: README)
- [ ] REQ-003: [Auth] Account listing, addition, and removal (source: README)
- [ ] REQ-004: [Sync] Parallel multi-account syncing via background threads (source: README)
- [ ] REQ-005: [Sync] Incremental sync using Gmail History API with historyId tracking (source: README)
- [ ] REQ-006: [Sync] Full sync with checkpoint-based resume for interrupted fetches (source: README)
- [ ] REQ-007: [Sync] Batch API fetching (50 per request) with rate limit handling (source: README)
- [ ] REQ-008: [Sync] Data persistence: .sync-state/ and .email-cache/ never deleted (source: README)
- [ ] REQ-009: [Sync] SyncManager thread-safe status tracking (idle/syncing/complete/error) (source: ARCHITECTURE)
- [ ] REQ-010: [Classify] AI email classification using Anthropic Claude API (source: README)
- [ ] REQ-011: [Classify] Token-optimized classification (sender+subject only, 70% savings) (source: README)
- [ ] REQ-012: [Classify] Claude Code CLI integration as alternative free method (source: README)
- [ ] REQ-013: [Labels] Gmail label creation and application for all categories (source: README)
- [ ] REQ-014: [Categories] Job search categories (interviews, applications, offers, rejections, recruiters) (source: config.py)
- [ ] REQ-015: [Categories] General categories (subscriptions, finance, social, updates, todo, saved) (source: config.py)

## Analysis & Intelligence

- [ ] REQ-016: [Analysis] AI-powered inbox pattern analysis using synced data (source: README)
- [ ] REQ-017: [Analytics] Email volume over time, hourly/weekly patterns, top senders/domains (source: README)
- [ ] REQ-018: [Priority] Multi-signal priority scoring (sender freq, reply rate, urgency, recency, direct-to) (source: README)
- [ ] REQ-019: [Priority] VIP and low-priority sender lists with persistent config (source: README)
- [ ] REQ-020: [Security] Phishing, spam, spoofing, suspicious link detection (source: README)
- [ ] REQ-021: [Duplicates] Exact Message-ID, similar content, and thread duplicate detection (source: README)
- [ ] REQ-022: [Reminders] Follow-up detection (questions, action items, awaiting reply) (source: codebase)
- [ ] REQ-023: [Reputation] Sender reputation scoring (frequency, reply rate, SPF/DKIM, relationship age) (source: codebase)
- [ ] REQ-024: [Summaries] Email digest summaries and thread overviews (source: codebase)

## Features

- [ ] REQ-025: [Search] TF-IDF semantic search with relevance ranking and find-similar (source: README)
- [ ] REQ-026: [Filters] Smart filter generation from sender/domain/subject patterns (source: README)
- [ ] REQ-027: [Filters] Gmail filter creation, listing, and deletion via API (source: README)
- [ ] REQ-028: [Unsubscribe] Subscription detection via headers, body links, sender patterns (source: README)
- [ ] REQ-029: [Unsubscribe] One-click unsubscribe via email (Gmail API) (source: README)
- [ ] REQ-030: [Bulk] Batch operations: label, archive, trash, star, read/unread, spam (source: README)
- [ ] REQ-031: [Export] Export to CSV, JSON, MBOX with path traversal and CSV injection prevention (source: codebase)
- [ ] REQ-032: [Storage] Storage analysis with cleanup suggestions (source: codebase)
- [ ] REQ-033: [Calendar] Event extraction from emails with ICS export (source: codebase)
- [ ] REQ-034: [MultiLabel] Rule-based multi-label classification (source: codebase)
- [ ] REQ-035: [Training] Custom category training from user examples (source: codebase)
- [ ] REQ-036: [Notifications] Webhook notifications with HMAC signing (source: codebase)
- [ ] REQ-037: [Scheduler] Background sync scheduling with configurable intervals (source: codebase)

## UI & UX

- [ ] REQ-038: [UI] Streamlit multi-tab interface (Dashboard, Analytics, Search, etc.) (source: ARCHITECTURE)
- [ ] REQ-039: [UI] Sidebar with account list, sync badges, and sync controls (source: README)
- [ ] REQ-040: [UI] Real-time progress bars during sync (source: README)
- [ ] REQ-041: [UI] Theme support (6 themes) (source: codebase)
- [ ] REQ-042: [UI] Mobile/PWA support with responsive layout (source: codebase)

## Infrastructure & Security

- [ ] REQ-043: [Security] No hardcoded secrets or API keys in committed code (source: .gitignore)
- [ ] REQ-044: [Security] Token storage uses JSON with 0o600 permissions, not pickle (source: this session fix)
- [ ] REQ-045: [Security] Webhook URL SSRF validation (HTTPS only, public IPs) (source: this session fix)
- [ ] REQ-046: [Security] No --dangerously-skip-permissions in CLI commands (source: this session fix)
- [ ] REQ-047: [Security] MBOX export header injection prevention (source: this session fix)
- [ ] REQ-048: [Security] Notifications deadlock fix (save_config outside lock) (source: this session fix)
- [ ] REQ-049: [Docker] Dockerfile with non-root user and health check (source: Dockerfile)
- [ ] REQ-050: [Deploy] Render.yaml for static site deployment with security headers (source: render.yaml)
- [ ] REQ-051: [Lint] Zero ruff errors on committed code (source: pyproject.toml ruff config)
- [ ] REQ-052: [Tests] Test coverage >= 80% across all metrics (source: project standards)

## macOS Native Helper

- [ ] REQ-053: [macOS] Swift menubar app with parallel multi-worker processing (source: README)
- [ ] REQ-054: [macOS] 9-worker architecture (Haiku + Sonnet) (source: ARCHITECTURE)

## Website

- [ ] REQ-055: [Website] React/Vite portfolio site with demo mode (source: render.yaml, docs/DEMO_MODE.md)
