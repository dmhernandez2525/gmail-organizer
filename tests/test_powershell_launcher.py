"""Adversarial contract tests for the Windows launcher pair."""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

from tests.launcher_test_support import (
    CMD_LAUNCHER,
    POWERSHELL_LAUNCHER,
    PWSH,
    build_venv_template,
    instrumented_launcher_command,
    make_project,
    prepare_powershell_coverage_environment,
    project_python,
    run_launcher,
    run_launcher_normally,
)

pytestmark = pytest.mark.skipif(PWSH is None, reason="PowerShell is not installed")


@pytest.fixture(scope="session")
def venv_template(tmp_path_factory):
    return build_venv_template(tmp_path_factory.mktemp("launcher-venv-template") / "venv")


@pytest.fixture
def launcher_fixture(tmp_path, venv_template):
    return make_project(tmp_path, venv_template)


def free_port() -> int:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    return port


def parse_plan(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def validation_codes(result: subprocess.CompletedProcess[str]) -> set[str]:
    return {error["Code"] for error in parse_plan(result)["Validation"]["Errors"]}


def validator_contract_document(launchable: bool) -> dict:
    return {
        "SchemaVersion": 1,
        "Launchable": launchable,
        "AppPresent": True,
        "PythonExecutable": "fixture-python",
        "PythonVersion": "3.11.0",
        "PythonVersionValid": True,
        "VenvRoot": "fixture-venv",
        "VenvValid": True,
        "DependenciesValid": launchable,
        "UnavailableDependencies": [] if launchable else ["streamlit"],
        "AnthropicKeyConfigured": True,
        "AnthropicKeySource": "dotenv",
        "ClientSecretValid": True,
        "PortAvailable": True,
        "Errors": []
        if launchable
        else [{"Code": "runtime_dependencies_unavailable", "Message": "Unavailable."}],
    }


def test_launcher_parses_without_errors():
    escaped_path = str(POWERSHELL_LAUNCHER).replace("'", "''")
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{escaped_path}', [ref]$tokens, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    result = subprocess.run(
        [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_validate_only_proves_a_sanitized_launch_plan(launcher_fixture):
    port = free_port()
    result = run_launcher(
        launcher_fixture, "-Port", str(port), "-MaxRestarts", "5", "-StartupTimeoutSeconds", "8"
    )

    assert result.returncode == 0, result.stderr
    plan = parse_plan(result)
    assert plan["ProjectRoot"] == str(launcher_fixture.root)
    assert plan["AppPath"] == str(launcher_fixture.root / "app.py")
    assert Path(plan["PythonExecutable"]).is_file()
    assert plan["VenvRoot"] == str(launcher_fixture.venv_root)
    assert plan["PythonArguments"][:4] == ["-m", "streamlit", "run", "app.py"]
    assert plan["PythonArguments"][-4:-2] == ["--server.address", "127.0.0.1"]
    assert plan["PythonArguments"][-1] == str(port)
    assert plan["Url"] == f"http://localhost:{port}"
    assert plan["MaxRestarts"] == 5
    assert plan["StartupTimeoutSeconds"] == 8
    assert plan["Launchable"] is True
    assert plan["Validation"]["Launchable"] is True
    assert plan["Validation"]["VenvValid"] is True
    assert plan["Validation"]["DependenciesValid"] is True
    assert plan["Validation"]["AnthropicKeySource"] == "dotenv"
    assert plan["Validation"]["ClientSecretValid"] is True
    assert plan["Validation"]["PortAvailable"] is True
    assert "fixture-key" not in result.stdout + result.stderr
    assert "fixture-client-secret" not in result.stdout + result.stderr


def test_windows_venv_layout_has_priority_when_present(launcher_fixture):
    windows_python = launcher_fixture.venv_root / "Scripts" / "python.exe"
    if os.name != "nt":
        windows_python.parent.mkdir(parents=True)
        delegate = project_python(launcher_fixture.venv_root)
        windows_python.write_text(
            f"#!/bin/sh\nexec '{delegate}' \"$@\"\n",
            encoding="utf-8",
        )
        windows_python.chmod(0o755)

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 0, result.stderr
    assert parse_plan(result)["PythonExecutable"] == str(windows_python)


def test_default_project_root_resolves_from_launcher_location(tmp_path, venv_template):
    fixture = make_project(tmp_path, venv_template)
    fixture_launcher = fixture.root / "scripts" / POWERSHELL_LAUNCHER.name
    launcher_arguments = [
        "-ValidateOnly",
        "-Port",
        str(free_port()),
    ]
    environment = fixture.env.copy()
    command = instrumented_launcher_command(
        launcher_arguments, environment, launcher_path=fixture_launcher
    )
    result = subprocess.run(
        command, capture_output=True, text=True, env=environment, check=False, timeout=20
    )

    assert result.returncode == 0, result.stderr
    assert parse_plan(result)["ProjectRoot"] == str(fixture.root)


def test_inherited_environment_key_takes_precedence(launcher_fixture):
    (launcher_fixture.root / ".env").write_text(
        "ANTHROPIC_API_KEY=dotenv-key\n", encoding="utf-8"
    )
    environment = launcher_fixture.env.copy()
    environment["ANTHROPIC_API_KEY"] = "process-key"

    result = run_launcher(launcher_fixture, "-Port", str(free_port()), env=environment)

    assert result.returncode == 0, result.stderr
    assert parse_plan(result)["Validation"]["AnthropicKeySource"] == "process_environment"
    assert "process-key" not in result.stdout + result.stderr
    assert "dotenv-key" not in result.stdout + result.stderr


def test_missing_dotenv_is_allowed_with_inherited_key(launcher_fixture):
    (launcher_fixture.root / ".env").unlink()
    environment = launcher_fixture.env.copy()
    environment["ANTHROPIC_API_KEY"] = "process-key"

    result = run_launcher(launcher_fixture, "-Port", str(free_port()), env=environment)

    assert result.returncode == 0, result.stderr
    assert parse_plan(result)["Launchable"] is True


@pytest.mark.parametrize(
    "env_text",
    [
        "ANTHROPIC_API_KEY=first\nANTHROPIC_API_KEY=\n",
        'ANTHROPIC_API_KEY=""\n',
        "ANTHROPIC_API_KEY=sk-ant-your-key-here\n",
        'ANTHROPIC_API_KEY="unterminated\n',
    ],
)
def test_invalid_effective_key_fails_closed(launcher_fixture, env_text):
    (launcher_fixture.root / ".env").write_text(env_text, encoding="utf-8")

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert parse_plan(result)["Launchable"] is False
    assert "anthropic_key_invalid" in validation_codes(result)
    assert "first" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "document",
    [None, {}, {"web": {}}, {"installed": {}}, "not-json"],
)
def test_invalid_oauth_configuration_fails_closed(launcher_fixture, document):
    secret_path = launcher_fixture.root / "client_secret.json"
    if document is None:
        secret_path.unlink()
    elif document == "not-json":
        secret_path.write_text("{not-json", encoding="utf-8")
    else:
        secret_path.write_text(json.dumps(document), encoding="utf-8")

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert parse_plan(result)["Launchable"] is False
    assert any(code.startswith("client_secret_") for code in validation_codes(result))
    assert "fixture-client-secret" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("relative_path", "expected_code"),
    [
        ("app.py", "app_missing"),
        ("scripts/validate_gmail_organizer_runtime.py", "validator_missing"),
    ],
)
def test_required_repository_file_failures_are_actionable(
    launcher_fixture, relative_path, expected_code
):
    (launcher_fixture.root / relative_path).unlink()

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert parse_plan(result)["Launchable"] is False
    assert expected_code in validation_codes(result)


