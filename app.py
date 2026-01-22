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

    st.subheader("Data Management")

    st.info("""**Data is never deleted from disk.**
- `.sync-state/` files contain your full email database per account
- `.email-cache/` checkpoint dirs allow resuming interrupted fetches
- Data persists across restarts and is reused automatically
    """)

    st.subheader("API Configuration")
    api_key_set = st.session_state.classifier.api_key is not None
    st.text(f"Anthropic API Key: {'Set' if api_key_set else 'Not set'}")
    if not api_key_set:
        st.warning("Set ANTHROPIC_API_KEY in .env file for API-based classification")


# ==================== MAIN ====================

def main():
    if 'session_logged' not in st.session_state:
        logger.info("=" * 60)
        logger.info("Gmail Organizer session started")
        logger.info("=" * 60)
        st.session_state.session_logged = True

    st.title("Gmail Organizer")
    st.markdown("AI-powered email management for multiple Gmail accounts")

    # Register accounts with sync manager
    register_all_accounts()

    # Render sidebar
    render_sidebar()

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard", "Analyze", "Process", "Results", "Settings"
    ])

    with tab1:
        dashboard_tab()
    with tab2:
        analyze_tab()
    with tab3:
        process_emails_tab()
    with tab4:
        results_tab()
    with tab5:
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
