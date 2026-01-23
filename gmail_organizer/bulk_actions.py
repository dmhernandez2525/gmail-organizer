"""Bulk Actions Engine - batch Gmail operations with progress tracking"""

import re
from typing import Dict, List, Optional, Callable, Tuple
from googleapiclient.errors import HttpError


class BulkActionEngine:
    """Execute batch Gmail operations with progress tracking"""

    BATCH_SIZE = 50  # Gmail API recommended batch size

    def __init__(self, service=None):
        self.service = service

    def apply_label(self, message_ids: List[str], label_id: str,
                    progress_callback: Optional[Callable] = None) -> Dict:
        """Add a label to multiple messages"""
        return self._batch_modify(
            message_ids, add_labels=[label_id],
            progress_callback=progress_callback
        )

    def remove_label(self, message_ids: List[str], label_id: str,
                     progress_callback: Optional[Callable] = None) -> Dict:
        """Remove a label from multiple messages"""
        return self._batch_modify(
            message_ids, remove_labels=[label_id],
            progress_callback=progress_callback
        )

    def archive(self, message_ids: List[str],
                progress_callback: Optional[Callable] = None) -> Dict:
        """Archive messages (remove INBOX label)"""
        return self._batch_modify(
            message_ids, remove_labels=['INBOX'],
            progress_callback=progress_callback
        )

    def unarchive(self, message_ids: List[str],
                  progress_callback: Optional[Callable] = None) -> Dict:
        """Move messages back to inbox"""
        return self._batch_modify(
            message_ids, add_labels=['INBOX'],
            progress_callback=progress_callback
        )

    def mark_read(self, message_ids: List[str],
                  progress_callback: Optional[Callable] = None) -> Dict:
        """Mark messages as read"""
        return self._batch_modify(
            message_ids, remove_labels=['UNREAD'],
            progress_callback=progress_callback
        )

    def mark_unread(self, message_ids: List[str],
                    progress_callback: Optional[Callable] = None) -> Dict:
        """Mark messages as unread"""
        return self._batch_modify(
            message_ids, add_labels=['UNREAD'],
            progress_callback=progress_callback
        )

    def star(self, message_ids: List[str],
             progress_callback: Optional[Callable] = None) -> Dict:
        """Star messages"""
        return self._batch_modify(
            message_ids, add_labels=['STARRED'],
            progress_callback=progress_callback
        )

    def unstar(self, message_ids: List[str],
               progress_callback: Optional[Callable] = None) -> Dict:
        """Unstar messages"""
        return self._batch_modify(
            message_ids, remove_labels=['STARRED'],
            progress_callback=progress_callback
        )

    def mark_important(self, message_ids: List[str],
                       progress_callback: Optional[Callable] = None) -> Dict:
        """Mark messages as important"""
        return self._batch_modify(
            message_ids, add_labels=['IMPORTANT'],
            progress_callback=progress_callback
        )

    def mark_not_important(self, message_ids: List[str],
                           progress_callback: Optional[Callable] = None) -> Dict:
        """Mark messages as not important"""
        return self._batch_modify(
            message_ids, remove_labels=['IMPORTANT'],
            progress_callback=progress_callback
        )

    def move_to_trash(self, message_ids: List[str],
                      progress_callback: Optional[Callable] = None) -> Dict:
        """Move messages to trash"""
        return self._batch_modify(
            message_ids, add_labels=['TRASH'], remove_labels=['INBOX'],
            progress_callback=progress_callback
        )

    def mark_spam(self, message_ids: List[str],
                  progress_callback: Optional[Callable] = None) -> Dict:
        """Mark messages as spam"""
        return self._batch_modify(
            message_ids, add_labels=['SPAM'], remove_labels=['INBOX'],
            progress_callback=progress_callback
        )

    def _batch_modify(self, message_ids: List[str],
                      add_labels: List[str] = None,
                      remove_labels: List[str] = None,
                      progress_callback: Optional[Callable] = None) -> Dict:
        """
        Execute batch modify operation using Gmail API batchModify.

        Args:
            message_ids: List of Gmail message IDs
            add_labels: Labels to add
            remove_labels: Labels to remove
            progress_callback: Called with (processed, total) for progress updates

        Returns:
            Dict with 'success', 'failed', 'total' counts
        """
        if not self.service:
            return {'success': 0, 'failed': len(message_ids), 'total': len(message_ids),
                    'error': 'No Gmail service available'}

        result = {'success': 0, 'failed': 0, 'total': len(message_ids), 'errors': []}

        # Process in batches of 1000 (Gmail API limit for batchModify)
        batch_limit = 1000
        for i in range(0, len(message_ids), batch_limit):
            batch = message_ids[i:i + batch_limit]

            body = {'ids': batch}
            if add_labels:
                body['addLabelIds'] = add_labels
            if remove_labels:
                body['removeLabelIds'] = remove_labels

            try:
                self.service.users().messages().batchModify(
                    userId='me', body=body
                ).execute()
                result['success'] += len(batch)
            except HttpError as e:
                result['failed'] += len(batch)
                result['errors'].append(str(e))

            if progress_callback:
                progress_callback(min(i + batch_limit, len(message_ids)),
                                  len(message_ids))

        return result

    def get_or_create_label(self, label_name: str) -> Optional[str]:
        """Get label ID by name, creating it if needed"""
        if not self.service:
            return None

        try:
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

            for label in labels:
                if label['name'].lower() == label_name.lower():
                    return label['id']

            # Create new label
            label_body = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            created = self.service.users().labels().create(
                userId='me', body=label_body
            ).execute()
            return created['id']
        except HttpError as e:
            return None

    def list_labels(self) -> List[Dict]:
        """List all Gmail labels"""
        if not self.service:
            return []

        try:
            results = self.service.users().labels().list(userId='me').execute()
            return results.get('labels', [])
        except HttpError:
            return []


def filter_emails(emails: List[Dict],
                  sender_filter: str = "",
                  category_filter: str = "",
                  label_filter: str = "",
                  subject_filter: str = "",
                  date_from: str = "",
                  date_to: str = "",
                  has_attachment: Optional[bool] = None,
                  is_unread: Optional[bool] = None) -> List[Dict]:
    """
    Filter emails by multiple criteria.

    Args:
        emails: List of email dicts
        sender_filter: Substring match on sender
        category_filter: Exact match on category
        label_filter: Must have this label
        subject_filter: Substring match on subject
        date_from: YYYY-MM-DD start date
        date_to: YYYY-MM-DD end date
        has_attachment: Filter by attachment presence
        is_unread: Filter by read/unread status

    Returns:
        Filtered list of emails
    """
    results = emails

    if sender_filter:
        sender_lower = sender_filter.lower()
        results = [e for e in results
                   if sender_lower in e.get('sender', '').lower()]

    if category_filter:
        results = [e for e in results
                   if e.get('category', '') == category_filter]

    if label_filter:
        results = [e for e in results
                   if label_filter in e.get('labels', [])]

    if subject_filter:
        subject_lower = subject_filter.lower()
        results = [e for e in results
                   if subject_lower in e.get('subject', '').lower()]

    if date_from:
        results = [e for e in results
                   if e.get('date', '')[:10] >= date_from]

    if date_to:
        results = [e for e in results
                   if e.get('date', '')[:10] <= date_to]

    if has_attachment is not None:
        results = [e for e in results
                   if bool(e.get('has_attachment', False)) == has_attachment]

    if is_unread is not None:
        results = [e for e in results
                   if ('UNREAD' in e.get('labels', [])) == is_unread]

    return results
