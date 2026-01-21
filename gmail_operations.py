"""Gmail API operations for fetching and organizing emails"""

import base64
from typing import List, Dict, Optional
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest
from email.mime.text import MIMEText
from config import CATEGORIES, BATCH_SIZE
import time


class GmailOperations:
    """Handle Gmail operations like fetching emails, creating labels, and filters"""

    def __init__(self, service, account_email):
        self.service = service
        self.account_email = account_email
        self.labels_cache = None

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
        from logger import logger

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
            logger.info(f"Fetching details for {total_to_fetch} emails...")
            print(f"Fetching details for {total_to_fetch} emails...")

            if progress_callback:
                progress_callback(0, total_to_fetch, f"Fetching details for {total_to_fetch:,} emails...")

            # Fetch email details using BATCH API for 100x speed improvement!
            # Process in batches of 100 (Gmail API limit per batch request)
            # Gmail API limit: 15,000 quota units/min, messages.get = 5 units
            # Max: 3,000 messages/min = 30 batches/min = 1 batch every 2 seconds
            batch_size = 100
            retry_delay = 2.5  # Start with 2.5 seconds between batches

            for batch_start in range(0, len(message_ids), batch_size):
                batch_end = min(batch_start + batch_size, len(message_ids))
                batch_ids = message_ids[batch_start:batch_end]

                # Fetch this batch with retry logic for rate limits
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        batch_emails = self._fetch_emails_batch(batch_ids)
                        emails.extend(batch_emails)
                        break  # Success, exit retry loop
                    except HttpError as e:
                        if 'rateLimitExceeded' in str(e) or 'Quota exceeded' in str(e):
                            if retry < max_retries - 1:
                                wait_time = retry_delay * (2 ** retry)  # Exponential backoff
                                logger.warning(f"Rate limit hit, waiting {wait_time:.1f}s before retry...")
                                time.sleep(wait_time)
                            else:
                                logger.error(f"Max retries reached for batch, some emails may be missing")
                        else:
                            raise  # Re-raise non-rate-limit errors

                # Progress updates
                fetched_count = batch_end
                if fetched_count % 500 == 0 or fetched_count == total_to_fetch:
                    logger.info(f"  Fetched {fetched_count}/{total_to_fetch} email details...")
                    print(f"  Fetched {fetched_count}/{total_to_fetch} emails...")

                # Update UI progress every batch
                if progress_callback:
                    progress_callback(fetched_count, total_to_fetch, f"Fetched {fetched_count:,}/{total_to_fetch:,} emails")

                # Rate limiting: 2.5 seconds between batches (30 batches/min max)
                time.sleep(retry_delay)

            logger.info(f"Successfully fetched {len(emails)} emails")

            if progress_callback:
                progress_callback(len(emails), len(emails), f"✓ Fetched {len(emails):,} emails!")

        except HttpError as error:
            logger.error(f"Error fetching emails: {error}", exc_info=True)
            print(f"An error occurred: {error}")

        return emails

    def _fetch_emails_batch(self, email_ids: List[str]) -> List[Dict]:
        """
        Fetch multiple emails in a single batch request (100x faster!)

        Args:
            email_ids: List of email IDs to fetch (max 100 per batch)

        Returns:
            List of email dictionaries

        Raises:
            HttpError: If rate limit is exceeded, will be caught and retried by caller
        """
        from logger import logger

        emails = []
        rate_limit_errors = []
        batch = self.service.new_batch_http_request()

        def callback(request_id, response, exception):
            """Callback for each email in the batch"""
            if exception is not None:
                # Check if it's a rate limit error
                if isinstance(exception, HttpError):
                    error_str = str(exception)
                    if 'rateLimitExceeded' in error_str or 'Quota exceeded' in error_str:
                        rate_limit_errors.append(exception)
                        return
                logger.warning(f"Error fetching email in batch: {exception}")
                return

            try:
                headers = response['payload'].get('headers', [])

                subject = self._get_header(headers, 'Subject')
                sender = self._get_header(headers, 'From')
                date = self._get_header(headers, 'Date')

                emails.append({
                    'email_id': response['id'],
                    'subject': subject,
                    'sender': sender,
                    'date': date,
                    'body_preview': "",  # Not needed for classification
                    'labels': response.get('labelIds', [])
                })
            except Exception as e:
                logger.warning(f"Error parsing email in batch: {e}")

        # Add all emails to batch request
        for email_id in email_ids:
            batch.add(
                self.service.users().messages().get(
                    userId='me',
                    id=email_id,
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'To', 'Date']
                ),
                callback=callback
            )

        # Execute batch (fetches all emails in 1 HTTP request!)
        batch.execute()

        # If we hit rate limits, raise the error so the caller can retry
        if rate_limit_errors:
            logger.warning(f"Rate limit hit for {len(rate_limit_errors)} emails in batch")
            raise rate_limit_errors[0]  # Raise first rate limit error to trigger retry

        return emails

    def _get_email_details(self, email_id: str, metadata_only: bool = True) -> Optional[Dict]:
        """
        Get email information

        Args:
            email_id: Gmail message ID
            metadata_only: If True, only fetch headers (MUCH faster, no body)
        """
        try:
            # Use 'metadata' format for just headers (10x faster than 'full')
            # Only fetch subject, from, to, date headers
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='metadata',
                metadataHeaders=['Subject', 'From', 'To', 'Date']
            ).execute()

            headers = message['payload'].get('headers', [])

            # Extract key information
            subject = self._get_header(headers, 'Subject')
            sender = self._get_header(headers, 'From')
            date = self._get_header(headers, 'Date')

            # No body needed for classification - saves tons of time
            body_preview = ""

            return {
                'email_id': email_id,
                'subject': subject,
                'sender': sender,
                'date': date,
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

    def _get_body_preview(self, payload: Dict, max_length=500) -> str:
        """Extract email body preview"""
        body = ""

        # Try to get plain text body
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
        elif 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

        # Clean and truncate
        body = body.replace('\n', ' ').replace('\r', ' ').strip()
        return body[:max_length]

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
        from logger import logger

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
    from gmail_auth import GmailAuthManager

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
