"""Contract and fixture tests for the Windows PowerShell launcher."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "launch_gmail_organizer.ps1"
PWSH = shutil.which("pwsh")


def run_launcher(project_root: Path, *extra_args: str, env: dict[str, str] | None = None):
    command = [
        PWSH,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(LAUNCHER),
        "-ValidateOnly",
        "-ProjectRoot",
        str(project_root),
        *extra_args,
    ]
    return subprocess.run(command, capture_output=True, text=True, env=env, check=False)


def run_launcher_normally(project_root: Path, *extra_args: str):
    command = [
        PWSH,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(LAUNCHER),
        "-ProjectRoot",
        str(project_root),
        "-NoBrowser",
        *extra_args,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=15)


def make_project(tmp_path: Path, env_text: str = "ANTHROPIC_API_KEY=test-secret\n") -> Path:
    project_root = tmp_path / "gmail-organizer fixture"
    streamlit = project_root / "venv" / "bin" / "streamlit"
    streamlit.parent.mkdir(parents=True)
    streamlit.write_text("#!/bin/sh\n", encoding="utf-8")
    (project_root / "app.py").write_text("# fixture\n", encoding="utf-8")
    (project_root / ".env").write_text(env_text, encoding="utf-8")
    return project_root


pytestmark = pytest.mark.skipif(PWSH is None, reason="PowerShell is not installed")


def test_launcher_parses_without_errors():
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{LAUNCHER}', [ref]$tokens, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    result = subprocess.run(
        [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_validate_only_builds_sanitized_launch_plan(tmp_path):
    secret = "test-secret-that-must-not-be-printed"
    project_root = make_project(tmp_path, f"ANTHROPIC_API_KEY={secret}\n")
    (project_root / "client_secret.json").write_text("{}\n", encoding="utf-8")

    result = run_launcher(project_root, "-Port", "8601", "-MaxRestarts", "5")

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["ProjectRoot"] == str(project_root)
    assert plan["AppPath"] == str(project_root / "app.py")
    assert plan["ClientSecretPresent"] is True
    assert plan["AnthropicKeyConfigured"] is True
    assert plan["StreamlitCommand"] == str(project_root / "venv" / "bin" / "streamlit")
    assert plan["StreamlitArguments"][1] == "app.py"
    assert plan["StreamlitArguments"][-1] == "8601"
    assert plan["Url"] == "http://localhost:8601"
    assert plan["MaxRestarts"] == 5
    assert secret not in result.stdout
    assert secret not in result.stderr


def test_validate_only_supports_windows_venv_layout(tmp_path):
    project_root = make_project(tmp_path)
    windows_streamlit = project_root / "venv" / "Scripts" / "streamlit.exe"
    windows_streamlit.parent.mkdir(parents=True)
    windows_streamlit.write_text("fixture\n", encoding="utf-8")

    result = run_launcher(project_root)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["StreamlitCommand"] == str(windows_streamlit)


def test_default_project_root_resolves_from_launcher_location(tmp_path):
    project_root = make_project(tmp_path)
    fixture_launcher = project_root / "scripts" / LAUNCHER.name
    fixture_launcher.parent.mkdir()
    shutil.copy2(LAUNCHER, fixture_launcher)
    result = subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(fixture_launcher),
            "-ValidateOnly",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ProjectRoot"] == str(project_root)


@pytest.mark.parametrize(
    ("env_text", "expected"),
    [
        ("ANTHROPIC_API_KEY=configured\n", True),
        ("  ANTHROPIC_API_KEY = configured  \n", True),
        ('ANTHROPIC_API_KEY="configured value" # local note\n', True),
        ("ANTHROPIC_API_KEY='configured # value'\n", True),
        ("ANTHROPIC_API_KEY=configured # local note\n", True),
        ("ANTHROPIC_API_KEY=\n", False),
        ('ANTHROPIC_API_KEY=""\n', False),
        ("ANTHROPIC_API_KEY=''\n", False),
        ('ANTHROPIC_API_KEY="   "\n', False),
        ('ANTHROPIC_API_KEY="unterminated\n', False),
        ("# ANTHROPIC_API_KEY=commented\n", False),
        ("ANTHROPIC_API_KEY=   # comment only\n", False),
    ],
)
def test_anthropic_key_detection_handles_common_env_forms(tmp_path, env_text, expected):
    project_root = make_project(tmp_path, env_text)

    result = run_launcher(project_root)

    assert result.returncode == 0
    assert json.loads(result.stdout)["AnthropicKeyConfigured"] is expected


def test_missing_client_secret_and_key_are_warnings_not_secret_output(tmp_path):
    project_root = make_project(tmp_path, "USE_CLAUDE_CODE=true\n")

    result = run_launcher(project_root)

    assert result.returncode == 0
    plan = json.loads(result.stdout)
    assert plan["ClientSecretPresent"] is False
    assert plan["AnthropicKeyConfigured"] is False
    assert "client_secret.json was not found" in result.stderr
    assert "ANTHROPIC_API_KEY is not configured" in result.stderr


@pytest.mark.parametrize(
    ("missing_name", "message"),
    [
        ("app.py", "app.py was not found"),
        (".env", ".env was not found"),
    ],
)
def test_required_project_file_failures_are_actionable(tmp_path, missing_name, message):
    project_root = make_project(tmp_path)
    (project_root / missing_name).rename(project_root / f"{missing_name}.missing")

    result = run_launcher(project_root)

    assert result.returncode == 1
    assert message in result.stderr
    assert "test-secret" not in result.stderr


def test_missing_project_root_is_actionable(tmp_path):
    result = run_launcher(tmp_path / "not-present")

    assert result.returncode == 1
    assert "Cannot find path" in result.stderr


def test_missing_streamlit_is_actionable(tmp_path):
    project_root = make_project(tmp_path)
    streamlit = project_root / "venv" / "bin" / "streamlit"
    streamlit.rename(streamlit.with_suffix(".missing"))
    isolated_env = os.environ.copy()
    isolated_env["PATH"] = ""

    result = run_launcher(project_root, env=isolated_env)

    assert result.returncode == 1
    assert "Streamlit was not found" in result.stderr


def test_system_streamlit_fallback_is_supported(tmp_path):
    project_root = make_project(tmp_path)
    streamlit = project_root / "venv" / "bin" / "streamlit"
    streamlit.rename(streamlit.with_suffix(".missing"))
    command_dir = tmp_path / "commands"
    command_dir.mkdir()
    fallback = command_dir / "streamlit"
    fallback.write_text("#!/bin/sh\n", encoding="utf-8")
    fallback.chmod(0o755)
    isolated_env = os.environ.copy()
    isolated_env["PATH"] = str(command_dir)

    result = run_launcher(project_root, env=isolated_env)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["StreamlitCommand"] == str(fallback)


@pytest.mark.skipif(os.name != "posix", reason="Uses a POSIX fixture executable")
def test_no_browser_launch_runs_fake_streamlit_to_clean_exit(tmp_path):
    project_root = make_project(tmp_path)
    streamlit = project_root / "venv" / "bin" / "streamlit"
    streamlit.write_text("#!/bin/sh\nsleep 3\nexit 0\n", encoding="utf-8")
    streamlit.chmod(0o755)

    result = run_launcher_normally(project_root, "-MaxRestarts", "0")

    assert result.returncode == 0, result.stderr
    assert "Gmail Organizer is running at http://localhost:8501" in result.stdout


@pytest.mark.skipif(os.name != "posix", reason="Uses a POSIX fixture executable")
def test_no_browser_launch_reports_bounded_runtime_failure(tmp_path):
    project_root = make_project(tmp_path)
    streamlit = project_root / "venv" / "bin" / "streamlit"
    streamlit.write_text("#!/bin/sh\nsleep 3\nexit 7\n", encoding="utf-8")
    streamlit.chmod(0o755)

    result = run_launcher_normally(project_root, "-MaxRestarts", "0")

    assert result.returncode == 1
    assert "Streamlit stopped with code 7 after 0 restart attempts" in result.stderr
    assert "test-secret" not in result.stdout
    assert "test-secret" not in result.stderr


def test_launcher_has_safe_process_and_restart_contract():
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "[ValidateRange(0, 100)]" in source
    assert "Stop-Process -Id $process.Id" in source
    assert "kill" not in source.lower()
    assert "ConvertTo-Json" in source
    assert "Get-Content" not in source
    assert "Start-Process $Plan.Url" in source
    assert "/Users/" not in source
    assert "Invoke-WebRequest" not in source
    assert "Invoke-RestMethod" not in source


def test_readme_documents_windows_launcher():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert ".\\scripts\\launch_gmail_organizer.ps1" in readme
    assert "-ValidateOnly" in readme
