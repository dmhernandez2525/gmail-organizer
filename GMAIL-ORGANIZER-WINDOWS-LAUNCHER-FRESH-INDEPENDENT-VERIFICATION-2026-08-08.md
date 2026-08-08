# Gmail Organizer Windows Launcher Fresh Independent Verification

- **Audit name:** Gmail Organizer Windows Launcher Repair Acceptance Audit
- **Agent ID:** `/root/review_alerts_fresh` (independent adversarial reviewer)
- **Timestamp:** 2026-08-08 11:40:46 CDT (-0500)
- **Preserved rejection commit:** `0f929fd364f761927fb228d6c4b0153279e61a83`
- **Implementation commit:** `509c961d857a455a102d6a9fed50937c94f3bbff`
- **Repair report commit:** `4cc8ceaa01c88267f08c70e929632cb88c8df3c1`
- **Branch:** `feature/gmail-organizer-powershell-launcher-2026-08-04`
- **Review type:** Fresh independent review of the exact implementation and its report

## Verdict

**REJECT**

The repair closes several original gaps, but the exact implementation is not release-ready. Two
adversarial reproductions demonstrate that its readiness and cleanup contracts can report success
when they did not succeed. The committed CI workflow also fails locally before it can establish the
new acceptance gates. These are behavior and enforcement failures, not merely unexecuted native
Windows acceptance checks.

No implementation file was changed during this review. The isolated adversarial probes were kept
outside the repository under `~/.Trash/` and were not committed.

## Exact scope and integrity

The implementation range from `0f929fd` through `509c961` changes 16 files with 3,059 insertions and
303 deletions. Commit `4cc8cea` adds only the repair report. The preserved rejection report remains
unchanged: its worktree blob and the blob at `0f929fd` are both
`b5ec5d42b9aa55c706d784814c9d9697728415a7`.

The tracked worktree was clean before this report. `git diff --check` and `git fsck --strict`
reported no candidate corruption. `git fsck` listed four dangling trees, which are unrelated
unreachable objects and not evidence of damage to the candidate history.

## Blocking findings

### F-01: High: readiness can belong to an unrelated process

`Wait-GmailOrganizerReady` in `scripts/launch_gmail_organizer.ps1:347-365` considers startup ready
when both of these conditions hold:

1. the launched Python process has not exited; and
2. any TCP listener accepts a connection on the selected port.

It does not prove that the listener belongs to the launched process or that the listener is a
healthy Streamlit application. The final availability check at lines 414-417 releases its temporary
listener before `Start-Process`, so another process can acquire the port between that check and the
readiness poll.

The committed race test at `tests/test_powershell_launcher.py:504-533` occupies the port before
`Start-GmailOrganizer` performs its final availability check. It proves that pre-start occupation
is rejected, but it does not exercise occupation after that check or ownership of the listener used
as readiness evidence.

An isolated failure-injection probe exercised the exact launch and readiness functions while
modeling the missing interleaving at the final availability seam:

- the launch plan validated while the port was free;
- the final check reported the prior free state while an unrelated PowerShell process acquired the
  port before `Start-Process` resumed;
- the synthetic Streamlit child stayed alive but never opened a listener;
- the launcher invoked the browser action, printed its ready message, and returned success; and
- the probe asserted the false browser marker and `FALSE_READY_ACCEPTED` result, with `1 passed`.

This invalidates the claimed readiness and browser gate. A competing local service can be opened in
the browser as Gmail Organizer, and a child that never served Streamlit can still produce launcher
success.

Required correction: readiness must validate an expected application-level response and bind that
response to the launch instance, or otherwise prove listener ownership. Add a deterministic test in
which an unrelated listener wins the post-check race and require launch failure with no browser
action.

### F-02: High: a failed Windows tree kill is ignored

`Stop-OwnedProcessTree` at `scripts/launch_gmail_organizer.ps1:371-397` runs
`taskkill.exe /PID <pid> /T /F` when `taskkill.exe` exists. It does not check the native exit code.
It also discards the Boolean result of `WaitForExit(5000)` and does not verify that the parent or its
descendants stopped. The parent-only `Stop-Process` fallback is used only when `taskkill.exe` cannot
be found, not when it is found and fails.

