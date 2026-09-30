---
name: automata-codex-sessions
description: Use when discovering, independently copying, explicitly forking, or recoverably trashing/restoring native Codex sessions in an authorized store. Not for Pi sessions.
---

# Automata Codex Sessions

Manage selected native Codex histories without confusing a linked fork with an
independent copy. Pi running a Codex model is still Pi; this capability requires
ordinary Codex CLI 0.159.0 on Linux, not Pi session tools.

## Establish scope and readiness

Use `session_management.py` directly under the approved installation root and its
installed README. The helper is installed with `automata codex install`; it is a
shell control, not an MCP tool, hook action, chat launcher or persistent host.
Confirm the existing helper, native binary/version, explicit native store and
private management-state directory. State must be outside the native store and
replaceable assets. Do not install, activate hooks, infer global roots or attach
to an existing daemon as a fallback. Mutations require bubblewrap; trash also
requires `gio` and an explicitly authorized XDG data home on the staging filesystem.

Obtain authority for discovery scope first: one exact absolute project cwd, or
explicit all-projects discovery within one selected store. These do not authorize
other stores, reading conversations for curiosity, or mutating every result.
Before trash, explain that dependency safety checks inspect indexed metadata and
rollout headers across the selected store, including sessions outside the listed
cwd; effects remain limited to exact selected IDs. Unknown unrelated headers or
schema may conservatively block removal. Do not bypass that check.

## Discover and select

```sh
python3 "$HELPER" list --store-root "$STORE" --state-root "$STATE" \
  --cwd "$EXACT_PROJECT_CWD"
```

Use `--all-projects` instead of `--cwd` only with that broader authority. For the
next page pass `--cursor "$CURSOR"` with the same roots/caller, without discovery
filters. Pages contain at most 100 entries, default 20; names, IDs, directory
status and provenance are metadata, not transcript previews. Coverage is indexed
sessions only; unavailable entries and missing stores/directories are explicit.
Do not supplement this with filesystem history scans or treat a missing cwd as
permission to delete.

Bind the user's selection to full IDs from a fresh page. Its separate
`copyReceipt`, `forkReceipt` and `trashReceipt` expire after five minutes and cover
only that page. A newer listing/page supersedes old receipts. Each mutation
consumes its action receipt; never manufacture or edit receipt state.

## Authorize the operation

Confirm selected-session ownership and inactivity from task context. A listing,
idle timestamp or the helper's private native process cannot establish whether
another Codex process owns a session. Known current sessions are rejected. Keep
`CODEX_THREAD_ID` intact, or supply the known `--current-thread UUID`; use
`--outside-session` only when genuinely operating outside a Codex session.
`--inactive-owned` is an attestation of established facts, not a way to skip them.

All mutations require `--binary "$NATIVE_CODEX"`, the same explicit roots, exact
`--ids UUID ...`, and the caller/inactivity flags above. Use a fresh receipt even
when a previous attempt failed; first inspect any partial outcome, without an
automatic retry.

- **Independent copy:** `copy --receipt "$COPY_RECEIPT" --target-cwd "$DEST"`.
  Destination must already exist and differ from the source cwd. The new session
  remains in the selected native store. The adapter uses a native fresh identity,
  destination cwd and source provenance, materializes the exact original record
  tail, and verifies complete native history in a source-free store before
  exclusive publication. This is not merely native `thread/fork`. Source history
  and old paths remain unchanged; project files and external assets are not copied.
- **Linked fork:** `fork --receipt "$FORK_RECEIPT" --target-cwd "$DEST"` only
  when a linked native fork is explicitly wanted. It can depend on source history.
  Never silently substitute it when independent copying is requested.
- **Recoverable removal:** `trash --receipt "$TRASH_RECEIPT"
  --xdg-data-home "$XDG_DATA_HOME"`. An exact selected-history/metadata package
  must reach genuine OS trash with verified `.trashinfo` before native deletion.
  Unselected spawned descendants or history dependents reject the operation;
  even fully selected dependency groups are unsupported in this version. There
  is no permanent-delete fallback or JSONL-only removal shortcut.
- **Restore:** `restore --recovery-id "$RECOVERY_ID"` with exact recorded IDs.
  This restores only the receipt-bound original path, rejects collisions, resumes
  natively to rebuild projections, and verifies original IDs, name, full-history
  digest and original rollout-byte prefix. Copying a JSONL back alone is not a
  verified restore. The trash bundle remains for recovery; do not purge it as an
  incidental cleanup step.

Copy/trash support materialized paginated histories, not unresolved `history_base`
references. Archived, pinned, project/section-enriched sessions and unsupported
ancillary state (goals, queues, attachments, dynamic tools, memories) are rejected
rather than silently lost. Native provenance without a history reference does
not itself make a materialized copy dependent. Do not hand-edit source JSONL/DBs
to make a rejected session eligible.

## Verify, report and retain

Report per-ID success, failure and unattempted results, new IDs/provenance or the
recovery ID, and any retained destination/recovery artifacts. A failed publication
may leave a destination session; do not delete it or retry automatically. Native
management performs no model turns. It uses short-lived, network-isolated native
processes with synthesized config and disabled hooks, not real credentials.

Private state retains metadata receipts, copy provenance and recovery journals;
recovery bundles contain the selected original history. Temporary copy-validation
stores are disposable internal work, not user destinations. Retention can grow
across operations. Keep recovery state and OS-trash contents until the owner
approves cleanup after verification; do not infer deletion authority from age or
terminal status. Operational logs/caches and arbitrary external files are outside
this recovery contract. Stop and report unsupported state, uncertain inactivity,
changed sources, partial outcomes or a runtime/version mismatch.
