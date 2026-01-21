"""Streamlit Frontend for Gmail Organizer"""

import streamlit as st
import pandas as pd
from gmail_auth import GmailAuthManager
from gmail_operations import GmailOperations
from email_classifier import EmailClassifier
from email_analyzer import EmailAnalyzer
from config import CATEGORIES
from logger import setup_logger
import claude_code_integration as claude_code
import time
import json
import os

# Set up logging
logger = setup_logger('frontend')

st.set_page_config(
    page_title="Gmail Organizer",
    page_icon="📧",
    layout="wide"
)

# Initialize session state
if 'auth_manager' not in st.session_state:
    st.session_state.auth_manager = GmailAuthManager()

if 'classifier' not in st.session_state:
    st.session_state.classifier = EmailClassifier()

if 'analyzer' not in st.session_state:
    st.session_state.analyzer = EmailAnalyzer()

if 'processing_results' not in st.session_state:
    st.session_state.processing_results = {}

if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

if 'suggested_categories' not in st.session_state:
    st.session_state.suggested_categories = None


def main():
    # Log session start
    if 'session_logged' not in st.session_state:
        logger.info("=" * 60)
        logger.info("Gmail Organizer session started")
        logger.info("=" * 60)
        st.session_state.session_logged = True

    st.title("📧 Gmail Organizer")
    st.markdown("AI-powered email management for multiple Gmail accounts")

    # Sidebar
    with st.sidebar:
        st.header("Accounts")

        # List authenticated accounts
        accounts = st.session_state.auth_manager.list_authenticated_accounts()

        if accounts:
            st.success(f"{len(accounts)} account(s) authenticated")

            for name, email in accounts:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{name}")
                    st.caption(email)
                with col2:
                    if st.button("❌", key=f"remove_{name}"):
                        st.session_state.auth_manager.remove_account(name)
                        st.rerun()

        else:
            st.info("No accounts authenticated yet")

        st.markdown("---")

        # Add new account
        if st.button("➕ Add Gmail Account", use_container_width=True):
            st.session_state.show_add_account = True

        # Add account form
        if st.session_state.get('show_add_account', False):
            with st.form("add_account_form"):
                account_name = st.text_input("Account name", placeholder="e.g., personal, work, job-search")

                submitted = st.form_submit_button("Authenticate")

                if submitted and account_name:
                    try:
                        with st.spinner("Opening browser for authentication..."):
                            service, email, name = st.session_state.auth_manager.authenticate_account(account_name)
                            st.success(f"✓ Authenticated: {email}")
                            st.session_state.show_add_account = False
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Authentication failed: {e}")

    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Analyze First", "📥 Process Emails", "📊 Results", "⚙️ Settings"])

    with tab1:
        analyze_tab(accounts)

    with tab2:
        process_emails_tab(accounts)

    with tab3:
        results_tab()

    with tab4:
        settings_tab()


