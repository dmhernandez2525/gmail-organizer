"""Streamlit Frontend for Gmail Organizer - Multi-Account Parallel Sync UI"""

import streamlit as st
import pandas as pd
from gmail_organizer.auth import GmailAuthManager
from gmail_organizer.operations import GmailOperations
from gmail_organizer.classifier import EmailClassifier
from gmail_organizer.analyzer import EmailAnalyzer
from gmail_organizer.config import CATEGORIES
from gmail_organizer.logger import setup_logger
from gmail_organizer.sync_manager import SyncManager
from gmail_organizer.analytics import EmailAnalytics
from gmail_organizer.filters import SmartFilterGenerator, FilterRule
from gmail_organizer.unsubscribe import UnsubscribeManager
from gmail_organizer.search import SearchIndex
from gmail_organizer.bulk_actions import BulkActionEngine, filter_emails
from gmail_organizer.priority import PriorityScorer
from gmail_organizer.duplicates import DuplicateDetector
from gmail_organizer.security import EmailSecurityScanner
from gmail_organizer.reminders import FollowUpDetector
from gmail_organizer.summaries import EmailSummarizer
from gmail_organizer.reputation import SenderReputation
from gmail_organizer.storage import StorageAnalyzer
from gmail_organizer.export import EmailExporter
from gmail_organizer.themes import ThemeManager
from gmail_organizer.scheduler import SyncScheduler
from gmail_organizer.notifications import NotificationManager, NotificationEvent, EVENT_TYPES
from gmail_organizer.multi_label import MultiLabelClassifier
from gmail_organizer import claude_integration as claude_code
import time

# Set up logging
logger = setup_logger('frontend')

st.set_page_config(
    page_title="Gmail Organizer",
    page_icon="📧",
    layout="wide"
)

# ==================== SESSION STATE INIT ====================

if 'auth_manager' not in st.session_state:
    st.session_state.auth_manager = GmailAuthManager()

if 'sync_manager' not in st.session_state:
    st.session_state.sync_manager = SyncManager()

if 'classifier' not in st.session_state:
    st.session_state.classifier = EmailClassifier()

if 'analyzer' not in st.session_state:
    st.session_state.analyzer = EmailAnalyzer()

if 'processing_results' not in st.session_state:
    st.session_state.processing_results = {}

if 'theme_manager' not in st.session_state:
    st.session_state.theme_manager = ThemeManager()

if 'current_theme' not in st.session_state:
    st.session_state.current_theme = "default"

if 'scheduler' not in st.session_state:
    st.session_state.scheduler = SyncScheduler()

if 'notification_manager' not in st.session_state:
    st.session_state.notification_manager = NotificationManager()

# Per-account analysis and suggestions
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}  # account_name -> analysis dict

if 'suggested_categories' not in st.session_state:
    st.session_state.suggested_categories = {}  # account_name -> suggestions dict


# ==================== ACCOUNT REGISTRATION ====================

def register_all_accounts():
    """Register all authenticated accounts with SyncManager on first run"""
    if st.session_state.get('_accounts_registered'):
        return

    auth_manager = st.session_state.auth_manager
    sync_mgr = st.session_state.sync_manager

    try:
        accounts = auth_manager.list_authenticated_accounts()
        for name, email in accounts:
            try:
                service, _, _ = auth_manager.authenticate_account(name)
                sync_mgr.register_account(name, service, email)
            except Exception as e:
                logger.warning(f"Could not register account {name}: {e}")
    except Exception as e:
        logger.error(f"Error loading accounts: {e}")

    st.session_state._accounts_registered = True


# ==================== SIDEBAR ====================

def render_sidebar():
    """Render sidebar with account list, sync badges, and controls"""
    sync_mgr = st.session_state.sync_manager

    with st.sidebar:
        st.header("Accounts")

        accounts = st.session_state.auth_manager.list_authenticated_accounts()
        statuses = sync_mgr.get_all_statuses()

        if accounts:
            for name, email in accounts:
                status = statuses.get(name)
                state = status.state if status else "idle"

                # Status badge
                badge_map = {
                    "complete": "🟢",
                    "syncing": "🔵",
                    "idle": "⚪",
                    "error": "🔴"
                }
                badge = badge_map.get(state, "⚪")

                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"{badge} **{name}**")
                    if status and status.emails_data:
                        st.caption(f"{email} ({len(status.emails_data):,} emails)")
                    else:
                        st.caption(email)

                with col2:
                    if state == "syncing":
                        st.caption("⏳")
                    else:
                        if st.button("🔄", key=f"sync_{name}", help=f"Sync {name}"):
                            sync_mgr.start_sync(name)
                            st.rerun()

                # Show progress bar when syncing
                if state == "syncing" and status:
                    if status.total > 0:
                        st.progress(min(status.progress / status.total, 1.0))
                    st.caption(status.message)

            st.markdown("---")

            # Sync All button
            if sync_mgr.is_any_syncing():
                st.info("Syncing in progress...")
            else:
                if st.button("🔄 Sync All Accounts", use_container_width=True):
                    sync_mgr.start_all_syncs()
                    st.rerun()
        else:
            st.info("No accounts authenticated yet")

        st.markdown("---")

        # Add new account
        if st.button("➕ Add Gmail Account", use_container_width=True):
            st.session_state.show_add_account = True

        if st.session_state.get('show_add_account', False):
            with st.form("add_account_form"):
                account_name = st.text_input(
                    "Account name",
                    placeholder="e.g., personal, work"
                )
                submitted = st.form_submit_button("Authenticate")
                if submitted and account_name:
                    try:
                        with st.spinner("Opening browser for authentication..."):
                            service, email, name = st.session_state.auth_manager.authenticate_account(account_name)
                            sync_mgr.register_account(name, service, email)
                            st.success(f"Authenticated: {email}")
                            st.session_state.show_add_account = False
                            st.session_state._accounts_registered = False
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Authentication failed: {e}")

        # Remove account
        if accounts and len(accounts) > 0:
            st.markdown("---")
            with st.expander("Remove account"):
                for name, email in accounts:
                    if st.button(f"Remove {name}", key=f"remove_{name}"):
                        st.session_state.auth_manager.remove_account(name)
                        st.session_state._accounts_registered = False
                        st.rerun()


# ==================== DASHBOARD TAB ====================

def dashboard_tab():
    """Overview of all accounts with sync status and controls"""
    st.header("Dashboard")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    statuses = sync_mgr.get_all_statuses()

    # Summary metrics
    total_emails = sum(len(s.emails_data) for s in statuses.values())
    synced_count = sum(1 for s in statuses.values() if s.state == "complete")
    syncing_count = sum(1 for s in statuses.values() if s.state == "syncing")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Accounts", len(accounts))
    with col2:
        st.metric("Synced", synced_count)
    with col3:
        st.metric("Syncing", syncing_count)
    with col4:
        st.metric("Total Emails", f"{total_emails:,}")

    st.markdown("---")

    # Account cards
    for name, email in accounts:
        status = statuses.get(name, None)
        state = status.state if status else "idle"

        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                badge_map = {
                    "complete": "🟢 Synced",
                    "syncing": "🔵 Syncing",
                    "idle": "⚪ Idle",
                    "error": "🔴 Error"
                }
                st.subheader(f"{badge_map.get(state, '⚪ Idle')} | {name}")
                st.caption(email)

            with col2:
                if status and status.emails_data:
                    st.metric("Emails", f"{len(status.emails_data):,}")
                if status and status.last_sync_time:
                    st.caption(f"Last sync: {status.last_sync_time[:19]}")

            with col3:
                if state == "syncing":
                    if status and status.total > 0:
                        st.progress(min(status.progress / status.total, 1.0))
                    st.caption(status.message if status else "")
                elif state == "error":
                    st.error(status.error if status else "Unknown error")
                    if st.button("Retry", key=f"retry_{name}"):
                        sync_mgr.start_sync(name)
                        st.rerun()
                else:
                    if st.button("Sync", key=f"dash_sync_{name}"):
                        sync_mgr.start_sync(name)
                        st.rerun()

            st.markdown("---")

    # Sync All button at bottom
    if not sync_mgr.is_any_syncing():
        if st.button("🔄 Sync All Accounts", type="primary", use_container_width=True, key="dash_sync_all"):
            sync_mgr.start_all_syncs()
            st.rerun()


# ==================== ANALYZE TAB ====================

def analyze_tab():
    """Pattern analysis using already-synced data (no re-fetching)"""
    st.header("Analyze Inbox Patterns")
    st.markdown("Analyze your synced emails to discover patterns and suggest categories.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    # Filter to accounts with synced data
    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    # Account selection
    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account to analyze", list(account_options.keys()))
    account_name = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)
    st.success(f"Using {len(emails):,} synced emails (no re-fetching needed)")

    col1, col2 = st.columns(2)
    with col1:
        job_search_focus = st.checkbox(
            "Prioritize job-related categories",
            value=True
        )
    with col2:
        analyze_all = st.checkbox("All", value=True, key="analyze_all",
                                  help="Analyze all synced emails")
        if analyze_all:
            max_analyze = len(emails)
        else:
            max_analyze = st.number_input(
                "Max emails to analyze",
                min_value=100,
                max_value=len(emails),
                value=min(1000, len(emails)),
                step=100,
                help="More emails = better pattern detection"
            )

    if st.button("Analyze Patterns", type="primary", use_container_width=True):
        with st.spinner("Analyzing email patterns..."):
            # Run analyzer on synced data
            sample = emails[:max_analyze]
            analysis = st.session_state.analyzer.analyze_emails(sample)
            st.session_state.analysis_results[account_name] = analysis

            # Get AI suggestions
            suggestions = st.session_state.analyzer.suggest_categories(
                analysis, job_search_focused=job_search_focus
            )
            st.session_state.suggested_categories[account_name] = suggestions
            logger.info(f"Analysis complete for {account_name}: {analysis['unique_senders']} unique senders")
            st.rerun()

    # Show results if available for this account
    if account_name in st.session_state.analysis_results:
        st.markdown("---")
        show_analysis_results(account_name)

    if account_name in st.session_state.suggested_categories:
        st.markdown("---")
        show_suggested_categories(account_name)


def show_analysis_results(account_name: str):
    """Display analysis results for a specific account"""
    st.subheader("Inbox Analysis")

    analysis = st.session_state.analysis_results[account_name]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Emails Analyzed", f"{analysis['total_emails']:,}")
    with col2:
        st.metric("Unique Senders", f"{analysis['unique_senders']:,}")
    with col3:
        avg = analysis['total_emails'] / max(analysis['unique_senders'], 1)
        st.metric("Avg per Sender", f"{avg:.1f}")

    with st.expander("Top Senders"):
        sender_data = [{"Sender": s[:50], "Emails": c} for s, c in analysis['top_senders'][:15]]
        if sender_data:
            st.dataframe(pd.DataFrame(sender_data), use_container_width=True)

    with st.expander("Top Domains"):
        domain_data = [{"Domain": d, "Emails": c} for d, c in analysis['top_domains'][:15]]
        if domain_data:
            st.dataframe(pd.DataFrame(domain_data), use_container_width=True)


def show_suggested_categories(account_name: str):
    """Display AI-suggested categories for a specific account"""
    st.subheader("AI-Suggested Categories")

    suggestions = st.session_state.suggested_categories[account_name]

    if 'summary' in suggestions:
        st.info(suggestions['summary'])

    categories = suggestions.get('categories', [])
    for i, cat in enumerate(categories):
        with st.expander(f"{cat['name']} ({cat['estimated_volume']} volume)", expanded=i < 3):
            st.markdown(f"**Description:** {cat['description']}")
            st.markdown(f"**Why:** {cat['reasoning']}")

    if st.button("Approve Categories", type="primary", key=f"approve_{account_name}"):
        st.session_state.setdefault('approved_categories', {})[account_name] = categories
        st.success("Categories approved! Go to Process tab to apply them.")


# ==================== PROCESS TAB ====================

def process_emails_tab():
    """Classification using synced data"""
    st.header("Process Emails")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    # Filter to accounts with synced data
    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    # Show if custom categories available
    if st.session_state.get('approved_categories'):
        st.info("Using your custom analyzed categories!")

    # Account selection
    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account to process", list(account_options.keys()),
                                  key="process_account_select")
    account_name = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)
    st.success(f"Using {len(emails):,} synced emails (no re-fetching needed)")

    col1, col2 = st.columns(2)
    with col1:
        max_process = st.number_input(
            "Emails to process",
            min_value=10,
            max_value=len(emails),
            value=min(len(emails), 100),
            step=50,
            key="process_max"
        )
    with col2:
        # Show categories
        with st.expander("Categories to apply"):
            st.subheader("Job Search")
            for key, info in CATEGORIES['job_search'].items():
                st.markdown(f"- **{info['name']}**: {info['description']}")
            st.subheader("General")
            for key, info in CATEGORIES['general'].items():
                st.markdown(f"- **{info['name']}**: {info['description']}")

    # Classification method
    use_claude_code = st.session_state.get('use_claude_code', False)

    if use_claude_code:
        st.info("Using Claude Code CLI for classification (free, runs in Terminal)")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Step 1: Export & Launch Claude Code", type="primary", use_container_width=True):
                process_with_claude_code_step1(account_name, emails[:max_process])
        with col2:
            if st.button("Step 2: Apply Results", use_container_width=True):
                process_with_claude_code_step2(account_name)
    else:
        st.info("Using Anthropic API for classification")

        if st.button("Start Processing", type="primary", use_container_width=True):
            process_account(account_name, emails[:max_process])


