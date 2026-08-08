"""Unit tests for the secret-safe launcher runtime validator."""

from __future__ import annotations

import json
import runpy
import socket
import sys
from pathlib import Path

import pytest

from scripts import validate_gmail_organizer_runtime as validator


@pytest.mark.parametrize(
    ("raw", "expected", "valid"),
    [
        ("configured", "configured", True),
        ("configured # note", "configured", True),
        ("configured#literal", "configured#literal", True),
        ("'configured # literal' # note", "configured # literal", True),
        ('"configured value" # note', "configured value", True),
        ('"configured value"', "configured value", True),
        ('"configured value"#note', "configured value", True),
        ('"configured\\nvalue"', "configured\nvalue", True),
        ("", "", True),
        ("'unterminated", None, False),
        ('"unterminated', None, False),
        ('"valid" trailing', None, False),
        ("${EXPANSION}", None, False),
    ],
)
def test_parse_env_value_is_fail_closed(raw, expected, valid):
    assert validator.parse_env_value(raw) == (expected, valid)


def test_dotenv_duplicate_key_uses_last_assignment(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=first\nANTHROPIC_API_KEY=second\n", encoding="utf-8"
    )
    errors = []

    value = validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors)

    assert value == "second"
    assert errors == []


def test_dotenv_malformed_last_assignment_fails_closed(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        'ANTHROPIC_API_KEY=first\nANTHROPIC_API_KEY="unterminated\n', encoding="utf-8"
    )
    errors = []

    value = validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors)

    assert value is None
    assert [error["Code"] for error in errors] == ["env_key_malformed"]
    assert "first" not in json.dumps(errors)


def test_dotenv_valid_last_assignment_supersedes_malformed_earlier_value(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        'ANTHROPIC_API_KEY="unterminated\nANTHROPIC_API_KEY=effective\n',
        encoding="utf-8",
    )
    errors = []

    value = validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors)

    assert value == "effective"
    assert errors == []


def test_dotenv_bare_last_key_is_a_malformed_override(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=first\nANTHROPIC_API_KEY\n",
        encoding="utf-8",
    )
    errors = []

    value = validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors)

    assert value is None
    assert [error["Code"] for error in errors] == ["env_key_malformed"]


def test_dotenv_missing_is_not_an_io_error(tmp_path):
    errors = []
    assert validator.read_effective_dotenv_value(tmp_path / ".env", "KEY", errors) is None
    assert errors == []


def test_empty_dotenv_has_no_effective_assignment(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    errors = []

    assert validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors) is None
    assert errors == []


def test_whitespace_and_comment_only_dotenv_has_no_effective_assignment(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("   \n# comment\n", encoding="utf-8")
    errors = []

    assert validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors) is None
    assert errors == []


def test_dotenv_with_only_unrelated_assignment_has_no_effective_key(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("UNRELATED=value\n", encoding="utf-8")
    errors = []

    assert validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors) is None
    assert errors == []


def test_dotenv_ignores_comments_and_unrelated_assignments(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment\nUNRELATED=value\nANTHROPIC_API_KEY=effective\n", encoding="utf-8"
    )
    errors = []

    value = validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors)

    assert value == "effective"
    assert errors == []