def analyze_tab(accounts):
    """Analyze inbox first to discover patterns"""
    if not accounts:
        st.warning("No accounts authenticated. Please add a Gmail account from the sidebar.")
        return

    st.header("🔍 Analyze Your Inbox First")
    st.markdown("""
    **Smart approach:** Let AI analyze your actual emails to discover patterns,
    then suggest categories based on what you REALLY have in your inbox.
    """)

    # Account selection
    account_options = {f"{name} ({email})": name for name, email in accounts}
    selected_account = st.selectbox(
        "Select account to analyze",
        options=list(account_options.keys())
    )

    account_name = account_options[selected_account]

    # Get total email count for the selected account
    # Cache the count to avoid repeated API calls
    cache_key = f"email_count_{account_name}"

    if cache_key not in st.session_state:
        try:
            service, email, _ = st.session_state.auth_manager.authenticate_account(account_name)
            ops = GmailOperations(service, email)

            # Get count based on scan option (will be set below)
            if 'scan_option_analyze' not in st.session_state:
                st.session_state.scan_option_analyze = "All Mail (Inbox + Sent + Archives)"

            # Determine query for count
            scan_queries = {
                "All Mail (Inbox + Sent + Archives)": "",
                "Inbox Only": "in:inbox",
                "Unread Only": "is:unread"
            }
            count_query = scan_queries.get(st.session_state.scan_option_analyze, "")
            total_emails = ops.get_email_count(query=count_query)

            # Cache the result
            st.session_state[cache_key] = total_emails
            logger.info(f"Account {account_name} has {total_emails} emails (query: '{count_query}')")
        except Exception as e:
            logger.error(f"Could not get email count: {e}", exc_info=True)
            st.session_state[cache_key] = 1000  # Fallback
            total_emails = 1000
    else:
        total_emails = st.session_state[cache_key]

    col1, col2 = st.columns(2)

    with col1:
        # Option to choose between All or Custom
        analyze_option = st.radio(
            "Emails to analyze",
            options=[f"All ({total_emails:,} emails)", "Custom amount"],
            index=0,
            key="analyze_amount_option",
            help="Analyzing all emails gives the best category suggestions"
        )

        if "Custom amount" in analyze_option:
            sample_size = st.number_input(
                "Number of emails",
                min_value=100,
                max_value=total_emails,
                value=min(500, total_emails),
                step=100,
                key="analyze_custom_amount"
            )
        else:
            # Analyze all emails
            sample_size = total_emails
            if total_emails > 5000:
                st.caption(f"ℹ️ Analyzing {total_emails:,} emails may take several minutes. Consider testing with fewer first.")

    with col2:
        scan_option = st.selectbox(
            "What to scan",
            options=[
                "All Mail (Inbox + Sent + Archives)",
                "Inbox Only",
                "Unread Only",
                "Custom Query"
            ],
            index=0,  # Default to "All Mail"
            help="Scan everything for best category suggestions",
            key="scan_option_analyze"
        )

        # Map selection to query
        query_map = {
            "All Mail (Inbox + Sent + Archives)": "",
            "Inbox Only": "in:inbox",
            "Unread Only": "is:unread",
            "Custom Query": None
        }

        query = query_map.get(scan_option, "")

        if scan_option == "Custom Query":
            query = st.text_input(
                "Gmail search query",
                value="in:inbox",
                help="e.g., 'from:linkedin.com', 'after:2024/01/01'"
            )

    job_search_focus = st.checkbox(
        "I'm job searching (prioritize job-related categories)",
        value=True
    )

    # Analyze button
    if st.button("🔍 Analyze Inbox", type="primary", use_container_width=True):
        logger.info(f"User clicked Analyze: {sample_size} emails from query '{query}'")
        analyze_inbox(account_name, sample_size, query, job_search_focus)

    # Show results if available
    if st.session_state.analysis_results:
        st.markdown("---")
        show_analysis_results()

    if st.session_state.suggested_categories:
        st.markdown("---")
        show_suggested_categories()


def analyze_inbox(account_name, sample_size, query, job_search_focus):
    """Analyze inbox and suggest categories"""
    logger.info(f"Starting inbox analysis for {account_name} - {sample_size} emails, query: '{query}'")

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Authenticate
        status_text.text("Authenticating...")
        progress_bar.progress(10)
        logger.info(f"Authenticating account: {account_name}")

        service, email, _ = st.session_state.auth_manager.authenticate_account(account_name)
        ops = GmailOperations(service, email)

        # Fetch sample emails
        status_text.text(f"Fetching up to {sample_size:,} emails for analysis...")
        progress_bar.progress(30)
        logger.info(f"Fetching {sample_size} emails with query: '{query}'")

        # Show info about large fetches
        if sample_size > 5000:
            st.info(f"📥 Fetching {sample_size:,} emails may take 5-10 minutes. Please be patient...")

        emails = ops.fetch_emails(max_results=sample_size, query=query)

        if not emails:
            logger.warning(f"No emails found for account {account_name} with query '{query}'")
            st.warning("No emails found to analyze.")
            return

        logger.info(f"✓ Fetched {len(emails)} emails")
        st.info(f"✓ Fetched {len(emails)} emails")

        # Analyze patterns
        status_text.text("Analyzing email patterns...")
        progress_bar.progress(50)
        logger.info("Analyzing email patterns...")

        analysis = st.session_state.analyzer.analyze_emails(emails)
        st.session_state.analysis_results = analysis
        logger.info(f"Analysis complete: {analysis['unique_senders']} unique senders, {analysis['total_emails']} emails")

        # Get AI suggestions
        status_text.text("Getting AI category suggestions...")
        progress_bar.progress(70)
        logger.info("Getting AI category suggestions...")

        suggestions = st.session_state.analyzer.suggest_categories(
            analysis,
            job_search_focused=job_search_focus
        )
        st.session_state.suggested_categories = suggestions
        logger.info(f"AI suggested {len(suggestions.get('categories', []))} categories")

        progress_bar.progress(100)
        status_text.text("✓ Analysis complete!")
        logger.info("Analysis complete!")

        st.success("Analysis complete! Review the suggestions below.")
        st.rerun()

    except Exception as e:
        logger.error(f"Error during analysis: {e}", exc_info=True)
        st.error(f"Error during analysis: {e}")
        import traceback
        st.code(traceback.format_exc())


