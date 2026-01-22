"""Gmail API Authentication Module"""

import os
import json
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .config import SCOPES, CREDENTIALS_DIR, TOKEN_PREFIX


class GmailAuthManager:
    """Manages authentication for multiple Gmail accounts"""

    def __init__(self, client_secret_path="client_secret.json"):
        self.client_secret_path = client_secret_path
        self.credentials_dir = Path(CREDENTIALS_DIR)
        self.credentials_dir.mkdir(exist_ok=True)
        self.authenticated_accounts = {}

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
            token_path = self.credentials_dir / f"{TOKEN_PREFIX}{account_name}.pickle"
            if token_path.exists():
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)

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

                # Save credentials
                token_path = self.credentials_dir / f"{TOKEN_PREFIX}{account_name}.pickle"
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)

                print(f"✓ Authenticated: {email} (saved as '{account_name}')")

                return service, email, account_name

        # Build service with existing credentials
        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        email = profile['emailAddress']

        print(f"✓ Loaded credentials for: {email}")

        return service, email, account_name

    def load_all_accounts(self):
        """
        Load all previously authenticated accounts

        Returns:
            dict: {account_name: (service, email)}
        """
        accounts = {}

        for token_file in self.credentials_dir.glob(f"{TOKEN_PREFIX}*.pickle"):
            account_name = token_file.stem.replace(TOKEN_PREFIX, '')
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

        for token_file in self.credentials_dir.glob(f"{TOKEN_PREFIX}*.pickle"):
            account_name = token_file.stem.replace(TOKEN_PREFIX, '')
            try:
                with open(token_file, 'rb') as f:
                    creds = pickle.load(f)
                    service = build('gmail', 'v1', credentials=creds)
                    profile = service.users().getProfile(userId='me').execute()
                    email = profile['emailAddress']
                    accounts.append((account_name, email))
            except Exception as e:
                print(f"Error reading account '{account_name}': {e}")

        return accounts

    def remove_account(self, account_name):
        """Remove an authenticated account"""
        token_path = self.credentials_dir / f"{TOKEN_PREFIX}{account_name}.pickle"
        if token_path.exists():
            token_path.unlink()
            print(f"✓ Removed account: {account_name}")
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