An isolated failure-injection probe forced the Windows branch and supplied a `taskkill` substitute
that exited 9 without stopping the owned process. The exact function returned after five seconds
while the process was still running and emitted `TASKKILL_FAILURE_LEFT_PROCESS_RUNNING`. The probe
then stopped its own temporary process in a separate cleanup block.

The committed native test covers successful descendant removal, not command failure, access
failure, timeout, or a surviving process. In production, this gap can leave an owned server or
descendant running after timeout or error, then cause the next restart to fail on the occupied port.

Required correction: check the native result, verify termination after the wait, use a safe fallback
where possible, and surface cleanup failure. Add failure-injection coverage and assert both parent
and descendant termination.

### F-03: High: the committed CI workflow is locally known to fail

The implementation removes the old masked pytest command, which is directionally correct, but the
replacement workflow is not currently passable under its own allowed tool versions.

The exact Python-job Ruff command from `.github/workflows/ci.yml:29-35` was run with Ruff 0.15.0,
which satisfies the workflow's `ruff>=0.1.0` declaration. It failed with 34 existing errors in
`gmail_organizer/` and `app.py`. The narrower command covering all changed Python launcher and
validator files passed, so the repair report's changed-file lint claim is accurate. The workflow's
broader enforced command is still red.

The full `tests/` suite was also run with the project Python 3.11.8 venv and an isolated, no-install
pytest 9.0.2 support path. It produced `1200 passed, 7 skipped, 1 failed`. The deterministic failure
is `tests/test_auth.py::TestAuthenticateAccount::test_refreshes_expired_credentials`: the test's
`MagicMock` credential fields cannot be JSON-serialized by `_save_credentials_json`, the refresh
path falls through to OAuth, and the synthetic client configuration is then rejected. A focused
rerun reproduced the same failure.

These are inherited application/test defects, but commit `509c961` makes the broad lint and test
commands mandatory. The workflow cannot currently serve as release evidence until its enforced
commands pass. Waiting for a Windows runner cannot correct the failing Ubuntu job.

Required correction: bring the exact Python-job lint target to green and correct the failing auth
test or its fixture without restoring failure masking. Reproduce the exact CI commands before
requesting another independent acceptance review.

### F-04: Medium: four independent coverage dimensions are not enforced as named

All reported local percentages reproduced above 80 percent, but the committed gates expose three
named metrics, not four:

- Python: `Line`, `Branch`, and `Function`;
- PowerShell: `Line`, `Branch`, and `Function`.

For Python, the line percentage uses `covered_lines / num_statements`, so executable statements and
lines are collapsed into the same numerator and denominator. For PowerShell, the line metric is
actually unique `StatementAst` start lines, so it is a statement-line metric rather than separate
statement and physical-line measurements. The PowerShell branch metric measures true and false
outcomes only for `IfStatementAst` clause bodies. It does not measure loop outcomes, exception
paths, short-circuit decisions, or other control-flow branches.

The repair report accurately calls the PowerShell number a conditional-branch metric, so the
reported 93.90 percent itself is not falsified. The stronger requirement to enforce statements,
branches, functions, and lines as four coverage dimensions remains incomplete. Current CI also
cannot reach these checks because of F-03.

Required correction: define all four dimensions explicitly, use a branch model that covers the
launcher control-flow contract, and enforce each dimension at 80 percent or higher without
skip-only or empty artifacts.

## Verified corrections

The following repair claims checked out independently:

- The root `launch_gmail_organizer.cmd` resolves its own directory, quotes the script and project
  root, prefers `pwsh.exe`, falls back to `powershell.exe`, preserves the child code, and pauses on
  failure unless the explicit no-pause flag is set.
- The README now provides Windows prerequisites, PowerShell-native venv setup, process-scoped
  execution-policy language, manual bootstrap boundaries, validation semantics, and residual OAuth
  acceptance work.
- Runtime selection is limited to `venv` or `.venv`; no system Python or Streamlit fallback remains.
- The validator requires Python 3.11 or newer, the selected venv prefix, the declared import set,
  an effective non-placeholder Anthropic key, installed-app OAuth JSON shape, `app.py`, and a free
  loopback port.
