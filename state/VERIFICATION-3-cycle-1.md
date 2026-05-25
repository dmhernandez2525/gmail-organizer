# Verification-3: Data Integrity and Integration Report (Cycle 1)

**Auditor:** Verifier-3
**Date:** 2026-03-28
**Scope:** Data flows, schema consistency, state integrity, API integration, cross-module compatibility

---

## 1. Email Dict Key Consistency

### Finding DI-001: CRITICAL - Two incompatible email dict schemas coexist

**Severity: HIGH**

The codebase has two fundamentally different email dict schemas that are never reconciled:

**Schema A (operations.py "processed" format):** Produced by `_fetch_emails_batch()` at `operations.py:629-638` and `_get_email_details()` at `operations.py:688-698`:
```python
{
    'email_id': ...,   # from response['id']
    'subject': ...,
    'sender': ...,     # from 'From' header
    'to': ...,
    'date': ...,       # from 'Date' header (RFC 2822 string)
    'snippet': ...,
    'body_preview': ...,
    'labels': ...,     # from labelIds
}
```

**Schema B (raw Gmail API format):** Expected by `duplicates.py`, `storage.py`, and parts of `reminders.py`:
```python
{
    'id': ...,                # NOT email_id
    'threadId': ...,
    'payload': {'headers': [...]},  # NOT flat sender/subject
    'labelIds': [...],        # NOT labels
    'internalDate': ...,      # NOT date
    'sizeEstimate': ...,
}
```

**Affected modules expecting Schema B keys:**

| Module | File:Line | Key Expected | Present in Schema A? |
|--------|-----------|-------------|---------------------|
| `duplicates.py` | :209, :499-505 | `payload.headers` | NO |
| `duplicates.py` | :129, :282 | `threadId` | NO |
| `duplicates.py` | :509 | `internalDate` | NO |
| `duplicates.py` | :43, :59 | `sizeEstimate` | NO |
| `duplicates.py` | :425 | `labelIds` | NO (has `labels` instead) |
| `storage.py` | :64, :76, :283-284, :323-335, :353 | `sizeEstimate`, `labelIds`, `payload`, `internalDate` | NO |
| `reminders.py` | :168, :222 | `threadId` | NO |
| `reminders.py` | :317 | `internalDate` (as fallback) | NO |
| `reminders.py` | :84 (docstring) | `id`, `from`, `labelIds` | NO (has `email_id`, `sender`, `labels`) |

**Impact:** Any attempt to use `DuplicateDetector`, `StorageAnalyzer`, or `FollowUpDetector` on emails from `sync_emails()` will silently produce empty/wrong results. Headers will be missing, sizes will be 0, thread grouping will fail, duplicate detection will be completely broken.

### Finding DI-002: MEDIUM - Inconsistent sender key fallback patterns

Multiple modules use `email.get("sender", email.get("from", ""))` as a fallback pattern:
- `reminders.py:355`, `reputation.py:129,275`, `summaries.py:403`, `training.py:94,126,205`, `multi_label.py:189`, `calendar_integration.py:205`, `mobile.py:230`

However, the canonical email dict from `operations.py` always uses `sender` (never `from`). This fallback is dead code that creates a false impression of compatibility with raw Gmail API dicts. Meanwhile, modules like `analytics.py`, `priority.py`, and `search.py` only use `email.get('sender', '')` without the fallback. This inconsistency is not a runtime bug but indicates confusion about the expected schema.

### Finding DI-003: MEDIUM - body key inconsistency across modules

Modules access body content under different keys:

| Module | Key Used | File:Line |
|--------|----------|-----------|
| `operations.py` (produces) | `body_preview` | :636 |
| `search.py` | `body_preview` | :267 |
| `security.py` | `body_preview` | :94 |
| `filters.py` | `body_preview` | :224 |
| `unsubscribe.py` | `body_preview` | :170 |
| `reminders.py` | `body` then `snippet` | :184, :287 |
| `summaries.py` | `snippet` then `body` | :219, :320, :387 |
| `multi_label.py` | `body` then `snippet` | :191 |
| `export.py` (mbox) | `body` then `snippet` | :271 |
| `calendar_integration.py` | `body` then `snippet` | :204 |

**Impact:** `reminders.py`, `summaries.py`, `multi_label.py`, `export.py` (mbox), and `calendar_integration.py` will never see the body text because they look for `body` first, but operations.py stores it as `body_preview`. They fall back to `snippet` which is a shorter version.

### Finding DI-004: LOW - `message_id` field never populated

`export.py:255` checks `email.get("message_id")` for MBOX export headers, but `operations.py` never extracts the `Message-ID` header into the email dict. This field will always be empty in MBOX exports.

---

## 2. Token Storage Migration

### Finding DI-005: MEDIUM - `_migrate_pickle_to_json` does not handle corrupt pickle files

**File:** `auth.py:45-55`