def test_dotenv_invalid_utf8_fails_without_exposing_bytes(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_bytes(b"ANTHROPIC_API_KEY=\xff\n")
    errors = []

    value = validator.read_effective_dotenv_value(env_path, "ANTHROPIC_API_KEY", errors)

    assert value is None
    assert errors == [{"Code": "env_unreadable", "Message": ".env could not be read as UTF-8 text."}]


def test_invalid_double_quoted_escape_fails_closed():
    assert validator.parse_env_value('"invalid\\q"') == (None, False)


def test_process_environment_takes_precedence_over_dotenv(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("ANTHROPIC_API_KEY=dotenv-key\n", encoding="utf-8")
    errors = []

    configured, source = validator.validate_anthropic_key(
        env_path, {"ANTHROPIC_API_KEY": "process-key"}, errors
    )

    assert configured is True
    assert source == "process_environment"
    assert errors == []


def test_blank_process_environment_does_not_fall_back_to_dotenv(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("ANTHROPIC_API_KEY=dotenv-key\n", encoding="utf-8")
    errors = []

    configured, source = validator.validate_anthropic_key(
        env_path, {"ANTHROPIC_API_KEY": ""}, errors
    )

    assert configured is False
    assert source == "process_environment"
    assert [error["Code"] for error in errors] == ["anthropic_key_invalid"]


def test_missing_key_without_dotenv_is_rejected(tmp_path):
    errors = []

    configured, source = validator.validate_anthropic_key(tmp_path / ".env", {}, errors)

    assert configured is False
    assert source == "missing"
    assert [error["Code"] for error in errors] == ["anthropic_key_invalid"]


@pytest.mark.parametrize("placeholder", sorted(validator.PLACEHOLDER_KEYS))
def test_placeholder_keys_are_rejected(tmp_path, placeholder):
    env_path = tmp_path / ".env"
    env_path.write_text(f"ANTHROPIC_API_KEY={placeholder}\n", encoding="utf-8")
    errors = []

    configured, source = validator.validate_anthropic_key(env_path, {}, errors)

    assert configured is False
    assert source == "dotenv"
    assert errors[0]["Code"] == "anthropic_key_invalid"


def valid_client_secret_document():
    return {
        "installed": {
            "client_id": "fixture-id",
            "client_secret": "fixture-secret",
            "auth_uri": "https://fixture.invalid/auth",
            "token_uri": "https://fixture.invalid/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def test_client_secret_valid_shape_passes_without_outputting_values(tmp_path):
    secret_path = tmp_path / "client_secret.json"
    secret_path.write_text(json.dumps(valid_client_secret_document()), encoding="utf-8")
    errors = []

    assert validator.validate_client_secret(secret_path, errors) is True
    assert errors == []


@pytest.mark.parametrize(
    ("document", "code"),
    [
        ("string-document", "client_secret_invalid_shape"),
        ({}, "client_secret_invalid_shape"),
        ({"web": {}}, "client_secret_invalid_shape"),
        ({"installed": "not-an-object"}, "client_secret_invalid_shape"),
        ({"installed": {}}, "client_secret_invalid_shape"),
        (
            {
                "installed": {
                    "client_id": "id",
                    "client_secret": "secret",
                    "auth_uri": "auth",
                    "token_uri": "token",
                    "redirect_uris": [],
                }
            },
            "client_secret_invalid_shape",
        ),
        (
            {
                "installed": {
                    "client_id": "id",
                    "client_secret": "secret",
                    "auth_uri": "auth",
                    "token_uri": "token",
                    "redirect_uris": "http://localhost",
                }
            },
            "client_secret_invalid_shape",
        ),
        (
            {
                "installed": {
                    "client_id": "id",
                    "client_secret": "secret",
                    "auth_uri": "auth",
                    "token_uri": "token",
                    "redirect_uris": [7],
                }
            },
            "client_secret_invalid_shape",
        ),
        (
            {
                "installed": {
                    "client_id": " ",
                    "client_secret": "secret",
                    "auth_uri": "auth",
                    "token_uri": "token",
                    "redirect_uris": [" "],
                }
            },
            "client_secret_invalid_shape",
        ),
    ],
)
def test_client_secret_invalid_shapes_fail(tmp_path, document, code):
    secret_path = tmp_path / "client_secret.json"
    secret_path.write_text(json.dumps(document), encoding="utf-8")
    errors = []

    assert validator.validate_client_secret(secret_path, errors) is False
    assert errors[0]["Code"] == code
    assert "fixture-secret" not in json.dumps(errors)


def test_client_secret_missing_and_invalid_json_fail(tmp_path):
    errors = []
    assert validator.validate_client_secret(tmp_path / "missing.json", errors) is False
    assert errors[0]["Code"] == "client_secret_missing"

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{not json", encoding="utf-8")
    errors = []
    assert validator.validate_client_secret(invalid_path, errors) is False
    assert errors[0]["Code"] == "client_secret_invalid_json"


def test_runtime_module_failures_report_labels_not_exception_text(monkeypatch):
    def fake_import(name):
        if name == "anthropic":
            raise RuntimeError("sensitive exception detail")
        return object()

    monkeypatch.setattr(validator.importlib, "import_module", fake_import)
    errors = []

    valid, unavailable = validator.validate_runtime_modules(errors)

    assert valid is False
    assert unavailable == ["anthropic"]
    serialized = json.dumps(errors)
    assert "anthropic" in serialized
    assert "sensitive exception detail" not in serialized


@pytest.mark.parametrize(("label", "module_name"), sorted(validator.RUNTIME_MODULES.items()))
def test_each_declared_runtime_import_is_independently_required(monkeypatch, label, module_name):
    def fake_import(candidate):
        if candidate == module_name:
            raise ImportError("fixture failure")
        return object()

    monkeypatch.setattr(validator.importlib, "import_module", fake_import)
    errors = []

    valid, unavailable = validator.validate_runtime_modules(errors)

    assert valid is False
    assert unavailable == [label]
    assert errors[0]["Code"] == "runtime_dependencies_unavailable"


def test_runtime_module_success(monkeypatch):
    monkeypatch.setattr(validator.importlib, "import_module", lambda _name: object())
    errors = []
    assert validator.validate_runtime_modules(errors) == (True, [])
    assert errors == []


def test_port_validation_detects_occupied_port():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        errors = []
        assert validator.validate_port(port, errors) is False
        assert errors[0]["Code"] == "port_unavailable"
    finally:
        listener.close()


def test_port_validation_accepts_available_port():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    errors = []
    assert validator.validate_port(port, errors) is True
    assert errors == []


def test_same_path_normalizes_resolved_paths(tmp_path):
    directory = tmp_path / "directory"
    directory.mkdir()
    assert validator.same_path(directory, directory / ".") is True


def test_validate_runtime_assembles_a_launchable_result(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("# fixture\n", encoding="utf-8")
    monkeypatch.setattr(validator, "validate_runtime_modules", lambda _errors: (True, []))
    monkeypatch.setattr(
        validator,
        "validate_anthropic_key",
        lambda _path, _environment, _errors: (True, "process_environment"),
    )
    monkeypatch.setattr(validator, "validate_client_secret", lambda _path, _errors: True)
    monkeypatch.setattr(validator, "validate_port", lambda _port, _errors: True)

    result = validator.validate_runtime(tmp_path, Path(sys.prefix), 8501)

    assert result["Launchable"] is True
    assert result["AppPresent"] is True
    assert result["PythonVersionValid"] is True
    assert result["VenvValid"] is True
    assert result["DependenciesValid"] is True
    assert result["AnthropicKeySource"] == "process_environment"
    assert result["ClientSecretValid"] is True
    assert result["PortAvailable"] is True
    assert result["Errors"] == []


def test_validate_runtime_aggregates_every_failed_prerequisite(monkeypatch, tmp_path):
    def reject_modules(errors):
        validator.add_error(errors, "runtime_dependencies_unavailable", "Unavailable.")
        return False, ["streamlit"]

    def reject_key(_path, _environment, errors):
        validator.add_error(errors, "anthropic_key_invalid", "Invalid.")
        return False, "missing"

    def reject_secret(_path, errors):
        validator.add_error(errors, "client_secret_missing", "Missing.")
        return False

    def reject_port(_port, errors):
        validator.add_error(errors, "port_unavailable", "Unavailable.")
        return False

    monkeypatch.setattr(validator.sys, "version_info", (3, 10, 9))
    monkeypatch.setattr(validator, "validate_runtime_modules", reject_modules)
    monkeypatch.setattr(validator, "validate_anthropic_key", reject_key)
    monkeypatch.setattr(validator, "validate_client_secret", reject_secret)
    monkeypatch.setattr(validator, "validate_port", reject_port)

    result = validator.validate_runtime(tmp_path, tmp_path / "wrong-venv", 8501)

    assert result["Launchable"] is False
    assert result["AppPresent"] is False
    assert result["PythonVersionValid"] is False
    assert result["VenvValid"] is False
    assert result["UnavailableDependencies"] == ["streamlit"]
    assert {error["Code"] for error in result["Errors"]} == {
        "app_missing",
        "python_version_unsupported",
        "wrong_python_environment",
        "runtime_dependencies_unavailable",
        "anthropic_key_invalid",
        "client_secret_missing",
        "port_unavailable",
    }


def test_main_returns_success_for_launchable_result(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        validator,
        "validate_runtime",
        lambda *_args, **_kwargs: {"SchemaVersion": 1, "Launchable": True, "Errors": []},
    )

    exit_code = validator.main(
        [
            "--project-root",
            str(tmp_path),
            "--expected-venv",
            str(tmp_path),
            "--port",
            "8501",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["Launchable"] is True


def test_main_returns_sanitized_internal_error(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        validator,
        "validate_runtime",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("secret detail")),
    )

    exit_code = validator.main(
        [
            "--project-root",
            str(tmp_path),
            "--expected-venv",
            str(tmp_path),
            "--port",
            "8501",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    result = json.loads(output)
    assert result["Errors"][0]["Code"] == "validator_internal_error"
    assert result["Launchable"] is False
    assert result["DependenciesValid"] is False
    assert result["UnavailableDependencies"] == sorted(validator.RUNTIME_MODULES)
    assert result["AnthropicKeySource"] == "missing"
    assert result["VenvRoot"] == str(tmp_path)
    assert "secret detail" not in output


def test_script_entrypoint_runs_the_complete_success_contract(monkeypatch, capsys, tmp_path):
    (tmp_path / "app.py").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=fixture-key\n", encoding="utf-8")
    (tmp_path / "client_secret.json").write_text(
        json.dumps(valid_client_secret_document()), encoding="utf-8"
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(validator.importlib, "import_module", lambda _name: object())
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(validator.__file__),
            "--project-root",
            str(tmp_path),
            "--expected-venv",
            str(Path(sys.prefix)),
            "--port",
            str(port),
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(validator.__file__), run_name="__main__")

    assert exit_info.value.code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["Launchable"] is True
    assert output["AnthropicKeySource"] == "dotenv"
