# Final Verification 3: Data Integrity & Cross-Module Compatibility

**Verifier:** Fresh read, no prior knowledge of fixes
**Date:** 2026-03-28
**Scope:** Email dict schema from operations.py vs. all consumer modules; SCOPES; state atomicity

---

## 1. Email Dict Schema Produced by operations.py

### _fetch_emails_batch (line 587, callback at line 606)

Fields stored per email dict (lines 637-654):

| Key | Source |
|-----|--------|
| `email_id` | `response['id']` |
| `subject` | From header extraction |
| `sender` | From header extraction |
| `to` | To header extraction |
| `date` | Date header extraction |
| `snippet` | `response.get('snippet', '')` |
| `body_preview` | `_get_body_preview(response['payload'])` |
| `labels` | `response.get('labelIds', [])` |
| `headers` | Flat dict built from `payload.headers` (lines 631-635) |
| `threadId` | `response.get('threadId', '')` |
| `labelIds` | `response.get('labelIds', [])` (duplicate of labels) |
| `sizeEstimate` | `response.get('sizeEstimate', 0)` |
| `internalDate` | `response.get('internalDate', '')` |
| `payload` | `response.get('payload', {})` |

### _get_email_details (line 683)

Fields stored per email dict (lines 705-719):

Same fields as above EXCEPT:
- **MISSING: `headers` (flat dict)** -- This method does NOT build the flat `headers` dict that `_fetch_emails_batch` provides.

**FINDING (MEDIUM):** `_get_email_details` omits the `headers` flat dict. Any email fetched via this single-email path will lack `headers`, breaking `unsubscribe.py` (which reads `email.get('headers', {})`). In practice, this method appears to be a fallback/utility; the main paths use `_fetch_emails_batch`. Risk is limited to code paths that call `_get_email_details` directly.

---

## 2. Cross-Module Compatibility Analysis

### storage.py -- PASS

Needs: `sizeEstimate`, `payload` (with `headers` list), `internalDate`, `labelIds`
- `sizeEstimate`: present (line 651)
- `payload`: present (line 653), carries full Gmail payload with `headers` as list of `{name, value}` dicts
- `internalDate`: present (line 652)
- `labelIds`: present (line 650)
- storage.py accesses via `email.get("sizeEstimate", 0)` (line 64), `email.get("payload", {})` (line 283), `email.get("internalDate")` (line 324), `email.get("labelIds", [])` (line 77). All match.

### duplicates.py -- PASS

Needs: `payload.headers` (for Message-ID), `threadId`, `internalDate`, `sizeEstimate`, `email_id`, `labelIds`
- `_get_header` at line 499 reads `email.get("payload", {}).get("headers", [])` -- matches payload structure
- `threadId`: present (line 649)
- `internalDate`: present (line 652)
- `sizeEstimate`: present (line 651)
- `email_id`: present (line 638)
- `labelIds`: present (line 650)

### unsubscribe.py -- PASS (with caveat)

Needs: `headers` dict with `List-Unsubscribe`, `sender`, `body_preview`, `date`, `category`
- `headers` flat dict: present in `_fetch_emails_batch` (line 648), accessed as `email.get('headers', {})` at unsubscribe.py line 158, then `headers.get('List-Unsubscribe', '')` at line 159. **Matches.**
- `sender`: present (line 640)
- `body_preview`: present (line 644), read at unsubscribe.py line 169. **Matches.**
- `date`: present (line 643), read at unsubscribe.py line 175. **Matches.**
- `category`: Not set by operations.py by default. Read at unsubscribe.py line 183 with `email.get('category', '')`. Safely defaults to empty string. This field is populated downstream by classification. **OK, not a bug.**

**Caveat:** If `_get_email_details` is used instead of batch, `headers` flat dict is missing (see Finding above).

### reminders.py -- PASS

Needs body content under what key?
- Line 184: `email.get("body_preview") or email.get("body") or email.get("snippet") or ""`
- Line 287: same fallback chain
- `body_preview` is present (line 644). Falls back to `snippet` (line 643). **Matches.**
- Also uses: `subject` (line 183), `sender`/`from` (line 355), `date`/`internalDate` (line 317), `threadId` (line 169), `labelIds` (line 425 via `email.get("labelIds", [])`). All present.

### summaries.py -- PASS

Needs body content under what key?
- Line 219: `e.get("snippet") or e.get("body") or ""`
- Line 320-321: `email.get("body_preview") or email.get("body_preview") or email.get("snippet") or email.get("body") or ""`
- Line 387: `email.get("body_preview") or email.get("snippet") or email.get("body") or ""`
- Both `body_preview` (line 644) and `snippet` (line 643) are present. **Matches.**
- Also uses: `sender`/`from` (line 403), `subject` (line 269), `date` (line 311), `threadId` (line 120), `category` (line 125), `labels` (line 323). All present or safely defaulted.