def show_analysis_results():
    """Display analysis results"""
    st.subheader("📊 Inbox Analysis")

    analysis = st.session_state.analysis_results

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Emails Analyzed", analysis['total_emails'])

    with col2:
        st.metric("Unique Senders", analysis['unique_senders'])

    with col3:
        avg_per_sender = analysis['total_emails'] / max(analysis['unique_senders'], 1)
        st.metric("Avg per Sender", f"{avg_per_sender:.1f}")

    # Top senders
    with st.expander("📧 Top Senders"):
        sender_data = []
        for sender, count in analysis['top_senders'][:15]:
            sender_data.append({"Sender": sender[:50], "Emails": count})
        st.dataframe(pd.DataFrame(sender_data), use_container_width=True)

    # Top domains
    with st.expander("🌐 Top Domains"):
        domain_data = []
        for domain, count in analysis['top_domains'][:15]:
            domain_data.append({"Domain": domain, "Emails": count})
        st.dataframe(pd.DataFrame(domain_data), use_container_width=True)


def show_suggested_categories():
    """Display AI-suggested categories"""
    st.subheader("🤖 AI-Suggested Categories")

    suggestions = st.session_state.suggested_categories

    if 'summary' in suggestions:
        st.info(suggestions['summary'])

    st.markdown("**Review and approve these categories:**")

    categories = suggestions.get('categories', [])

    # Show each category
    for i, cat in enumerate(categories):
        with st.expander(f"📁 {cat['name']} ({cat['estimated_volume']} volume)", expanded=i < 3):
            st.markdown(f"**Description:** {cat['description']}")
            st.markdown(f"**Why:** {cat['reasoning']}")

            col1, col2 = st.columns([3, 1])
            with col1:
                st.text_input(
                    "Edit category name",
                    value=cat['name'],
                    key=f"cat_name_{i}"
                )
            with col2:
                st.selectbox(
                    "Volume",
                    options=["high", "medium", "low"],
                    index=["high", "medium", "low"].index(cat['estimated_volume']),
                    key=f"cat_volume_{i}"
                )

    # Approve button
    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("**Ready to use these categories?**")
        st.caption("These will be created as Gmail labels and used for categorization")

    with col2:
        if st.button("✅ Approve & Continue", type="primary", use_container_width=True):
            st.session_state.approved_categories = categories
            st.success("Categories approved! Go to 'Process Emails' tab to apply them.")
            # TODO: Update config.py with these categories


