"""Gmail API Authentication Module"""

import os
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .config import SCOPES, CREDENTIALS_DIR, TOKEN_PREFIX


def _load_credentials_json(token_path: Path) -> Credentials:
    """Load credentials from a JSON token file (safe alternative to pickle)."""
    with open(token_path, 'r') as f:
        data = json.load(f)
    return Credentials(
        token=data.get('token'),
        refresh_token=data.get('refresh_token'),
        token_uri=data.get('token_uri'),
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        scopes=data.get('scopes'),
    )


def _save_credentials_json(creds: Credentials, token_path: Path):
    """Save credentials to a JSON token file (safe alternative to pickle)."""
    data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
    }
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, 'w') as f:
        json.dump(data, f, indent=2)
    # Restrict file permissions to owner only
    os.chmod(token_path, 0o600)


def _migrate_pickle_to_json(pickle_path: Path) -> Path:
    """Migrate a legacy .pickle token to .json format, then remove the pickle."""
    import pickle
    json_path = pickle_path.with_suffix('.json')
    if json_path.exists():
        return json_path
    try:
        with open(pickle_path, 'rb') as f:
            creds = pickle.load(f)  # noqa: S301 - one-time migration only
        _save_credentials_json(creds, json_path)
        # Verify JSON was written successfully before deleting pickle
        if json_path.exists() and json_path.stat().st_size > 0:
            pickle_path.unlink()
        return json_path
    except Exception as e:
        # If migration fails, keep the pickle and raise so caller can handle
        if json_path.exists():
            json_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to migrate token {pickle_path.name}: {e}") from e


class GmailAuthManager:
    """Manages authentication for multiple Gmail accounts"""

    def __init__(self, client_secret_path="client_secret.json"):
        self.client_secret_path = client_secret_path
        self.credentials_dir = Path(CREDENTIALS_DIR)
        self.credentials_dir.mkdir(exist_ok=True)
        self.authenticated_accounts = {}

    def _get_token_path(self, account_name: str) -> Path:
        """Get the JSON token path for an account, migrating from pickle if needed."""
        json_path = self.credentials_dir / f"{TOKEN_PREFIX}{account_name}.json"
        if json_path.exists():
            return json_path
        pickle_path = self.credentials_dir / f"{TOKEN_PREFIX}{account_name}.pickle"
        if pickle_path.exists():
            return _migrate_pickle_to_json(pickle_path)
        return json_path

    def _iter_token_files(self):
        """Iterate over all token files, migrating pickles to JSON on the fly."""
        for token_file in self.credentials_dir.glob(f"{TOKEN_PREFIX}*.json"):
            account_name = token_file.stem.replace(TOKEN_PREFIX, '')
            yield account_name, token_file
        for pickle_file in self.credentials_dir.glob(f"{TOKEN_PREFIX}*.pickle"):
            account_name = pickle_file.stem.replace(TOKEN_PREFIX, '')
            json_path = _migrate_pickle_to_json(pickle_file)
            yield account_name, json_path

    def authenticate_account(self, account_name=None):
        """
        Authenticate a Gmail account using OAuth 2.0

        Args:
            account_name: Optional name to identify this account

        Returns:
            tuple: (service, account_email, account_name)
        """
        if not os.path.exists(self.client_secret_path):
            raise FileNotFoundError(
                f"Client secret file not found at {self.client_secret_path}\n"
                "Please download credentials from Google Cloud Console."
            )

        creds = None
        token_path = None

        # If account_name provided, try to load existing token
        if account_name:
            token_path = self._get_token_path(account_name)
            if token_path.exists():
                creds = _load_credentials_json(token_path)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}. Re-authenticating...")
                    creds = None

            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

                # Get email address for this account
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                email = profile['emailAddress']

                # If no account_name provided, use email
                if not account_name:
                    account_name = email.split('@')[0]

                # Save credentials as JSON (not pickle)
                token_path = self._get_token_path(account_name)
                _save_credentials_json(creds, token_path)

                print(f"Authenticated: {email} (saved as '{account_name}')")

                return service, email, account_name

        # Build service with existing credentials
        try:
            service = build('gmail', 'v1', credentials=creds)
            profile = service.users().getProfile(userId='me').execute()
            email = profile['emailAddress']
        except HttpError as e:
            raise RuntimeError(f"Gmail API error for account '{account_name}': {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Gmail for account '{account_name}': {e}") from e

        print(f"Loaded credentials for: {email}")

        return service, email, account_name

    def load_all_accounts(self):
        """
        Load all previously authenticated accounts

        Returns:
            dict: {account_name: (service, email)}
        """
        accounts = {}

        for account_name, _ in self._iter_token_files():
            try:
                service, email, _ = self.authenticate_account(account_name)
                accounts[account_name] = (service, email)
            except Exception as e:
                print(f"Failed to load account '{account_name}': {e}")

        return accounts

    def list_authenticated_accounts(self):
        """
        List all authenticated accounts

        Returns:
            list: [(account_name, email), ...]
        """
        accounts = []

        for account_name, token_file in self._iter_token_files():
            try:
                creds = _load_credentials_json(token_file)
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                email = profile['emailAddress']
                accounts.append((account_name, email))
            except Exception as e:
                print(f"Error reading account '{account_name}': {e}")

        return accounts

    def remove_account(self, account_name):
        """Remove an authenticated account"""
        token_path = self._get_token_path(account_name)
        if token_path.exists():
            token_path.unlink()
            print(f"Removed account: {account_name}")
            return True
        return False


if __name__ == "__main__":
    # Test authentication
    auth_manager = GmailAuthManager()

    print("Available accounts:")
    accounts = auth_manager.list_authenticated_accounts()

    if accounts:
        for name, email in accounts:
            print(f"  - {name}: {email}")
    else:
        print("  No accounts authenticated yet.")
        print("\nAuthenticating new account...")
        auth_manager.authenticate_account()