The migration function calls `pickle.load(f)` without any exception handling. If a `.pickle` file is corrupt (truncated, encoding error, malicious content), the function will raise an unhandled exception that propagates up to `_get_token_path()`, `_iter_token_files()`, `authenticate_account()`, etc.

```python
def _migrate_pickle_to_json(pickle_path: Path) -> Path:
    # ...
    with open(pickle_path, 'rb') as f:
        creds = pickle.load(f)  # No try/except - crash on corrupt pickle
    _save_credentials_json(creds, json_path)
    pickle_path.unlink()  # Deletes the pickle even if json save partially failed
    return json_path
```

Additionally, there is no verification that the loaded pickle object is actually a `Credentials` instance. If the pickle contains a different type, `_save_credentials_json` will fail or produce an invalid JSON.

### Finding DI-006: LOW - JSON token schema may have null fields

`_load_credentials_json` at `auth.py:14-25` uses `data.get()` for all fields, which means any missing key returns `None`. The `Credentials` constructor may accept `None` for `token` or `refresh_token`, but this could silently create a non-functional credentials object rather than failing fast.

### Finding DI-007: LOW - Race condition: pickle deleted before JSON verified

At `auth.py:53-54`, the pickle is deleted (`unlink()`) immediately after `_save_credentials_json` writes the JSON. If the process crashes between `json.dump` and `os.chmod` (line 42), or if `json.dump` writes a partial file, the pickle is already gone and the JSON may be corrupt.

---

## 3. Sync State Integrity

### Finding DI-008: HIGH - Non-atomic writes to sync state files risk data corruption

**File:** `operations.py:178-190`

`_save_sync_state` writes directly to the sync state file with `json.dump`:

```python
with open(sync_path, 'w') as f:
    json.dump(state, f)
```

If the process crashes mid-write (or is killed), the file will be truncated/corrupt. On next load at `operations.py:126-128`, `json.load()` will raise `JSONDecodeError`, which is caught and returns the default empty state, **losing all previously synced email data**.

The same issue exists in:
- `sync_manager.py:218-221` (merged state save)
- `priority.py:62-63` (priority config save)
- `unsubscribe.py:114-115` (unsubscribe state save)
- `notifications.py:340-341` (webhook config save)
- `notifications.py:367-368` (notification history save)
- `scheduler.py:240-241` (schedule config save)
- `training.py:391-393` (training data save)

**Proper fix:** Write to a temporary file first, then atomically rename (`os.replace()`).

### Finding DI-009: MEDIUM - Checkpoint index.json and batch files can become inconsistent

**File:** `operations.py:70-99`

`_save_checkpoint` writes the index file and batch files in separate operations:
1. Writes `index.json` (line 79-80)
2. Counts existing batch file lines (lines 84-87)
3. Writes new batch file (lines 93-96)

If the process crashes after writing `index.json` but before writing the batch file, the index will claim more emails exist than are actually stored. On recovery at `_load_sync_state` (line 147), `checkpoint_count > len(sync_emails_dict)` triggers a merge from checkpoint, but the batch files won't have the data the index claims.

### Finding DI-010: MEDIUM - Duplicate emails possible during checkpoint merging

**File:** `operations.py:148-169`

When checkpoint emails are merged into sync state, the merge key is `email.get("email_id", "")`. If `email_id` is empty string (which happens for any malformed email), all such emails collapse into a single entry in the merged dict, potentially losing data.

---

## 4. Gmail API Integration

### Finding DI-011: HIGH - `messages().send()` requires `gmail.send` scope, not present

**File:** `unsubscribe.py:371`, `config.py:12-16`

The configured scopes are:
```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]
```

`UnsubscribeManager.unsubscribe_via_email()` calls `service.users().messages().send()` which requires the `gmail.send` scope (or `gmail.compose`). The `gmail.modify` scope does NOT grant send permission. This call will fail with a 403 Forbidden error at runtime.

**Evidence:** `unsubscribe.py:371`:
```python
self.service.users().messages().send(userId='me', body=body).execute()
```

### Finding DI-012: LOW - Inconsistent HttpError handling across modules

Most modules catch `HttpError` but handle it differently:
- `operations.py:580` - logs and continues, returns partial results
- `operations.py:252-257` - special handling for historyId errors
- `bulk_actions.py:152` - appends error string to result dict
- `filters.py:243-244, 258, 271` - prints error, returns None/False
- `operations.py:789,800` - prints error, returns None/empty list

No module implements retry logic except `fetch_emails` (which has proper exponential backoff). Transient API errors in label creation, filter operations, or bulk actions will fail permanently.

---

## 5. Configuration Consistency

### Finding DI-013: MEDIUM - Docker volume missing `.sync-state/` directory

**File:** `docker-compose.yml`

The docker-compose volumes mount:
- `./credentials:/app/credentials`
- `./.email-cache:/app/.email-cache`
- `./logs:/app/logs`

But `.sync-state/` is NOT mounted. This means:
- All sync state (historyId, cached emails) is lost when the container restarts
- Priority config, unsubscribe state, notification config, schedule config, and training data are all stored in `.sync-state/` and will be lost
- Every container restart triggers a full re-sync instead of incremental

