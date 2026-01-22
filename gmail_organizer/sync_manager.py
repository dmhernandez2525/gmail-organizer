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
            self._statuses[account_name] = SyncStatus(state="syncing", message="Starting sync...")

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
        """Load emails from .sync-state/ files on disk"""
        sync_path = self._get_sync_state_path(email)
        if sync_path.exists():
            try:
                with open(sync_path, 'r') as f:
                    state = json.load(f)
                    emails_dict = state.get("emails", {})
                    if emails_dict:
                        return list(emails_dict.values())
            except Exception:
                pass
        return []