def process_emails_tab(accounts):
    """Email processing interface"""
    if not accounts:
        st.warning("No accounts authenticated. Please add a Gmail account from the sidebar.")
        return

    st.header("Process Emails")

    # Show if custom categories available
    if st.session_state.get('approved_categories'):
        st.info("✓ Using your custom analyzed categories!")

    else:
        st.info("💡 Tip: Use 'Analyze First' tab to discover categories based on your actual emails")

    # Account selection
    account_options = {f"{name} ({email})": name for name, email in accounts}
    selected_account = st.selectbox(
        "Select account to process",
        options=list(account_options.keys())
    )

    account_name = account_options[selected_account]

    # Get total email count for the selected account
    # Cache the count to avoid repeated API calls
    cache_key_process = f"email_count_process_{account_name}"

    if cache_key_process not in st.session_state:
        try:
            service, email, _ = st.session_state.auth_manager.authenticate_account(account_name)
            ops = GmailOperations(service, email)

            # Get count based on scan option (will be set below)
            if 'scan_option_process' not in st.session_state:
                st.session_state.scan_option_process = "All Mail (Everything)"

            # Determine query for count
            scan_queries_process = {
                "All Mail (Everything)": "",
                "Inbox Only": "in:inbox",
                "Unread Only": "is:unread",
                "Sent Mail": "in:sent"
            }
            count_query_process = scan_queries_process.get(st.session_state.scan_option_process, "")
            total_emails_process = ops.get_email_count(query=count_query_process)

            # Cache the result
            st.session_state[cache_key_process] = total_emails_process
            logger.info(f"Account {account_name} has {total_emails_process} emails for processing (query: '{count_query_process}')")
        except Exception as e:
            logger.error(f"Could not get email count for processing: {e}", exc_info=True)
            st.session_state[cache_key_process] = 1000  # Fallback
            total_emails_process = 1000
    else:
        total_emails_process = st.session_state[cache_key_process]

    col1, col2 = st.columns(2)

    with col1:
        # Option to choose between All or Custom
        process_option = st.radio(
            "Emails to process",
            options=[f"All ({total_emails_process:,} emails)", "Custom amount"],
            index=0,
            key="process_amount_option",
            help="Process all emails to fully organize your inbox"
        )

        if "Custom amount" in process_option:
            max_emails = st.number_input(
                "Number of emails",
                min_value=10,
                max_value=max(total_emails_process, 10000),
                value=min(100, total_emails_process),
                step=50,
                key="process_custom_amount"
            )
        else:
            # Process all emails
            max_emails = total_emails_process
            if total_emails_process > 1000:
                st.caption(f"ℹ️ Processing {total_emails_process:,} emails may take a while. Consider testing with fewer first.")

    with col2:
        scan_option = st.selectbox(
            "What to scan",
            options=[
                "All Mail (Everything)",
                "Inbox Only",
                "Unread Only",
                "Sent Mail",
                "Custom Query"
            ],
            index=0,  # Default to "All Mail"
            help="Scan everything for complete organization",
            key="scan_option_process"
        )

        # Map selection to query
        query_map = {
            "All Mail (Everything)": "",
            "Inbox Only": "in:inbox",
            "Unread Only": "is:unread",
            "Sent Mail": "in:sent",
            "Custom Query": None
        }

        query = query_map.get(scan_option, "")

        if scan_option == "Custom Query":
            query = st.text_input(
                "Gmail search query",
                value="in:inbox",
                help="e.g., 'from:linkedin.com', 'after:2024/01/01'",
                key="process_custom_query"
            )

    # Show categories that will be created
    with st.expander("📁 Categories to be created"):
        st.subheader("Job Search Categories")
        for key, info in CATEGORIES['job_search'].items():
            st.markdown(f"**{info['name']}** - {info['description']}")

        st.subheader("General Categories")
        for key, info in CATEGORIES['general'].items():
            st.markdown(f"**{info['name']}** - {info['description']}")

    # Check if using Claude Code
    use_claude_code = st.session_state.get('use_claude_code', False)

    if use_claude_code:
        st.info("🤖 Using Claude Code CLI for classification (free, runs in Terminal)")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📤 Step 1: Export & Launch Claude Code", type="primary", use_container_width=True):
                logger.info(f"User clicked Export for Claude Code: {max_emails} emails")
                process_with_claude_code_step1(account_name, max_emails, query)

        with col2:
            if st.button("✅ Step 2: Apply Results from Claude Code", use_container_width=True):
                logger.info("User clicked Apply Results")
                process_with_claude_code_step2(account_name)
    else:
        # Original API-based processing
        st.info("💰 Using Anthropic API for classification (costs tokens)")

        if st.button("🚀 Start Processing", type="primary", use_container_width=True):
            logger.info(f"User clicked Process: {max_emails} emails from query '{query}'")
            process_account(account_name, max_emails, query)