### Finding DI-014: LOW - `.env.example` missing referenced env var `API_KEY`

**File:** `.env.example`

The `.env.example` contains `API_KEY=your-secret-key-here` but no code references this env var. It appears to be a placeholder for a future feature. Not a bug, but misleading.

### Finding DI-015: LOW - Docker environment missing `DEMO_MODE` variable

The render.yaml likely sets `NEXT_PUBLIC_DEMO_MODE` for the website, but docker-compose.yml does not provide any demo mode environment variable for the Streamlit app.

---

## 6. Cross-Module Data Flow

### Finding DI-016: HIGH - Classifier output does not match what label application expects

The data flow for classification and label application is:

1. `classifier.py:classify_batch()` adds `category` and `confidence` keys to email dicts
2. `operations.py:create_all_labels()` returns `{category_key: label_id}` mapping
3. `operations.py:apply_label_to_email(email_id, label_id)` applies a label

The issue: `classify_batch` at `classifier.py:108-123` accesses `email.get('subject', '')` and `email.get('sender', '')` which match Schema A. But then the caller must map `email['category']` to a label_id and call `apply_label_to_email(email['email_id'], label_id)`.

This flow actually works correctly because both the classifier and the label application operate on Schema A email dicts. However, `classify_email` accepts `body_preview` as a named parameter (line 26), but `classify_batch` hardcodes `body_preview=""` (line 116), meaning the body is never used in batch classification even if available. This is intentional (documented as token optimization) but worth noting.

### Finding DI-017: CRITICAL - `storage.py` and `duplicates.py` are unusable with synced data

As detailed in DI-001, `StorageAnalyzer` and `DuplicateDetector` expect raw Gmail API format (Schema B) with `payload`, `headers`, `sizeEstimate`, `internalDate`, `labelIds`, and `threadId`. The `sync_emails()` and `fetch_emails()` methods in `operations.py` produce Schema A dicts.

Any UI or feature that calls these modules with data from `sync_emails()` will get:
- Storage analysis: All sizes = 0, no senders detected, no years, no attachments
- Duplicate detection: No Message-ID headers found, no thread grouping, no date proximity checks

These modules are effectively dead code in the current architecture unless someone passes raw API responses directly.

---

## 7. State File Schemas

### Finding DI-018: LOW - notification_config.json uses `asdict()` serialization, round-trips correctly

`notifications.py` saves webhook configs via `asdict(wh)` at line 337 and loads them via `WebhookConfig(**item)` at line 355. The dataclass fields match perfectly. Round-trip is correct.

### Finding DI-019: LOW - priority_config.json schema is stable

`priority.py` loads with defaults at lines 52-56 and saves the same dict structure at line 63. The `weights`, `vip_senders`, `low_priority_senders`, and `thresholds` keys are always present. Round-trip is correct.

### Finding DI-020: LOW - unsubscribe_state.json schema is stable

`unsubscribe.py` loads with default `{'unsubscribed': {}, 'ignored': []}` at line 108 and saves the same structure at line 115. The `.setdefault()` calls at lines 391 and 398 ensure keys exist before modification. Round-trip is correct.

### Finding DI-021: LOW - training data round-trips correctly

`training.py` saves at lines 378-393 and loads at lines 397-421 using the same 6-key schema (`email_id`, `category`, `sender`, `subject`, `domain`, `keywords`). The `_load_training_data` method uses `.get()` with defaults for all keys. Round-trip is correct.

### Finding DI-022: MEDIUM - scheduler config deserializes without validation

`scheduler.py:257` does `ScheduleConfig(**config_dict)` which will crash if the JSON file contains unexpected keys (e.g., from a future version). No validation or filtering of unknown keys.

---

## Summary by Severity

| Severity | Count | Finding IDs |
|----------|-------|-------------|
| CRITICAL | 2 | DI-001, DI-017 |
| HIGH | 3 | DI-008, DI-011, DI-016 (partially OK) |
| MEDIUM | 6 | DI-002, DI-003, DI-005, DI-009, DI-010, DI-013, DI-022 |
| LOW | 6 | DI-004, DI-006, DI-007, DI-012, DI-014, DI-015, DI-018-DI-021 |

## Top Priority Fixes

1. **DI-001 / DI-017**: Resolve the two-schema problem. Either: (a) have `operations.py` preserve raw Gmail API fields alongside processed fields, or (b) rewrite `duplicates.py` and `storage.py` to work with Schema A. Currently these modules cannot function.

2. **DI-008**: Implement atomic writes for all state files using write-to-temp + `os.replace()`.

3. **DI-011**: Add `gmail.send` (or `gmail.compose`) to SCOPES if unsubscribe-via-email is a supported feature. Note: changing scopes requires users to re-authenticate.

4. **DI-013**: Add `.sync-state/` volume mount to docker-compose.yml.

5. **DI-003**: Standardize body key access. If `body_preview` is the canonical key, update all modules to use it consistently.
