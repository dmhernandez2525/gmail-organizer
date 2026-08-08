# Gmail Organizer Windows Launcher Repair Report

- **Audit name:** Gmail Organizer Windows Launcher Rejection Repair
- **Agent ID:** `/root/verify_package101c_second` (implementing repair agent)
- **Timestamp:** 2026-08-08 10:50:52 CDT (-0500)
- **Starting report-only commit:** `0f929fd364f761927fb228d6c4b0153279e61a83`
- **Implementation commit:** `509c961d857a455a102d6a9fed50937c94f3bbff`
- **Branch:** `feature/gmail-organizer-powershell-launcher-2026-08-04`
- **Original independent verdict:** Reject pending corrections and native Windows evidence

## Status

**REPAIR IMPLEMENTED AND LOCALLY VERIFIED. RELEASE ACCEPTANCE REMAINS PENDING.**

This is an implementation report, not an independent acceptance. The implementing agent did not
reverse or supersede the original rejection. A separate reviewer must evaluate the implementation
commit and the native Windows job before changing release status.

The original independent report remains byte-for-byte unchanged. Its worktree blob and the blob at
`0f929fd` both hash to `b5ec5d42b9aa55c706d784814c9d9697728415a7`.

## Correction disposition

| Original finding | Repair implemented | Remaining independent evidence |
| --- | --- | --- |
| F-01, no Windows double-click entry point | Added repository-root `launch_gmail_organizer.cmd`. It resolves its own root, quotes the PowerShell script and project root, prefers `pwsh.exe`, falls back to `powershell.exe`, preserves the child exit code, and pauses on failure unless the test-only no-pause environment flag is set. | Native `cmd.exe` cases are committed but were not runnable on macOS. |
| F-02, incomplete Windows setup and overstated validation | README now gives Windows prerequisites, PowerShell-native environment and venv commands before usage, manual bootstrap boundaries, process-only execution-policy scope, validation semantics, and residual OAuth acceptance work. | Documentation still requires independent usability review on supported Windows editions. |
| F-03, false-positive `Launchable` | Launcher now selects only `venv` or `.venv` Python and invokes a repository-owned stdlib validator. Validation fails closed on interpreter execution, full JSON schema and semantic contract, Python version, exact venv prefix, required imports, effective Anthropic configuration, installed-app OAuth JSON shape, and port availability. | Real installed dependency combinations remain a native CI and user-environment concern. |
| F-04, Windows lifetime and readiness unproven | Streamlit is started through the selected Python with `-m streamlit`; readiness is TCP-polled before browser action; startup timeout and clean-before-ready receive distinct failure codes; cleanup uses exact-PID `taskkill /T /F` on Windows; restarts remain bounded. Browser ordering, timeout cleanup, process-tree cleanup, and console signal tests were added. | Real default-browser association, literal Ctrl+C, and console-window close remain manual native acceptance gates. Automated native coverage uses Ctrl+Break because it is reliably targetable to a test process group. |
| F-05, no enforceable native CI | Existing masked pytest success was removed. Added an explicit `windows-latest` job, an explicit PowerShell 7 availability check, native launcher tests, Python line/branch/function gates, and PowerShell line/conditional-branch/function gates. Empty or skip-only PowerShell coverage cannot satisfy the job. | The workflow was not pushed or run by this agent, so the first GitHub-hosted Windows result is still required. |
| F-06, incorrect Anthropic precedence | Process-level `ANTHROPIC_API_KEY` now has strict precedence, including a blank inherited override. The dotenv parser uses the final target assignment, fails on a malformed final override, rejects known placeholders, and does not print values. | Application-level product policy could later choose to make Claude Code mode exempt; this repair deliberately documents and enforces the stricter Windows launcher contract. |

## Implementation summary

### Runtime behavior

- No system Python or system Streamlit fallback remains.
- The selected venv Python must report the selected venv as `sys.prefix` and Python 3.11 or newer.
- Declared runtime packages are checked through their actual import paths, including Google auth
  transport and credentials, OAuth flow, Google API discovery, Streamlit, Anthropic, pandas,
  FastAPI, Uvicorn, and WebSockets.
- `client_secret.json` must be valid JSON with an `installed` object, required nonblank string
  fields, and a nonempty string-only `redirect_uris` array.
- Validator stdout is sanitized JSON. Import output and exception detail are suppressed. The
  PowerShell consumer rejects partial, mistyped, inconsistent, or unsupported validator results.
- The requested port is checked during validation and immediately before process start.
- Browser action occurs only after the child is still alive and the port accepts a TCP connection.
- Normal completion returns success. Fast nonzero exit, clean exit before readiness, readiness
  timeout, restart exhaustion, and validation failure return nonzero.

### Adversarial coverage

Tests cover or assign to native Windows CI:

