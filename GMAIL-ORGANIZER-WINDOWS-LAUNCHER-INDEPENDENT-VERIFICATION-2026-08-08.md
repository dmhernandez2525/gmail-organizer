# Gmail Organizer Windows Launcher Independent Verification

- **Audit name:** Gmail Organizer Windows Launcher Release-Readiness Audit
- **Agent ID:** `/root/verify_package101c_second` (Codex independent verification agent)
- **Timestamp:** 2026-08-08 09:40:12 CDT (-0500)
- **Candidate HEAD:** `0440054fea61bd1d49e682d6139c788d755c527a`
- **Requested base:** `aafed394878640ecfaa229a24bf3084189f65e43`
- **Branch:** `feature/gmail-organizer-powershell-launcher-2026-08-04`
- **Review type:** Candidate-delta review only
- **External activity:** None. No install, browsing, push, merge, deployment, message, or canonical-task edit was performed.

## Exact commit scope

The requested range is a three-commit linear delta from `aafed39`:

1. `61327f75f0d65667be59f9be31541e9cb5b27dbd` - add Windows PowerShell launcher
2. `103f2c321c93c23a18903bcb43852dc1f54f242a` - reject empty quoted Anthropic keys
3. `0440054fea61bd1d49e682d6139c788d755c527a` - retry fast launcher startup failures

The range changes exactly three files:

- `README.md`: 18 added lines
- `scripts/launch_gmail_organizer.ps1`: new, 217 lines
- `tests/test_powershell_launcher.py`: new, 300 lines

No inherited application, authentication, dependency, CI, or packaging file changed in this range.

## Verdict

**REJECT - CORRECTIONS AND NATIVE WINDOWS EVIDENCE REQUIRED.**

The PowerShell logic is disciplined and all 27 committed launcher tests pass locally. The candidate
is a credible command-line PowerShell launcher, but it is not yet proven or documented as a usable
native Windows launcher. It supplies no repository-owned double-click entry point, the README gives
Windows launch commands after a POSIX-only installation flow, and `-ValidateOnly` reports
`Launchable = true` after presence checks that do not establish a healthy virtual environment,
Python interpreter, dependency set, or valid authentication configuration. Native Windows process
lifetime, Ctrl+C cleanup, and the real `streamlit.exe`/`.cmd` process boundary remain untested.

The candidate can be reconsidered after the documentation claims are narrowed or the missing
behavior is implemented and verified on native Windows.

## Findings

### F-01 - High - No repository-owned Windows double-click experience exists

The candidate adds only a `.ps1` file. It does not add a `.cmd`/`.bat` wrapper, signed launcher,
shortcut installer, or documented file association. `README.md:312-317` instructs the user to open
PowerShell, change directory, and invoke the script manually.

That is a valid command-line workflow, but it is not a default Windows double-click workflow. The
README also does not state the required PowerShell edition/version, explain execution-policy
behavior, or ensure that an error remains visible when a user invokes `Run with PowerShell` and the
temporary console exits.

If double-click usability is required, the requirement is missing. If the intended scope is only a
PowerShell command, the artifact and documentation must say so explicitly and treat double-click as
an unimplemented follow-up.

### F-02 - High - The Windows setup documentation is incomplete and overstates validation

The new Windows usage block follows installation instructions that remain POSIX-specific:

- `README.md:271-278` uses `cp` and `nano`;
- `README.md:289-294` uses `python3`, `source venv/bin/activate`, and a POSIX venv path; and
- the prerequisites at `README.md:256-261` do not name a supported Windows version or PowerShell
  version.

A new Windows user cannot follow the documented installation path in standard PowerShell without
translating commands that the README does not provide.

`README.md:325` also says the launcher checks the virtual environment and authentication
configuration. The code does less:

- `Resolve-StreamlitCommand` accepts a system `streamlit` from `PATH`, so a project venv is not
  required or verified;
- no Python interpreter, supported Python version, venv health, or required import is checked;
- `client_secret.json` is checked only for file presence, not JSON validity or OAuth shape; and
- the Anthropic key check establishes only that one `.env` assignment appears nonempty.

The README should either provide complete Windows setup instructions and describe these as
presence checks, or the launcher should perform the stronger checks it currently claims.

### F-03 - High - `Launchable = true` is not an established launchability result