def process_with_claude_code_step1(account_name, max_emails, query):
    """Step 1: Export emails and launch Claude Code in Terminal"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Authenticate
        status_text.text("Authenticating account...")
        progress_bar.progress(20)
        logger.info(f"Authenticating account: {account_name}")

        service, email, _ = st.session_state.auth_manager.authenticate_account(account_name)
        ops = GmailOperations(service, email)

        # Fetch emails
        status_text.text(f"Fetching up to {max_emails} emails...")
        progress_bar.progress(40)
        logger.info(f"Fetching {max_emails} emails with query: '{query}'")

        emails = ops.fetch_emails(max_results=max_emails, query=query)

        if not emails:
            st.warning("No emails found matching the query.")
            return

        logger.info(f"Found {len(emails)} emails")

        # Export to JSON
        status_text.text(f"Exporting {len(emails)} emails for Claude Code...")
        progress_bar.progress(60)

        emails_file = claude_code.export_emails_for_claude(emails)

        # Create prompt
        status_text.text("Creating classification prompt...")
        progress_bar.progress(80)

        prompt_file = claude_code.create_classification_prompt(
            CATEGORIES,
            job_search_focused=True
        )

        # Store emails in session for later use
        st.session_state.pending_emails = emails
        st.session_state.pending_account = account_name

        progress_bar.progress(100)
        status_text.text("✓ Ready to launch Claude Code!")

        st.success(f"✓ Exported {len(emails)} emails!")

        # Launch Terminal with Claude Code
        try:
            claude_code.launch_claude_code_terminal(prompt_file)
            st.info("""
🚀 **Terminal opened with Claude Code!**

**What to do:**
1. Wait for Claude Code to process all emails (1-2 minutes)
2. When it says "Classification complete", come back here
3. Click "Step 2: Apply Results" button below

**Files created:**
- `.claude-processing/emails.json` (your emails)
- `.claude-processing/prompt.md` (instructions for Claude)
- `.claude-processing/results.json` (will be created by Claude)
            """)

        except Exception as e:
            st.error(f"Failed to launch Terminal: {e}")
            logger.error(f"Failed to launch Terminal: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in Claude Code Step 1: {e}", exc_info=True)
        st.error(f"Error: {e}")


def process_with_claude_code_step2(account_name):
    """Step 2: Read Claude Code results and apply labels"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Check if we have pending emails
        if 'pending_emails' not in st.session_state:
            st.error("No emails found. Please run Step 1 first.")
            return

        emails = st.session_state.pending_emails

        # Read classification results
        status_text.text("Reading classification results from Claude Code...")
        progress_bar.progress(20)

        results = claude_code.read_classification_results()

        if not results:
            st.error("No results found. Make sure Claude Code finished processing and created results.json")
            return

        logger.info(f"Found {len(results)} classification results")

        # Create a mapping of email_id -> category
        classifications = {r['id']: r['category'] for r in results}

        # Authenticate
        status_text.text("Authenticating...")
        progress_bar.progress(30)

        service, email, _ = st.session_state.auth_manager.authenticate_account(account_name)
        ops = GmailOperations(service, email)

        # Create labels
        status_text.text("Creating Gmail labels...")
        progress_bar.progress(40)

        label_map = ops.create_all_labels()
        logger.info(f"Created/verified {len(label_map)} labels")

        # Apply labels
        status_text.text("Applying labels to emails...")
        progress_bar.progress(50)

        applied_count = 0
        category_counts = {}

        for i, email in enumerate(emails):
            email_id = email['email_id']
            category = classifications.get(email_id, 'saved')  # Default to 'saved' if not classified

            label_id = label_map.get(category)

            if label_id:
                success = ops.apply_label_to_email(email_id, label_id)
                if success:
                    applied_count += 1
                    category_counts[category] = category_counts.get(category, 0) + 1

            if (i + 1) % 50 == 0:
                progress = 50 + int((i + 1) / len(emails) * 50)
                progress_bar.progress(min(progress, 99))
                status_text.text(f"Applied {applied_count} labels so far...")

        progress_bar.progress(100)
        status_text.text("✓ Processing complete!")

        logger.info(f"Applied {applied_count} labels to {len(emails)} emails")

        # Show success
        st.success(f"✓ Processed {len(emails)} emails and applied {applied_count} labels!")

        # Show summary
        st.subheader("Summary")

        summary_data = []
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            cat_info = st.session_state.classifier.get_category_info(category)
            percentage = (count / len(emails)) * 100
            summary_data.append({
                'Category': cat_info['name'],
                'Count': count,
                'Percentage': f"{percentage:.1f}%"
            })

        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

        # Cleanup
        claude_code.cleanup_processing_files()
        del st.session_state.pending_emails
        del st.session_state.pending_account

    except Exception as e:
        logger.error(f"Error in Claude Code Step 2: {e}", exc_info=True)
        st.error(f"Error: {e}")


