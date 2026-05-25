"""Tests for gmail_organizer.auth module."""

import json
import os
import pickle
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from gmail_organizer.auth import (
    _load_credentials_json,
    _save_credentials_json,
    _migrate_pickle_to_json,
    GmailAuthManager,
)


# ---------------------------------------------------------------------------
# _load_credentials_json
# ---------------------------------------------------------------------------

class TestLoadCredentialsJson:
    """Tests for _load_credentials_json."""

    def test_loads_all_fields(self, token_json_file, fake_creds_data):
        """All credential fields should be populated from the JSON file."""
        with patch("gmail_organizer.auth.Credentials") as MockCreds:
            instance = MagicMock()
            MockCreds.return_value = instance

            _load_credentials_json(token_json_file)

            MockCreds.assert_called_once_with(
                token=fake_creds_data["token"],
                refresh_token=fake_creds_data["refresh_token"],
                token_uri=fake_creds_data["token_uri"],
                client_id=fake_creds_data["client_id"],
                client_secret=fake_creds_data["client_secret"],
                scopes=fake_creds_data["scopes"],
            )

    def test_returns_credentials_object(self, token_json_file):
        """Should return whatever Credentials() produces."""
        sentinel = object()
        with patch("gmail_organizer.auth.Credentials", return_value=sentinel):
            result = _load_credentials_json(token_json_file)
            assert result is sentinel

    def test_raises_on_missing_file(self, tmp_path):
        """Should raise FileNotFoundError for a nonexistent path."""
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError):
            _load_credentials_json(missing)


# ---------------------------------------------------------------------------
# _save_credentials_json
# ---------------------------------------------------------------------------

class TestSaveCredentialsJson:
    """Tests for _save_credentials_json."""

    def test_round_trip(self, tmp_path, mock_credentials, fake_creds_data):
        """Saving then reading the JSON file should preserve all fields."""
        token_path = tmp_path / "credentials" / "token_roundtrip.json"
        _save_credentials_json(mock_credentials, token_path)

        with open(token_path, "r") as f:
            data = json.load(f)

        assert data["token"] == fake_creds_data["token"]
        assert data["refresh_token"] == fake_creds_data["refresh_token"]
        assert data["token_uri"] == fake_creds_data["token_uri"]
        assert data["client_id"] == fake_creds_data["client_id"]
        assert data["client_secret"] == fake_creds_data["client_secret"]
        assert data["scopes"] == fake_creds_data["scopes"]

    def test_creates_parent_directories(self, tmp_path, mock_credentials):
        """Parent directories should be created if they do not exist."""
        nested = tmp_path / "a" / "b" / "c" / "token.json"
        _save_credentials_json(mock_credentials, nested)
        assert nested.exists()

    def test_file_permissions_0600(self, tmp_path, mock_credentials):
        """The saved file must have 0o600 permissions (owner read/write only)."""
        token_path = tmp_path / "token_perms.json"
        _save_credentials_json(mock_credentials, token_path)

        mode = stat.S_IMODE(os.stat(token_path).st_mode)
        assert mode == 0o600


# ---------------------------------------------------------------------------
# _migrate_pickle_to_json
# ---------------------------------------------------------------------------

class _PicklableCredentials:
    """A simple picklable stand-in for google.oauth2.credentials.Credentials."""

    def __init__(self, data):
        self.token = data["token"]
        self.refresh_token = data["refresh_token"]
        self.token_uri = data["token_uri"]
        self.client_id = data["client_id"]
        self.client_secret = data["client_secret"]
        self.scopes = data["scopes"]


