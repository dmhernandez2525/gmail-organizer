"""Shared fixtures for gmail-organizer tests."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def fake_creds_data():
    """Return a dict representing stored credential fields."""
    return {
        "token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake-client-id.apps.googleusercontent.com",
        "client_secret": "fake-client-secret",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.settings.basic",
        ],
    }


@pytest.fixture
def token_json_file(tmp_path, fake_creds_data):
    """Write a valid token JSON file and return its Path."""
    token_path = tmp_path / "credentials" / "token_testuser.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w") as f:
        json.dump(fake_creds_data, f)
    return token_path


@pytest.fixture
def mock_credentials(fake_creds_data):
    """Return a MagicMock that behaves like google.oauth2.credentials.Credentials."""
    creds = MagicMock()
    creds.token = fake_creds_data["token"]
    creds.refresh_token = fake_creds_data["refresh_token"]
    creds.token_uri = fake_creds_data["token_uri"]
    creds.client_id = fake_creds_data["client_id"]
    creds.client_secret = fake_creds_data["client_secret"]
    creds.scopes = fake_creds_data["scopes"]
    creds.valid = True
    creds.expired = False
    return creds


@pytest.fixture
def mock_gmail_service():
    """Return a MagicMock mimicking the Gmail API service object."""
    service = MagicMock()
    profile_response = {"emailAddress": "testuser@gmail.com"}
    service.users.return_value.getProfile.return_value.execute.return_value = (
        profile_response
    )
    return service


@pytest.fixture
def client_secret_file(tmp_path):
    """Create a minimal client_secret.json and return its path."""
    secret_path = tmp_path / "client_secret.json"
    secret_data = {
        "installed": {
            "client_id": "fake-client-id",
            "client_secret": "fake-client-secret",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
        }
    }
    with open(secret_path, "w") as f:
        json.dump(secret_data, f)
    return secret_path