def process_account(account_name, max_emails, query):
    """Process a single account"""
    logger.info(f"Starting email processing for {account_name} - max {max_emails} emails, query: '{query}'")

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Authenticate
        status_text.text("Authenticating account...")
        progress_bar.progress(10)
        logger.info(f"Authenticating account: {account_name}")

        service, email, _ = st.session_state.auth_manager.authenticate_account(account_name)
        ops = GmailOperations(service, email)

        # Create labels
        status_text.text("Creating Gmail labels...")
        progress_bar.progress(20)
        logger.info("Creating Gmail labels...")

        label_map = ops.create_all_labels()
        logger.info(f"Created/verified {len(label_map)} labels")

        # Fetch emails
        status_text.text(f"Fetching up to {max_emails} emails...")
        progress_bar.progress(30)
        logger.info(f"Fetching up to {max_emails} emails with query: '{query}'")

        emails = ops.fetch_emails(max_results=max_emails, query=query)

        if not emails:
            logger.warning(f"No emails found for account {account_name} with query '{query}'")
            st.warning("No emails found matching the query.")
            return

        logger.info(f"Found {len(emails)} emails")
        st.info(f"Found {len(emails)} emails")

        # Classify emails
        status_text.text("Classifying emails with AI...")
        progress_bar.progress(50)
        logger.info("Starting AI email classification...")

        classified_emails = []
        # Check if user wants to include email body (costs more tokens)
        use_body = st.session_state.get('use_email_body', False)

        for i, email in enumerate(emails):
            # Token optimization: By default, only use sender + subject (~70% token savings)
            body_preview = email.get('body_preview', '') if use_body else ""

            category, confidence = st.session_state.classifier.classify_email(
                email['subject'],
                email['sender'],
                body_preview=body_preview
            )

            email['category'] = category
            email['confidence'] = confidence
            classified_emails.append(email)

            if (i + 1) % 10 == 0:
                progress = 50 + int((i + 1) / len(emails) * 30)
                progress_bar.progress(progress)
                logger.info(f"Classified {i + 1}/{len(emails)} emails")

        logger.info(f"Classification complete: {len(classified_emails)} emails classified")

        # Apply labels
        status_text.text("Applying labels to emails...")
        progress_bar.progress(80)
        logger.info("Applying labels to emails...")

        applied_count = 0
        category_counts = {}

        for i, email in enumerate(classified_emails):
            category = email['category']
            label_id = label_map.get(category)

            if label_id:
                success = ops.apply_label_to_email(email['email_id'], label_id)
                if success:
                    applied_count += 1
                    category_counts[category] = category_counts.get(category, 0) + 1

            if (i + 1) % 10 == 0:
                progress = 80 + int((i + 1) / len(emails) * 20)
                progress_bar.progress(min(progress, 99))

        progress_bar.progress(100)
        status_text.text("✓ Processing complete!")
        logger.info(f"Processing complete: {len(emails)} emails processed, {applied_count} labels applied")

        # Log category breakdown
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {category}: {count} emails")

        # Store results
        st.session_state.processing_results[account_name] = {
            'email': email,
            'total_processed': len(emails),
            'total_labeled': applied_count,
            'category_counts': category_counts,
            'classified_emails': classified_emails
        }

        # Show success message
        st.success(f"✓ Processed {len(emails)} emails and applied {applied_count} labels!")
        logger.info(f"Results stored for account: {account_name}")

        # Show summary
        st.subheader("Summary")

        summary_data = []
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            cat_info = st.session_state.classifier.get_category_info(category)
            percentage = (count / len(emails)) * 100
            summary_data.append({
                'Category': cat_info['name'],
                'Count': count,
                'Percentage': f"{percentage:.1f}%"
            })

        st.dataframe(pd.DataFrame(summary_data), use_container_width=True)

    except Exception as e:
        logger.error(f"Error processing account {account_name}: {e}", exc_info=True)
        st.error(f"Error processing account: {e}")
        import traceback
        st.code(traceback.format_exc())