class TestMigratePickleToJson:
    """Tests for _migrate_pickle_to_json."""

    def _create_pickle_token(self, path, creds_data):
        """Helper: write a picklable credentials object to a pickle file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        creds = _PicklableCredentials(creds_data)
        with open(path, "wb") as f:
            pickle.dump(creds, f)

    def test_creates_json_and_removes_pickle(self, tmp_path, fake_creds_data):
        """Migration should produce a .json file and delete the .pickle file."""
        pickle_path = tmp_path / "token_migrate.pickle"
        self._create_pickle_token(pickle_path, fake_creds_data)

        json_path = _migrate_pickle_to_json(pickle_path)

        assert json_path.suffix == ".json"
        assert json_path.exists()
        assert not pickle_path.exists()

    def test_json_content_matches_credentials(self, tmp_path, fake_creds_data):
        """The migrated JSON should contain the same data as the original pickle."""
        pickle_path = tmp_path / "token_content.pickle"
        self._create_pickle_token(pickle_path, fake_creds_data)

        json_path = _migrate_pickle_to_json(pickle_path)

        with open(json_path, "r") as f:
            data = json.load(f)

        assert data["token"] == fake_creds_data["token"]
        assert data["refresh_token"] == fake_creds_data["refresh_token"]

    def test_skips_if_json_already_exists(self, tmp_path, fake_creds_data):
        """If a .json file already exists, migration should return it without
        touching the pickle."""
        pickle_path = tmp_path / "token_skip.pickle"
        json_path = pickle_path.with_suffix(".json")

        self._create_pickle_token(pickle_path, fake_creds_data)
        json_path.write_text("{}")  # pre-existing JSON

        result = _migrate_pickle_to_json(pickle_path)

        assert result == json_path
        # Pickle should still be present since migration was skipped
        assert pickle_path.exists()

    def test_json_has_secure_permissions(self, tmp_path, fake_creds_data):
        """The migrated JSON should have 0o600 permissions."""
        pickle_path = tmp_path / "token_secure.pickle"
        self._create_pickle_token(pickle_path, fake_creds_data)

        json_path = _migrate_pickle_to_json(pickle_path)

        mode = stat.S_IMODE(os.stat(json_path).st_mode)
        assert mode == 0o600


# ---------------------------------------------------------------------------
# GmailAuthManager.__init__
# ---------------------------------------------------------------------------

class TestGmailAuthManagerInit:
    """Tests for GmailAuthManager initialization."""

    def test_creates_credentials_directory(self, tmp_path, monkeypatch):
        """The credentials directory should be created on init."""
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(tmp_path / "creds"))
        manager = GmailAuthManager()
        assert Path(manager.credentials_dir).is_dir()

    def test_stores_client_secret_path(self, tmp_path, monkeypatch):
        """The client_secret_path attribute should match the argument."""
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(tmp_path / "creds"))
        manager = GmailAuthManager(client_secret_path="/custom/path.json")
        assert manager.client_secret_path == "/custom/path.json"


# ---------------------------------------------------------------------------
# GmailAuthManager._get_token_path
# ---------------------------------------------------------------------------

class TestGetTokenPath:
    """Tests for GmailAuthManager._get_token_path."""

    def test_returns_json_path_when_json_exists(self, tmp_path, monkeypatch):
        """Should return the .json path when it already exists."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        json_file = creds_dir / "token_alice.json"
        json_file.write_text("{}")

        result = manager._get_token_path("alice")
        assert result == json_file

    def test_migrates_pickle_when_only_pickle_exists(self, tmp_path, monkeypatch, fake_creds_data):
        """Should trigger pickle migration and return the new .json path."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        pickle_file = creds_dir / "token_bob.pickle"
        creds_obj = _PicklableCredentials(fake_creds_data)
        with open(pickle_file, "wb") as f:
            pickle.dump(creds_obj, f)

        result = manager._get_token_path("bob")
        assert result.suffix == ".json"
        assert result.exists()
        assert not pickle_file.exists()

    def test_returns_json_path_when_neither_exists(self, tmp_path, monkeypatch):
        """Should return the expected .json path even if no file exists yet."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        result = manager._get_token_path("newuser")
        assert result == creds_dir / "token_newuser.json"
        assert not result.exists()


# ---------------------------------------------------------------------------
# GmailAuthManager._iter_token_files
# ---------------------------------------------------------------------------