- project roots with spaces, an ampersand, and Unicode;
- root `.cmd` argument forwarding, missing launcher, missing PowerShell, PowerShell 5.1 fallback,
  and pause-on-error behavior;
- stale Python shims, absent venv, `.venv` fallback, wrong interpreter environment, and missing
  runtime imports;
- process environment precedence, blank inherited overrides, duplicate dotenv keys, malformed
  final overrides, comments, quotes, placeholders, and secret non-disclosure;
- missing, invalid-JSON, wrong-type, `web`-only, incomplete, and malformed installed OAuth
  configurations;
- invalid validator output, incomplete schema, invalid field types, inconsistent semantics,
  unsupported exit codes, and exit/result disagreement;
- occupied validation port and a port-acquisition race immediately before process start;
- readiness-gated browser action, clean exit, fast failure, bounded retry, startup timeout, and
  clean-before-ready failure;
- native Windows descendant cleanup after timeout and a console control signal with port release.

## Reproduced local evidence

| Gate | Result |
| --- | --- |
| Focused validator and launcher suite | PASS, 119 passed and 7 native-Windows skips in 50.56 seconds |
| Stdlib validator coverage runner | PASS, 67 tests; line 99.61%, function 100.00%, source-decision branch 84.38% |
| Instrumented PowerShell launcher coverage | PASS, 52 tests and 7 native-Windows skips; line 196/205 (95.61%), function 13/14 (92.86%), conditional branch 77/82 (93.90%) |
| Ruff on all changed Python production and test utilities | PASS; inherited top-level Ruff configuration deprecation warning only |
| Python byte compilation with an external bytecode cache | PASS |
| PowerShell parser on production launcher and all PowerShell probes/checkers | PASS, zero parser errors |
| Workflow YAML parse | PASS |
| `git diff --check` before implementation commit | PASS |
| Original independent-report preservation | PASS, identical Git blob hash |
| Concrete local-path, private-key, and credential-pattern scan | PASS; fixtures and documented placeholder only |
| Runtime downloader, installer, or web-request scan | PASS, none in `.cmd`, PowerShell, or validator runtime code |

The stdlib Python branch metric excludes interpreter-generated exception-dispatch jumps and the
module entrypoint guard, neither of which is a source decision. The Windows CI job additionally uses
the declared `pytest-cov` dependency and separately enforces formal line, branch, and top-level
function percentages at 80% or higher.

## Honest blockers and residuals

1. **Native Windows execution is not reproduced locally.** `cmd.exe` is unavailable on this macOS
   host. Seven committed cases are therefore skipped locally and must run on `windows-latest`.
2. **The workflow has not run.** No push or network operation was authorized, so native CI and its
   formal Python coverage result remain pending.
3. **PowerShell 5.1 is not installed locally.** Compatibility is parser-reviewed and assigned to the
   native `.cmd` fallback test, not claimed as locally executed.
4. **PSScriptAnalyzer is not installed.** It was not installed because installation was prohibited.
5. **Default browser integration remains external.** The automated probe replaces only the browser
   action and proves it cannot run before the readiness marker. It does not prove a user's Windows
   HTTP association.
6. **Console-window close is not deterministically automated.** Native CI covers Ctrl+Break and port
   release. Literal Ctrl+C and closing the containing console require a manual disposable-process
   acceptance check.
7. **Real OAuth remains manual.** A disposable Desktop-app credential and nonproduction test account
   are required to prove the Google consent flow without risking a real mailbox.
8. **Repository-wide pytest is host-blocked.** The full `tests/` collection stops with 24 inherited
   import errors because the host Python lacks `google_auth_oauthlib` and `googleapiclient`. The
   project venv has runtime packages but lacks pytest and coverage. No package installation was
performed. The focused changed-code suite is independent of that blocker.

No real `.env`, OAuth credential, token, or mailbox content was opened or used. Only isolated
fixture projects and synthetic values were used. No install, browse, network request, push, merge,
deployment, credential mutation, or external-system message occurred.

## Required independent follow-up

1. Review implementation commit `509c961d857a455a102d6a9fed50937c94f3bbff` without relying on this
   implementing agent's conclusions.
2. Run the GitHub Actions Windows job and require every native test and all three coverage metrics
   to pass. Do not accept a skipped or missing coverage artifact.
3. On a disposable Windows 10 or 11 account, double-click the root `.cmd`, verify persistent errors,
   test literal Ctrl+C and console close, and confirm no owned descendant remains.
4. With disposable OAuth credentials and a nonproduction Google account, verify one consent flow
   and default-browser opening after readiness without performing mailbox mutations.
5. Only an independent reviewer should issue an acceptance or change the prior rejection status.

## Repair conclusion

All corrections that can be implemented and exercised safely on the current host are complete in
the implementation commit. The remaining work is evidence collection at native Windows and real
integration boundaries. This report intentionally leaves release acceptance open.