def test_missing_project_root_is_actionable(tmp_path):
    command = [
        PWSH,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(POWERSHELL_LAUNCHER),
        "-ValidateOnly",
        "-ProjectRoot",
        str(tmp_path / "not-present"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert "Cannot find path" in result.stderr


def test_project_venv_is_required_even_when_system_python_exists(launcher_fixture):
    shutil.move(launcher_fixture.venv_root, launcher_fixture.root / "venv.missing")

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert "project_venv_missing" in validation_codes(result)
    assert parse_plan(result)["PythonExecutable"] is None


def test_dot_venv_layout_is_used_when_primary_venv_is_absent(launcher_fixture):
    dot_venv = launcher_fixture.root / ".venv"
    launcher_fixture.venv_root.rename(dot_venv)

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 0, result.stderr
    assert parse_plan(result)["VenvRoot"] == str(dot_venv)


def test_stale_python_shim_fails_closed(launcher_fixture):
    python = project_python(launcher_fixture.venv_root)
    python.unlink()
    if os.name == "nt":
        python.write_bytes(b"not-a-windows-executable")
    else:
        python.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
        python.chmod(0o755)

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert parse_plan(result)["Launchable"] is False
    assert "python_execution_failed" in validation_codes(result)


@pytest.mark.parametrize(
    ("output", "exit_code", "expected_code"),
    [
        ("not-json", 0, "validator_output_invalid"),
        (json.dumps({"Launchable": False}), 1, "validator_contract_invalid"),
        (json.dumps({"Launchable": True, "Errors": []}), 0, "validator_contract_invalid"),
        (json.dumps(validator_contract_document(False)), 0, "validator_exit_mismatch"),
        (json.dumps(validator_contract_document(True)), 1, "validator_exit_mismatch"),
        (json.dumps(validator_contract_document(False)), 2, "validator_exit_invalid"),
    ],
)
def test_validator_process_contract_fails_closed(
    launcher_fixture, output, exit_code, expected_code
):
    validator_path = launcher_fixture.root / "scripts" / "validate_gmail_organizer_runtime.py"
    validator_path.write_text(
        f"print({output!r})\nraise SystemExit({exit_code})\n",
        encoding="utf-8",
    )

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert expected_code in validation_codes(result)


@pytest.mark.parametrize(
    "case",
    [
        "schema",
        "schema_type",
        "boolean",
        "python_executable",
        "venv_root",
        "python_version",
        "key_source",
        "dependency_type",
        "dependency_consistency",
        "error_shape",
        "launchable_semantics",
    ],
)
def test_validator_schema_rejects_invalid_field_types_and_semantics(launcher_fixture, case):
    document = validator_contract_document(True)
    if case == "schema":
        document["SchemaVersion"] = 2
    elif case == "schema_type":
        document["SchemaVersion"] = "1"
    elif case == "boolean":
        document["PortAvailable"] = "true"
    elif case == "python_executable":
        document["PythonExecutable"] = ""
    elif case == "venv_root":
        document["VenvRoot"] = ""
    elif case == "python_version":
        document["PythonVersion"] = "3.11"
    elif case == "key_source":
        document["AnthropicKeySource"] = "unknown"
    elif case == "dependency_type":
        document["DependenciesValid"] = False
        document["UnavailableDependencies"] = [7]
        document["Launchable"] = False
        document["Errors"] = [{"Code": "dependency", "Message": "Unavailable."}]
    elif case == "dependency_consistency":
        document["UnavailableDependencies"] = ["streamlit"]
    elif case == "error_shape":
        document["DependenciesValid"] = False
        document["UnavailableDependencies"] = ["streamlit"]
        document["Launchable"] = False
        document["Errors"] = [{"Code": "dependency"}]
    elif case == "launchable_semantics":
        document["Launchable"] = False

    validator_path = launcher_fixture.root / "scripts" / "validate_gmail_organizer_runtime.py"
    output = json.dumps(document)
    validator_path.write_text(
        f"print({output!r})\nraise SystemExit(1)\n",
        encoding="utf-8",
    )

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert "validator_contract_invalid" in validation_codes(result)


def test_wrong_python_environment_fails_closed(launcher_fixture):
    (launcher_fixture.venv_root / "pyvenv.cfg").unlink()

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    assert "wrong_python_environment" in validation_codes(result)
    assert parse_plan(result)["Validation"]["VenvValid"] is False


def test_missing_runtime_package_fails_closed(launcher_fixture):
    (launcher_fixture.stubs / "anthropic.py").unlink()

    result = run_launcher(launcher_fixture, "-Port", str(free_port()))

    assert result.returncode == 1
    plan = parse_plan(result)
    assert plan["Validation"]["DependenciesValid"] is False
    assert "anthropic" in plan["Validation"]["UnavailableDependencies"]
    assert "runtime_dependencies_unavailable" in validation_codes(result)


def test_occupied_port_fails_validation(launcher_fixture):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        result = run_launcher(launcher_fixture, "-Port", str(port))
    finally:
        listener.close()

    assert result.returncode == 1
    assert parse_plan(result)["Validation"]["PortAvailable"] is False
    assert "port_unavailable" in validation_codes(result)


def test_no_browser_launch_waits_for_readiness_and_clean_exit(launcher_fixture):
    port = free_port()
    ready_file = launcher_fixture.root / "ready.marker"
    environment = launcher_fixture.env.copy()
    environment.update(
        {
            "FAKE_STREAMLIT_MODE": "clean",
            "FAKE_STREAMLIT_READY_DELAY": "0.7",
            "FAKE_STREAMLIT_DURATION": "0.6",
            "FAKE_STREAMLIT_READY_FILE": str(ready_file),
        }
    )
    started = time.monotonic()

    result = run_launcher_normally(
        launcher_fixture,
        "-Port",
        str(port),
        "-MaxRestarts",
        "0",
        "-StartupTimeoutSeconds",
        "4",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert ready_file.exists()
    assert time.monotonic() - started >= 0.7
    assert f"Gmail Organizer is ready at http://localhost:{port}" in result.stdout


def test_browser_action_runs_only_after_server_readiness(launcher_fixture):
    port = free_port()
    ready_file = launcher_fixture.root / "ready.marker"
    browser_file = launcher_fixture.root / "browser.marker"
    probe = POWERSHELL_LAUNCHER.parents[1] / "tests" / "browser_readiness_probe.ps1"
    environment = launcher_fixture.env.copy()
    environment.update(
        {
            "FAKE_STREAMLIT_MODE": "clean",
            "FAKE_STREAMLIT_READY_DELAY": "0.6",
            "FAKE_STREAMLIT_DURATION": "0.4",
            "FAKE_STREAMLIT_READY_FILE": str(ready_file),
        }
    )
    prepare_powershell_coverage_environment(environment)

    result = subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(probe),
            "-LauncherPath",
            str(POWERSHELL_LAUNCHER),
            "-ProjectRoot",
            str(launcher_fixture.root),
            "-BrowserMarkerPath",
            str(browser_file),
            "-ReadyMarkerPath",
            str(ready_file),
            "-Port",
            str(port),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert ready_file.is_file()
    assert browser_file.read_text(encoding="utf-8") == f"http://localhost:{port}"


def test_port_race_is_rejected_immediately_before_process_start(launcher_fixture):
    port = free_port()
    probe = POWERSHELL_LAUNCHER.parents[1] / "tests" / "powershell_port_race_probe.ps1"
    environment = launcher_fixture.env.copy()
    prepare_powershell_coverage_environment(environment)

    result = subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(probe),
            "-LauncherPath",
            str(POWERSHELL_LAUNCHER),
            "-ProjectRoot",
            str(launcher_fixture.root),
            "-Port",
            str(port),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=20,
    )

    assert result.returncode == 1
    assert f"Local port {port} became unavailable before Streamlit startup" in result.stderr


def test_unrelated_post_check_listener_cannot_satisfy_readiness(launcher_fixture):
    port = free_port()
    browser_file = launcher_fixture.root / "browser.marker"
    listener_ready_file = launcher_fixture.root / "unrelated-listener.marker"
    probe = POWERSHELL_LAUNCHER.parents[1] / "tests" / "unrelated_listener_race_probe.ps1"
    environment = launcher_fixture.env.copy()
    environment.update({"FAKE_STREAMLIT_MODE": "timeout", "FAKE_STREAMLIT_DURATION": "10"})
    prepare_powershell_coverage_environment(environment)

    result = subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(probe),
            "-LauncherPath",
            str(POWERSHELL_LAUNCHER),
            "-ProjectRoot",
            str(launcher_fixture.root),
            "-BrowserMarkerPath",
            str(browser_file),
            "-ListenerReadyPath",
            str(listener_ready_file),
            "-Port",
            str(port),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "UNRELATED_LISTENER_REJECTED" in result.stdout
    assert listener_ready_file.is_file()
    assert not browser_file.exists()


def test_failed_taskkill_is_visible_and_parent_fallback_stops_process(launcher_fixture):
    port = free_port()
    probe = POWERSHELL_LAUNCHER.parents[1] / "tests" / "process_cleanup_failure_probe.ps1"
    environment = launcher_fixture.env.copy()
    environment.update({"FAKE_STREAMLIT_MODE": "timeout", "FAKE_STREAMLIT_DURATION": "30"})
    prepare_powershell_coverage_environment(environment)

    result = subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(probe),
            "-LauncherPath",
            str(POWERSHELL_LAUNCHER),
            "-ProjectRoot",
            str(launcher_fixture.root),
            "-Port",
            str(port),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=20,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "TASKKILL_FAILURE_SURFACED" in result.stdout


def test_missing_health_endpoint_fails_closed():
    port = free_port()
    probe = POWERSHELL_LAUNCHER.parents[1] / "tests" / "health_failure_probe.ps1"
    environment = os.environ.copy()
    prepare_powershell_coverage_environment(environment)

    result = subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(probe),
            "-LauncherPath",
            str(POWERSHELL_LAUNCHER),
            "-Port",
            str(port),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "UNHEALTHY_ENDPOINT_REJECTED" in result.stdout


def test_normal_launch_rejects_failed_validation_before_start(launcher_fixture):
    (launcher_fixture.root / "client_secret.json").unlink()

    result = run_launcher_normally(
        launcher_fixture,
        "-Port",
        str(free_port()),
        "-MaxRestarts",
        "0",
    )

    assert result.returncode == 1
    assert "VALIDATION ERROR [client_secret_missing]" in result.stderr
    assert "Launch validation failed" in result.stderr


def test_launch_reports_bounded_fast_runtime_failure(launcher_fixture):
    environment = launcher_fixture.env.copy()
    environment["FAKE_STREAMLIT_MODE"] = "fast_fail"

    result = run_launcher_normally(
        launcher_fixture,
        "-Port",
        str(free_port()),
        "-MaxRestarts",
        "0",
        "-StartupTimeoutSeconds",
        "2",
        env=environment,
    )

    assert result.returncode == 1
    assert "Streamlit stopped with code 7 after 0 restart attempts" in result.stderr
    assert "fixture-key" not in result.stdout + result.stderr


def test_clean_exit_before_readiness_is_not_reported_as_success(launcher_fixture):
    environment = launcher_fixture.env.copy()
    environment["FAKE_STREAMLIT_MODE"] = "fast_clean"

    result = run_launcher_normally(
        launcher_fixture,
        "-Port",
        str(free_port()),
        "-MaxRestarts",
        "0",
        "-StartupTimeoutSeconds",
        "2",
        env=environment,
    )

    assert result.returncode == 1
    assert "Streamlit stopped with code 125 after 0 restart attempts" in result.stderr
    assert "Gmail Organizer is ready" not in result.stdout


def test_launch_retries_a_fast_startup_failure(launcher_fixture):
    port = free_port()
    attempt_file = launcher_fixture.root / "attempted"
    environment = launcher_fixture.env.copy()
    environment.update(
        {
            "FAKE_STREAMLIT_MODE": "retry_once",
            "FAKE_STREAMLIT_ATTEMPT_FILE": str(attempt_file),
            "FAKE_STREAMLIT_DURATION": "0.5",
        }
    )

    result = run_launcher_normally(
        launcher_fixture,
        "-Port",
        str(port),
        "-MaxRestarts",
        "1",
        "-StartupTimeoutSeconds",
        "3",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert attempt_file.exists()
    assert "Restarting, attempt 1 of 1" in result.stdout + result.stderr
    assert f"Gmail Organizer is ready at http://localhost:{port}" in result.stdout


def test_startup_timeout_is_bounded_and_does_not_claim_ready(launcher_fixture):
    environment = launcher_fixture.env.copy()
    environment.update({"FAKE_STREAMLIT_MODE": "timeout", "FAKE_STREAMLIT_DURATION": "5"})

    result = run_launcher_normally(
        launcher_fixture,
        "-Port",
        str(free_port()),
        "-MaxRestarts",
        "0",
        "-StartupTimeoutSeconds",
        "1",
        env=environment,
    )

    assert result.returncode == 1
    assert "did not become ready within 1 seconds" in result.stdout + result.stderr
    assert "Streamlit stopped with code 124" in result.stderr
    assert "Gmail Organizer is ready" not in result.stdout


def test_current_quoting_and_process_contract_is_narrow():
    source = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    assert "Resolve-Path -LiteralPath" in source
    assert "-FilePath $Plan.PythonExecutable" in source
    assert "-ArgumentList $Plan.PythonArguments" in source
    assert '"-m"' in source and '"streamlit"' in source
    assert "Get-Command taskkill.exe -CommandType Application" in source
    assert "Get-ListeningProcessIds" in source
    assert "Test-TcpPortOwnedByProcess" in source
    assert "Test-GmailOrganizerHealth" in source
    assert "/_stcore/health" in source
    assert "Stop-Process -Id $Process.Id -Force" in source
    assert "Get-Process -Name" not in source
    assert "Open-GmailOrganizerBrowser -Url $Plan.Url" in source
    assert source.index("if ($readiness.Ready)") < source.index(
        "Open-GmailOrganizerBrowser -Url $Plan.Url"
    )
    assert "/Users/" not in source
    assert "Invoke-WebRequest" not in source
    assert "Invoke-RestMethod" not in source


def test_cmd_wrapper_is_quoted_scoped_and_error_persistent():
    source = CMD_LAUNCHER.read_text(encoding="utf-8")

    assert 'for %%I in ("%~dp0.")' in source
    assert '"%GO_POWERSHELL%"' in source
    assert '-ExecutionPolicy Bypass -File "%GO_SCRIPT%" -ProjectRoot "%GO_ROOT%" %*' in source
    assert "GMAIL_ORGANIZER_NO_PAUSE" in source
    assert "pause >nul" in source
    assert "exit /b %GO_EXIT%" in source
    assert "/Users/" not in source


@pytest.mark.skipif(os.name != "nt", reason="Requires native cmd.exe and Windows path parsing")
def test_cmd_wrapper_preserves_project_path_with_spaces_and_metacharacters(tmp_path, venv_template):
    fixture = make_project(tmp_path, venv_template, name="project with spaces & symbols ü")
    port = free_port()
    command_text = f'call "{fixture.root / CMD_LAUNCHER.name}" -ValidateOnly -Port {port}'

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", command_text],
        capture_output=True,
        text=True,
        env=fixture.env,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert parse_plan(result)["ProjectRoot"] == str(fixture.root)


@pytest.mark.skipif(os.name != "nt", reason="Requires native cmd.exe")
def test_cmd_wrapper_reports_missing_repository_launcher(tmp_path, venv_template):
    fixture = make_project(tmp_path, venv_template)
    (fixture.root / "scripts" / POWERSHELL_LAUNCHER.name).unlink()
    command_text = f'call "{fixture.root / CMD_LAUNCHER.name}" -ValidateOnly'

    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", command_text],
        capture_output=True,
        text=True,
        env=fixture.env,
        check=False,
        timeout=15,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "PowerShell launcher was not found" in combined
    assert "Gmail Organizer did not start" in combined


@pytest.mark.skipif(os.name != "nt", reason="Requires native Windows PowerShell fallback")
def test_cmd_wrapper_falls_back_to_windows_powershell(tmp_path, venv_template):
    fixture = make_project(tmp_path, venv_template)
    system_root = Path(os.environ["SystemRoot"])
    environment = fixture.env.copy()
    environment["PATH"] = os.pathsep.join(
        [
            str(system_root / "System32"),
            str(system_root / "System32" / "WindowsPowerShell" / "v1.0"),
        ]
    )
    command_text = (
        f'call "{fixture.root / CMD_LAUNCHER.name}" '
        f"-ValidateOnly -Port {free_port()}"
    )

    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", command_text],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert parse_plan(result)["Launchable"] is True


@pytest.mark.skipif(os.name != "nt", reason="Requires native cmd.exe")
def test_cmd_wrapper_reports_missing_powershell_without_closing_over_error(tmp_path, venv_template):
    fixture = make_project(tmp_path, venv_template)
    command_directory = tmp_path / "cmd-tools-only"
    command_directory.mkdir()
    system_root = Path(os.environ["SystemRoot"])
    shutil.copy2(system_root / "System32" / "where.exe", command_directory / "where.exe")
    environment = fixture.env.copy()
    environment["PATH"] = str(command_directory)
    command_text = f'call "{fixture.root / CMD_LAUNCHER.name}" -ValidateOnly'

    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", command_text],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=15,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "PowerShell was not found" in combined
    assert "Gmail Organizer did not start" in combined


@pytest.mark.skipif(os.name != "nt", reason="Requires native cmd.exe pause behavior")
def test_cmd_wrapper_keeps_failure_visible_until_keypress(tmp_path, venv_template):
    fixture = make_project(tmp_path, venv_template, client_secret=None)
    environment = fixture.env.copy()
    environment.pop("GMAIL_ORGANIZER_NO_PAUSE", None)
    command_text = (
        f'call "{fixture.root / CMD_LAUNCHER.name}" '
        f"-ValidateOnly -Port {free_port()}"
    )

    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", command_text],
        input="\n",
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=30,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert "client_secret_missing" in combined
    assert "Press any key to close this window" in combined


@pytest.mark.skipif(os.name != "nt", reason="Requires native Windows process-tree semantics")
def test_windows_startup_timeout_removes_spawned_descendant(launcher_fixture):
    child_pid_file = launcher_fixture.root / "child.pid"
    environment = launcher_fixture.env.copy()
    environment.update(
        {
            "FAKE_STREAMLIT_MODE": "spawn_timeout",
            "FAKE_STREAMLIT_DURATION": "10",
            "FAKE_STREAMLIT_CHILD_PID_FILE": str(child_pid_file),
        }
    )

    result = run_launcher_normally(
        launcher_fixture,
        "-Port",
        str(free_port()),
        "-MaxRestarts",
        "0",
        "-StartupTimeoutSeconds",
        "1",
        env=environment,
    )

    assert result.returncode == 1
    child_pid = int(child_pid_file.read_text(encoding="utf-8"))
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, child_pid)
    exit_code = ctypes.c_ulong()
    still_active = bool(
        handle
        and ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        and exit_code.value == 259
    )
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
    assert not still_active, f"descendant process {child_pid} survived taskkill /T"


@pytest.mark.skipif(os.name != "nt", reason="Requires native Windows console control events")
def test_windows_ctrl_break_stops_launcher_and_releases_port(launcher_fixture):
    port = free_port()
    ready_file = launcher_fixture.root / "ready.marker"
    environment = launcher_fixture.env.copy()
    environment.update(
        {
            "FAKE_STREAMLIT_MODE": "clean",
            "FAKE_STREAMLIT_DURATION": "120",
            "FAKE_STREAMLIT_READY_FILE": str(ready_file),
        }
    )
    command = [
        PWSH,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(POWERSHELL_LAUNCHER),
        "-ProjectRoot",
        str(launcher_fixture.root),
        "-NoBrowser",
        "-Port",
        str(port),
        "-MaxRestarts",
        "0",
        "-StartupTimeoutSeconds",
        "5",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not ready_file.exists():
        time.sleep(0.1)
    assert ready_file.exists(), "fixture server never became ready"

    process.send_signal(signal.CTRL_BREAK_EVENT)
    process.communicate(timeout=15)

    released = False
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            released = probe.connect_ex(("127.0.0.1", port)) != 0
        finally:
            probe.close()
        if released:
            break
        time.sleep(0.1)
    assert released


def test_readme_documents_truthful_windows_contract():
    readme = (POWERSHELL_LAUNCHER.parents[1] / "README.md").read_text(encoding="utf-8")

    assert ".\\launch_gmail_organizer.cmd" in readme
    assert "PowerShell 5.1 or PowerShell 7" in readme
    assert "process only" in readme
    assert "does not install" in readme
    assert "Launchable" in readme
    assert "native Windows" in readme