class TestIterTokenFiles:
    """Tests for GmailAuthManager._iter_token_files."""

    def test_yields_json_tokens(self, tmp_path, monkeypatch):
        """Should yield account names and paths for .json token files."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        (creds_dir / "token_one.json").write_text("{}")
        (creds_dir / "token_two.json").write_text("{}")

        results = list(manager._iter_token_files())
        names = {name for name, _ in results}
        assert names == {"one", "two"}

    def test_migrates_pickle_tokens(self, tmp_path, monkeypatch, fake_creds_data):
        """Should migrate pickle tokens and yield them as JSON."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        pickle_file = creds_dir / "token_legacy.pickle"
        creds_obj = _PicklableCredentials(fake_creds_data)
        with open(pickle_file, "wb") as f:
            pickle.dump(creds_obj, f)

        results = list(manager._iter_token_files())
        assert len(results) == 1
        name, path = results[0]
        assert name == "legacy"
        assert path.suffix == ".json"
        assert not pickle_file.exists()

    def test_empty_directory(self, tmp_path, monkeypatch):
        """Should yield nothing when the credentials directory is empty."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        results = list(manager._iter_token_files())
        assert results == []


# ---------------------------------------------------------------------------
# GmailAuthManager.authenticate_account
# ---------------------------------------------------------------------------

class TestAuthenticateAccount:
    """Tests for GmailAuthManager.authenticate_account."""

    def test_raises_when_client_secret_missing(self, tmp_path, monkeypatch):
        """Should raise FileNotFoundError when client_secret.json is absent."""
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(tmp_path / "creds"))
        manager = GmailAuthManager(client_secret_path=str(tmp_path / "missing.json"))

        with pytest.raises(FileNotFoundError, match="Client secret file not found"):
            manager.authenticate_account("test")

    def test_loads_existing_valid_credentials(
        self, tmp_path, monkeypatch, client_secret_file, fake_creds_data, mock_gmail_service
    ):
        """When a valid token exists, should load it and return the service."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        # Write a token file
        token_path = creds_dir / "token_myaccount.json"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            json.dump(fake_creds_data, f)

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False

        with patch("gmail_organizer.auth._load_credentials_json", return_value=mock_creds), \
             patch("gmail_organizer.auth.build", return_value=mock_gmail_service):
            service, email, name = manager.authenticate_account("myaccount")

        assert email == "testuser@gmail.com"
        assert name == "myaccount"
        assert service is mock_gmail_service

    def test_refreshes_expired_credentials(
        self, tmp_path, monkeypatch, client_secret_file, fake_creds_data, mock_gmail_service
    ):
        """When creds are expired but have a refresh token, should attempt refresh."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        token_path = creds_dir / "token_expired.json"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            json.dump(fake_creds_data, f)

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "fake-refresh"

        # After refresh, valid becomes True
        def simulate_refresh(_request):
            mock_creds.valid = True

        mock_creds.refresh.side_effect = simulate_refresh

        with patch("gmail_organizer.auth._load_credentials_json", return_value=mock_creds), \
             patch("gmail_organizer.auth.build", return_value=mock_gmail_service), \
             patch("gmail_organizer.auth.Request"):
            service, email, name = manager.authenticate_account("expired")

        mock_creds.refresh.assert_called_once()
        assert email == "testuser@gmail.com"

    def test_runs_oauth_flow_when_no_creds(
        self, tmp_path, monkeypatch, client_secret_file, mock_gmail_service
    ):
        """When no token file exists, should run the OAuth flow."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        new_creds = MagicMock()
        new_creds.valid = True

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds

        with patch("gmail_organizer.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
             patch("gmail_organizer.auth.build", return_value=mock_gmail_service), \
             patch("gmail_organizer.auth._save_credentials_json") as mock_save:
            service, email, name = manager.authenticate_account("newacct")

        mock_flow.run_local_server.assert_called_once_with(port=0)
        mock_save.assert_called_once()
        assert email == "testuser@gmail.com"
        assert name == "newacct"

    def test_oauth_flow_derives_account_name_from_email(
        self, tmp_path, monkeypatch, client_secret_file, mock_gmail_service
    ):
        """When account_name is None, should derive it from the email address."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        new_creds = MagicMock()
        new_creds.valid = True

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds

        with patch("gmail_organizer.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
             patch("gmail_organizer.auth.build", return_value=mock_gmail_service), \
             patch("gmail_organizer.auth._save_credentials_json"):
            service, email, name = manager.authenticate_account(None)

        assert name == "testuser"  # derived from testuser@gmail.com

    def test_oauth_flow_after_failed_refresh(
        self, tmp_path, monkeypatch, client_secret_file, fake_creds_data, mock_gmail_service
    ):
        """When token refresh fails, should fall through to the OAuth flow."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        token_path = creds_dir / "token_badrefresh.json"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            json.dump(fake_creds_data, f)

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "bad-token"
        mock_creds.refresh.side_effect = Exception("refresh failed")

        new_creds = MagicMock()
        new_creds.valid = True

        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds

        with patch("gmail_organizer.auth._load_credentials_json", return_value=mock_creds), \
             patch("gmail_organizer.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow), \
             patch("gmail_organizer.auth.build", return_value=mock_gmail_service), \
             patch("gmail_organizer.auth._save_credentials_json"), \
             patch("gmail_organizer.auth.Request"):
            service, email, name = manager.authenticate_account("badrefresh")

        mock_flow.run_local_server.assert_called_once()
        assert email == "testuser@gmail.com"


# ---------------------------------------------------------------------------
# GmailAuthManager.load_all_accounts
# ---------------------------------------------------------------------------

class TestLoadAllAccounts:
    """Tests for GmailAuthManager.load_all_accounts."""

    def test_loads_all_token_files(self, tmp_path, monkeypatch, client_secret_file, mock_gmail_service, fake_creds_data):
        """Should return a dict of all successfully loaded accounts."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        # Create two token files
        for name in ("acct1", "acct2"):
            path = creds_dir / f"token_{name}.json"
            with open(path, "w") as f:
                json.dump(fake_creds_data, f)

        mock_creds = MagicMock()
        mock_creds.valid = True

        with patch("gmail_organizer.auth._load_credentials_json", return_value=mock_creds), \
             patch("gmail_organizer.auth.build", return_value=mock_gmail_service):
            accounts = manager.load_all_accounts()

        assert len(accounts) == 2
        assert "acct1" in accounts
        assert "acct2" in accounts

    def test_skips_failed_accounts(self, tmp_path, monkeypatch, client_secret_file, fake_creds_data):
        """Should skip accounts that fail to authenticate without raising."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        path = creds_dir / "token_broken.json"
        with open(path, "w") as f:
            json.dump(fake_creds_data, f)

        with patch.object(manager, "authenticate_account", side_effect=Exception("auth error")):
            accounts = manager.load_all_accounts()

        assert accounts == {}

    def test_empty_when_no_tokens(self, tmp_path, monkeypatch, client_secret_file):
        """Should return an empty dict when no token files exist."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager(client_secret_path=str(client_secret_file))

        accounts = manager.load_all_accounts()
        assert accounts == {}


# ---------------------------------------------------------------------------
# GmailAuthManager.list_authenticated_accounts
# ---------------------------------------------------------------------------

class TestListAuthenticatedAccounts:
    """Tests for GmailAuthManager.list_authenticated_accounts."""

    def test_lists_all_accounts(self, tmp_path, monkeypatch, fake_creds_data, mock_gmail_service):
        """Should return a list of (account_name, email) tuples."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        (creds_dir / "token_user1.json").write_text(json.dumps(fake_creds_data))
        (creds_dir / "token_user2.json").write_text(json.dumps(fake_creds_data))

        mock_creds = MagicMock()
        mock_creds.valid = True

        with patch("gmail_organizer.auth._load_credentials_json", return_value=mock_creds), \
             patch("gmail_organizer.auth.build", return_value=mock_gmail_service):
            result = manager.list_authenticated_accounts()

        names = {name for name, _ in result}
        assert names == {"user1", "user2"}
        assert all(email == "testuser@gmail.com" for _, email in result)

    def test_skips_erroring_accounts(self, tmp_path, monkeypatch, fake_creds_data):
        """Should skip accounts that error during credential loading."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        (creds_dir / "token_bad.json").write_text(json.dumps(fake_creds_data))

        with patch("gmail_organizer.auth._load_credentials_json", side_effect=Exception("corrupt")):
            result = manager.list_authenticated_accounts()

        assert result == []


# ---------------------------------------------------------------------------
# GmailAuthManager.remove_account
# ---------------------------------------------------------------------------

class TestRemoveAccount:
    """Tests for GmailAuthManager.remove_account."""

    def test_deletes_existing_token(self, tmp_path, monkeypatch, fake_creds_data):
        """Should delete the token file and return True."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        token_path = creds_dir / "token_removeme.json"
        token_path.write_text(json.dumps(fake_creds_data))

        result = manager.remove_account("removeme")

        assert result is True
        assert not token_path.exists()

    def test_returns_false_for_nonexistent_account(self, tmp_path, monkeypatch):
        """Should return False when the token file does not exist."""
        creds_dir = tmp_path / "creds"
        monkeypatch.setattr("gmail_organizer.auth.CREDENTIALS_DIR", str(creds_dir))
        manager = GmailAuthManager()

        result = manager.remove_account("ghost")
        assert result is False