`New-LaunchPlan` sets `Launchable = $true` unconditionally after locating `app.py`, `.env`, and a
Streamlit command. It does not execute a harmless Streamlit version/import probe or prove that the
selected console-script shim points to a valid interpreter and installed application dependencies.

Concrete false-positive cases include a stale or corrupt `venv/Scripts/streamlit.exe`, a system
Streamlit tied to the wrong Python environment, missing application dependencies, an occupied port,
or invalid OAuth JSON. Those cases can pass `-ValidateOnly` and then fail at startup.

The launcher does not create or repair a venv, and that is a reasonable safety boundary. It must,
however, document that bootstrap is manual and avoid calling a presence-only plan `Launchable`.
Alternatively, it can add non-mutating interpreter and import/version probes with clear results.

### F-04 - Medium - Native Windows process lifetime and shutdown remain unproven

The local tests prove that PowerShell waits for a POSIX fixture process, propagates clean and
nonzero exits, retries a fast failure within the configured bound, and calls `Stop-Process` only for
the PID returned by `Start-Process`.

They do not prove the corresponding native Windows behavior:

- the Windows-layout test creates a text file named `streamlit.exe` but never executes it;
- the three normal-launch tests are explicitly POSIX-only and will skip on Windows;
- no test sends Ctrl+C, closes the console, or verifies that a real Windows Streamlit process and
  all required descendants terminate;
- the launcher also supports `streamlit.cmd`, where the returned process can be a command wrapper;
  cleanup still targets only that one returned PID; and
- browser launch occurs after a fixed two-second sleep, not after a readiness check.

Stopping only the owned PID is safer than a broad process-name kill and is verified. Complete
Streamlit shutdown, the README's Ctrl+C instruction, absence of orphaned descendants, default
browser behavior, and error visibility are native Windows acceptance gates.

### F-05 - Medium - The committed test suite does not enforce Windows lifecycle behavior in CI

All 27 tests are module-skipped when `pwsh` is unavailable. The existing CI job runs on Ubuntu and
does not explicitly provision or version-pin PowerShell. Even if the runner image supplies `pwsh`,
the tests execute against Linux process behavior. The inherited CI test command also masks any
pytest failure with `|| echo`. No Windows job exists.

Even on a Windows runner, the only three normal process-lifecycle tests skip because they require a
POSIX fixture executable. The current suite therefore provides valuable parser, validation-plan,
and local cross-platform contract coverage, but it does not continuously exercise native Windows
launch, stop, restart, or browser behavior.

### F-06 - Low - Anthropic configuration detection can disagree with application semantics

`Test-AnthropicKeyConfigured` safely avoids printing the value and correctly rejects the tested
empty/comment forms. Two semantic gaps remain:

- it checks only `.env`, while the application also inherits a process-level
  `ANTHROPIC_API_KEY`; a valid inherited key can still produce a warning; and
- it returns on the first nonempty assignment, while dotenv-style duplicate keys can be resolved by
  a later assignment, producing a false positive or false negative.

The warning is non-blocking, so this is not a launch failure. The field should be described as a
heuristic presence check or aligned with the application's effective environment resolution.

## Verified behavior

The following candidate behavior checked out:

- **PowerShell syntax:** The PowerShell 7.3.6 parser reports zero errors.
- **Current argument quoting:** `Start-Process` receives the executable path and working directory
  as dedicated parameters. Every current child argument is a fixed token or validated integer, so
  no user-controlled shell string is assembled.
- **Project-root paths:** Default root resolution uses `$PSScriptRoot`; overrides use
  `Resolve-Path -LiteralPath`; child paths use `Join-Path`. Local tests cover a project root with
  spaces.
- **Interpreter-command precedence:** Windows `venv/Scripts/streamlit.exe`, then `.cmd`, then the
  POSIX venv command, then a PATH fallback are considered in deterministic order. Discovery of the
  fake Windows `.exe` path is tested, though execution is not.
- **Bounded restarts:** `MaxRestarts` is range-validated from 0 through 100. The default is three
  restart attempts, and both immediate and delayed nonzero exits are bounded.
- **Local error propagation:** Missing root/app/.env/Streamlit failures return 1 with actionable
  messages. A child exit code 7 becomes launcher exit 1 after the configured retry bound. A child
  exit code 0 returns success.
