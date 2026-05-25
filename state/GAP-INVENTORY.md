# Gap Inventory - Final State (Cycle 2)

## Tier A (Critical) - ALL RESOLVED

- [x] GAP-001: [Tier A] Swift helper uses --dangerously-skip-permissions - **DONE** (Cycle 1)
- [x] GAP-002: [Tier A] Email schema mismatch - **DONE** (Cycle 11: added raw Gmail API fields to sync output)
- [x] GAP-003: [Tier A] Silent exception swallowing - **DONE** (Cycle 2)
- [x] GAP-004: [Tier A] auth.py unprotected API calls - **DONE** (Cycle 3)
- [x] V4-A1: [Tier A] mobile.py O(n^2) PNG generation - **DONE** (Cycle 10)

## Tier B (Important) - ALL RESOLVED

- [x] GAP-005: [Tier B] Non-atomic state file writes - **DONE** (Cycle 15: atomic write for sync state)
- [x] GAP-006: [Tier B] gmail.send scope missing - **DONE** (Cycle 13)
- [x] GAP-007: [Tier B] Body key inconsistency - **DONE** (Cycle 12: 5 modules fixed)
- [x] GAP-008: [Tier B] MBOX sanitization incomplete - **DONE** (Cycle 5)
- [x] GAP-009: [Tier B] Classifier error confidence - **DONE** (Cycle 4)
- [x] GAP-010: [Tier B] Pickle migration error recovery - **DONE** (Cycle 6)
- [x] GAP-011: [Tier B] Docker .sync-state/ volume - **DONE** (Cycle 8)
- [x] GAP-012: [Tier B] Unsubscribe header detection - **DONE** (Cycle 16: headers dict in sync output)
- [x] GAP-013: [Tier B] Empty subjects crash - **DONE** (Cycle 7)
- [x] GAP-014: [Tier B] App crash without API key - **DONE** (Cycle 14)

## Tier C (Completeness)

- [x] GAP-015: [Tier C] Ruff lint errors - **DONE** (Cycle 9)
- [x] GAP-016: [Tier C] .env.example cleanup - **DONE** (Cycle 17)
- [ ] GAP-017: [Tier C] operations.py test coverage at 35% - OPEN (complex mocking of Gmail API batch/pagination; core logic verified by integration)
- [ ] GAP-018: [Tier C] analyzer.py test coverage at 19% - OPEN (requires mocking Anthropic API; module is thin wrapper around API call)

## Summary
- Total gaps found: 18 + 1 from V4
- Tier A resolved: 5/5
- Tier B resolved: 10/10
- Tier C resolved: 2/4
- Remaining: 2 Tier C (test coverage for modules that are thin API wrappers)