- The PowerShell consumer rejects missing, mistyped, inconsistent, unsupported, and exit-mismatched
  validator results. Validator output and import failures do not disclose secret values or exception
  detail.
- Dotenv precedence matches the application boundary: process environment wins even when blank;
  otherwise the final target assignment is used. Malformed final assignments fail closed.
- Streamlit is started through the selected interpreter with `-m streamlit`. Startup timeout, clean
  exit before readiness, fast nonzero failure, bounded retry, and no-browser paths are covered.
- The exact focused suite reproduced the report result: `119 passed, 7 skipped`.
- The stdlib validator runner reproduced line 99.61 percent, function 100.00 percent, and
  source-decision branch 84.38 percent across 67 passing tests.
- The PowerShell tracer reproduced 196/205 statement lines, or 95.61 percent; 13/14 functions, or
  92.86 percent; and 77/82 conditional outcomes, or 93.90 percent.
- Changed Python launcher utilities pass Ruff, all reviewed Python files compile, the PowerShell
  launcher and probes parse under PowerShell 7.3.6, and the workflow YAML parses.
- Runtime launcher code contains no downloader, installer, web request, concrete user path, or
  embedded real credential.

## Residual platform gates

The following gates remain valid and explicit, but they do not supersede the blockers above:

1. Run all seven currently skipped cases on a native Windows runner after F-01 through F-04 are
   corrected.
2. Prove root `.cmd` behavior, quoting, pause behavior, PowerShell 5.1 fallback, successful process
   tree cleanup, and console control behavior on Windows 10 or 11.
3. Prove literal Ctrl+C and console-window close, not only Ctrl+Break, with default restart settings
   and no owned descendants left behind.
4. Prove the real default-browser association after verified application readiness.
5. Use only disposable Desktop-app OAuth credentials and a nonproduction Google account for one
   consent flow without mailbox mutation.
6. Run the formal pytest-cov gate and require nonempty artifacts. PSScriptAnalyzer remains
   unavailable locally and should be run in an approved environment if it is part of acceptance.

## Reproduced evidence

| Check | Result |
| --- | --- |
| Exact focused launcher and validator suite | PASS, 119 passed and 7 Windows skips in 93.76 seconds |
| Isolated unrelated-listener readiness probe | DEFECT REPRODUCED, 1 passed and false browser action asserted |
| Isolated failed-taskkill probe | DEFECT REPRODUCED, owned process remained alive until probe cleanup |
| Stdlib Python coverage | PASS, line 99.61%, function 100.00%, source-decision branch 84.38% |
| Instrumented PowerShell coverage | PASS, statement-line 95.61%, function 92.86%, conditional branch 93.90% |
| Exact workflow Ruff command | FAIL, 34 errors in inherited application targets |
| Changed Python utility Ruff command | PASS, inherited configuration warning only |
| Full Python suite in isolated no-install project-venv harness | FAIL, 1200 passed, 7 skipped, 1 failed |
| Focused failing auth test rerun | FAIL, 1 failed with the same refresh fixture path |
| Python compilation, PowerShell parsing, workflow YAML parse | PASS |
| `git diff --check` and `git fsck --strict` | PASS for candidate integrity |
| Native Windows, PowerShell 5.1, real browser, real OAuth | NOT RUN, explicit platform or credential gates |

## Acceptance conditions

Do not change this verdict based only on the existing repair report or local happy-path suite.
Correct F-01 through F-04, keep the original rejection report unchanged, and then require:

1. the two new failure-injection cases to fail closed;
2. the exact Linux and Windows CI jobs to pass without masking or skipped required cases;
3. all four defined coverage dimensions at 80 percent or higher;
4. native Windows 10 or 11 evidence for `.cmd`, PowerShell 5.1, lifecycle, and cleanup; and
5. the explicitly bounded manual browser, console-close, and disposable OAuth checks.

Until those conditions are met, the prior release rejection remains in force.

## External activity and credential safety

No dependency install, network request, browsing, push, merge, deployment, external message, or
credential use occurred. No real `.env`, OAuth credential, token, or mailbox content was opened.
Only synthetic fixture values and disposable local processes were used.