- **Browser control:** `-NoBrowser` suppresses automatic browser launch in tested process paths.
  The browser-open branch itself remains a native acceptance gate.
- **Narrow cleanup:** The source contains no process-name kill and calls `Stop-Process` only with
  the PID returned by `Start-Process`.
- **Secret handling:** Validation emits paths and boolean presence flags but not `.env` values.
  Tests confirm a sentinel key is absent from stdout and stderr. No concrete API key, OAuth secret,
  or user-specific home path was added by the delta.
- **No downloader or network action:** The launcher contains no web request, remote execution, or
  dependency installation behavior.
- **Portability:** No concrete user path is embedded. The only `/Users/` text in the delta is a
  generic negative assertion in the test file.
- **Git hygiene before report:** The requested candidate was clean at the exact requested HEAD.

## Reproduced checks

| Check | Result |
| --- | --- |
| Launcher pytest suite, verbose then final quiet rerun | PASS twice, 27/27 in 29.19 and 28.84 seconds |
| Direct PowerShell parser check | PASS, 0 parser errors |
| `ruff check tests/test_powershell_launcher.py` | PASS; inherited Ruff configuration deprecation warning only |
| `python3 -m py_compile tests/test_powershell_launcher.py` with external bytecode cache | PASS |
| Real-project `-ValidateOnly -NoBrowser -MaxRestarts 0` | PASS, exit 0; sanitized JSON only |
| `git diff --check aafed39..0440054` | PASS |
| Concrete path and credential-literal scan of the three changed files | PASS; documented placeholder and test sentinels only |
| PSScriptAnalyzer | NOT RUN; module is not installed and installation was prohibited |

## Inherited auth-suite dependency blocker

The launcher tests do not import the application authentication stack. As a separate boundary
check, the unchanged auth test was attempted:

- the host interpreter collected `tests/test_auth.py` with exit 2 because
  `google_auth_oauthlib` is not installed; and
- the existing project venv contains `google_auth_oauthlib` and Streamlit but cannot run the test
  because it does not contain pytest.

`tests/test_auth.py`, `gmail_organizer/auth.py`, `requirements.txt`, and `pyproject.toml` are all
unchanged from `aafed39`. No install was authorized. This is an inherited local dependency/tooling
blocker, not a launcher regression, and it does not reduce the reproduced 27/27 launcher result.
Native Google OAuth browser flow on Windows remains a separate integration gate.

## Residual native Windows gates

Before calling the launcher Windows-ready, verify on supported Windows versions and PowerShell
editions:

1. standard `venv/Scripts/streamlit.exe` execution with a project path containing spaces and Unicode;
2. the `.cmd` and PATH fallback behavior, or remove unsupported fallback forms;
3. PowerShell execution-policy and script-origin behavior;
4. an explicit decision and test for double-click versus terminal-only use;
5. Ctrl+C, console-close, normal exit, startup crash, restart exhaustion, and descendant cleanup;
6. default-browser launch only after server readiness, plus `-NoBrowser`;
7. port-in-use behavior and error visibility;
8. missing, malformed, and valid Google OAuth configuration without exposing values; and
9. one safe first-time OAuth flow with disposable credentials and no real mailbox action.

## Required correction set

1. Add complete Windows setup and supported-version documentation, including manual venv bootstrap
   and safe execution-policy expectations.
2. Either add a deliberate double-click entry point with persistent actionable errors or explicitly
   scope the feature to an already-open PowerShell session.
3. Rename/narrow `Launchable` and the README validation claim, or add non-mutating interpreter,
   dependency, and configuration probes.
4. Add native Windows tests for a real executable process boundary, Ctrl+C, cleanup, restart, and
   browser readiness. Ensure CI cannot silently skip or mask the suite.
5. Validate or redesign process ownership when a launcher shim or `.cmd` wrapper creates descendants.
6. Align Anthropic presence reporting with inherited environment and dotenv precedence, or label it
   as a heuristic warning.

After correction, rerun the exact 27 tests, parser/Ruff/compile/static checks, native Windows
lifecycle matrix, and clean-state verification. Do not treat the inherited auth dependency blocker
as evidence against this delta, but do close it before claiming full application-suite validation.
