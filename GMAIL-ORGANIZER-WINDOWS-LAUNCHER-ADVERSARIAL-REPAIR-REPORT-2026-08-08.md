# Gmail Organizer Windows Launcher Adversarial Repair Report

- **Audit name:** Gmail Organizer Windows Launcher Adversarial Repair
- **Agent ID:** `/root/review_alerts_fresh` (implementing repair agent)
- **Timestamp:** 2026-08-08 12:09:44 CDT (-0500)
- **Starting rejection report commit:** `412ad6834568311b4da292531debaf05c51e6117`
- **Repair implementation commit:** `180c1d4802afde2ed1e9116f2e75fae285f41ddf`
- **Branch:** `feature/gmail-organizer-powershell-launcher-2026-08-04`
- **Review type:** Author repair report with local adversarial verification

## Status

**REPAIR IMPLEMENTED AND LOCALLY VERIFIED. INDEPENDENT ACCEPTANCE REQUIRED.**

This report records the repair author's evidence. It does not reverse the preserved independent
`REJECT` verdict in commit `412ad6834568311b4da292531debaf05c51e6117`. A different reviewer must
inspect the exact implementation commit and issue any acceptance decision. No implementation file
changed after commit `180c1d4802afde2ed1e9116f2e75fae285f41ddf`.

## Repair disposition

### F-01: Readiness could belong to an unrelated process

**Disposition: repaired locally, native Windows confirmation remains.**

The launcher now starts Streamlit on `127.0.0.1` and requires all of the following before opening
the browser:

1. the launched Streamlit process is still running;
2. the listening socket's process ID is the exact launched process ID;
3. `GET /_stcore/health` returns HTTP 200 with the trimmed response body `ok`; and
4. the socket still belongs to the exact launched process ID after the health response.

On Windows, ownership is determined from `netstat.exe -ano -p TCP`. The local non-Windows test
harness uses `lsof` only to exercise the contract against synthetic processes. Failure to obtain
ownership evidence fails closed.

The new adversarial race fixture lets an unrelated process win the modeled post-check listener
race and serve a valid synthetic health response. The launcher rejects that listener and does not
invoke the browser action. A separate probe proves that an owned listener without the expected
health response also fails closed.

The two ownership checks materially narrow the time-of-check/time-of-use interval, but they are not
claimed to be an atomic operating-system transaction. Native Windows evidence is still required for
the `netstat.exe` parsing and real Streamlit process relationship.

### F-02: Failed Windows process-tree cleanup was ignored

**Disposition: repaired locally, native descendant-cleanup confirmation remains.**

`Stop-OwnedProcessTree` now checks the native `taskkill.exe /PID <pid> /T /F` exit result, waits for
the launched parent, verifies its termination, and attempts a parent-only `Stop-Process` fallback
when tree cleanup fails. It throws a stable cleanup error whenever `taskkill.exe` fails, even if the
parent fallback succeeds. A missing `taskkill.exe` also produces a visible failure after the safe
parent fallback.

The new failure-injection test supplies a fake `taskkill` executable that exits nonzero. It verifies
that the error is visible and the parent fallback stops the owned parent process. This implementation
does not falsely claim descendant cleanup after a failed tree-kill command. Because a failed
`taskkill` cannot prove that descendants stopped, the surfaced error remains the required result.

Successful descendant-tree termination and the exact failure behavior still require a native
Windows run.

### F-03: The committed CI workflow was locally known to fail

**Disposition: repaired for the candidate scope, inherited baseline remains explicitly visible.**

The blocking Ruff step now enforces the repaired candidate Python scope, including the changed auth
test. That exact command passes locally. A separate informational step runs Ruff against the
inherited `gmail_organizer/` and `app.py` baseline with `continue-on-error: true`. This step reports
the inherited debt rather than hiding it or making unrelated baseline cleanup a condition of this
launcher repair.

The inherited baseline currently reports 34 Ruff findings:

- 28 `I001` import-order findings;
- 3 `E741` ambiguous-variable findings; and
- 3 `F841` unused-variable findings.

The deterministic auth refresh fixture was corrected to serialize concrete credential fields. The
full no-install project test run now passes with `1204 passed` and `7 skipped`. No pytest, lint, or
coverage failure is masked in the repaired candidate gates.

The informational baseline step is expected to remain red until separately authorized baseline
cleanup occurs. It is not release-acceptance evidence for the launcher.

### F-04: Four independent coverage dimensions were not enforced as named

**Disposition: repaired with explicit source-based definitions.**

Both Python and PowerShell coverage checks now report and enforce Statement, Branch, Function, and
Line at 80 percent or higher. The definitions are intentionally explicit:

