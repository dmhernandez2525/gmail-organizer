#!/usr/bin/env python3
"""Fail-closed, secret-safe runtime validation for the desktop launcher."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any

MINIMUM_PYTHON = (3, 11)
RUNTIME_MODULES = {
    "anthropic": "anthropic",
    "dotenv": "dotenv",
    "fastapi": "fastapi",
    "google-auth": "google.auth.transport.requests",
    "google-auth credentials": "google.oauth2.credentials",
    "google-auth-httplib2": "google_auth_httplib2",
    "google-auth-oauthlib": "google_auth_oauthlib.flow",
    "google-api-python-client": "googleapiclient.discovery",
    "pandas": "pandas",
    "pydantic": "pydantic",
    "streamlit": "streamlit",
    "uvicorn": "uvicorn",
    "websockets": "websockets",
}
PLACEHOLDER_KEYS = {
    "changeme",
    "replace-me",
    "replace-this-key",
    "sk-ant-your-key-here",
    "your-api-key",
    "your-key-here",
}
ENV_ASSIGNMENT = re.compile(
    r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$"
)


def add_error(errors: list[dict[str, str]], code: str, message: str) -> None:
    errors.append({"Code": code, "Message": message})


def same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def parse_double_quoted_value(raw: str) -> tuple[str | None, bool]:
    escaped = False
    closing_index: int | None = None
    for index, character in enumerate(raw[1:], start=1):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            closing_index = index
            break

    if closing_index is None:
        return None, False

    trailing = raw[closing_index + 1 :].strip()
    if trailing and not trailing.startswith("#"):
        return None, False

    quoted = raw[: closing_index + 1]
    try:
        return json.loads(quoted), True
    except json.JSONDecodeError:
        return None, False


def parse_env_value(raw: str) -> tuple[str | None, bool]:
    value = raw.strip()
    if not value:
        return "", True

    if value.startswith("'"):
        match = re.fullmatch(r"'([^']*)'\s*(?:#.*)?", value)
        return (match.group(1), True) if match else (None, False)

    if value.startswith('"'):
        return parse_double_quoted_value(value)

    if "${" in value:
        return None, False

    return re.sub(r"\s+#.*$", "", value).strip(), True


def read_effective_dotenv_value(
    env_path: Path, key: str, errors: list[dict[str, str]]
) -> str | None:
    if not env_path.is_file():
        return None

    try:
        lines = env_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        add_error(errors, "env_unreadable", ".env could not be read as UTF-8 text.")
        return None

    target_prefix = re.compile(rf"^\s*(?:export\s+)?{re.escape(key)}(?:\s|=|$)")
    effective_raw: str | None = None
    effective_line: int | None = None
    assignment_found = False
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        match = ENV_ASSIGNMENT.fullmatch(line)
        if match and match.group("key") == key:
            assignment_found = True
            effective_raw = match.group("value")
            effective_line = line_number
            continue
        if not target_prefix.match(line):
            continue

        assignment_found = True
        effective_raw = None
        effective_line = line_number

    if not assignment_found:
        return None

    parsed, valid = parse_env_value(effective_raw) if effective_raw is not None else (None, False)
    if not valid:
        add_error(
            errors,
            "env_key_malformed",
            f"{key} has unsupported or malformed syntax on .env line {effective_line}.",
        )
        return None

    return parsed


def validate_anthropic_key(
    env_path: Path, environ: dict[str, str], errors: list[dict[str, str]]
) -> tuple[bool, str]:
    if "ANTHROPIC_API_KEY" in environ:
        value = environ["ANTHROPIC_API_KEY"]
        source = "process_environment"
    else:
        value = read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors)
        source = "dotenv" if value is not None else "missing"

    normalized = value.strip() if isinstance(value, str) else ""
    configured = bool(normalized) and normalized.lower() not in PLACEHOLDER_KEYS
    if not configured:
        add_error(
            errors,
            "anthropic_key_invalid",
            "ANTHROPIC_API_KEY is missing, blank, malformed, or still a placeholder.",
        )
    return configured, source


def validate_client_secret(path: Path, errors: list[dict[str, str]]) -> bool:
    if not path.is_file():
        add_error(
            errors,
            "client_secret_missing",
            "client_secret.json is required for the Windows Gmail OAuth workflow.",
        )
        return False

    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        add_error(errors, "client_secret_invalid_json", "client_secret.json is not valid JSON.")
        return False

    if not isinstance(document, dict) or not isinstance(document.get("installed"), dict):
        add_error(
            errors,
            "client_secret_invalid_shape",
            "client_secret.json must contain an installed desktop-app credential object.",
        )
        return False

    installed = document["installed"]
    required_strings = ("client_id", "client_secret", "auth_uri", "token_uri")
    missing = [
        field
        for field in required_strings
        if not isinstance(installed.get(field), str) or not installed[field].strip()
    ]
    redirect_uris = installed.get("redirect_uris")
    redirects_valid = (
        isinstance(redirect_uris, list)
        and bool(redirect_uris)
        and all(isinstance(uri, str) and bool(uri.strip()) for uri in redirect_uris)
    )
    if missing or not redirects_valid:
        add_error(
            errors,
            "client_secret_invalid_shape",
            "The installed OAuth credential is missing required desktop-app fields.",
        )
        return False
    return True


def validate_runtime_modules(errors: list[dict[str, str]]) -> tuple[bool, list[str]]:
    unavailable: list[str] = []
    for label, module_name in RUNTIME_MODULES.items():
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                importlib.import_module(module_name)
        except Exception:
            unavailable.append(label)

    if unavailable:
        add_error(
            errors,
            "runtime_dependencies_unavailable",
            "Required runtime imports failed: " + ", ".join(sorted(unavailable)) + ".",
        )
    return not unavailable, sorted(unavailable)


def validate_port(port: int, errors: list[dict[str, str]]) -> bool:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", port))
    except OSError:
        add_error(errors, "port_unavailable", f"Local port {port} is already in use.")
        return False
    finally:
        listener.close()
    return True


def validate_runtime(project_root: Path, expected_venv: Path, port: int) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    project_root = project_root.resolve()
    expected_venv = expected_venv.resolve()
    app_path = project_root / "app.py"
    env_path = project_root / ".env"
    client_secret_path = project_root / "client_secret.json"

    app_present = app_path.is_file()
    if not app_present:
        add_error(errors, "app_missing", "app.py was not found in the selected project root.")

    python_version_valid = sys.version_info >= MINIMUM_PYTHON
    if not python_version_valid:
        add_error(errors, "python_version_unsupported", "Python 3.11 or newer is required.")

    venv_valid = same_path(Path(sys.prefix), expected_venv)
    if not venv_valid:
        add_error(
            errors,
            "wrong_python_environment",
            "The selected Python executable is not running from the selected project venv.",
        )

    dependencies_valid, unavailable_modules = validate_runtime_modules(errors)
    key_valid, key_source = validate_anthropic_key(env_path, os.environ, errors)
    client_secret_valid = validate_client_secret(client_secret_path, errors)
    port_available = validate_port(port, errors)

    return {
        "SchemaVersion": 1,
        "Launchable": not errors,
        "AppPresent": app_present,
        "PythonExecutable": str(Path(sys.executable).resolve()),
        "PythonVersion": ".".join(str(part) for part in sys.version_info[:3]),
        "PythonVersionValid": python_version_valid,
        "VenvRoot": str(expected_venv),
        "VenvValid": venv_valid,
        "DependenciesValid": dependencies_valid,
        "UnavailableDependencies": unavailable_modules,
        "AnthropicKeyConfigured": key_valid,
        "AnthropicKeySource": key_source,
        "ClientSecretValid": client_secret_valid,
        "PortAvailable": port_available,
        "Errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--expected-venv", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int, choices=range(1, 65536))
    return parser


def build_internal_failure(expected_venv: Path, error_name: str) -> dict[str, Any]:
    return {
        "SchemaVersion": 1,
        "Launchable": False,
        "AppPresent": False,
        "PythonExecutable": str(Path(sys.executable).resolve()),
        "PythonVersion": ".".join(str(part) for part in sys.version_info[:3]),
        "PythonVersionValid": False,
        "VenvRoot": str(expected_venv.resolve()),
        "VenvValid": False,
        "DependenciesValid": False,
        "UnavailableDependencies": sorted(RUNTIME_MODULES),
        "AnthropicKeyConfigured": False,
        "AnthropicKeySource": "missing",
        "ClientSecretValid": False,
        "PortAvailable": False,
        "Errors": [
            {
                "Code": "validator_internal_error",
                "Message": f"Runtime validation failed internally ({error_name}).",
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_runtime(args.project_root, args.expected_venv, args.port)
    except Exception as error:
        result = build_internal_failure(args.expected_venv, type(error).__name__)
    print(json.dumps(result, sort_keys=True))
    if result["Launchable"]:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
