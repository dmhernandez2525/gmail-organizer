"""Tests for gmail_organizer/claude_integration.py"""

import inspect
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def processing_dir(tmp_path, monkeypatch):
    """Redirect PROCESSING_DIR to a temp directory for isolation."""
    proc_dir = tmp_path / ".claude-processing"
    proc_dir.mkdir()
    monkeypatch.setattr(
        "gmail_organizer.claude_integration.PROCESSING_DIR", proc_dir
    )
    return proc_dir


@pytest.fixture
def sample_emails():
    """A small list of email dicts matching the expected input shape."""
    return [
        {
            "email_id": "abc123",
            "sender": "recruiter@bigco.com",
            "subject": "Exciting role at BigCo",
            "date": "2026-03-20",
        },
        {
            "email_id": "def456",
            "sender": "newsletter@news.com",
            "subject": "Weekly digest",
            "date": "2026-03-21",
        },
    ]


@pytest.fixture
def sample_categories():
    """Minimal category dict used by create_classification_prompt."""
    return {
        "job_search": {
            "recruiter_outreach": {
                "name": "Recruiter Outreach",
                "description": "Messages from recruiters",
            },
        },
        "general": {
            "newsletters": {
                "name": "Newsletters",
                "description": "Subscription newsletters",
            },
        },
    }


# ---------------------------------------------------------------------------
# check_claude_code_installed
# ---------------------------------------------------------------------------