- Python Statement measures AST statement entries whose source line executed.
- Python Branch uses the stdlib validator's source-decision model.
- Python Function measures entered function definitions.
- Python Line measures executable source lines recorded as executed.
- PowerShell Statement measures direct block statements covered when any breakpointable source
  position in the statement extent executes.
- PowerShell Branch measures entered and skipped body outcomes for `if` clauses and loop statements.
- PowerShell Function measures functions whose first direct body statement executes.
- PowerShell Line measures unique direct-statement start lines with a covered statement.

The PowerShell branch percentage is a source-decision proxy for the launcher's `if` and loop
control-flow contract. It does not claim generic runtime branch coverage for short-circuit operand
decisions, exception dispatch, switch-clause evaluation, asynchronous external-process behavior, or
operating-system internals. The launcher currently has no switch-based control flow. The Python
Statement metric is likewise an AST source-statement metric, not bytecode event coverage.

## Local validation evidence

All validation below used existing local tools and synthetic fixtures. No dependency installation or
network access occurred.

| Check | Result |
| --- | --- |
| Focused launcher and validator suite without PowerShell coverage | PASS, 122 passed and 7 native Windows skips in 53.59 seconds |
| Focused suite with PowerShell coverage instrumentation | PASS, 122 passed and 7 native Windows skips in 64.93 seconds |
| Unrelated-listener post-check race regression | PASS, competitor with valid synthetic health response rejected and browser marker absent |
| Missing-health regression | PASS, listener without expected health response rejected |
| Failed-taskkill regression | PASS, failure surfaced and parent fallback stopped the owned process |
| Python stdlib coverage | PASS, Statement 100.00%, Branch 84.38%, Function 100.00%, Line 99.61% across 67 passing tests |
| Instrumented PowerShell coverage | PASS, Statement 218/246 or 88.62%, Branch 106/132 or 80.30%, Function 15/16 or 93.75%, Line 202/228 or 88.60% |
| Full no-install project suite | PASS, 1204 passed and 7 native Windows skips in 64.70 seconds |
| Exact blocking candidate-scope Ruff command | PASS, inherited configuration deprecation warning only |
| Explicit inherited repository Ruff baseline report | INFORMATIONAL FAIL, 34 inherited findings reported without concealment |
| Python compilation with external cache | PASS |
| PowerShell parser for launcher, assertions, instrumentation, and probes | PASS, 9 files under PowerShell 7.3.6 |
| Workflow YAML parse | PASS |
| `git diff --check` before report creation | PASS |
| Concrete user-path, secret, installer, and downloader scan | PASS, no runtime violation found |
| Native Windows, PowerShell 5.1, default browser, console-close, real OAuth | NOT RUN, explicit platform or credential gates |

## Honest limitations and remaining acceptance gates

Seven cases are skipped outside native Windows. Before release acceptance, an independent reviewer
must run the exact candidate through a native Windows 10 or 11 environment and verify:

1. the root `.cmd` entry point, quoting, exit propagation, failure pause, and explicit no-pause mode;
2. Windows PowerShell 5.1 compatibility and the intended PowerShell 7 preference;
3. `netstat.exe` ownership parsing against an actual Streamlit 1.31 process and its
   `/_stcore/health` endpoint;
4. the unrelated-listener race fails closed with no default-browser action;
5. successful `taskkill /T /F` removes the parent and all owned descendants;
6. taskkill failure is visible and never represented as successful tree cleanup;
7. literal Ctrl+C and console-window close behavior, not only synthetic control events;
8. the actual default browser opens only after process-bound application readiness;
9. the formal pytest-cov workflow gate produces nonempty artifacts and passes all four thresholds;
10. PSScriptAnalyzer in an approved environment if it remains part of release acceptance; and
11. one bounded consent flow using disposable Desktop-app OAuth credentials and a nonproduction
    Google account, without mailbox mutation.

CI was not pushed or run remotely. The local Mac cannot establish native Windows acceptance,
PowerShell 5.1 behavior, Windows console lifecycle semantics, default-browser integration, or real
OAuth consent behavior. Those are explicit gates, not inferred successes.

## Independent follow-up required

The next reviewer should begin from implementation commit
`180c1d4802afde2ed1e9116f2e75fae285f41ddf`, read the preserved rejection at
`412ad6834568311b4da292531debaf05c51e6117`, reproduce the adversarial tests, and inspect the exact
coverage definitions before deciding acceptance. The reviewer should treat this document as author
evidence only and should independently verify every release-critical claim.

## External activity and credential safety

No dependency install, network request, browsing, push, merge, deployment, external message, or
credential use occurred. No real `.env`, OAuth credential, token, mailbox content, or user data was
opened. Only synthetic fixture values, local loopback listeners, and disposable local processes were
used.
