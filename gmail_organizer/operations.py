"""Gmail API operations for fetching and organizing emails"""

import base64
import json
from pathlib import Path
from typing import List, Dict, Optional
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest
from email.mime.text import MIMEText
from .config import CATEGORIES, BATCH_SIZE
import time


class GmailOperations:
    """Handle Gmail operations like fetching emails, creating labels, and filters"""

    def __init__(self, service, account_email):
        self.service = service
        self.account_email = account_email
        self.labels_cache = None
        self.checkpoint_dir = Path(__file__).parent.parent / ".email-cache"
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.sync_state_dir = Path(__file__).parent.parent / ".sync-state"
        self.sync_state_dir.mkdir(exist_ok=True)

    def _get_checkpoint_path(self, query: str) -> Path:
        """Get checkpoint directory path for a specific query"""
        safe_query = query.replace(':', '_').replace(' ', '_').replace('/', '_') if query else 'all'
        safe_email = self.account_email.replace('@', '_at_').replace('.', '_')
        checkpoint_subdir = self.checkpoint_dir / f"{safe_email}_{safe_query}"
        checkpoint_subdir.mkdir(exist_ok=True)
        return checkpoint_subdir

    def _load_checkpoint(self, checkpoint_path: Path) -> Dict:
        """Load existing checkpoint from directory-based storage"""
        from gmail_organizer.logger import logger

        emails = []
        fetched_ids = set()

        if not checkpoint_path.exists():
            return {"emails": emails, "fetched_ids": fetched_ids}

        # Load index file (tracks fetched IDs)
        index_file = checkpoint_path / "index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    fetched_ids = set(json.load(f))
            except Exception as e:
                logger.warning(f"Could not load checkpoint index: {e}")

        # Load email data from batch files
        batch_files = sorted(checkpoint_path.glob("batch_*.jsonl"))
        for batch_file in batch_files:
            try:
                with open(batch_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            emails.append(json.loads(line))
            except Exception as e:
                logger.warning(f"Could not load batch file {batch_file}: {e}")

        if emails:
            logger.info(f"📂 Loaded checkpoint: {len(emails)} emails already fetched")

        return {"emails": emails, "fetched_ids": fetched_ids}

    def _save_checkpoint(self, checkpoint_path: Path, emails: List[Dict], fetched_ids: set):
        """Save progress using append-only batch files (efficient for large datasets)"""
        from gmail_organizer.logger import logger

        try:
            checkpoint_path.mkdir(exist_ok=True)

            # Save index (fetched IDs) - small file, fast to write
            index_file = checkpoint_path / "index.json"
            with open(index_file, 'w') as f:
                json.dump(list(fetched_ids), f)

            # Determine which emails haven't been written to batch files yet
            existing_count = 0
            batch_files = sorted(checkpoint_path.glob("batch_*.jsonl"))
            for bf in batch_files:
                with open(bf, 'r') as f:
                    existing_count += sum(1 for line in f if line.strip())

            # Append new emails to a new batch file
            new_emails = emails[existing_count:]
            if new_emails:
                batch_num = len(batch_files)
                batch_file = checkpoint_path / f"batch_{batch_num:04d}.jsonl"
                with open(batch_file, 'w') as f:
                    for email in new_emails:
                        f.write(json.dumps(email) + '\n')

        except Exception as e:
            logger.warning(f"Could not save checkpoint: {e}")

    # ==================== SYNC STATE MANAGEMENT ====================
    # These methods manage the historyId for incremental sync using Gmail's History API

    def _get_sync_state_path(self) -> Path:
        """Get sync state file path for this account"""
        safe_email = self.account_email.replace('@', '_at_').replace('.', '_')
        return self.sync_state_dir / f"sync_state_{safe_email}.json"

    def _load_sync_state(self) -> Dict:
        """Load sync state (historyId, last sync time, email database).

        Also checks the checkpoint directory - if it has more emails than
        the sync state (e.g., due to an interrupted sync), merges them in.
        """
        from gmail_organizer.logger import logger

        state = {
            "history_id": None,
            "last_sync_time": None,
            "emails": {},
            "total_synced": 0
        }

        sync_path = self._get_sync_state_path()
        if sync_path.exists():
            try:
                with open(sync_path, 'r') as f:
                    state = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load sync state: {e}")

        # Recovery: check if checkpoint has more data than sync state
        # This handles the case where a sync was interrupted before saving state
        checkpoint_path = self._get_checkpoint_path("")
        sync_emails_dict = state.get("emails", {})

        # Quick check: compare index size (just IDs) before loading full checkpoint
        index_file = checkpoint_path / "index.json"
        checkpoint_count = 0
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    checkpoint_count = len(json.load(f))
            except Exception:
                pass

        if checkpoint_count > len(sync_emails_dict):
            # Checkpoint has more data - load full checkpoint and merge
            checkpoint = self._load_checkpoint(checkpoint_path)
            checkpoint_emails = checkpoint.get("emails", [])

            logger.info(
                f"Checkpoint has more emails ({len(checkpoint_emails)}) than sync state "
                f"({len(sync_emails_dict)}), merging checkpoint data"
            )
            # Merge: start with sync state, overlay with checkpoint data
            merged = dict(sync_emails_dict)
            for email in checkpoint_emails:
                email_id = email.get("email_id", "")
                if email_id:
                    merged[email_id] = email
            state["emails"] = merged
            state["total_synced"] = len(merged)
            # Save the merged state so we don't have to merge again next time
            self._save_sync_state(
                state.get("history_id", ""),
                merged,
                state.get("last_sync_time")
            )

        return state

    def _save_sync_state(self, history_id: str, emails: Dict, last_sync_time: str = None):
        """Save sync state after successful sync"""
        from datetime import datetime
        from gmail_organizer.logger import logger

        sync_path = self._get_sync_state_path()
        try:
            state = {
                "history_id": history_id,
                "last_sync_time": last_sync_time or datetime.now().isoformat(),
                "emails": emails,
                "total_synced": len(emails)
            }
            with open(sync_path, 'w') as f:
                json.dump(state, f)
            logger.info(f"Saved sync state: historyId={history_id}, {len(emails)} emails")
        except Exception as e:
            logger.error(f"Could not save sync state: {e}")

    def get_current_history_id(self) -> Optional[str]:
        """Get the current historyId from Gmail profile"""
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('historyId')
        except HttpError as e:
            from gmail_organizer.logger import logger
            logger.error(f"Could not get current historyId: {e}")
            return None

    def sync_emails(self, query: str = "", progress_callback=None) -> List[Dict]:
        """
        Smart sync: Uses incremental sync if available, otherwise full sync.

        This is the recommended method for fetching emails as it:
        1. Checks if we have a previous sync state (historyId)
        2. If yes, uses history.list to only fetch new/changed emails (FAST!)
        3. If no, performs a full sync and saves the historyId for next time

        Args:
            query: Gmail search query (used for full sync filtering)
            progress_callback: Optional callback function(current, total, message)

        Returns:
            List of all email dictionaries (cached + new)
        """
        from gmail_organizer.logger import logger
        from datetime import datetime

        sync_state = self._load_sync_state()
        stored_history_id = sync_state.get("history_id")
        cached_emails = sync_state.get("emails", {})

        if stored_history_id and cached_emails:
            logger.info(f"Found sync state: historyId={stored_history_id}, {len(cached_emails)} cached emails")
            print(f"📂 Found previous sync: {len(cached_emails):,} emails cached")

            # Try incremental sync
            try:
                new_emails, deleted_ids, current_history_id = self._incremental_sync(
                    stored_history_id,
                    progress_callback
                )

                if new_emails is not None:  # Incremental sync succeeded
                    # Update cache: add new emails, remove deleted
                    for email in new_emails:
                        cached_emails[email['email_id']] = email
                    for email_id in deleted_ids:
                        cached_emails.pop(email_id, None)

                    # Save updated state
                    self._save_sync_state(current_history_id, cached_emails)

                    logger.info(f"Incremental sync complete: +{len(new_emails)} new, -{len(deleted_ids)} deleted")
                    print(f"✓ Incremental sync: +{len(new_emails):,} new, -{len(deleted_ids):,} deleted")
                    print(f"✓ Total emails: {len(cached_emails):,}")

                    return list(cached_emails.values())

            except HttpError as e:
                if 'historyId' in str(e) or '404' in str(e):
                    logger.warning(f"History expired, falling back to full sync: {e}")
                    print("⚠️  History expired, performing full sync...")
                else:
                    raise

        # Full sync needed (first time or history expired)
        logger.info("Performing full sync...")
        print("🔄 Performing full sync (this will be cached for future incremental syncs)...")

        # Get current historyId BEFORE fetching (to capture any changes during fetch)
        current_history_id = self.get_current_history_id()

        # Perform full sync
        emails = self.fetch_emails(
            max_results=1000000,  # Effectively unlimited
            query=query,
            progress_callback=progress_callback
        )

        if emails:
            # Convert to dict for efficient lookups
            emails_dict = {e['email_id']: e for e in emails}

            # Merge with previously cached emails to prevent data loss
            # (handles case where current fetch got fewer emails than a previous sync)
            if cached_emails and len(cached_emails) > len(emails_dict):
                logger.info(
                    f"Merging with {len(cached_emails)} previously cached emails "
                    f"(fetched {len(emails_dict)} this run)"
                )
                merged = dict(cached_emails)
                merged.update(emails_dict)  # New data takes priority
                emails_dict = merged

            # Get the historyId from the most recent message for accuracy
            try:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=emails[0]['email_id'],
                    format='minimal'
                ).execute()
                current_history_id = msg.get('historyId', current_history_id)
            except Exception:
                pass  # Use profile historyId as fallback

            # Save sync state for future incremental syncs
            self._save_sync_state(current_history_id, emails_dict)
            logger.info(f"Full sync complete: {len(emails_dict)} emails, historyId={current_history_id}")
            print(f"✓ Full sync complete: {len(emails_dict):,} emails")
            print(f"✓ Saved sync state for future incremental syncs")

            return list(emails_dict.values())

        return emails

    def _incremental_sync(self, start_history_id: str, progress_callback=None) -> tuple:
        """
        Fetch only new/changed emails since the given historyId.

        Uses Gmail's history.list API which is MUCH faster than full sync.

        Args:
            start_history_id: The historyId from last sync
            progress_callback: Optional progress callback

        Returns:
            Tuple of (new_emails, deleted_ids, current_history_id) or (None, None, None) on failure
        """
        from gmail_organizer.logger import logger

        logger.info(f"Starting incremental sync from historyId={start_history_id}")

        if progress_callback:
            progress_callback(0, 100, "Checking for new emails...")

        new_message_ids = set()
        deleted_ids = set()
        label_changes = {}  # message_id -> new labels

        page_token = None
        history_count = 0

        try:
            while True:
                # Fetch history records
                results = self.service.users().history().list(
                    userId='me',
                    startHistoryId=start_history_id,
                    historyTypes=['messageAdded', 'messageDeleted', 'labelAdded', 'labelRemoved'],
                    pageToken=page_token
                ).execute()

                history_records = results.get('history', [])
                current_history_id = results.get('historyId', start_history_id)

                for record in history_records:
                    history_count += 1

                    # New messages
                    for msg in record.get('messagesAdded', []):
                        new_message_ids.add(msg['message']['id'])

                    # Deleted messages
                    for msg in record.get('messagesDeleted', []):
                        msg_id = msg['message']['id']
                        deleted_ids.add(msg_id)
                        new_message_ids.discard(msg_id)  # Don't fetch if deleted

                    # Label changes (for existing messages)
                    for msg in record.get('labelsAdded', []):
                        msg_id = msg['message']['id']
                        if msg_id not in new_message_ids:
                            label_changes[msg_id] = msg['message'].get('labelIds', [])

                    for msg in record.get('labelsRemoved', []):
                        msg_id = msg['message']['id']
                        if msg_id not in new_message_ids:
                            label_changes[msg_id] = msg['message'].get('labelIds', [])

                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            logger.info(f"History scan complete: {history_count} records, {len(new_message_ids)} new, {len(deleted_ids)} deleted")

            if not new_message_ids and not deleted_ids:
                logger.info("No changes since last sync")
                print("✓ No new emails since last sync")
                return [], [], current_history_id

            # Fetch details for new messages
            new_emails = []
            if new_message_ids:
                if progress_callback:
                    progress_callback(0, len(new_message_ids), f"Fetching {len(new_message_ids)} new emails...")

                logger.info(f"Fetching {len(new_message_ids)} new email details...")
                print(f"📥 Fetching {len(new_message_ids):,} new emails...")

                # Use batch fetching for efficiency
                message_ids_list = list(new_message_ids)
                batch_size = 50

                for batch_start in range(0, len(message_ids_list), batch_size):
                    batch_ids = message_ids_list[batch_start:batch_start + batch_size]
                    batch_emails, failed_ids = self._fetch_emails_batch(batch_ids)
                    new_emails.extend(batch_emails)

                    if progress_callback:
                        progress_callback(
                            len(new_emails),
                            len(new_message_ids),
                            f"Fetched {len(new_emails)}/{len(new_message_ids)} new emails"
                        )

                    # Small delay between batches
                    if batch_start + batch_size < len(message_ids_list):
                        time.sleep(1)

            return new_emails, list(deleted_ids), current_history_id

        except HttpError as e:
            error_str = str(e)
            if '404' in error_str or 'notFound' in error_str:
                logger.warning(f"History not found (too old?): {e}")
                return None, None, None
            raise

    def fetch_emails(self, max_results=100, query="in:inbox", progress_callback=None) -> List[Dict]:
        """
        Fetch emails from Gmail with pagination support

        Args:
            max_results: Maximum number of emails to fetch (no limit if set high)
            query: Gmail search query (e.g., "in:inbox", "is:unread")
            progress_callback: Optional callback function(current, total, message) for progress updates

        Returns:
            List of email dictionaries
        """
        from gmail_organizer.logger import logger

        emails = []
        message_ids = []
        page_token = None
        fetched_count = 0

        try:
            # First, get all message IDs using pagination
            logger.info(f"Fetching message IDs (max: {max_results}, query: '{query}')...")

            if progress_callback:
                progress_callback(0, max_results, "Finding message IDs...")

            while fetched_count < max_results:
                # Fetch up to 500 message IDs per page (API max)
                page_size = min(500, max_results - fetched_count)

                results = self.service.users().messages().list(
                    userId='me',
                    maxResults=page_size,
                    q=query if query else None,
                    pageToken=page_token
                ).execute()

                messages = results.get('messages', [])

                if not messages:
                    break

                message_ids.extend([msg['id'] for msg in messages])
                fetched_count += len(messages)

                logger.info(f"  Found {fetched_count} message IDs so far...")

                # Update UI progress
                if progress_callback:
                    progress_callback(fetched_count, max_results, f"Found {fetched_count:,} message IDs...")

                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            if not message_ids:
                logger.warning(f"No messages found for query: {query}")
                print(f"No messages found for query: {query}")
                return []

            total_to_fetch = len(message_ids)

            # Load checkpoint to resume from where we left off
            checkpoint_path = self._get_checkpoint_path(query)
            checkpoint = self._load_checkpoint(checkpoint_path)
            fetched_ids = set(checkpoint.get("fetched_ids", []))
            emails = checkpoint.get("emails", [])

            if fetched_ids:
                logger.info(f"📂 Loaded checkpoint: {len(emails)} emails already fetched")
                print(f"📂 Resuming from checkpoint: {len(emails):,} emails already fetched")

            # Filter to only fetch emails we haven't fetched yet
            message_ids = [msg_id for msg_id in message_ids if msg_id not in fetched_ids]
            remaining_to_fetch = len(message_ids)

            if remaining_to_fetch == 0:
                logger.info(f"✓ All {total_to_fetch} emails already fetched from checkpoint!")
                print(f"✓ All emails already fetched!")
                return emails

            logger.info(f"Fetching details for {remaining_to_fetch} emails ({len(emails)} already cached)...")
            print(f"Fetching details for {remaining_to_fetch:,} new emails ({len(emails):,} already cached)...")

            if progress_callback:
                progress_callback(len(emails), total_to_fetch, f"Fetching {remaining_to_fetch:,} new emails...")

            # Fetch email details using BATCH API for 100x speed improvement!
            # Google recommends batches under 50 for reliability
            # Gmail API limit: 15,000 quota units/min, messages.get = 5 units
            # Max: 3,000 messages/min = 60 batches of 50/min = 1 batch every second
            # Using 2s delay = 30 batches/min = 1,500 emails/min (safe margin)
            batch_size = 50  # Google recommends < 50 for reliability
            batch_delay = 2.0  # 30 batches/min, well within 60 batch/min limit
            checkpoint_interval = 500  # Save checkpoint every N emails

            for batch_start in range(0, len(message_ids), batch_size):
                batch_end = min(batch_start + batch_size, len(message_ids))
                batch_ids = message_ids[batch_start:batch_end]

                # Fetch with retry logic - handles partial failures!
                max_retries = 5
                ids_to_fetch = batch_ids.copy()

                for retry in range(max_retries):
                    if not ids_to_fetch:
                        break  # All succeeded

                    # Fetch batch - returns (successful_emails, failed_ids) tuple
                    batch_emails, failed_ids_batch = self._fetch_emails_batch(ids_to_fetch)

                    # ALWAYS save successful emails immediately (even on partial failure)
                    if batch_emails:
                        emails.extend(batch_emails)
                        for email in batch_emails:
                            fetched_ids.add(email['email_id'])

                    # Only retry the failed IDs, not the entire batch!
                    if failed_ids_batch:
                        ids_to_fetch = failed_ids_batch
                        if retry < max_retries - 1:
                            # Backoff: 10s, 30s, 60s, 60s (capped)
                            wait_time = min(10.0 * (3 ** retry), 60.0)
                            logger.warning(f"Rate limit hit for {len(failed_ids_batch)} emails in batch")
                            logger.warning(f"Rate limit hit (retry {retry + 1}/{max_retries}), waiting {wait_time:.1f}s...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Max retries reached for batch {batch_start}-{batch_end}, skipping {len(ids_to_fetch)} emails")
                    else:
                        break  # All succeeded

                # Save checkpoint periodically (not every batch - too expensive for large sets)
                fetched_count = len(emails)
                if fetched_count % checkpoint_interval < batch_size:
                    self._save_checkpoint(checkpoint_path, emails, fetched_ids)
                    logger.info(f"  Checkpoint saved: {fetched_count}/{total_to_fetch} emails")

                # Progress updates
                if fetched_count % 500 == 0 or fetched_count == total_to_fetch:
                    logger.info(f"  Fetched {fetched_count}/{total_to_fetch} email details...")

                # Update UI progress every batch
                if progress_callback:
                    progress_callback(fetched_count, total_to_fetch, f"Fetched {fetched_count:,}/{total_to_fetch:,} emails")

                # Rate limiting between batches
                time.sleep(batch_delay)

            # Final checkpoint save
            self._save_checkpoint(checkpoint_path, emails, fetched_ids)

            logger.info(f"Successfully fetched {len(emails)} total emails")
            print(f"✓ Fetch complete: {len(emails):,} total emails")

            if progress_callback:
                progress_callback(len(emails), total_to_fetch, f"✓ Fetched {len(emails):,} emails!")

        except HttpError as error:
            logger.error(f"Error fetching emails: {error}", exc_info=True)
            print(f"An error occurred: {error}")

        return emails

    def _fetch_emails_batch(self, email_ids: List[str]) -> tuple:
        """
        Fetch multiple emails in a single batch request (100x faster!)

        Args:
            email_ids: List of email IDs to fetch (max 50 per batch recommended)

        Returns:
            Tuple of (successful_emails, failed_ids) - returns partial results!
        """
        from gmail_organizer.logger import logger

        emails = []
        failed_ids = []
        batch = self.service.new_batch_http_request()

        # Map request_id to email_id for tracking failures
        request_id_map = {}

        def callback(request_id, response, exception):
            """Callback for each email in the batch"""
            email_id = request_id_map.get(request_id)

            if exception is not None:
                # Track failed IDs for retry
                if email_id:
                    failed_ids.append(email_id)
                if isinstance(exception, HttpError):
                    error_str = str(exception)
                    if 'rateLimitExceeded' in error_str or 'Quota exceeded' in error_str:
                        return  # Don't log rate limit errors (too noisy)
                logger.warning(f"Error fetching email {email_id}: {exception}")
                return

            try:
                headers = response['payload'].get('headers', [])

                subject = self._get_header(headers, 'Subject')
                sender = self._get_header(headers, 'From')
                to = self._get_header(headers, 'To')
                date = self._get_header(headers, 'Date')
                body_preview = self._get_body_preview(response['payload'])

                emails.append({
                    'email_id': response['id'],
                    'subject': subject,
                    'sender': sender,
                    'to': to,
                    'date': date,
                    'snippet': response.get('snippet', ''),
                    'body_preview': body_preview,
                    'labels': response.get('labelIds', [])
                })
            except Exception as e:
                logger.warning(f"Error parsing email in batch: {e}")
                if email_id:
                    failed_ids.append(email_id)

        # Add all emails to batch request with tracking
        for i, email_id in enumerate(email_ids):
            request_id = f"req_{i}"
            request_id_map[request_id] = email_id
            batch.add(
                self.service.users().messages().get(
                    userId='me',
                    id=email_id,
                    format='full'
                ),
                callback=callback,
                request_id=request_id
            )

        # Execute batch (fetches all emails in 1 HTTP request!)
        batch.execute()

        # Return both successful emails AND failed IDs (partial results!)
        if failed_ids:
            logger.info(f"Batch: {len(emails)} succeeded, {len(failed_ids)} failed")

        return emails, failed_ids

    def _get_email_details(self, email_id: str) -> Optional[Dict]:
        """
        Get full email information including body content.

        Args:
            email_id: Gmail message ID
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()

            headers = message['payload'].get('headers', [])

            subject = self._get_header(headers, 'Subject')
            sender = self._get_header(headers, 'From')
            to = self._get_header(headers, 'To')
            date = self._get_header(headers, 'Date')
            body_preview = self._get_body_preview(message['payload'])

            return {
                'email_id': email_id,
                'subject': subject,
                'sender': sender,
                'to': to,
                'date': date,
                'snippet': message.get('snippet', ''),
                'body_preview': body_preview,
                'labels': message.get('labelIds', [])
            }

        except HttpError as error:
            print(f"Error fetching email {email_id}: {error}")
            return None

    def _get_header(self, headers: List[Dict], name: str) -> str:
        """Extract a specific header value"""
        for header in headers:
            if header['name'].lower() == name.lower():
                return header['value']
        return ""

    def _get_body_preview(self, payload: Dict, max_length=2000) -> str:
        """Extract email body text content"""
        body = ""

        # Try to get plain text body (recursively check parts)
        body = self._extract_text_from_payload(payload)

        # Clean and truncate
        body = body.replace('\r', '').strip()
        return body[:max_length]

    def _extract_text_from_payload(self, payload: Dict) -> str:
        """Recursively extract text/plain content from email payload"""
        # Direct body data
        if payload.get('mimeType') == 'text/plain' and 'data' in payload.get('body', {}):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

        # Check parts recursively
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                    return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                # Recurse into multipart
                if 'parts' in part:
                    result = self._extract_text_from_payload(part)
                    if result:
                        return result

        # Fallback: try body directly
        if 'body' in payload and 'data' in payload.get('body', {}):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

        return ""

    def get_or_create_label(self, label_name: str, color: str = None) -> str:
        """
        Get existing label ID or create new label

        Args:
            label_name: Name of the label (e.g., "Job/Applications")
            color: Optional hex color code

        Returns:
            Label ID
        """
        # Refresh labels cache
        self._refresh_labels_cache()

        # Check if label exists
        for label in self.labels_cache:
            if label['name'] == label_name:
                return label['id']

        # Create new label
        print(f"Creating label: {label_name}")

        label_object = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }

        if color:
            # Gmail uses predefined color IDs, map hex to closest
            label_object['color'] = self._get_gmail_color(color)

        try:
            result = self.service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()

            # Refresh cache
            self.labels_cache = None

            return result['id']

        except HttpError as error:
            print(f"Error creating label '{label_name}': {error}")
            return None

    def _refresh_labels_cache(self):
        """Refresh the labels cache"""
        if self.labels_cache is None:
            try:
                results = self.service.users().labels().list(userId='me').execute()
                self.labels_cache = results.get('labels', [])
            except HttpError as error:
                print(f"Error fetching labels: {error}")
                self.labels_cache = []

    def _get_gmail_color(self, hex_color: str) -> Dict:
        """
        Map hex color to Gmail's color system
        Gmail uses predefined background and text colors
        """
        # Simplified mapping - Gmail has specific color palette
        color_map = {
            "#fb4c2f": {"backgroundColor": "#fb4c2f", "textColor": "#ffffff"},  # Red
            "#fad165": {"backgroundColor": "#fad165", "textColor": "#000000"},  # Yellow
            "#16a766": {"backgroundColor": "#16a766", "textColor": "#ffffff"},  # Green
            "#7bd148": {"backgroundColor": "#7bd148", "textColor": "#ffffff"},  # Bright green
            "#b99aff": {"backgroundColor": "#b99aff", "textColor": "#000000"},  # Purple
            "#ff7537": {"backgroundColor": "#ff7537", "textColor": "#ffffff"},  # Orange
        }

        return color_map.get(hex_color, {"backgroundColor": "#cccccc", "textColor": "#000000"})

    def apply_label_to_email(self, email_id: str, label_id: str):
        """Apply a label to an email"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            return True
        except HttpError as error:
            print(f"Error applying label to email {email_id}: {error}")
            return False

    def create_filter(self, category_key: str, label_id: str):
        """
        Create Gmail filter for automatic categorization

        Args:
            category_key: The category key (e.g., "applications")
            label_id: The label ID to apply
        """
        # This is a simplified version
        # In practice, you'd need to analyze patterns and create specific filters
        print(f"Note: Automatic filter creation for '{category_key}' requires pattern analysis")
        print(f"  You can manually create filters in Gmail settings for label: {label_id}")

    def create_all_labels(self) -> Dict[str, str]:
        """
        Create all predefined labels

        Returns:
            Dict mapping category_key to label_id
        """
        label_map = {}

        print("\nCreating Gmail labels...")

        for group_name, group in CATEGORIES.items():
            for category_key, category_info in group.items():
                label_name = category_info['name']
                color = category_info.get('color')

                label_id = self.get_or_create_label(label_name, color)
                if label_id:
                    label_map[category_key] = label_id
                    print(f"  ✓ {label_name}")

        return label_map

    def get_email_count(self, query="") -> int:
        """
        Get count of emails matching query.
        For empty query (all mail), uses Gmail profile API for accurate total.
        For specific queries, uses resultSizeEstimate (approximate).
        """
        from gmail_organizer.logger import logger

        try:
            # For all mail (empty query), use profile API for accurate count
            if not query or query.strip() == "":
                try:
                    profile = self.service.users().getProfile(userId='me').execute()
                    total_messages = profile.get('messagesTotal', 0)
                    logger.info(f"Gmail profile API: Total messages = {total_messages}")
                    return total_messages
                except HttpError as api_error:
                    logger.warning(f"Profile API failed (using estimate fallback): {api_error}")
                    # Fall through to use messages.list instead
                except Exception as e:
                    logger.warning(f"Profile API error (using estimate fallback): {e}")
                    # Fall through to use messages.list instead

            # For specific queries, use messages.list with resultSizeEstimate
            try:
                results = self.service.users().messages().list(
                    userId='me',
                    q=query if query else None,
                    maxResults=1
                ).execute()

                count = results.get('resultSizeEstimate', 0)
                logger.debug(f"Gmail API resultSizeEstimate for query '{query}': {count}")
                return count

            except HttpError as api_error:
                logger.error(f"Messages list API failed: {api_error}")
                return 0

        except Exception as error:
            logger.error(f"Unexpected error counting emails: {error}", exc_info=True)
            return 0


if __name__ == "__main__":
    from gmail_organizer.auth import GmailAuthManager

    # Test Gmail operations
    auth_manager = GmailAuthManager()
    accounts = auth_manager.list_authenticated_accounts()

    if not accounts:
        print("No accounts authenticated. Run gmail_auth.py first.")
    else:
        account_name, email = accounts[0]
        service, _, _ = auth_manager.authenticate_account(account_name)

        ops = GmailOperations(service, email)

        print(f"\nTesting Gmail Operations for: {email}")
        print(f"Inbox email count: {ops.get_email_count('in:inbox')}")

        print("\nFetching 5 emails...")
        emails = ops.fetch_emails(max_results=5)

        for email in emails:
            print(f"\n- {email['subject'][:60]}")
            print(f"  From: {email['sender'][:40]}")