class TestCheckClaudeCodeInstalled:
    """Tests for the check_claude_code_installed function."""

    @patch("gmail_organizer.claude_integration.subprocess.run")
    def test_returns_true_when_claude_found(self, mock_run):
        from gmail_organizer.claude_integration import check_claude_code_installed

        mock_run.return_value = MagicMock(
            returncode=0, stdout="/usr/local/bin/claude\n"
        )
        assert check_claude_code_installed()
        mock_run.assert_called_once_with(
            ["which", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    @patch("gmail_organizer.claude_integration.subprocess.run")
    def test_returns_false_when_not_found(self, mock_run):
        from gmail_organizer.claude_integration import check_claude_code_installed

        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert not check_claude_code_installed()

    @patch("gmail_organizer.claude_integration.subprocess.run")
    def test_returns_false_on_exception(self, mock_run):
        from gmail_organizer.claude_integration import check_claude_code_installed

        mock_run.side_effect = FileNotFoundError("which not found")
        assert not check_claude_code_installed()

    @patch("gmail_organizer.claude_integration.subprocess.run")
    def test_returns_false_when_stdout_empty_but_rc_zero(self, mock_run):
        from gmail_organizer.claude_integration import check_claude_code_installed

        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert not check_claude_code_installed()


# ---------------------------------------------------------------------------
# export_emails_for_claude
# ---------------------------------------------------------------------------

class TestExportEmailsForClaude:
    """Tests for export_emails_for_claude."""

    def test_creates_correct_json(self, processing_dir, sample_emails):
        from gmail_organizer.claude_integration import export_emails_for_claude

        output_path = export_emails_for_claude(sample_emails)
        assert Path(output_path).exists()

        with open(output_path) as f:
            data = json.load(f)

        assert len(data) == 2
        assert data[0]["id"] == "abc123"
        assert data[0]["from"] == "recruiter@bigco.com"
        assert data[0]["subject"] == "Exciting role at BigCo"
        assert data[0]["date"] == "2026-03-20"

    def test_creates_processing_dir_if_missing(self, tmp_path, monkeypatch):
        from gmail_organizer.claude_integration import export_emails_for_claude

        new_dir = tmp_path / "new-processing"
        monkeypatch.setattr(
            "gmail_organizer.claude_integration.PROCESSING_DIR", new_dir
        )
        export_emails_for_claude([])
        assert new_dir.exists()

    def test_custom_output_filename(self, processing_dir, sample_emails):
        from gmail_organizer.claude_integration import export_emails_for_claude

        output_path = export_emails_for_claude(sample_emails, "custom.json")
        assert Path(output_path).name == "custom.json"

    def test_handles_missing_fields_gracefully(self, processing_dir):
        from gmail_organizer.claude_integration import export_emails_for_claude

        emails = [{"some_other_field": "value"}]
        output_path = export_emails_for_claude(emails)

        with open(output_path) as f:
            data = json.load(f)

        assert data[0]["id"] == ""
        assert data[0]["from"] == ""
        assert data[0]["subject"] == ""
        assert data[0]["date"] == ""


# ---------------------------------------------------------------------------
# create_classification_prompt
# ---------------------------------------------------------------------------

class TestCreateClassificationPrompt:
    """Tests for create_classification_prompt."""

    def test_creates_valid_prompt_file(self, processing_dir, sample_categories):
        from gmail_organizer.claude_integration import create_classification_prompt

        path = create_classification_prompt(sample_categories)
        assert Path(path).exists()

        content = Path(path).read_text()
        assert "Email Classification Task" in content
        assert "recruiter_outreach" in content
        assert "newsletters" in content

    def test_job_search_focused_true(self, processing_dir, sample_categories):
        from gmail_organizer.claude_integration import create_classification_prompt

        path = create_classification_prompt(sample_categories, job_search_focused=True)
        content = Path(path).read_text()
        assert "Focus on job search categories" in content

    def test_job_search_focused_false(self, processing_dir, sample_categories):
        from gmail_organizer.claude_integration import create_classification_prompt

        path = create_classification_prompt(sample_categories, job_search_focused=False)
        content = Path(path).read_text()
        assert "Treat all categories equally" in content

    def test_prompt_contains_output_format(self, processing_dir, sample_categories):
        from gmail_organizer.claude_integration import create_classification_prompt

        path = create_classification_prompt(sample_categories)
        content = Path(path).read_text()
        assert "results.json" in content
        assert "category" in content
        assert "confidence" in content


# ---------------------------------------------------------------------------
# read_classification_results
# ---------------------------------------------------------------------------

class TestReadClassificationResults:
    """Tests for read_classification_results."""

    def test_reads_valid_json(self, processing_dir):
        from gmail_organizer.claude_integration import read_classification_results

        results = [
            {"id": "abc123", "category": "recruiter_outreach", "confidence": 0.95}
        ]
        results_path = processing_dir / "results.json"
        results_path.write_text(json.dumps(results))

        data = read_classification_results()
        assert data is not None
        assert len(data) == 1
        assert data[0]["id"] == "abc123"

    def test_returns_none_for_missing_file(self, processing_dir):
        from gmail_organizer.claude_integration import read_classification_results

        # No results.json created
        assert read_classification_results() is None

    def test_returns_none_for_invalid_json(self, processing_dir):
        from gmail_organizer.claude_integration import read_classification_results

        results_path = processing_dir / "results.json"
        results_path.write_text("not valid json {{{")
        assert read_classification_results() is None


# ---------------------------------------------------------------------------
# cleanup_processing_files
# ---------------------------------------------------------------------------

class TestCleanupProcessingFiles:
    """Tests for cleanup_processing_files."""

    def test_removes_all_files(self, processing_dir):
        from gmail_organizer.claude_integration import cleanup_processing_files

        (processing_dir / "emails.json").write_text("{}")
        (processing_dir / "prompt.md").write_text("prompt")
        (processing_dir / "results.json").write_text("[]")

        assert len(list(processing_dir.iterdir())) == 3
        cleanup_processing_files()
        assert len(list(processing_dir.iterdir())) == 0

    def test_handles_empty_directory(self, processing_dir):
        from gmail_organizer.claude_integration import cleanup_processing_files

        # Should not raise
        cleanup_processing_files()
        assert len(list(processing_dir.iterdir())) == 0


# ---------------------------------------------------------------------------
# launch_claude_code_terminal: verify no --dangerously-skip-permissions
# ---------------------------------------------------------------------------

class TestLaunchClaudeCodeTerminal:
    """Verify launch_claude_code_terminal does NOT use --dangerously-skip-permissions."""

    def test_no_dangerously_skip_permissions_in_source(self):
        from gmail_organizer import claude_integration

        source = inspect.getsource(claude_integration.launch_claude_code_terminal)
        assert "--dangerously-skip-permissions" not in source, (
            "launch_claude_code_terminal must not use --dangerously-skip-permissions"
        )

    def test_uses_stdin_redirect_pattern(self):
        """The command should pipe prompt via stdin: claude < {prompt_file}."""
        from gmail_organizer import claude_integration

        source = inspect.getsource(claude_integration.launch_claude_code_terminal)
        assert "claude <" in source or "claude < " in source, (
            "launch_claude_code_terminal should use 'claude < {prompt_file}' pattern"
        )

    @patch("gmail_organizer.claude_integration.subprocess.run")
    def test_calls_osascript(self, mock_run, processing_dir):
        from gmail_organizer.claude_integration import launch_claude_code_terminal

        mock_run.return_value = MagicMock(returncode=0)
        launch_claude_code_terminal("/tmp/prompt.md")

        call_args = mock_run.call_args
        assert call_args[0][0][0] == "osascript"

    @patch("gmail_organizer.claude_integration.subprocess.run")
    def test_raises_on_failure(self, mock_run, processing_dir):
        from gmail_organizer.claude_integration import launch_claude_code_terminal

        mock_run.side_effect = subprocess.CalledProcessError(1, "osascript")
        with pytest.raises(subprocess.CalledProcessError):
            launch_claude_code_terminal("/tmp/prompt.md")