def process_with_claude_code_step1(account_name: str, emails: list):
    """Export emails and launch Claude Code in Terminal"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text(f"Exporting {len(emails)} emails for Claude Code...")
        progress_bar.progress(30)

        emails_file = claude_code.export_emails_for_claude(emails)

        status_text.text("Creating classification prompt...")
        progress_bar.progress(60)

        prompt_file = claude_code.create_classification_prompt(
            CATEGORIES, job_search_focused=True
        )

        st.session_state.pending_emails = emails
        st.session_state.pending_account = account_name

        progress_bar.progress(100)
        status_text.text("Ready!")

        st.success(f"Exported {len(emails)} emails!")

        try:
            claude_code.launch_claude_code_terminal(prompt_file)
            st.info("""
**Terminal opened with Claude Code!**

1. Wait for Claude Code to process all emails
2. When done, click "Step 2: Apply Results"

Files created:
- `.claude-processing/emails.json`
- `.claude-processing/prompt.md`
- `.claude-processing/results.json` (created by Claude)
            """)
        except Exception as e:
            st.error(f"Failed to launch Terminal: {e}")

    except Exception as e:
        logger.error(f"Error in Claude Code Step 1: {e}", exc_info=True)
        st.error(f"Error: {e}")


def process_with_claude_code_step2(account_name: str):
    """Read Claude Code results and apply labels"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        if 'pending_emails' not in st.session_state:
            st.error("No emails found. Please run Step 1 first.")
            return

        emails = st.session_state.pending_emails

        status_text.text("Reading classification results...")
        progress_bar.progress(20)

        results = claude_code.read_classification_results()
        if not results:
            st.error("No results found. Make sure Claude Code finished and created results.json")
            return

        classifications = {r['id']: r['category'] for r in results}

        status_text.text("Authenticating...")
        progress_bar.progress(30)

        service, email, _ = st.session_state.auth_manager.authenticate_account(account_name)
        ops = GmailOperations(service, email)

        status_text.text("Creating labels...")
        progress_bar.progress(40)
        label_map = ops.create_all_labels()

        status_text.text("Applying labels...")
        progress_bar.progress(50)

        applied_count = 0
        category_counts = {}

        for i, email_item in enumerate(emails):
            email_id = email_item['email_id']
            category = classifications.get(email_id, 'saved')
            label_id = label_map.get(category)

            if label_id:
                success = ops.apply_label_to_email(email_id, label_id)
                if success:
                    applied_count += 1
                    category_counts[category] = category_counts.get(category, 0) + 1

            if (i + 1) % 50 == 0:
                progress = 50 + int((i + 1) / len(emails) * 50)
                progress_bar.progress(min(progress, 99))
                status_text.text(f"Applied {applied_count} labels...")

        progress_bar.progress(100)
        status_text.text("Complete!")

        st.session_state.processing_results[account_name] = {
            'email': email,
            'total_processed': len(emails),
            'total_labeled': applied_count,
            'category_counts': category_counts,
            'classified_emails': [
                {**e, 'category': classifications.get(e['email_id'], 'saved'), 'confidence': 1.0}
                for e in emails
            ]
        }

        st.success(f"Processed {len(emails)} emails, applied {applied_count} labels!")
        show_processing_summary(category_counts, len(emails))

        claude_code.cleanup_processing_files()
        del st.session_state.pending_emails
        del st.session_state.pending_account

    except Exception as e:
        logger.error(f"Error in Claude Code Step 2: {e}", exc_info=True)
        st.error(f"Error: {e}")


def process_account(account_name: str, emails: list):
    """Process emails using Anthropic API classification"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text("Authenticating...")
        progress_bar.progress(10)

        service, account_email, _ = st.session_state.auth_manager.authenticate_account(account_name)
        ops = GmailOperations(service, account_email)

        status_text.text("Creating labels...")
        progress_bar.progress(20)
        label_map = ops.create_all_labels()

        # Classify
        status_text.text("Classifying emails with AI...")
        progress_bar.progress(30)

        use_body = st.session_state.get('use_email_body', False)
        classified_emails = []

        for i, email_item in enumerate(emails):
            body_preview = email_item.get('body_preview', '') if use_body else ""
            category, confidence = st.session_state.classifier.classify_email(
                email_item['subject'],
                email_item['sender'],
                body_preview=body_preview
            )
            email_item['category'] = category
            email_item['confidence'] = confidence
            classified_emails.append(email_item)

            if (i + 1) % 10 == 0:
                progress = 30 + int((i + 1) / len(emails) * 40)
                progress_bar.progress(min(progress, 70))
                status_text.text(f"Classified {i + 1}/{len(emails)}...")

        # Apply labels
        status_text.text("Applying labels...")
        progress_bar.progress(70)

        applied_count = 0
        category_counts = {}

        for i, email_item in enumerate(classified_emails):
            category = email_item['category']
            label_id = label_map.get(category)

            if label_id:
                success = ops.apply_label_to_email(email_item['email_id'], label_id)
                if success:
                    applied_count += 1
                    category_counts[category] = category_counts.get(category, 0) + 1

            if (i + 1) % 10 == 0:
                progress = 70 + int((i + 1) / len(emails) * 30)
                progress_bar.progress(min(progress, 99))

        progress_bar.progress(100)
        status_text.text("Complete!")

        st.session_state.processing_results[account_name] = {
            'email': account_email,
            'total_processed': len(emails),
            'total_labeled': applied_count,
            'category_counts': category_counts,
            'classified_emails': classified_emails
        }

        st.success(f"Processed {len(emails)} emails, applied {applied_count} labels!")
        show_processing_summary(category_counts, len(emails))

    except Exception as e:
        logger.error(f"Error processing {account_name}: {e}", exc_info=True)
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())


def show_processing_summary(category_counts: dict, total: int):
    """Show category distribution summary"""
    summary_data = []
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        cat_info = st.session_state.classifier.get_category_info(category)
        pct = (count / total) * 100
        summary_data.append({
            'Category': cat_info['name'],
            'Count': count,
            'Percentage': f"{pct:.1f}%"
        })
    if summary_data:
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)


# ==================== RESULTS TAB ====================

def results_tab():
    """Multi-account results with search/filter"""
    st.header("Processing Results")

    if not st.session_state.processing_results:
        st.info("No results yet. Process some emails first!")
        return

    accounts = list(st.session_state.processing_results.keys())

    # Account selector
    selected_account = st.selectbox("View results for", accounts, key="results_account")
    result = st.session_state.processing_results[selected_account]

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Processed", result['total_processed'])
    with col2:
        st.metric("Labels Applied", result['total_labeled'])
    with col3:
        rate = (result['total_labeled'] / max(result['total_processed'], 1)) * 100
        st.metric("Success Rate", f"{rate:.1f}%")

    # Category breakdown chart
    st.subheader("Category Distribution")
    chart_data = []
    for category, count in result['category_counts'].items():
        cat_info = st.session_state.classifier.get_category_info(category)
        chart_data.append({'Category': cat_info['name'], 'Count': count})

    if chart_data:
        df = pd.DataFrame(chart_data)
        st.bar_chart(df.set_index('Category'))

    # Email details with search
    st.subheader("Email Details")

    search_query = st.text_input("Search emails", placeholder="Filter by subject or sender...",
                                 key="results_search")

    classified = result.get('classified_emails', [])
    if search_query:
        search_lower = search_query.lower()
        classified = [e for e in classified
                      if search_lower in e.get('subject', '').lower()
                      or search_lower in e.get('sender', '').lower()]

    if classified:
        emails_df = pd.DataFrame([
            {
                'Subject': e['subject'][:60],
                'From': e['sender'][:40],
                'Category': st.session_state.classifier.get_category_info(e.get('category', 'saved'))['name'],
                'Confidence': f"{e.get('confidence', 0):.0%}"
            }
            for e in classified[:500]  # Limit display
        ])
        st.dataframe(emails_df, use_container_width=True)
        if len(classified) > 500:
            st.caption(f"Showing 500 of {len(classified)} results")
    else:
        st.info("No emails match the search.")


# ==================== SETTINGS TAB ====================

def settings_tab():
    """Classification method, sync config, data management"""
    st.header("Settings")

    st.subheader("AI Classification Method")

    if 'claude_code_installed' not in st.session_state:
        st.session_state.claude_code_installed = claude_code.check_claude_code_installed()

    if st.session_state.claude_code_installed:
        st.success("Claude Code CLI detected!")
        use_claude_code = st.checkbox(
            "Use Claude Code for classification (Recommended)",
            value=True,
            help="Free, faster, uses full Claude context. Runs locally via Terminal."
        )
        st.session_state.use_claude_code = use_claude_code

        if use_claude_code:
            st.info("""
**How it works:**
1. App exports emails to `.claude-processing/emails.json`
2. Opens Terminal and runs Claude Code
3. Claude processes and saves results
4. App reads results and applies Gmail labels

**Benefits:** Free, no API costs, full context window!
            """)
    else:
        st.warning("Claude Code CLI not found")
        st.info("Install with: `npm install -g @anthropic-ai/claude-code`")
        st.session_state.use_claude_code = False

    st.markdown("---")

    st.subheader("API Classification Settings")

    use_email_body = st.checkbox(
        "Include email body in API classification",
        value=False,
        help="Uses ~70% more tokens. Sender + Subject is usually enough."
    )
    st.session_state.use_email_body = use_email_body

    if use_email_body:
        st.warning("Including email body will use significantly more tokens.")
    else:
        st.success("Token optimization ON: Using only sender + subject (~70% savings)")

    st.markdown("---")

    st.subheader("Sync Configuration")

    st.success("""**Incremental sync enabled**
- First run: Full sync (fetches all, saves state)
- Future runs: Only new/changed emails (fast!)
    """)

    # Show sync state info
    sync_mgr = st.session_state.sync_manager
    statuses = sync_mgr.get_all_statuses()

    if statuses:
        with st.expander("Sync State Info"):
            for name, status in statuses.items():
                st.markdown(f"**{name}**")
                st.text(f"  State: {status.state}")
                st.text(f"  Emails: {len(status.emails_data):,}")
                if status.last_sync_time:
                    st.text(f"  Last sync: {status.last_sync_time[:19]}")

    st.markdown("---")

    st.subheader("Scheduled Syncs")

    scheduler = st.session_state.scheduler
    # Connect scheduler to sync manager
    scheduler.set_sync_callback(lambda name: sync_mgr.start_sync(name))

    accounts = st.session_state.auth_manager.list_authenticated_accounts()
    if accounts:
        status_summary = scheduler.get_status_summary()
        if status_summary["scheduler_running"]:
            st.success(f"Scheduler active: {status_summary['enabled_count']} account(s) scheduled")
            if status_summary["next_sync_time"]:
                try:
                    from datetime import datetime
                    next_time = datetime.fromisoformat(status_summary["next_sync_time"])
                    st.caption(f"Next sync: {status_summary['next_sync_account']} at {next_time.strftime('%H:%M')}")
                except Exception:
                    pass
        else:
            st.info("No scheduled syncs active. Enable below to auto-sync periodically.")

        for acc_name, acc_email in accounts:
            schedule = scheduler.get_schedule(acc_name)
            with st.expander(f"Schedule: {acc_name} ({acc_email})"):
                enabled = st.checkbox(
                    "Enable auto-sync",
                    value=schedule.enabled,
                    key=f"sched_enabled_{acc_name}"
                )
                interval = st.select_slider(
                    "Sync interval",
                    options=[5, 10, 15, 30, 60, 120, 240, 480, 720, 1440],
                    value=schedule.interval_minutes,
                    format_func=lambda x: f"{x} min" if x < 60 else f"{x // 60} hr{'s' if x > 60 else ''}",
                    key=f"sched_interval_{acc_name}"
                )

                if enabled != schedule.enabled or interval != schedule.interval_minutes:
                    scheduler.update_schedule(acc_name, enabled=enabled, interval_minutes=interval)
                    st.rerun()

                if schedule.last_run:
                    st.caption(f"Last auto-sync: {schedule.last_run[:19]}")
                if schedule.run_count:
                    st.caption(f"Total auto-syncs: {schedule.run_count}")
    else:
        st.info("Authenticate accounts first to configure scheduled syncs.")

    st.markdown("---")

    st.subheader("Data Management")

    st.info("""**Data is never deleted from disk.**