def results_tab():
    """Show processing results"""
    if not st.session_state.processing_results:
        st.info("No results yet. Process some emails first!")
        return

    st.header("Processing Results")

    # Account selector
    accounts = list(st.session_state.processing_results.keys())
    selected_account = st.selectbox("View results for", accounts)

    result = st.session_state.processing_results[selected_account]

    # Metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Processed", result['total_processed'])

    with col2:
        st.metric("Labels Applied", result['total_labeled'])

    with col3:
        success_rate = (result['total_labeled'] / result['total_processed']) * 100
        st.metric("Success Rate", f"{success_rate:.1f}%")

    # Category breakdown
    st.subheader("Category Distribution")

    chart_data = []
    for category, count in result['category_counts'].items():
        cat_info = st.session_state.classifier.get_category_info(category)
        chart_data.append({
            'Category': cat_info['name'],
            'Count': count
        })

    df = pd.DataFrame(chart_data)
    st.bar_chart(df.set_index('Category'))

    # Email details
    st.subheader("Email Details")

    emails_df = pd.DataFrame([
        {
            'Subject': e['subject'][:60],
            'From': e['sender'][:40],
            'Category': st.session_state.classifier.get_category_info(e['category'])['name'],
            'Confidence': f"{e['confidence']:.0%}"
        }
        for e in result['classified_emails']
    ])

    st.dataframe(emails_df, use_container_width=True)


def settings_tab():
    """Settings and configuration"""
    st.header("Settings")

    st.subheader("🤖 AI Classification Method")

    # Check if Claude Code is installed (cache result)
    if 'claude_code_installed' not in st.session_state:
        st.session_state.claude_code_installed = claude_code.check_claude_code_installed()

    claude_code_installed = st.session_state.claude_code_installed

    if claude_code_installed:
        st.success("✅ Claude Code CLI detected!")

        use_claude_code = st.checkbox(
            "Use Claude Code for classification (Recommended)",
            value=True,
            help="Free, faster, and uses your full Claude context. Runs locally via Terminal."
        )

        st.session_state.use_claude_code = use_claude_code

        if use_claude_code:
            st.info("""
**How it works:**
1. App exports emails to `.claude-processing/emails.json`
2. Click button → Opens Terminal → Runs Claude Code
3. Claude processes all emails and saves results
4. App reads results and applies Gmail labels

**Benefits:** Free, no API costs, full context window!
            """)
        else:
            st.warning("Will use Anthropic API directly (costs money)")
    else:
        st.warning("⚠️ Claude Code CLI not found")
        st.info("Install with: `npm install -g @anthropic-ai/claude-code`")
        st.session_state.use_claude_code = False

    st.markdown("---")

    st.subheader("🔧 API Classification Settings")

    # Token optimization toggle (only relevant if using API)
    use_email_body = st.checkbox(
        "Include email body in API classification",
        value=False,
        help="⚠️ Uses ~70% more tokens. Sender + Subject is usually enough for accurate classification."
    )

    if use_email_body:
        st.warning("Including email body will use significantly more tokens and cost more.")
    else:
        st.success("✅ Token optimization ON: Using only sender + subject (~70% token savings)")

    # Store in session state
    st.session_state.use_email_body = use_email_body

    st.markdown("---")

    st.subheader("API Configuration")

    api_key_set = st.session_state.classifier.api_key is not None
    st.text(f"Anthropic API Key: {'✓ Set' if api_key_set else '✗ Not set'}")

    if not api_key_set:
        st.warning("Anthropic API key not found. Please set ANTHROPIC_API_KEY in .env file")

    st.subheader("About")
    st.markdown("""
    **Gmail Organizer** uses AI to automatically categorize your emails across multiple Gmail accounts.

    Features:
    - Multi-account support
    - AI-powered classification
    - Automatic label creation
    - Job search focused categories
    - Batch processing

    **Privacy:** All processing happens locally. Email content is sent to Anthropic Claude for classification only.
    """)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        st.error(f"Critical error: {e}")
        st.error("Please check the logs for details.")
        st.code(f"Logs: ~/Desktop/Projects/PersonalProjects/gmail-organizer/logs/")
