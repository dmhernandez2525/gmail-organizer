"""Local-only fixture helpers for launcher contract tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
import venv
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POWERSHELL_LAUNCHER = REPO_ROOT / "scripts" / "launch_gmail_organizer.ps1"
RUNTIME_VALIDATOR = REPO_ROOT / "scripts" / "validate_gmail_organizer_runtime.py"
CMD_LAUNCHER = REPO_ROOT / "launch_gmail_organizer.cmd"
POWERSHELL_COVERAGE_DRIVER = REPO_ROOT / "tests" / "instrument_powershell_launcher.ps1"
PWSH = shutil.which("pwsh")


VALID_CLIENT_SECRET = {
    "installed": {
        "client_id": "fixture-client-id",
        "client_secret": "fixture-client-secret",
        "auth_uri": "https://fixture.invalid/auth",
        "token_uri": "https://fixture.invalid/token",
        "redirect_uris": ["http://localhost"],
    }
}


STREAMLIT_MAIN = r'''from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def argument_value(name: str, default: str) -> str:
    try:
        return sys.argv[sys.argv.index(name) + 1]
    except (ValueError, IndexError):
        return default


mode = os.environ.get("FAKE_STREAMLIT_MODE", "clean")
port = int(argument_value("--server.port", "8501"))
if mode in {"fast_fail", "fast_clean"}:
    default_exit = "0" if mode == "fast_clean" else "7"
    raise SystemExit(int(os.environ.get("FAKE_STREAMLIT_EXIT", default_exit)))
if mode == "retry_once":
    marker = Path(os.environ["FAKE_STREAMLIT_ATTEMPT_FILE"])
    if not marker.exists():
        marker.write_text("attempted\n", encoding="utf-8")
        raise SystemExit(7)
if mode in {"timeout", "spawn_timeout"}:
    child = None
    if mode == "spawn_timeout":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        Path(os.environ["FAKE_STREAMLIT_CHILD_PID_FILE"]).write_text(
            str(child.pid), encoding="utf-8"
        )
    time.sleep(float(os.environ.get("FAKE_STREAMLIT_DURATION", "10")))
    raise SystemExit(0)

time.sleep(float(os.environ.get("FAKE_STREAMLIT_READY_DELAY", "0")))
listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("127.0.0.1", port))
listener.listen(8)
ready_file = os.environ.get("FAKE_STREAMLIT_READY_FILE")
if ready_file:
    Path(ready_file).write_text("ready\n", encoding="utf-8")
time.sleep(float(os.environ.get("FAKE_STREAMLIT_DURATION", "1")))
listener.close()
raise SystemExit(int(os.environ.get("FAKE_STREAMLIT_EXIT", "0")))
'''


@dataclass
class LauncherFixture:
    root: Path
    env: dict[str, str]
    stubs: Path
    venv_root: Path


def build_venv_template(path: Path) -> Path:
    venv.EnvBuilder(with_pip=False, clear=True).create(path)
    return path


def copy_venv(template: Path, destination: Path) -> None:
    shutil.copytree(template, destination, symlinks=True)


def write_runtime_stubs(stubs: Path) -> None:
    modules = {
        "anthropic.py": "",
        "dotenv.py": "",
        "fastapi.py": "",
        "google/__init__.py": "",
        "google/auth/__init__.py": "",
        "google/auth/transport/__init__.py": "",
        "google/auth/transport/requests.py": "",
        "google/oauth2/__init__.py": "",
        "google/oauth2/credentials.py": "",
        "google_auth_httplib2.py": "",
        "google_auth_oauthlib/__init__.py": "",
        "google_auth_oauthlib/flow.py": "",
        "googleapiclient/__init__.py": "",
        "googleapiclient/discovery.py": "",
        "googleapiclient/errors.py": "",
        "pandas.py": "",
        "pydantic.py": "",
        "streamlit/__init__.py": "",
        "streamlit/__main__.py": STREAMLIT_MAIN,
        "uvicorn.py": "",
        "websockets.py": "",
    }
    for relative_path, body in modules.items():
        target = stubs / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def make_project(
    tmp_path: Path,
    venv_template: Path,
    *,
    name: str = "gmail-organizer fixture",
    env_text: str | None = "ANTHROPIC_API_KEY=fixture-key\n",
    client_secret: object | None = VALID_CLIENT_SECRET,
) -> LauncherFixture:
    project_root = tmp_path / name
    project_root.mkdir(parents=True)
    (project_root / "scripts").mkdir()
    shutil.copy2(POWERSHELL_LAUNCHER, project_root / "scripts" / POWERSHELL_LAUNCHER.name)
    shutil.copy2(RUNTIME_VALIDATOR, project_root / "scripts" / RUNTIME_VALIDATOR.name)
    shutil.copy2(CMD_LAUNCHER, project_root / CMD_LAUNCHER.name)
    (project_root / "app.py").write_text("# fixture\n", encoding="utf-8")
    if env_text is not None:
        (project_root / ".env").write_text(env_text, encoding="utf-8")
    if client_secret is not None:
        (project_root / "client_secret.json").write_text(
            json.dumps(client_secret), encoding="utf-8"
        )

    venv_root = project_root / "venv"
    copy_venv(venv_template, venv_root)
    stubs = project_root / "test-runtime-stubs"
    write_runtime_stubs(stubs)

    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env["PYTHONPATH"] = str(stubs)
    env["GMAIL_ORGANIZER_NO_PAUSE"] = "1"
    return LauncherFixture(project_root, env, stubs, venv_root)


def run_launcher(
    fixture: LauncherFixture,
    *extra_args: str,
    env: dict[str, str] | None = None,
    timeout: int = 20,
) -> subprocess.CompletedProcess[str]:
    launcher_arguments = [
        "-ValidateOnly",
        "-ProjectRoot",
        str(fixture.root),
        *extra_args,
    ]
    environment = (env or fixture.env).copy()
    command = instrumented_launcher_command(launcher_arguments, environment)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=timeout,
    )


def run_launcher_normally(
    fixture: LauncherFixture,
    *extra_args: str,
    env: dict[str, str] | None = None,
    timeout: int = 25,
) -> subprocess.CompletedProcess[str]:
    launcher_arguments = [
        "-ProjectRoot",
        str(fixture.root),
        "-NoBrowser",
        *extra_args,
    ]
    environment = (env or fixture.env).copy()
    command = instrumented_launcher_command(launcher_arguments, environment)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=timeout,
    )


def project_python(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def instrumented_launcher_command(
    launcher_arguments: list[str],
    environment: dict[str, str],
    launcher_path: Path = POWERSHELL_LAUNCHER,
) -> list[str]:
    command = [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-File"]
    if environment.get("GMAIL_ORGANIZER_PS_COVERAGE_FILE"):
        launcher_parameters: dict[str, str | bool] = {}
        index = 0
        while index < len(launcher_arguments):
            parameter_name = launcher_arguments[index].removeprefix("-")
            if parameter_name in {"ValidateOnly", "NoBrowser"}:
                launcher_parameters[parameter_name] = True
                index += 1
            else:
                launcher_parameters[parameter_name] = launcher_arguments[index + 1]
                index += 2
        environment["GMAIL_ORGANIZER_PS_PARAMETERS_JSON"] = json.dumps(launcher_parameters)
        environment["GMAIL_ORGANIZER_PS_COVERAGE_RUN_ID"] = uuid.uuid4().hex
        return command + [
            str(POWERSHELL_COVERAGE_DRIVER),
            "-LauncherPath",
            str(launcher_path),
        ]
    return command + [str(launcher_path), *launcher_arguments]


def prepare_powershell_coverage_environment(environment: dict[str, str]) -> None:
    if environment.get("GMAIL_ORGANIZER_PS_COVERAGE_FILE"):
        environment["GMAIL_ORGANIZER_PS_COVERAGE_RUN_ID"] = uuid.uuid4().hex


def isolated_test_environment(stubs: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("ANTHROPIC_API_KEY", None)
    environment["PYTHONPATH"] = str(stubs)
    return environment


def current_python_executable() -> Path:
    return Path(sys.executable).resolve()
