"""Gmail API operations for fetching and organizing emails"""

import base64
from typing import List, Dict, Optional
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
from config import CATEGORIES, BATCH_SIZE


class GmailOperations:
    """Handle Gmail operations like fetching emails, creating labels, and filters"""

    def __init__(self, service, account_email):
        self.service = service
        self.account_email = account_email
        self.labels_cache = None

    def fetch_emails(self, max_results=100, query="in:inbox") -> List[Dict]:
        """
        Fetch emails from Gmail with pagination support

        Args:
            max_results: Maximum number of emails to fetch (no limit if set high)
            query: Gmail search query (e.g., "in:inbox", "is:unread")

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

                # Check if there are more pages
                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            if not message_ids:
                logger.warning(f"No messages found for query: {query}")
                print(f"No messages found for query: {query}")
                return []

            logger.info(f"Fetching details for {len(message_ids)} emails...")
            print(f"Fetching details for {len(message_ids)} emails...")

            # Now fetch email details in batches using batch API
            batch_size = 100  # Process 100 emails per batch
            for i in range(0, len(message_ids), batch_size):
                batch_ids = message_ids[i:i + batch_size]

                for email_id in batch_ids:
                    email_data = self._get_email_details(email_id)
                    if email_data:
                        emails.append(email_data)

                if (i + batch_size) % 500 == 0 or i + batch_size >= len(message_ids):
                    logger.info(f"  Fetched {min(i + batch_size, len(message_ids))}/{len(message_ids)} email details...")
                    print(f"  Fetched {min(i + batch_size, len(message_ids))}/{len(message_ids)} emails...")

            logger.info(f"Successfully fetched {len(emails)} emails")

        except HttpError as error:
            logger.error(f"Error fetching emails: {error}", exc_info=True)
            print(f"An error occurred: {error}")

        return emails

    def _get_email_details(self, email_id: str) -> Optional[Dict]:
        """Get detailed information about a single email"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()

            headers = message['payload'].get('headers', [])

            # Extract key information
            subject = self._get_header(headers, 'Subject')
            sender = self._get_header(headers, 'From')
            date = self._get_header(headers, 'Date')

            # Get email body preview
            body_preview = self._get_body_preview(message['payload'])

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