### multi_label.py -- PASS

Needs body content under what key?
- Line 191: `email.get("body_preview") or email.get("body") or email.get("snippet") or ""`
- `body_preview` present. **Matches.**
- Also uses: `sender`/`from` (line 189), `subject` (line 190), `email_id` (line 188). All present.

### calendar_integration.py -- PASS

Needs body content under what key?
- Line 204: `email.get("body_preview") or email.get("body") or email.get("snippet") or ""`
- `body_preview` present. **Matches.**
- Also uses: `email_id` (line 197), `subject` (line 203), `sender`/`from` (line 205), `date` (line 206). All present.

### export.py (mbox) -- PASS

Needs body content under what key?
- Line 271: `email.get("body_preview") or email.get("body") or email.get("snippet") or ""`
- `body_preview` present. **Matches.**
- Also uses: `sender` (line 240), `to` (line 251), `subject` (line 252), `date` (line 253), `message_id` (line 255), `labels` (line 258), `category` (line 265). All present or safely defaulted.

---

## 3. config.py SCOPES Check -- PASS

File: `config.py`, lines 12-17

```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]
```

`gmail.send` is included (line 15). This is required for `unsubscribe.py`'s `unsubscribe_via_email()` method (line 334) which calls `service.users().messages().send()`. **Confirmed present.**

---

## 4. Body Content Key Consistency -- PASS

All consumer modules use a consistent fallback chain to access body content:

```
email.get("body_preview") or email.get("body") or email.get("snippet") or ""
```

The primary key is `body_preview`, which is populated by operations.py at line 644 via `_get_body_preview()`. The fallback `snippet` is also always populated (line 643). The key `body` is never set by operations.py but is included as a fallback for potential external data sources.

**Consistency verdict: All modules agree on the fallback chain. No mismatch.**

---

## 5. State File Atomicity Check -- MIXED

### _save_sync_state (operations.py lines 172-192) -- ATOMIC

Uses write-to-tmp + `os.replace` pattern:
```python
tmp_path = sync_path.with_suffix('.tmp')
with open(tmp_path, 'w') as f:
    json.dump(state, f)
os.replace(str(tmp_path), str(sync_path))
```
**This is the correct atomic write pattern.** `os.replace` is atomic on POSIX systems.

### _save_checkpoint (operations.py lines 69-98) -- NOT ATOMIC

Writes `index.json` directly:
```python
with open(index_file, 'w') as f:
    json.dump(list(fetched_ids), f)
```
And writes batch files directly:
```python
with open(batch_file, 'w') as f:
    for email in new_emails:
        f.write(json.dumps(email) + '\n')
```
**No atomic write pattern.** If the process crashes mid-write, `index.json` could be corrupted. The batch JSONL files are append-only new files so they are lower risk (a new file either exists or doesn't), but `index.json` overwrites in place.

### _save_state in unsubscribe.py (lines 109-114) -- NOT ATOMIC

```python
with open(state_file, 'w') as f:
    json.dump(self._unsubscribe_state, f, indent=2)
```
**Direct write, no atomic pattern.** If process crashes during write, `unsubscribe_state.json` could be corrupted/truncated.

---

## Summary

| Check | Result | Severity |
|-------|--------|----------|
| storage.py compatibility | PASS | -- |
| duplicates.py compatibility | PASS | -- |
| unsubscribe.py compatibility | PASS (caveat on _get_email_details path) | LOW |
| reminders.py compatibility | PASS | -- |
| summaries.py compatibility | PASS | -- |
| multi_label.py compatibility | PASS | -- |
| calendar_integration.py compatibility | PASS | -- |
| export.py (mbox) compatibility | PASS | -- |
| config.py gmail.send scope | PASS | -- |
| Body key consistency | PASS | -- |
| _get_email_details missing `headers` dict | FINDING | MEDIUM |
| _save_sync_state atomicity | PASS (atomic) | -- |
| _save_checkpoint atomicity | FINDING | LOW |
| unsubscribe _save_state atomicity | FINDING | LOW |

### Findings Requiring Action

1. **MEDIUM: `_get_email_details` (line 683) is missing the flat `headers` dict** that `_fetch_emails_batch` provides. Any code path calling this method directly will produce emails without `headers`, which would break `unsubscribe.py`'s `List-Unsubscribe` detection. Fix: add the same `headers_dict` construction (lines 631-635 pattern) to `_get_email_details`.

2. **LOW: `_save_checkpoint` writes `index.json` non-atomically.** A crash during write could corrupt the checkpoint index. The data can be rebuilt from batch files, so impact is limited to a slower recovery. Fix: use tmp+rename pattern.

3. **LOW: `unsubscribe.py` `_save_state` writes non-atomically.** A crash during write could corrupt the unsubscribe state. Data loss is limited to the unsubscribe tracking list. Fix: use tmp+rename pattern.
