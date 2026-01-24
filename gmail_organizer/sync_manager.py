"""Thread-safe sync manager for parallel multi-account Gmail syncing"""

import threading
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class SyncStatus:
    """Status of a sync operation for one account"""
    state: str = "idle"  # idle | syncing | complete | error
    progress: int = 0
    total: int = 0
    message: str = ""
    emails_data: List[Dict] = field(default_factory=list)
    error: str = ""
    last_sync_time: str = ""


class SyncManager:
    """Thread-safe manager for parallel account syncing"""

    def __init__(self):
        self._statuses: Dict[str, SyncStatus] = {}
        self._lock = threading.Lock()
        self._services: Dict[str, Tuple] = {}  # name -> (service, email)
        self._sync_state_dir = Path(__file__).parent.parent / ".sync-state"
        self._sync_state_dir.mkdir(exist_ok=True)

    def register_account(self, name: str, service, email: str):
        """Register an account for syncing"""
        with self._lock:
            self._services[name] = (service, email)
            if name not in self._statuses:
                self._statuses[name] = SyncStatus()
                # Try to load existing data from disk
                emails = self._load_from_disk(email)
                if emails:
                    self._statuses[name].emails_data = emails
                    self._statuses[name].state = "complete"
                    self._statuses[name].message = f"{len(emails):,} emails loaded from disk"
                    # Load last sync time from sync state file
                    sync_path = self._get_sync_state_path(email)
                    if sync_path.exists():
                        try:
                            with open(sync_path, 'r') as f:
                                state = json.load(f)
                                self._statuses[name].last_sync_time = state.get("last_sync_time", "")
                        except Exception:
                            pass

    def start_sync(self, account_name: str, query: str = ""):
        """Launch a background sync thread for one account"""
        with self._lock:
            if account_name not in self._services:
                return
            if self._statuses[account_name].state == "syncing":
                return  # Already syncing
            # Preserve existing emails_data during sync
            existing = self._statuses[account_name]
            existing.state = "syncing"
            existing.message = "Starting sync..."
            existing.progress = 0
            existing.total = 0
            existing.error = ""

        service, email = self._services[account_name]
        thread = threading.Thread(
            target=self._sync_worker,
            args=(account_name, service, email, query),
            daemon=True
        )
        thread.start()

    def start_all_syncs(self, query: str = ""):
        """Launch sync threads for all registered accounts in parallel"""
        with self._lock:
            accounts = list(self._services.keys())
        for name in accounts:
            self.start_sync(name, query)

    def get_status(self, account_name: str) -> SyncStatus:
        """Thread-safe status read for one account"""
        with self._lock:
            return self._statuses.get(account_name, SyncStatus())

    def get_all_statuses(self) -> Dict[str, SyncStatus]:
        """Get all account statuses"""
        with self._lock:
            return dict(self._statuses)

    def is_any_syncing(self) -> bool:
        """Check if any account is currently syncing"""
        with self._lock:
            return any(s.state == "syncing" for s in self._statuses.values())

    def get_emails(self, account_name: str) -> List[Dict]:
        """Get emails for an account from memory or disk fallback"""
        with self._lock:
            status = self._statuses.get(account_name)
            if status and status.emails_data:
                return list(status.emails_data)

        # Fallback: load from disk
        if account_name in self._services:
            _, email = self._services[account_name]
            emails = self._load_from_disk(email)
            if emails:
                with self._lock:
                    if account_name in self._statuses:
                        self._statuses[account_name].emails_data = emails
            return emails
        return []

    def _sync_worker(self, name: str, service, email: str, query: str):
        """Background thread function that performs the actual sync"""
        from gmail_organizer.operations import GmailOperations

        try:
            ops = GmailOperations(service, email)

            def progress_callback(current, total, message):
                with self._lock:
                    status = self._statuses.get(name)
                    if status:
                        status.progress = current
                        status.total = total
                        status.message = message

            emails = ops.sync_emails(query=query, progress_callback=progress_callback)

            with self._lock:
                status = self._statuses.get(name)
                if status:
                    status.state = "complete"
                    status.emails_data = emails
                    status.progress = len(emails)
                    status.total = len(emails)
                    status.message = f"Synced {len(emails):,} emails"
                    status.last_sync_time = datetime.now().isoformat()

        except Exception as e:
            with self._lock:
                status = self._statuses.get(name)
                if status:
                    status.state = "error"
                    status.error = str(e)
                    status.message = f"Error: {e}"

    def _get_sync_state_path(self, email: str) -> Path:
        """Get sync state file path for an account email"""
        safe_email = email.replace('@', '_at_').replace('.', '_')
        return self._sync_state_dir / f"sync_state_{safe_email}.json"

    def _load_from_disk(self, email: str) -> List[Dict]:
        """Load emails from .sync-state/ files on disk.

        Also checks the checkpoint directory - if it has more emails
        (e.g., from an interrupted sync), merges them into the result.
        """
        from gmail_organizer.logger import logger

        emails_dict = {}
        sync_path = self._get_sync_state_path(email)
        state = {}

        if sync_path.exists():
            try:
                with open(sync_path, 'r') as f:
                    state = json.load(f)
                    emails_dict = state.get("emails", {})
            except Exception:
                pass

        # Check checkpoint for more data (handles interrupted syncs)
        safe_email = email.replace('@', '_at_').replace('.', '_')
        checkpoint_dir = Path(__file__).parent.parent / ".email-cache" / f"{safe_email}_all"
        index_file = checkpoint_dir / "index.json"

        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    checkpoint_count = len(json.load(f))

                if checkpoint_count > len(emails_dict):
                    logger.info(
                        f"Checkpoint has {checkpoint_count} emails vs sync state "
                        f"{len(emails_dict)} for {email}, recovering..."
                    )
                    # Load checkpoint batch files
                    batch_files = sorted(checkpoint_dir.glob("batch_*.jsonl"))
                    checkpoint_emails = []
                    for batch_file in batch_files:
                        with open(batch_file, 'r') as f:
                            for line in f:
                                try:
                                    checkpoint_emails.append(json.loads(line))
                                except Exception:
                                    continue

                    # Merge: sync state + checkpoint data
                    merged = dict(emails_dict)
                    for em in checkpoint_emails:
                        email_id = em.get("email_id", "")
                        if email_id:
                            merged[email_id] = em
                    emails_dict = merged

                    # Save merged state to avoid re-merging next time
                    try:
                        save_state = {
                            "history_id": state.get("history_id") or "",
                            "last_sync_time": state.get("last_sync_time") or datetime.now().isoformat(),
                            "emails": emails_dict,
                            "total_synced": len(emails_dict)
                        }
                        with open(sync_path, 'w') as f:
                            json.dump(save_state, f)
                        logger.info(f"Saved merged sync state: {len(emails_dict)} emails for {email}")
                    except Exception as e:
                        logger.warning(f"Could not save merged state: {e}")
            except Exception:
                pass

        if emails_dict:
            return list(emails_dict.values())
        return []