- `.sync-state/` files contain your full email database per account
- `.email-cache/` checkpoint dirs allow resuming interrupted fetches
- Data persists across restarts and is reused automatically
    """)

    st.subheader("Theme")
    theme_mgr = st.session_state.theme_manager
    theme_names = theme_mgr.get_theme_names()
    theme_labels = {name: theme_mgr.get_theme(name)["name"] for name in theme_names}

    current = st.session_state.current_theme
    selected_theme = st.selectbox(
        "Color Theme",
        theme_names,
        index=theme_names.index(current) if current in theme_names else 0,
        format_func=lambda x: theme_labels.get(x, x),
        key="theme_select"
    )

    if selected_theme != st.session_state.current_theme:
        st.session_state.current_theme = selected_theme
        st.rerun()

    # Theme preview
    preview = theme_mgr.get_theme_preview(selected_theme)
    st.caption(preview["description"])
    preview_cols = st.columns(4)
    with preview_cols[0]:
        st.color_picker("Primary", preview["primary"], disabled=True, key="tp1")
    with preview_cols[1]:
        st.color_picker("Background", preview["background"], disabled=True, key="tp2")
    with preview_cols[2]:
        st.color_picker("Secondary", preview["secondary"], disabled=True, key="tp3")
    with preview_cols[3]:
        st.color_picker("Text", preview["text"], disabled=True, key="tp4")

    st.markdown("---")

    st.subheader("API Configuration")
    api_key_set = st.session_state.classifier.api_key is not None
    st.text(f"Anthropic API Key: {'Set' if api_key_set else 'Not set'}")
    if not api_key_set:
        st.warning("Set ANTHROPIC_API_KEY in .env file for API-based classification")


# ==================== ANALYTICS TAB ====================

def analytics_tab():
    """Email analytics with charts and insights"""
    st.header("Email Analytics")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    # Filter to accounts with synced data
    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    # Account selection
    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account", list(account_options.keys()),
                                  key="analytics_account")
    account_name = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)
    analytics = EmailAnalytics(emails)

    # Summary metrics
    summary = analytics.get_summary()
    date_range = summary['date_range']

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Emails", f"{summary['total_emails']:,}")
    with col2:
        st.metric("Unique Senders", f"{summary['unique_senders']:,}")
    with col3:
        st.metric("Unique Domains", f"{summary['unique_domains']:,}")
    with col4:
        st.metric("Avg/Day", f"{summary['avg_per_day']:.1f}")
    with col5:
        st.metric("Date Span", f"{date_range['span_days']} days")

    st.caption(f"Date range: {date_range['oldest']} to {date_range['newest']}")

    st.markdown("---")

    # Volume over time
    st.subheader("Email Volume Over Time")
    granularity = st.radio("Granularity", ["daily", "weekly", "monthly"],
                           index=2, horizontal=True, key="analytics_granularity")

    volume = analytics.get_volume_over_time(granularity)
    if volume:
        volume_df = pd.DataFrame(list(volume.items()), columns=['Date', 'Count'])
        st.line_chart(volume_df.set_index('Date'))

    # Inbox growth
    st.subheader("Inbox Growth (Cumulative)")
    growth = analytics.get_inbox_growth_rate()
    if growth:
        growth_df = pd.DataFrame(list(growth.items()), columns=['Month', 'Total'])
        st.area_chart(growth_df.set_index('Month'))

    st.markdown("---")

    # Time patterns
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Hour of Day Distribution")
        hourly = analytics.get_hourly_distribution()
        hourly_df = pd.DataFrame(
            [{'Hour': f"{h:02d}:00", 'Count': c} for h, c in hourly.items()]
        )
        st.bar_chart(hourly_df.set_index('Hour'))

    with col2:
        st.subheader("Day of Week Distribution")
        daily = analytics.get_day_of_week_distribution()
        daily_df = pd.DataFrame(
            [{'Day': d, 'Count': c} for d, c in daily.items()]
        )
        st.bar_chart(daily_df.set_index('Day'))

    st.markdown("---")

    # Sent vs Received
    st.subheader("Sent vs Received")
    response = analytics.get_response_patterns()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Received", f"{response['received']:,}")
    with col2:
        st.metric("Sent", f"{response['sent']:,}")
    with col3:
        st.metric("Send/Receive Ratio", f"{response['ratio']}")

    st.markdown("---")

    # Top senders and domains
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Senders")
        top_senders = analytics.get_top_senders(15)
        if top_senders:
            senders_df = pd.DataFrame(top_senders, columns=['Sender', 'Count'])
            st.dataframe(senders_df, use_container_width=True)

    with col2:
        st.subheader("Top Domains")
        top_domains = analytics.get_top_domains(15)
        if top_domains:
            domains_df = pd.DataFrame(top_domains, columns=['Domain', 'Count'])
            st.dataframe(domains_df, use_container_width=True)

    st.markdown("---")

    # Busiest periods
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Busiest Days")
        busiest = analytics.get_busiest_periods(10)
        if busiest:
            st.dataframe(
                pd.DataFrame(busiest, columns=['Date', 'Emails']),
                use_container_width=True
            )
    with col2:
        st.subheader("Quietest Days")
        quietest = analytics.get_quiet_periods(10)
        if quietest:
            st.dataframe(
                pd.DataFrame(quietest, columns=['Date', 'Emails']),
                use_container_width=True
            )

    # Monthly breakdown
    st.markdown("---")
    st.subheader("Monthly Breakdown")
    monthly = analytics.get_monthly_stats()
    if monthly:
        monthly_df = pd.DataFrame(monthly)
        st.dataframe(monthly_df, use_container_width=True)

    # Label distribution
    st.markdown("---")
    st.subheader("Label Distribution")
    labels = analytics.get_label_distribution()
    if labels:
        # Filter out system labels for cleaner display
        display_labels = {k: v for k, v in labels.items()
                         if not k.startswith('CATEGORY_')}
        if display_labels:
            labels_df = pd.DataFrame(
                list(display_labels.items()), columns=['Label', 'Count']
            )
            st.bar_chart(labels_df.set_index('Label'))


def filters_tab():
    """Smart filter generator - discover and create Gmail filters from patterns"""
    st.header("Smart Filters")
    st.markdown("Discover email patterns and create Gmail filters automatically.")

    sync_mgr = st.session_state.sync_manager

    accounts = st.session_state.auth_manager.list_authenticated_accounts()
    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    # Filter to accounts with synced + classified data
    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    # Account selection
    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account", list(account_options.keys()),
                                  key="filters_account")
    account_name = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)

    # Check if emails have been classified
    classified = [e for e in emails if e.get('category')]
    has_classified = len(classified) > 0

    # Get the service for this account
    service = None
    for name, email in accounts:
        if name == account_name:
            service = st.session_state.auth_manager.get_service(name)
            break

    filter_gen = SmartFilterGenerator(service=service)

    st.markdown("---")

    # Two sections: Generate filters from patterns, and manage existing filters
    gen_col, manage_col = st.tabs(["Generate Filters", "Manage Existing"])

    with gen_col:
        st.subheader("Generate Filters from Patterns")

        if not has_classified:
            st.info(
                "For best results, classify your emails first (Process tab). "
                "Filters will be generated from sender/domain/subject patterns."
            )
            # Still allow pattern detection on raw emails using labels as categories
            use_labels = st.checkbox("Use Gmail labels as categories instead",
                                     value=True, key="filters_use_labels")
            if use_labels:
                # Create pseudo-classified emails from label data
                for e in emails:
                    labels = e.get('labels', [])
                    # Use first non-system label as category
                    for lbl in labels:
                        if lbl not in ('INBOX', 'SENT', 'DRAFT', 'SPAM', 'TRASH',
                                       'UNREAD', 'STARRED', 'IMPORTANT') and \
                           not lbl.startswith('CATEGORY_'):
                            e['category'] = lbl
                            break
                classified = [e for e in emails if e.get('category')]

        if not classified:
            st.warning("No categorized emails found. Classify emails in the Process tab first.")
            return

        # Configuration
        col1, col2 = st.columns(2)
        with col1:
            min_frequency = st.slider(
                "Minimum pattern frequency",
                min_value=2, max_value=20, value=3,
                help="How many times a pattern must appear to suggest a filter",
                key="filters_min_freq"
            )
        with col2:
            st.metric("Classified Emails", f"{len(classified):,}")
            categories = set(e.get('category', '') for e in classified if e.get('category'))
            st.caption(f"{len(categories)} categories detected")

        if st.button("Analyze Patterns & Generate Filters", type="primary",
                     key="filters_generate"):
            with st.spinner("Analyzing email patterns..."):
                rules = filter_gen.analyze_patterns(classified, min_frequency=min_frequency)
                st.session_state[f'filter_rules_{account_name}'] = rules

        # Display generated rules
        rules_key = f'filter_rules_{account_name}'
        if rules_key in st.session_state and st.session_state[rules_key]:
            rules = st.session_state[rules_key]

            st.success(f"Found {len(rules)} filter suggestions")
            st.markdown("---")

            # Group rules by type
            sender_rules = [r for r in rules if 'from' in r.criteria and
                           not r.criteria['from'].startswith('@')]
            domain_rules = [r for r in rules if 'from' in r.criteria and
                           r.criteria['from'].startswith('@')]
            subject_rules = [r for r in rules if 'subject' in r.criteria]

            # Sender-based filters
            if sender_rules:
                st.subheader(f"Sender Filters ({len(sender_rules)})")
                for i, rule in enumerate(sender_rules[:20]):
                    with st.expander(
                        f"{rule.description} ({rule.match_count} matches)",
                        expanded=False
                    ):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**Criteria:** From `{rule.criteria['from']}`")
                            st.markdown(f"**Action:** Apply label `{rule.action_label}`")
                            st.markdown(f"**Matches:** {rule.match_count} emails")
                        with col2:
                            # Preview button
                            if st.button("Preview", key=f"preview_sender_{i}"):
                                matches = filter_gen.preview_filter(rule, emails)
                                st.session_state[f'preview_{account_name}_sender_{i}'] = matches

                            if service:
                                if st.button("Create Filter", key=f"create_sender_{i}",
                                             type="primary"):
                                    _create_filter_with_label(filter_gen, rule, service,
                                                             account_name)

                        # Show preview if available
                        preview_key = f'preview_{account_name}_sender_{i}'
                        if preview_key in st.session_state:
                            matches = st.session_state[preview_key]
                            st.caption(f"Would match {len(matches)} emails:")
                            preview_data = [
                                {'From': m.get('sender', '')[:50],
                                 'Subject': m.get('subject', '')[:60],
                                 'Date': m.get('date', '')[:16]}
                                for m in matches[:10]
                            ]
                            st.dataframe(pd.DataFrame(preview_data),
                                        use_container_width=True)
                            if len(matches) > 10:
                                st.caption(f"...and {len(matches) - 10} more")

            # Domain-based filters
            if domain_rules:
                st.subheader(f"Domain Filters ({len(domain_rules)})")
                for i, rule in enumerate(domain_rules[:15]):
                    with st.expander(
                        f"{rule.description} ({rule.match_count} matches)",
                        expanded=False
                    ):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**Criteria:** From `{rule.criteria['from']}`")
                            st.markdown(f"**Action:** Apply label `{rule.action_label}`")
                            st.markdown(f"**Matches:** {rule.match_count} emails")
                        with col2:
                            if st.button("Preview", key=f"preview_domain_{i}"):
                                matches = filter_gen.preview_filter(rule, emails)
                                st.session_state[f'preview_{account_name}_domain_{i}'] = matches

                            if service:
                                if st.button("Create Filter", key=f"create_domain_{i}",
                                             type="primary"):
                                    _create_filter_with_label(filter_gen, rule, service,
                                                             account_name)

                        preview_key = f'preview_{account_name}_domain_{i}'
                        if preview_key in st.session_state:
                            matches = st.session_state[preview_key]
                            st.caption(f"Would match {len(matches)} emails:")
                            preview_data = [
                                {'From': m.get('sender', '')[:50],
                                 'Subject': m.get('subject', '')[:60],
                                 'Date': m.get('date', '')[:16]}
                                for m in matches[:10]
                            ]
                            st.dataframe(pd.DataFrame(preview_data),
                                        use_container_width=True)
                            if len(matches) > 10:
                                st.caption(f"...and {len(matches) - 10} more")

            # Subject keyword filters
            if subject_rules:
                st.subheader(f"Subject Keyword Filters ({len(subject_rules)})")
                for i, rule in enumerate(subject_rules[:10]):
                    with st.expander(
                        f"{rule.description} ({rule.match_count} matches)",
                        expanded=False
                    ):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(
                                f"**Criteria:** Subject contains "
                                f"`{rule.criteria['subject']}`"
                            )
                            st.markdown(f"**Action:** Apply label `{rule.action_label}`")
                            st.markdown(f"**Matches:** {rule.match_count} emails")
                        with col2:
                            if st.button("Preview", key=f"preview_subject_{i}"):
                                matches = filter_gen.preview_filter(rule, emails)
                                st.session_state[f'preview_{account_name}_subject_{i}'] = matches

                            if service:
                                if st.button("Create Filter", key=f"create_subject_{i}",
                                             type="primary"):
                                    _create_filter_with_label(filter_gen, rule, service,
                                                             account_name)

                        preview_key = f'preview_{account_name}_subject_{i}'
                        if preview_key in st.session_state:
                            matches = st.session_state[preview_key]
                            st.caption(f"Would match {len(matches)} emails:")
                            preview_data = [
                                {'From': m.get('sender', '')[:50],
                                 'Subject': m.get('subject', '')[:60],
                                 'Date': m.get('date', '')[:16]}
                                for m in matches[:10]
                            ]
                            st.dataframe(pd.DataFrame(preview_data),
                                        use_container_width=True)
                            if len(matches) > 10:
                                st.caption(f"...and {len(matches) - 10} more")

            # Bulk create section
            if service:
                st.markdown("---")
                st.subheader("Bulk Create Filters")
                st.markdown(
                    "Select filters to create in bulk. Labels will be created automatically."
                )

                selected_indices = []
                for i, rule in enumerate(rules):
                    if st.checkbox(
                        f"{rule.description} ({rule.match_count} matches)",
                        key=f"bulk_select_{i}"
                    ):
                        selected_indices.append(i)

                if selected_indices:
                    st.info(f"{len(selected_indices)} filters selected")
                    if st.button(
                        f"Create {len(selected_indices)} Filters",
                        type="primary",
                        key="bulk_create_filters"
                    ):
                        progress = st.progress(0)
                        created = 0
                        errors = 0
                        for idx, sel_idx in enumerate(selected_indices):
                            rule = rules[sel_idx]
                            success = _create_filter_with_label(
                                filter_gen, rule, service, account_name, quiet=True
                            )
                            if success:
                                created += 1
                            else:
                                errors += 1
                            progress.progress((idx + 1) / len(selected_indices))

                        if errors == 0:
                            st.success(f"Successfully created {created} filters!")
                        else:
                            st.warning(
                                f"Created {created} filters, {errors} failed. "
                                f"Check logs for details."
                            )

    with manage_col:
        st.subheader("Existing Gmail Filters")

        if not service:
            st.warning("Could not connect to Gmail API for this account.")
            return

        if st.button("Load Existing Filters", key="load_existing_filters"):
            with st.spinner("Fetching filters from Gmail..."):
                existing = filter_gen.list_existing_filters()
                st.session_state[f'existing_filters_{account_name}'] = existing

        existing_key = f'existing_filters_{account_name}'
        if existing_key in st.session_state:
            existing = st.session_state[existing_key]

            if not existing:
                st.info("No existing filters found in this Gmail account.")
            else:
                st.success(f"Found {len(existing)} existing filters")

                for i, filt in enumerate(existing):
                    criteria = filt.get('criteria', {})
                    action = filt.get('action', {})

                    # Build description
                    desc_parts = []
                    if criteria.get('from'):
                        desc_parts.append(f"From: {criteria['from']}")
                    if criteria.get('to'):
                        desc_parts.append(f"To: {criteria['to']}")
                    if criteria.get('subject'):
                        desc_parts.append(f"Subject: {criteria['subject']}")
                    if criteria.get('query'):
                        desc_parts.append(f"Query: {criteria['query']}")
                    if criteria.get('hasTheWord'):
                        desc_parts.append(f"Has: {criteria['hasTheWord']}")

                    desc = " | ".join(desc_parts) if desc_parts else "Custom filter"

                    # Build action description
                    action_parts = []
                    if action.get('addLabelIds'):
                        action_parts.append(
                            f"Labels: {', '.join(action['addLabelIds'])}"
                        )
                    if action.get('removeLabelIds'):
                        action_parts.append(
                            f"Remove: {', '.join(action['removeLabelIds'])}"
                        )
                    if action.get('forward'):
                        action_parts.append(f"Forward: {action['forward']}")

                    action_desc = " | ".join(action_parts) if action_parts else "No action"

                    with st.expander(f"Filter {i+1}: {desc}", expanded=False):
                        st.markdown(f"**Criteria:** {desc}")
                        st.markdown(f"**Action:** {action_desc}")
                        st.caption(f"Filter ID: {filt.get('id', 'N/A')}")

                        if st.button(
                            "Delete Filter", key=f"delete_filter_{i}",
                            type="secondary"
                        ):
                            filter_id = filt.get('id')
                            if filter_id:
                                success = filter_gen.delete_filter(filter_id)
                                if success:
                                    st.success("Filter deleted!")
                                    # Refresh the list
                                    del st.session_state[existing_key]
                                    st.rerun()
                                else:
                                    st.error("Failed to delete filter.")


def _create_filter_with_label(filter_gen: SmartFilterGenerator, rule: FilterRule,
                              service, account_name: str, quiet: bool = False) -> bool:
    """Create a Gmail filter, creating the label first if needed."""
    try:
        # First ensure the label exists
        label_name = rule.action_label
        label_id = _get_or_create_label(service, label_name)

        if label_id:
            rule.label_id = label_id
            result = filter_gen.create_filter(rule)
            if result:
                if not quiet:
                    st.success(f"Filter created: {rule.description}")
                return True
            else:
                if not quiet:
                    st.error(f"Failed to create filter: {rule.description}")
                return False
        else:
            if not quiet:
                st.error(f"Failed to create label: {label_name}")
            return False
    except Exception as e:
        if not quiet:
            st.error(f"Error: {e}")
        logger.error(f"Error creating filter for {account_name}: {e}")
        return False


def _get_or_create_label(service, label_name: str) -> str:
    """Get existing label ID or create a new label, returns label ID."""
    try:
        # List existing labels
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])

        # Check if label already exists
        for label in labels:
            if label['name'].lower() == label_name.lower():
                return label['id']

        # Create the label
        label_body = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        created = service.users().labels().create(
            userId='me', body=label_body
        ).execute()
        return created['id']
    except Exception as e:
        logger.error(f"Error with label '{label_name}': {e}")
        return None


def unsubscribe_tab():
    """Unsubscribe manager - detect and manage email subscriptions"""
    st.header("Unsubscribe Manager")
    st.markdown("Detect newsletter and marketing subscriptions, and unsubscribe from unwanted ones.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    # Account selection
    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account", list(account_options.keys()),
                                  key="unsub_account")
    account_name = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)

    # Get service for this account
    service = None
    for name, email in accounts:
        if name == account_name:
            service = st.session_state.auth_manager.get_service(name)
            break

    unsub_mgr = UnsubscribeManager(service=service)

    st.markdown("---")

    # Detect subscriptions
    if st.button("Scan for Subscriptions", type="primary", key="unsub_scan"):
        with st.spinner("Analyzing email patterns for subscriptions..."):
            subs = unsub_mgr.detect_subscriptions(emails)
            st.session_state[f'subscriptions_{account_name}'] = subs

    subs_key = f'subscriptions_{account_name}'
    if subs_key not in st.session_state:
        st.info("Click 'Scan for Subscriptions' to detect newsletters and marketing emails.")
        return

    subscriptions = st.session_state[subs_key]

    if not subscriptions:
        st.success("No subscriptions detected in your emails!")
        return

    # Stats overview
    stats = unsub_mgr.get_subscription_stats(subscriptions)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Subscriptions", stats['total_subscriptions'])
    with col2:
        st.metric("With Unsubscribe", stats['with_unsubscribe'])
    with col3:
        st.metric("Total Emails", f"{stats['total_emails']:,}")
    with col4:
        st.metric("Daily Senders", stats['daily_senders'])
    with col5:
        st.metric("Already Unsub'd", stats['already_unsubscribed'])

    st.markdown("---")

    # Filter controls
    col1, col2, col3 = st.columns(3)
    with col1:
        show_filter = st.selectbox("Show", [
            "All Active", "With Unsubscribe Link", "High Frequency (5+/week)",
            "Already Unsubscribed"
        ], key="unsub_filter")
    with col2:
        sort_by = st.selectbox("Sort by", [
            "Frequency (Most)", "Frequency (Least)",
            "Recent First", "Oldest First", "Emails/Week"
        ], key="unsub_sort")
    with col3:
        min_emails = st.slider("Min emails", 1, 50, 3, key="unsub_min")

    # Filter subscriptions
    filtered = subscriptions
    if show_filter == "All Active":
        filtered = [s for s in filtered if not s.unsubscribed]
    elif show_filter == "With Unsubscribe Link":
        filtered = [s for s in filtered if s.has_unsubscribe and not s.unsubscribed]
    elif show_filter == "High Frequency (5+/week)":
        filtered = [s for s in filtered if s.emails_per_week >= 5 and not s.unsubscribed]
    elif show_filter == "Already Unsubscribed":
        filtered = [s for s in filtered if s.unsubscribed]

    filtered = [s for s in filtered if s.frequency >= min_emails]

    # Sort
    if sort_by == "Frequency (Most)":
        filtered.sort(key=lambda s: s.frequency, reverse=True)
    elif sort_by == "Frequency (Least)":
        filtered.sort(key=lambda s: s.frequency)
    elif sort_by == "Recent First":
        filtered.sort(key=lambda s: s.last_received or "", reverse=True)
    elif sort_by == "Oldest First":
        filtered.sort(key=lambda s: s.first_received or "")
    elif sort_by == "Emails/Week":
        filtered.sort(key=lambda s: s.emails_per_week, reverse=True)

    st.caption(f"Showing {len(filtered)} subscriptions")

    # Display subscriptions
    for i, sub in enumerate(filtered[:50]):
        status_icon = "✅" if sub.unsubscribed else ("🔗" if sub.has_unsubscribe else "⚠️")
        freq_label = f"{sub.emails_per_week}/wk" if sub.emails_per_week else f"{sub.frequency} total"

        with st.expander(
            f"{status_icon} {sub.sender_name or sub.sender_email} — "
            f"{sub.frequency} emails ({freq_label})",
            expanded=False
        ):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Sender:** {sub.sender_email}")
                if sub.sender_name:
                    st.markdown(f"**Name:** {sub.sender_name}")
                st.markdown(f"**Domain:** {sub.domain}")
                st.markdown(f"**Emails:** {sub.frequency} total, ~{sub.emails_per_week}/week")
                if sub.first_received:
                    st.markdown(f"**First seen:** {sub.first_received[:10]}")
                if sub.last_received:
                    st.markdown(f"**Last seen:** {sub.last_received[:10]}")
                if sub.category:
                    st.markdown(f"**Category:** {sub.category}")

                if sub.unsubscribed:
                    st.success(f"Unsubscribed on {sub.unsubscribe_date[:10]}")

                if sub.unsubscribe_link:
                    st.markdown(f"**Unsubscribe URL:** `{sub.unsubscribe_link[:80]}...`"
                                if len(sub.unsubscribe_link) > 80
                                else f"**Unsubscribe URL:** `{sub.unsubscribe_link}`")

            with col2:
                if not sub.unsubscribed:
                    if sub.unsubscribe_link:
                        st.link_button(
                            "Open Unsubscribe Link",
                            sub.unsubscribe_link,
                            type="primary"
                        )

                    if sub.unsubscribe_email and service:
                        if st.button("Send Unsubscribe Email",
                                     key=f"unsub_email_{i}"):
                            success = unsub_mgr.unsubscribe_via_email(sub)
                            if success:
                                st.success("Unsubscribe email sent!")
                                st.rerun()
                            else:
                                st.error("Failed to send unsubscribe email.")

                    if st.button("Mark as Unsubscribed",
                                 key=f"unsub_mark_{i}"):
                        unsub_mgr.mark_unsubscribed(sub.sender_email)
                        sub.unsubscribed = True
                        st.success("Marked as unsubscribed!")
                        st.rerun()

                    if st.button("Ignore", key=f"unsub_ignore_{i}",
                                 help="Hide from future scans"):
                        unsub_mgr.ignore_subscription(sub.sender_email)
                        st.info("Subscription ignored.")
                        st.rerun()

    if len(filtered) > 50:
        st.caption(f"Showing first 50 of {len(filtered)} subscriptions. "
                   f"Use filters above to narrow down.")

    # Top domains section
    st.markdown("---")
    st.subheader("Top Subscription Domains")

    domain_counts = Counter()
    for sub in [s for s in subscriptions if not s.unsubscribed]:
        domain_counts[sub.domain] += sub.frequency

    if domain_counts:
        top_domains = domain_counts.most_common(15)
        domain_df = pd.DataFrame(top_domains, columns=['Domain', 'Total Emails'])
        st.bar_chart(domain_df.set_index('Domain'))


def search_tab():
    """Semantic search - TF-IDF based email search with relevance ranking"""
    st.header("Email Search")
    st.markdown("Search your emails by meaning, not just keywords. "
                "Uses TF-IDF relevance ranking for intelligent results.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    # Account selection
    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account", list(account_options.keys()),
                                  key="search_account")
    account_name = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)

    # Build or retrieve index
    index_key = f'search_index_{account_name}'
    if index_key not in st.session_state:
        st.session_state[index_key] = None

    index = st.session_state[index_key]

    # Check if index needs rebuild
    needs_rebuild = (index is None or index.document_count != len(emails))

    if needs_rebuild:
        if st.button("Build Search Index", type="primary", key="build_index"):
            with st.spinner(f"Building search index for {len(emails):,} emails..."):
                new_index = SearchIndex()
                new_index.build_index(emails)
                st.session_state[index_key] = new_index
                index = new_index
                st.success(
                    f"Index built: {index.document_count:,} documents, "
                    f"{index.vocabulary_size:,} terms"
                )
        else:
            st.info("Click 'Build Search Index' to enable search. "
                    "This indexes all email subjects, senders, and body previews.")
            return

    # Show index stats
    if index:
        st.caption(
            f"Index: {index.document_count:,} documents, "
            f"{index.vocabulary_size:,} terms"
        )

    st.markdown("---")

    # Search interface
    query = st.text_input(
        "Search query",
        placeholder="e.g., 'meeting schedule tomorrow', 'invoice payment', 'job application status'",
        key="search_query"
    )

    # Advanced filters (collapsible)
    with st.expander("Advanced Filters", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            sender_filter = st.text_input(
                "Sender contains",
                placeholder="e.g., 'amazon' or 'john@'",
                key="search_sender"
            )
            date_from = st.date_input("From date", value=None, key="search_date_from")
        with col2:
            # Get categories from emails
            categories = sorted(set(
                e.get('category', '') for e in emails if e.get('category')
            ))
            category_options = ["All"] + categories
            category_filter = st.selectbox("Category", category_options,
                                           key="search_category")
            date_to = st.date_input("To date", value=None, key="search_date_to")

        max_results = st.slider("Max results", 10, 200, 50, key="search_max")

    # Execute search
    if query and index:
        cat_filter = category_filter if category_filter != "All" else ""
        date_from_str = date_from.isoformat() if date_from else ""
        date_to_str = date_to.isoformat() if date_to else ""

        results = index.search(
            query,
            limit=max_results,
            sender_filter=sender_filter,
            category_filter=cat_filter,
            date_from=date_from_str,
            date_to=date_to_str
        )

        if results:
            st.success(f"Found {len(results)} relevant emails")

            # Results table
            for rank, (email, score) in enumerate(results, 1):
                relevance_pct = min(score * 100, 100)
                sender = email.get('sender', 'Unknown')[:50]
                subject = email.get('subject', '(no subject)')
                date = email.get('date', '')[:16]
                category = email.get('category', '')

                col1, col2 = st.columns([5, 1])
                with col1:
                    with st.expander(
                        f"#{rank} — {subject[:70]}",
                        expanded=(rank <= 3)
                    ):
                        st.markdown(f"**From:** {sender}")
                        st.markdown(f"**Subject:** {subject}")
                        st.markdown(f"**Date:** {date}")
                        if category:
                            st.markdown(f"**Category:** {category}")

                        body = email.get('body_preview', '')
                        if body:
                            st.markdown("**Preview:**")
                            st.text(body[:300])

                        # Find similar button
                        if st.button("Find Similar", key=f"similar_{rank}"):
                            similar = index.find_similar(email, limit=5)
                            if similar:
                                st.markdown("**Similar emails:**")
                                for sim_email, sim_score in similar:
                                    st.caption(
                                        f"  [{sim_score:.0%}] "
                                        f"{sim_email.get('subject', '')[:60]} "
                                        f"— {sim_email.get('sender', '')[:30]}"
                                    )
                            else:
                                st.caption("No similar emails found.")
                with col2:
                    st.metric("Score", f"{relevance_pct:.0f}%")
        else:
            st.info("No results found. Try different search terms or broader filters.")

    elif query and not index:
        st.warning("Search index not built yet. Click 'Build Search Index' above.")


def bulk_actions_tab():
    """Bulk actions - batch operations on filtered emails"""
    st.header("Bulk Actions")
    st.markdown("Apply batch operations to filtered email selections.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    # Account selection
    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account", list(account_options.keys()),
                                  key="bulk_account")
    account_name = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)

    # Get service
    service = None
    for name, email in accounts:
        if name == account_name:
            service = st.session_state.auth_manager.get_service(name)
            break

    if not service:
        st.error("Could not connect to Gmail API for this account.")
        return

    engine = BulkActionEngine(service=service)

    st.markdown("---")

    # Filter section
    st.subheader("1. Select Emails")

    col1, col2, col3 = st.columns(3)
    with col1:
        sender_filter = st.text_input("Sender contains", key="bulk_sender",
                                      placeholder="e.g., 'newsletter@'")
        subject_filter = st.text_input("Subject contains", key="bulk_subject",
                                       placeholder="e.g., 'weekly digest'")
    with col2:
        categories = sorted(set(
            e.get('category', '') for e in emails if e.get('category')
        ))
        cat_options = ["Any"] + categories
        category_filter = st.selectbox("Category", cat_options, key="bulk_category")

        labels_in_emails = set()
        for e in emails:
            for lbl in e.get('labels', []):
                labels_in_emails.add(lbl)
        label_options = ["Any"] + sorted(labels_in_emails)
        label_filter = st.selectbox("Has label", label_options, key="bulk_label")
    with col3:
        date_from = st.date_input("From date", value=None, key="bulk_date_from")
        date_to = st.date_input("To date", value=None, key="bulk_date_to")

    # Apply filters
    filtered = filter_emails(
        emails,
        sender_filter=sender_filter,
        category_filter=category_filter if category_filter != "Any" else "",
        label_filter=label_filter if label_filter != "Any" else "",
        subject_filter=subject_filter,
        date_from=date_from.isoformat() if date_from else "",
        date_to=date_to.isoformat() if date_to else ""
    )

    # Show filter results
    st.info(f"**{len(filtered):,}** emails match your filters (out of {len(emails):,} total)")

    if filtered:
        # Preview sample
        with st.expander("Preview matched emails (first 20)", expanded=False):
            preview_data = []
            for e in filtered[:20]:
                preview_data.append({
                    'From': e.get('sender', '')[:40],
                    'Subject': e.get('subject', '')[:50],
                    'Date': e.get('date', '')[:10],
                    'Category': e.get('category', '')
                })
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True)
            if len(filtered) > 20:
                st.caption(f"...and {len(filtered) - 20} more")

    st.markdown("---")

    # Action section
    st.subheader("2. Choose Action")

    if not filtered:
        st.warning("No emails match your filters. Adjust filters above.")
        return

    # Check if emails have IDs (needed for API operations)
    emails_with_ids = [e for e in filtered if e.get('id')]
    if not emails_with_ids:
        st.warning(
            "Selected emails don't have Gmail message IDs. "
            "They may have been synced in an older format."
        )
        return

    message_ids = [e['id'] for e in emails_with_ids]

    col1, col2 = st.columns(2)
    with col1:
        action = st.selectbox("Action", [
            "Apply Label",
            "Remove Label",
            "Archive",
            "Move to Inbox",
            "Mark as Read",
            "Mark as Unread",
            "Star",
            "Unstar",
            "Mark Important",
            "Mark Not Important",
            "Move to Trash",
            "Mark as Spam"
        ], key="bulk_action")

    with col2:
        label_name = ""
        if action in ("Apply Label", "Remove Label"):
            existing_labels = engine.list_labels()
            user_labels = [l for l in existing_labels
                          if l.get('type') == 'user']
            label_names = sorted([l['name'] for l in user_labels])

            if action == "Apply Label":
                label_input_mode = st.radio(
                    "Label", ["Existing", "New"],
                    horizontal=True, key="bulk_label_mode"
                )
                if label_input_mode == "Existing" and label_names:
                    label_name = st.selectbox("Select label", label_names,
                                             key="bulk_label_select")
                else:
                    label_name = st.text_input("New label name",
                                              key="bulk_new_label")
            else:
                if label_names:
                    label_name = st.selectbox("Label to remove", label_names,
                                             key="bulk_label_remove")

    st.markdown("---")

    # Confirmation and execution
    st.subheader("3. Execute")

    danger_actions = {"Move to Trash", "Mark as Spam"}
    is_dangerous = action in danger_actions

    st.markdown(
        f"**Action:** {action}"
        + (f" → `{label_name}`" if label_name else "")
    )
    st.markdown(f"**Affected emails:** {len(message_ids):,}")

    if is_dangerous:
        st.warning(
            f"This is a destructive action! {len(message_ids):,} emails "
            f"will be {'trashed' if action == 'Move to Trash' else 'marked as spam'}."
        )
        confirm = st.checkbox(
            "I understand this action cannot be easily undone",
            key="bulk_confirm_danger"
        )
    else:
        confirm = True

    if confirm and st.button(
        f"Execute: {action}" + (f" ({label_name})" if label_name else ""),
        type="primary",
        key="bulk_execute"
    ):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(current, total):
            progress_bar.progress(current / total)
            status_text.text(f"Processing: {current:,}/{total:,}")

        # Execute the action
        if action == "Apply Label":
            if not label_name:
                st.error("Please specify a label name.")
                return
            label_id = engine.get_or_create_label(label_name)
            if not label_id:
                st.error(f"Failed to get/create label: {label_name}")
                return
            result = engine.apply_label(message_ids, label_id, update_progress)

        elif action == "Remove Label":
            if not label_name:
                st.error("Please specify a label to remove.")
                return
            label_id = engine.get_or_create_label(label_name)
            if not label_id:
                st.error(f"Label not found: {label_name}")
                return
            result = engine.remove_label(message_ids, label_id, update_progress)

        elif action == "Archive":
            result = engine.archive(message_ids, update_progress)

        elif action == "Move to Inbox":
            result = engine.unarchive(message_ids, update_progress)

        elif action == "Mark as Read":
            result = engine.mark_read(message_ids, update_progress)

        elif action == "Mark as Unread":
            result = engine.mark_unread(message_ids, update_progress)

        elif action == "Star":
            result = engine.star(message_ids, update_progress)

        elif action == "Unstar":
            result = engine.unstar(message_ids, update_progress)

        elif action == "Mark Important":
            result = engine.mark_important(message_ids, update_progress)

        elif action == "Mark Not Important":
            result = engine.mark_not_important(message_ids, update_progress)

        elif action == "Move to Trash":
            result = engine.move_to_trash(message_ids, update_progress)

        elif action == "Mark as Spam":
            result = engine.mark_spam(message_ids, update_progress)

        else:
            st.error(f"Unknown action: {action}")
            return

        # Show results
        progress_bar.progress(1.0)
        status_text.empty()

        if result['failed'] == 0:
            st.success(
                f"Successfully applied '{action}' to "
                f"{result['success']:,} emails!"
            )
        else:
            st.warning(
                f"Completed with errors: {result['success']:,} succeeded, "
                f"{result['failed']:,} failed."
            )
            if result.get('errors'):
                with st.expander("Error details"):
                    for err in result['errors'][:5]:
                        st.code(err)


def priority_tab():
    """Priority inbox - score and rank emails by importance"""
    st.header("Priority Inbox")
    st.markdown("Emails ranked by importance using sender patterns, urgency keywords, "
                "recency, and reply history.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    account_options = {f"{name} ({email}) - {count:,} emails": (name, email)
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account", list(account_options.keys()),
                                  key="priority_account")
    account_name, account_email = account_options[selected_label]

    emails = sync_mgr.get_emails(account_name)

    scorer = PriorityScorer()

    # Configuration in expander
    with st.expander("Priority Settings", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            high_threshold = st.slider(
                "High priority threshold", 0.3, 0.9, scorer.thresholds.get('high', 0.7),
                step=0.05, key="priority_high"
            )
            medium_threshold = st.slider(
                "Medium priority threshold", 0.1, 0.7, scorer.thresholds.get('medium', 0.4),
                step=0.05, key="priority_medium"
            )
            if st.button("Save Thresholds", key="priority_save_thresh"):
                scorer.thresholds = {'high': high_threshold, 'medium': medium_threshold}
                st.success("Thresholds saved!")

        with col2:
            vip_input = st.text_area(
                "VIP Senders (one per line)",
                value="\n".join(scorer.vip_senders),
                height=100, key="priority_vip"
            )
            low_input = st.text_area(
                "Low Priority Senders (one per line)",
                value="\n".join(scorer.low_priority_senders),
                height=100, key="priority_low"
            )
            if st.button("Save Sender Lists", key="priority_save_senders"):
                scorer.vip_senders = [s.strip() for s in vip_input.split('\n') if s.strip()]
                scorer.low_priority_senders = [s.strip() for s in low_input.split('\n') if s.strip()]
                st.success("Sender lists saved!")

    st.markdown("---")

    # Score emails
    if st.button("Score Emails", type="primary", key="priority_score"):
        with st.spinner("Scoring emails by priority..."):
            scored = scorer.score_emails(emails, user_email=account_email)
            st.session_state[f'priority_scored_{account_name}'] = scored

    scored_key = f'priority_scored_{account_name}'
    if scored_key not in st.session_state:
        st.info("Click 'Score Emails' to rank your inbox by priority.")
        return

    scored = st.session_state[scored_key]

    # Stats
    stats = scorer.get_priority_stats(scored)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("High Priority", stats['high'])
    with col2:
        st.metric("Medium Priority", stats['medium'])
    with col3:
        st.metric("Low Priority", stats['low'])
    with col4:
        st.metric("Total Scored", stats['total'])

    st.markdown("---")

    # Filter by priority level
    level_filter = st.radio(
        "Show", ["All", "High", "Medium", "Low"],
        horizontal=True, key="priority_filter"
    )

    filtered = scored
    if level_filter != "All":
        filtered = [(e, s, l) for e, s, l in scored if l == level_filter.lower()]

    st.caption(f"Showing {len(filtered)} emails")

    # Display
    for i, (email, score, level) in enumerate(filtered[:100]):
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(level, "⚪")
        subject = email.get('subject', '(no subject)')[:70]
        sender = email.get('sender', '')[:40]

        with st.expander(
            f"{icon} [{score:.0%}] {subject}",
            expanded=(i < 5 and level_filter == "All")
        ):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**From:** {email.get('sender', '')[:60]}")
                st.markdown(f"**Subject:** {email.get('subject', '')}")
                st.markdown(f"**Date:** {email.get('date', '')[:20]}")
                if email.get('category'):
                    st.markdown(f"**Category:** {email['category']}")
                body = email.get('body_preview', '')
                if body:
                    st.text(body[:200])
            with col2:
                st.metric("Score", f"{score:.0%}")
                st.caption(f"Priority: {level.upper()}")

    if len(filtered) > 100:
        st.caption(f"Showing first 100 of {len(filtered)} emails.")


def duplicates_tab():
    """Duplicate detection and thread cleanup"""
    st.header("Duplicate & Thread Cleanup")
    st.markdown("Detect duplicate emails and manage large threads to clean up your inbox.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated. Add a Gmail account from the sidebar.")
        return

    synced_accounts = []
    for name, email in accounts:
        emails = sync_mgr.get_emails(name)
        if emails:
            synced_accounts.append((name, email, len(emails)))

    if not synced_accounts:
        st.info("No synced data available. Go to Dashboard and sync your accounts first.")
        return

    account_options = {f"{name} ({email}) - {count:,} emails": name
                       for name, email, count in synced_accounts}
    selected_label = st.selectbox("Select account", list(account_options.keys()),
                                  key="dup_account")
    account_name = account_options[selected_label]
    emails = sync_mgr.get_emails(account_name)

    detector = DuplicateDetector()

    st.markdown("---")

    dup_tab, thread_tab = st.tabs(["Duplicates", "Large Threads"])

    with dup_tab:
        st.subheader("Duplicate Detection")

        if st.button("Scan for Duplicates", type="primary", key="dup_scan"):
            with st.spinner("Scanning for duplicate emails..."):
                duplicates = detector.find_duplicates(emails)
                st.session_state[f'duplicates_{account_name}'] = duplicates

        dup_key = f'duplicates_{account_name}'
        if dup_key in st.session_state:
            duplicates = st.session_state[dup_key]

            if not duplicates:
                st.success("No duplicates found!")
            else:
                stats = detector.get_cleanup_stats(duplicates, [])
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Duplicate Groups", stats['duplicate_groups'])
                with col2:
                    st.metric("Removable Emails", stats['removable_duplicates'])
                with col3:
                    st.metric("Space Savings", f"{stats['space_savings_mb']:.1f} MB")

                # Show by reason
                st.caption(
                    f"By type: Exact ID: {stats['by_reason'].get('exact_id', 0)}, "
                    f"Similar: {stats['by_reason'].get('similar_content', 0)}, "
                    f"Thread: {stats['by_reason'].get('same_thread', 0)}"
                )

                for i, group in enumerate(duplicates[:30]):
                    reason_label = {
                        'exact_id': 'Exact Duplicate',
                        'similar_content': 'Similar Content',
                        'same_thread': 'Thread Duplicate'
                    }.get(group.reason, group.reason)

                    with st.expander(
                        f"{reason_label}: {group.keep_email.get('subject', '')[:50]} "
                        f"({group.count} copies)",
                        expanded=False
                    ):
                        st.markdown(f"**Keep:** {group.keep_email.get('sender', '')[:40]} "
                                    f"— {group.keep_email.get('date', '')[:16]}")
                        st.markdown(f"**Removable:** {group.removable_count} emails")

                        for j, email in enumerate(group.emails):
                            if email.get('id') != group.keep_email.get('id'):
                                st.caption(
                                    f"  Remove: {email.get('sender', '')[:30]} "
                                    f"— {email.get('date', '')[:16]}"
                                )

    with thread_tab:
        st.subheader("Large Threads")

        min_thread_size = st.slider("Minimum thread size", 5, 50, 10,
                                    key="dup_min_thread")

        if st.button("Find Large Threads", type="primary", key="dup_threads"):
            with st.spinner("Scanning for large threads..."):
                threads = detector.find_large_threads(emails, min_size=min_thread_size)
                st.session_state[f'threads_{account_name}'] = threads

        thread_key = f'threads_{account_name}'
        if thread_key in st.session_state:
            threads = st.session_state[thread_key]

            if not threads:
                st.success("No large threads found!")
            else:
                st.info(f"Found {len(threads)} threads with {min_thread_size}+ messages")

                for i, thread in enumerate(threads[:20]):
                    with st.expander(
                        f"{thread.subject[:60]} ({thread.count} messages, "
                        f"{thread.participant_count} participants)",
                        expanded=False
                    ):
                        st.markdown(f"**Thread ID:** {thread.thread_id}")
                        st.markdown(f"**Messages:** {thread.count}")
                        st.markdown(f"**Participants:** {thread.participant_count}")

                        # Show first/last few messages
                        if thread.emails:
                            st.caption("First messages:")
                            for e in thread.emails[:3]:
                                st.caption(
                                    f"  {e.get('sender', '')[:30]} — "
                                    f"{e.get('date', '')[:16]}"
                                )
                            if thread.count > 6:
                                st.caption(f"  ... {thread.count - 6} more ...")
                            if thread.count > 3:
                                st.caption("Last messages:")
                                for e in thread.emails[-3:]:
                                    st.caption(
                                        f"  {e.get('sender', '')[:30]} — "
                                        f"{e.get('date', '')[:16]}"
                                    )


def security_tab():
    """Security scanner - detect phishing and spam"""
    st.header("Security Scanner")
    st.markdown("Scan emails for phishing attempts, suspicious links, spoofing, and spam indicators.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated.")
        return

    synced_accounts = [(n, e, len(sync_mgr.get_emails(n)))
                       for n, e in accounts if sync_mgr.get_emails(n)]
    if not synced_accounts:
        st.info("No synced data. Sync accounts first.")
        return

    account_options = {f"{n} ({e}) - {c:,} emails": n for n, e, c in synced_accounts}
    selected = st.selectbox("Account", list(account_options.keys()), key="sec_account")
    account_name = account_options[selected]
    emails = sync_mgr.get_emails(account_name)

    scanner = EmailSecurityScanner()
    st.markdown("---")

    if st.button("Scan for Threats", type="primary", key="sec_scan"):
        with st.spinner("Scanning emails for security threats..."):
            alerts = scanner.scan_emails(emails)
            st.session_state[f'security_alerts_{account_name}'] = alerts

    alerts_key = f'security_alerts_{account_name}'
    if alerts_key not in st.session_state:
        st.info("Click 'Scan for Threats' to analyze your emails.")
        return

    alerts = st.session_state[alerts_key]

    if not alerts:
        st.success("No security threats detected!")
        return

    stats = scanner.get_scan_stats(alerts)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("High Risk", stats['high_risk'])
    with col2:
        st.metric("Medium Risk", stats['medium_risk'])
    with col3:
        st.metric("Phishing", stats['phishing'])
    with col4:
        st.metric("Suspicious Links", stats['suspicious_link'])

    st.markdown("---")

    level_filter = st.radio("Filter", ["All", "High", "Medium", "Low"],
                            horizontal=True, key="sec_filter")

    filtered = alerts
    if level_filter != "All":
        filtered = [a for a in alerts if a.risk_level == level_filter.lower()]

    for i, alert in enumerate(filtered[:50]):
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[alert.risk_level]
        subject = alert.email.get('subject', '(no subject)')[:60]

        with st.expander(f"{icon} [{alert.risk_score:.0%}] {subject}", expanded=(i < 3)):
            st.markdown(f"**From:** {alert.email.get('sender', '')[:60]}")
            st.markdown(f"**Category:** {alert.category}")
            st.markdown(f"**Risk Score:** {alert.risk_score:.0%}")
            st.markdown("**Findings:**")
            for finding in alert.findings:
                st.markdown(f"- {finding}")


def reminders_tab():
    """Follow-up reminders - detect emails needing responses"""
    st.header("Follow-up Reminders")
    st.markdown("Detect emails that need your response, have unanswered questions, or are awaiting replies.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated.")
        return

    synced_accounts = [(n, e, len(sync_mgr.get_emails(n)))
                       for n, e in accounts if sync_mgr.get_emails(n)]
    if not synced_accounts:
        st.info("No synced data. Sync accounts first.")
        return

    account_options = {f"{n} ({e}) - {c:,} emails": (n, e) for n, e, c in synced_accounts}
    selected = st.selectbox("Account", list(account_options.keys()), key="reminder_account")
    account_name, account_email = account_options[selected]
    emails = sync_mgr.get_emails(account_name)

    col1, col2 = st.columns(2)
    with col1:
        max_days = st.slider("Look back (days)", 7, 90, 30, key="reminder_days")
    with col2:
        filter_type = st.selectbox("Show", ["All", "Overdue", "Soon", "Later"],
                                   key="reminder_filter")

    detector = FollowUpDetector()
    st.markdown("---")

    if st.button("Detect Follow-ups", type="primary", key="reminder_detect"):
        with st.spinner("Analyzing emails for follow-up needs..."):
            # Filter to recent emails within lookback period
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
            recent_emails = []
            for email in emails:
                date_str = email.get('date', '')
                if date_str:
                    try:
                        parsed = detector._parse_date(email)
                        if parsed >= cutoff:
                            recent_emails.append(email)
                    except Exception:
                        recent_emails.append(email)
                else:
                    recent_emails.append(email)

            items = detector.detect_follow_ups(recent_emails, user_email=account_email)
            st.session_state[f'followup_items_{account_name}'] = items

    items_key = f'followup_items_{account_name}'
    if items_key not in st.session_state:
        st.info("Click 'Detect Follow-ups' to scan for emails needing your attention.")
        return

    items = st.session_state[items_key]

    if not items:
        st.success("No follow-up items found! You're all caught up.")
        return

    stats = detector.get_follow_up_stats(items)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total", stats['total'])
    with col2:
        st.metric("Overdue", stats['by_urgency']['overdue'])
    with col3:
        st.metric("Due Soon", stats['by_urgency']['soon'])
    with col4:
        st.metric("Avg Wait (days)", stats['average_days_waiting'])

    st.markdown("---")

    # Stats breakdown
    stat_col1, stat_col2 = st.columns(2)
    with stat_col1:
        st.markdown("**By Reason:**")
        for reason, count in stats['by_reason'].items():
            if count > 0:
                label = reason.replace('_', ' ').title()
                st.markdown(f"- {label}: {count}")
    with stat_col2:
        st.markdown("**Oldest:** {} days waiting".format(stats['oldest_days']))

    st.markdown("---")

    # Filter items
    filtered = items
    if filter_type != "All":
        filtered = [item for item in items if item.urgency == filter_type.lower()]

    st.subheader(f"Items ({len(filtered)})")

    for i, item in enumerate(filtered[:50]):
        urgency_icon = {"overdue": "🔴", "soon": "🟡", "later": "🟢"}[item.urgency]
        reason_icon = {"question": "❓", "action_item": "📋", "awaiting_reply": "⏳"}[item.reason]
        subject = item.email.get('subject', '(no subject)')[:60]

        with st.expander(
            f"{urgency_icon} {reason_icon} [{item.days_waiting}d] {subject}",
            expanded=(i < 3 and item.urgency == "overdue")
        ):
            st.markdown(f"**From:** {item.email.get('sender', item.email.get('from', ''))[:60]}")
            st.markdown(f"**Date:** {item.email.get('date', 'Unknown')}")
            st.markdown(f"**Urgency:** {item.urgency.title()} ({item.days_waiting} days waiting)")
            st.markdown(f"**Reason:** {item.reason.replace('_', ' ').title()}")
            st.markdown(f"**Suggested Action:** {item.suggested_action}")

            snippet = item.email.get('snippet', item.email.get('body', ''))
            if snippet:
                st.markdown("**Preview:**")
                st.text(snippet[:300])


def summaries_tab():
    """Email summaries - digest views and thread overviews"""
    st.header("Email Summaries")
    st.markdown("Generate digest summaries, view thread conversations, and identify trending topics.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated.")
        return

    synced_accounts = [(n, e, len(sync_mgr.get_emails(n)))
                       for n, e in accounts if sync_mgr.get_emails(n)]
    if not synced_accounts:
        st.info("No synced data. Sync accounts first.")
        return

    account_options = {f"{n} ({e}) - {c:,} emails": n for n, e, c in synced_accounts}
    selected = st.selectbox("Account", list(account_options.keys()), key="summary_account")
    account_name = account_options[selected]
    emails = sync_mgr.get_emails(account_name)

    summarizer = EmailSummarizer()

    digest_tab, threads_tab = st.tabs(["Digest", "Thread Summaries"])

    with digest_tab:
        col1, col2 = st.columns(2)
        with col1:
            period = st.selectbox("Period", ["daily", "weekly", "monthly"], key="summary_period")
        with col2:
            ref_date = st.date_input("Reference date", key="summary_date")

        if st.button("Generate Digest", type="primary", key="gen_digest"):
            with st.spinner("Generating digest..."):
                digest = summarizer.generate_digest(
                    emails, period=period,
                    reference_date=ref_date.strftime("%Y-%m-%d") if ref_date else None
                )
                st.session_state[f'digest_{account_name}'] = digest

        digest_key = f'digest_{account_name}'
        if digest_key in st.session_state:
            digest = st.session_state[digest_key]

            st.subheader(f"Digest: {digest.period_start} to {digest.period_end}")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Emails", digest.total_emails)
            with col2:
                st.metric("Threads", digest.total_threads)
            with col3:
                st.metric("Need Response", digest.response_needed)
            with col4:
                st.metric("Busiest Hour", f"{digest.busiest_hour}:00")

            if digest.trending_topics:
                st.markdown("**Trending Topics:**")
                topic_text = ", ".join(f"`{word}` ({count})" for word, count in digest.trending_topics[:8])
                st.markdown(topic_text)

            if digest.category_breakdown:
                st.markdown("**Category Breakdown:**")
                cat_df = pd.DataFrame(
                    list(digest.category_breakdown.items()),
                    columns=["Category", "Count"]
                )
                st.bar_chart(cat_df.set_index("Category"))

            if digest.top_senders:
                st.markdown("**Top Senders:**")
                for sender, count in digest.top_senders[:5]:
                    st.markdown(f"- `{sender}` - {count} emails")

            if digest.highlights:
                st.markdown("---")
                st.subheader("Highlights")
                for h in digest.highlights[:5]:
                    st.markdown(f"- **{h['subject']}** from {h['sender']}")
                    if h.get('snippet'):
                        st.caption(h['snippet'])

            if digest.action_items:
                st.markdown("---")
                st.subheader("Action Items")
                for item in digest.action_items[:5]:
                    st.markdown(f"- **{item['subject']}** from {item['sender']}")
                    actions_str = ", ".join(item.get('actions', []))
                    if actions_str:
                        st.caption(f"Detected: {actions_str}")

    with threads_tab:
        if st.button("Analyze Threads", type="primary", key="analyze_threads"):
            with st.spinner("Analyzing email threads..."):
                thread_summaries = summarizer.summarize_threads(emails, limit=30)
                st.session_state[f'thread_summaries_{account_name}'] = thread_summaries

        threads_key = f'thread_summaries_{account_name}'
        if threads_key in st.session_state:
            thread_summaries = st.session_state[threads_key]

            if not thread_summaries:
                st.info("No multi-message threads found.")
            else:
                st.subheader(f"Top Threads ({len(thread_summaries)})")

                for i, ts in enumerate(thread_summaries):
                    icons = ""
                    if ts.has_question:
                        icons += "❓ "
                    if ts.has_action_item:
                        icons += "📋 "

                    with st.expander(
                        f"{icons}[{ts.message_count} msgs] {ts.subject[:50]}",
                        expanded=(i < 3)
                    ):
                        st.markdown(f"**Participants:** {', '.join(ts.participants[:5])}")
                        st.markdown(f"**Messages:** {ts.message_count}")
                        st.markdown(f"**Period:** {ts.date_range}")
                        st.markdown(f"**Last from:** {ts.last_sender}")
                        if ts.snippet:
                            st.markdown("**Latest:**")
                            st.text(ts.snippet)


def reputation_tab():
    """Sender reputation scores - trust scoring for email senders"""
    st.header("Sender Reputation")
    st.markdown("Analyze sender trustworthiness based on frequency, engagement, authentication, and relationship age.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated.")
        return

    synced_accounts = [(n, e, len(sync_mgr.get_emails(n)))
                       for n, e in accounts if sync_mgr.get_emails(n)]
    if not synced_accounts:
        st.info("No synced data. Sync accounts first.")
        return

    account_options = {f"{n} ({e}) - {c:,} emails": (n, e) for n, e, c in synced_accounts}
    selected = st.selectbox("Account", list(account_options.keys()), key="rep_account")
    account_name, account_email = account_options[selected]
    emails = sync_mgr.get_emails(account_name)

    scorer = SenderReputation()
    st.markdown("---")

    if st.button("Analyze Sender Reputations", type="primary", key="rep_analyze"):
        with st.spinner("Analyzing sender reputations..."):
            profiles = scorer.analyze_senders(emails, user_email=account_email)
            st.session_state[f'reputation_profiles_{account_name}'] = profiles

    profiles_key = f'reputation_profiles_{account_name}'
    if profiles_key not in st.session_state:
        st.info("Click 'Analyze Sender Reputations' to score your senders.")
        return

    profiles = st.session_state[profiles_key]

    if not profiles:
        st.info("No sender data found.")
        return

    stats = scorer.get_reputation_stats(profiles)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Senders", stats['total_senders'])
    with col2:
        st.metric("Trusted", stats['by_level']['trusted'])
    with col3:
        st.metric("Suspicious", stats['by_level']['suspicious'])
    with col4:
        st.metric("Avg Score", f"{stats['avg_reputation_score']:.0f}/100")

    st.markdown("---")

    rep_view, new_senders_view = st.tabs(["All Senders", "First-Time Senders"])

    with rep_view:
        level_filter = st.radio(
            "Filter by level", ["All", "Trusted", "Neutral", "Suspicious"],
            horizontal=True, key="rep_filter"
        )

        filtered = profiles
        if level_filter != "All":
            filtered = [p for p in profiles if p.reputation_level == level_filter.lower()]

        st.subheader(f"Senders ({len(filtered)})")

        # Display as a table
        table_data = []
        for p in filtered[:100]:
            level_icon = {"trusted": "🟢", "neutral": "🟡", "suspicious": "🔴", "unknown": "⚪"}
            table_data.append({
                "Status": level_icon.get(p.reputation_level, "⚪"),
                "Sender": p.sender_email[:40],
                "Score": f"{p.reputation_score:.0f}",
                "Emails": p.total_emails,
                "Reply Rate": f"{p.reply_rate:.0%}",
                "Read Rate": f"{p.read_rate:.0%}",
                "Auto": "Yes" if p.is_automated else "",
            })

        if table_data:
            st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

        # Suspicious senders detail
        if stats['suspicious_senders']:
            st.markdown("---")
            st.subheader("Suspicious Senders")
            for s in stats['suspicious_senders'][:10]:
                with st.expander(f"🔴 {s['sender_email']} (Score: {s['reputation_score']})"):
                    st.markdown(f"**Domain:** {s['domain']}")
                    st.markdown(f"**Total Emails:** {s['total_emails']}")
                    st.markdown(f"**Reputation:** {s['reputation_score']}/100")

    with new_senders_view:
        lookback = st.slider("Lookback period (days)", 7, 90, 30, key="rep_lookback")

        first_timers = scorer.get_first_time_senders(emails, lookback_days=lookback)

        if not first_timers:
            st.info(f"No first-time senders in the last {lookback} days.")
        else:
            st.subheader(f"First-Time Senders ({len(first_timers)})")
            for ft in first_timers[:30]:
                st.markdown(
                    f"- **{ft['sender_name'] or ft['sender_email']}** "
                    f"(`{ft['domain']}`) - {ft['email_count']} email(s) "
                    f"since {ft['first_email_date'].strftime('%b %d') if hasattr(ft['first_email_date'], 'strftime') else ft['first_email_date']}"
                )


def storage_tab():
    """Storage analyzer - breakdown of email storage usage"""
    st.header("Storage Analyzer")
    st.markdown("Analyze email storage usage, identify large emails, and get cleanup recommendations.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated.")
        return

    synced_accounts = [(n, e, len(sync_mgr.get_emails(n)))
                       for n, e in accounts if sync_mgr.get_emails(n)]
    if not synced_accounts:
        st.info("No synced data. Sync accounts first.")
        return

    account_options = {f"{n} ({e}) - {c:,} emails": n for n, e, c in synced_accounts}
    selected = st.selectbox("Account", list(account_options.keys()), key="storage_account")
    account_name = account_options[selected]
    emails = sync_mgr.get_emails(account_name)

    analyzer = StorageAnalyzer()
    st.markdown("---")

    if st.button("Analyze Storage", type="primary", key="storage_analyze"):
        with st.spinner("Analyzing storage usage..."):
            report = analyzer.analyze_storage(emails)
            st.session_state[f'storage_report_{account_name}'] = report

    report_key = f'storage_report_{account_name}'
    if report_key not in st.session_state:
        st.info("Click 'Analyze Storage' to scan your email storage usage.")
        return

    report = st.session_state[report_key]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Size", f"{report.total_size_mb:.1f} MB")
    with col2:
        st.metric("Avg Email Size", f"{report.avg_email_size_kb:.1f} KB")
    with col3:
        st.metric("With Attachments", report.emails_with_attachments)
    with col4:
        st.metric("Total Emails", len(emails))

    st.markdown("---")

    overview_tab, largest_tab, suggestions_tab = st.tabs(
        ["Breakdown", "Largest Emails", "Cleanup Suggestions"]
    )

    with overview_tab:
        if report.by_year:
            st.subheader("Storage by Year")
            year_data = pd.DataFrame(
                [(y, s / (1024 * 1024)) for y, s in report.by_year.items()],
                columns=["Year", "Size (MB)"]
            )
            st.bar_chart(year_data.set_index("Year"))

        if report.by_domain:
            st.subheader("Top Domains by Size")
            domain_data = []
            for domain, size in report.by_domain[:10]:
                domain_data.append({"Domain": domain, "Size (MB)": round(size / (1024 * 1024), 2)})
            if domain_data:
                st.dataframe(pd.DataFrame(domain_data), use_container_width=True, hide_index=True)

        if report.by_category:
            st.subheader("Storage by Category")
            cat_data = pd.DataFrame(
                [(c, s / (1024 * 1024)) for c, s in report.by_category.items()],
                columns=["Category", "Size (MB)"]
            )
            st.bar_chart(cat_data.set_index("Category"))

    with largest_tab:
        if report.largest_emails:
            st.subheader("Largest Emails")
            large_data = []
            for e in report.largest_emails:
                large_data.append({
                    "Subject": e.get("subject", "")[:40],
                    "Sender": e.get("sender", "")[:30],
                    "Date": e.get("date", ""),
                    "Size (MB)": e.get("size_mb", 0),
                    "Attachments": "Yes" if e.get("has_attachments") else "",
                })
            st.dataframe(pd.DataFrame(large_data), use_container_width=True, hide_index=True)
        else:
            st.info("No size data available for emails.")

    with suggestions_tab:
        suggestions = analyzer.get_cleanup_suggestions(report)
        st.subheader("Cleanup Recommendations")
        for i, suggestion in enumerate(suggestions, 1):
            st.markdown(f"{i}. {suggestion}")


def export_tab():
    """Export/Backup - export email data in various formats"""
    st.header("Export & Backup")
    st.markdown("Export your email data in CSV, JSON, or MBOX format for backup or analysis.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated.")
        return

    synced_accounts = [(n, e, len(sync_mgr.get_emails(n)))
                       for n, e in accounts if sync_mgr.get_emails(n)]
    if not synced_accounts:
        st.info("No synced data. Sync accounts first.")
        return

    account_options = {f"{n} ({e}) - {c:,} emails": n for n, e, c in synced_accounts}
    selected = st.selectbox("Account", list(account_options.keys()), key="export_account")
    account_name = account_options[selected]
    emails = sync_mgr.get_emails(account_name)

    exporter = EmailExporter()

    st.markdown("---")

    # Filter options
    st.subheader("Filter (optional)")
    col1, col2 = st.columns(2)
    with col1:
        filter_category = st.text_input("Category filter", key="export_category",
                                        placeholder="e.g., work, personal")
        filter_sender = st.text_input("Sender filter", key="export_sender",
                                      placeholder="e.g., @example.com")
    with col2:
        filter_date_from = st.date_input("From date", value=None, key="export_from")
        filter_date_to = st.date_input("To date", value=None, key="export_to")

    # Apply filters
    filtered = exporter.filter_emails(
        emails,
        category=filter_category or None,
        sender=filter_sender or None,
        date_from=filter_date_from.strftime("%Y-%m-%d") if filter_date_from else None,
        date_to=filter_date_to.strftime("%Y-%m-%d") if filter_date_to else None,
    )

    st.info(f"**{len(filtered):,}** emails selected for export (out of {len(emails):,} total)")

    st.markdown("---")

    # Export format selection
    st.subheader("Export Format")
    format_choice = st.radio(
        "Format", ["CSV", "JSON", "MBOX"],
        horizontal=True, key="export_format",
        help="CSV: Spreadsheet-compatible. JSON: Full data with metadata. MBOX: Standard email archive format."
    )

    # Size estimate
    try:
        estimate = exporter.get_export_size_estimate(filtered, format_choice.lower())
        estimate_mb = estimate / (1024 * 1024)
        st.caption(f"Estimated file size: {estimate_mb:.1f} MB")
    except Exception:
        pass

    # Export button
    filename_base = f"{account_name}_{len(filtered)}_emails"

    if st.button("Export", type="primary", key="export_btn"):
        if not filtered:
            st.warning("No emails to export. Adjust your filters.")
            return

        with st.spinner(f"Exporting {len(filtered):,} emails as {format_choice}..."):
            try:
                if format_choice == "CSV":
                    filepath = exporter.export_csv(filtered, f"{filename_base}.csv")
                elif format_choice == "JSON":
                    filepath = exporter.export_json(filtered, f"{filename_base}.json")
                else:
                    filepath = exporter.export_mbox(filtered, f"{filename_base}.mbox")

                st.success(f"Exported to: `{filepath}`")
                st.session_state[f'last_export_{account_name}'] = filepath

                # Show summary
                summary = exporter.export_summary(filtered)
                st.markdown("---")
                st.subheader("Export Summary")
                sum_col1, sum_col2, sum_col3 = st.columns(3)
                with sum_col1:
                    st.metric("Emails Exported", summary['total_emails'])
                with sum_col2:
                    if summary['date_range']['earliest']:
                        st.metric("Date Range",
                                  f"{summary['date_range']['earliest'][:10]} to {summary['date_range']['latest'][:10]}")
                with sum_col3:
                    st.metric("Avg Subject Length", f"{summary['avg_subject_length']:.0f} chars")

                if summary['categories']:
                    st.markdown("**Categories:**")
                    for cat, count in list(summary['categories'].items())[:5]:
                        st.markdown(f"- {cat}: {count}")

            except Exception as e:
                st.error(f"Export failed: {e}")


def notifications_tab():
    """Webhook and notifications management"""
    st.header("Notifications & Webhooks")
    st.markdown("Configure webhook endpoints to receive notifications about email events.")

    notif_mgr = st.session_state.notification_manager

    stats = notif_mgr.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Webhooks", stats['webhook_count'])
    with col2:
        st.metric("Active", stats['enabled_count'])
    with col3:
        st.metric("Notifications Sent", stats['total_notifications'])
    with col4:
        st.metric("Failures", stats['recent_failures'])

    st.markdown("---")

    webhooks_view, history_view, test_view = st.tabs(["Webhooks", "History", "Test"])

    with webhooks_view:
        st.subheader("Add Webhook")
        with st.form("add_webhook_form"):
            webhook_url = st.text_input("Webhook URL", placeholder="https://example.com/webhook")
            webhook_name = st.text_input("Name (optional)", placeholder="My Slack webhook")
            webhook_events = st.multiselect(
                "Events to subscribe",
                options=list(EVENT_TYPES.keys()),
                default=["sync_complete"],
                format_func=lambda x: f"{x}: {EVENT_TYPES.get(x, '')}",
            )
            webhook_secret = st.text_input("Secret (optional)", type="password",
                                           help="Used for HMAC signature verification")

            if st.form_submit_button("Add Webhook", type="primary"):
                if webhook_url:
                    notif_mgr.add_webhook(
                        url=webhook_url,
                        name=webhook_name,
                        events=webhook_events,
                        secret=webhook_secret,
                    )
                    st.success(f"Webhook added: {webhook_name or webhook_url[:30]}")
                    st.rerun()
                else:
                    st.error("URL is required.")

        # List existing webhooks
        webhooks = notif_mgr.get_webhooks()
        if webhooks:
            st.markdown("---")
            st.subheader(f"Configured Webhooks ({len(webhooks)})")

            for i, wh in enumerate(webhooks):
                status_icon = "🟢" if wh.enabled else "🔴"
                fail_text = f" ({wh.failure_count} failures)" if wh.failure_count else ""

                with st.expander(f"{status_icon} {wh.name or wh.url[:40]}{fail_text}"):
                    st.markdown(f"**URL:** `{wh.url}`")
                    st.markdown(f"**Events:** {', '.join(wh.events)}")
                    st.markdown(f"**Enabled:** {'Yes' if wh.enabled else 'No'}")
                    if wh.last_triggered:
                        st.markdown(f"**Last triggered:** {wh.last_triggered[:19]}")

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        new_state = not wh.enabled
                        if st.button(
                            "Enable" if new_state else "Disable",
                            key=f"toggle_wh_{i}"
                        ):
                            notif_mgr.update_webhook(i, enabled=new_state)
                            st.rerun()
                    with btn_col2:
                        if st.button("Remove", key=f"remove_wh_{i}"):
                            notif_mgr.remove_webhook(i)
                            st.rerun()

    with history_view:
        history = notif_mgr.get_history(limit=50)

        if not history:
            st.info("No notification history yet.")
        else:
            if st.button("Clear History", key="clear_notif_history"):
                notif_mgr.clear_history()
                st.rerun()

            for entry in history:
                event_icon = {
                    "sync_complete": "🔄",
                    "security_alert": "🔴",
                    "priority_email": "⭐",
                    "follow_up_overdue": "⏰",
                    "scheduled_sync": "📅",
                    "export_complete": "📦",
                }.get(entry.get("event_type", ""), "📧")

                timestamp = entry.get("timestamp", "")[:19]
                st.markdown(
                    f"{event_icon} **{entry.get('title', '')}** "
                    f"({entry.get('account_name', '')}) - "
                    f"{entry.get('webhooks_fired', 0)} webhook(s) - "
                    f"`{timestamp}`"
                )

    with test_view:
        st.subheader("Send Test Notification")
        st.markdown("Send a test event to verify your webhook configuration.")

        test_event_type = st.selectbox(
            "Event type",
            list(EVENT_TYPES.keys()),
            format_func=lambda x: f"{x}: {EVENT_TYPES[x]}",
            key="test_event_type"
        )

        if st.button("Send Test", type="primary", key="send_test_notif"):
            event = NotificationEvent(
                event_type=test_event_type,
                account_name="test",
                title=f"Test: {test_event_type}",
                message=f"This is a test notification for event type: {test_event_type}",
                data={"test": True},
            )
            notif_mgr.notify(event)
            st.success("Test notification sent! Check History tab and your webhook endpoints.")


def multi_label_tab():
    """Multi-label classification - assign multiple categories per email"""
    st.header("Multi-Label Classification")
    st.markdown("Classify emails with multiple labels using rule-based pattern matching.")

    sync_mgr = st.session_state.sync_manager
    accounts = st.session_state.auth_manager.list_authenticated_accounts()

    if not accounts:
        st.warning("No accounts authenticated.")
        return

    synced_accounts = [(n, e, len(sync_mgr.get_emails(n)))
                       for n, e in accounts if sync_mgr.get_emails(n)]
    if not synced_accounts:
        st.info("No synced data. Sync accounts first.")
        return

    account_options = {f"{n} ({e}) - {c:,} emails": n for n, e, c in synced_accounts}
    selected = st.selectbox("Account", list(account_options.keys()), key="ml_account")
    account_name = account_options[selected]
    emails = sync_mgr.get_emails(account_name)

    col1, col2 = st.columns(2)
    with col1:
        threshold = st.slider("Confidence threshold", 0.1, 0.9, 0.3, 0.05, key="ml_threshold")
    with col2:
        max_emails = st.number_input("Max emails to classify", 100, len(emails), min(1000, len(emails)),
                                     key="ml_max")

    classifier = MultiLabelClassifier(confidence_threshold=threshold)

    st.markdown("---")

    classify_view, rules_view = st.tabs(["Classify", "Rules"])

    with classify_view:
        if st.button("Run Classification", type="primary", key="ml_classify"):
            with st.spinner(f"Classifying {min(max_emails, len(emails)):,} emails..."):
                subset = emails[:max_emails]
                results = classifier.classify_batch(subset)
                st.session_state[f'ml_results_{account_name}'] = results

        results_key = f'ml_results_{account_name}'
        if results_key in st.session_state:
            results = st.session_state[results_key]
            stats = classifier.get_label_stats(results)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Emails Classified", stats['total_emails'])
            with col2:
                st.metric("Multi-Label", f"{stats['multi_label_pct']}%")
            with col3:
                st.metric("Avg Labels/Email", stats['avg_labels_per_email'])
            with col4:
                st.metric("Unique Labels", stats['unique_labels'])

            st.markdown("---")

            if stats['label_counts']:
                st.subheader("Label Distribution")
                label_df = pd.DataFrame(
                    list(stats['label_counts'].items()),
                    columns=["Label", "Count"]
                )
                st.bar_chart(label_df.set_index("Label"))

            st.markdown("---")

            # Filter results
            label_filter = st.selectbox(
                "Filter by label",
                ["All"] + list(stats['label_counts'].keys()),
                key="ml_label_filter"
            )

            filtered_results = results
            if label_filter != "All":
                filtered_results = [r for r in results if label_filter in r.all_labels]

            st.subheader(f"Results ({len(filtered_results)})")

            for i, result in enumerate(filtered_results[:50]):
                email = emails[i] if i < len(emails) else {}
                subject = email.get('subject', '(no subject)')[:50]
                labels_str = ", ".join(
                    f"{la.label} ({la.confidence:.0%})" for la in result.labels[:3]
                )

                with st.expander(f"[{result.primary_label}] {subject}"):
                    st.markdown(f"**From:** {email.get('sender', email.get('from', ''))[:50]}")
                    st.markdown(f"**Labels:** {labels_str}")
                    for la in result.labels:
                        st.markdown(f"- **{la.label}** ({la.confidence:.0%}): {', '.join(la.matched_rules[:2])}")

    with rules_view:
        st.subheader("Classification Rules")
        st.markdown("These rules determine how emails are categorized.")

        available_labels = classifier.get_available_labels()
        for label in sorted(available_labels):
            rules_for_label = [r for r in classifier.rules if r.label == label]
            for rule in rules_for_label:
                with st.expander(f"**{rule.label}** (weight: {rule.weight}) - {rule.description}"):
                    if rule.sender_patterns:
                        st.markdown(f"**Sender patterns:** `{'`, `'.join(rule.sender_patterns)}`")
                    if rule.subject_patterns:
                        st.markdown(f"**Subject patterns:** `{'`, `'.join(rule.subject_patterns)}`")
                    if rule.body_patterns:
                        st.markdown(f"**Body patterns:** `{'`, `'.join(rule.body_patterns)}`")
                    if rule.domain_patterns:
                        st.markdown(f"**Domain patterns:** `{'`, `'.join(rule.domain_patterns)}`")


# ==================== MAIN ====================

def main():
    if 'session_logged' not in st.session_state:
        logger.info("=" * 60)
        logger.info("Gmail Organizer session started")
        logger.info("=" * 60)
        st.session_state.session_logged = True

    # Apply theme
    theme_css = st.session_state.theme_manager.apply_theme_css(st.session_state.current_theme)
    if theme_css:
        st.markdown(theme_css, unsafe_allow_html=True)

    st.title("Gmail Organizer")
    st.markdown("AI-powered email management for multiple Gmail accounts")

    # Register accounts with sync manager
    register_all_accounts()

    # Render sidebar
    render_sidebar()

    # Main tabs
    tabs = st.tabs([
        "Dashboard", "Analytics", "Search", "Priority", "Smart Filters",
        "Unsubscribe", "Bulk Actions", "Cleanup", "Security", "Reminders",
        "Summaries", "Reputation", "Storage", "Export", "Notifications",
        "Multi-Label", "Analyze", "Process", "Results", "Settings"
    ])

    with tabs[0]:
        dashboard_tab()
    with tabs[1]:
        analytics_tab()
    with tabs[2]:
        search_tab()
    with tabs[3]:
        priority_tab()
    with tabs[4]:
        filters_tab()
    with tabs[5]:
        unsubscribe_tab()
    with tabs[6]:
        bulk_actions_tab()
    with tabs[7]:
        duplicates_tab()
    with tabs[8]:
        security_tab()
    with tabs[9]:
        reminders_tab()
    with tabs[10]:
        summaries_tab()
    with tabs[11]:
        reputation_tab()
    with tabs[12]:
        storage_tab()
    with tabs[13]:
        export_tab()
    with tabs[14]:
        notifications_tab()
    with tabs[15]:
        multi_label_tab()
    with tabs[16]:
        analyze_tab()
    with tabs[17]:
        process_emails_tab()
    with tabs[18]:
        results_tab()
    with tabs[19]:
        settings_tab()

    # Auto-refresh while syncing
    sync_mgr = st.session_state.sync_manager
    if sync_mgr.is_any_syncing():
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        st.error(f"Critical error: {e}")
        import traceback
        st.code(traceback.format_exc())
