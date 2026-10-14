---
name: automata-pi-sessions
description: Use for listing, inspecting inactive, copying or recoverably trashing Pi sessions, including missing-directory history. Not for scanning raw session files or permanently deleting them.
---

# Automata Pi Sessions

Use Pi session tools. This skill owns selection, consent and recovery; tools enforce
receipts and identity checks but cannot detect all other active Pi processes.

1. **Choose discovery scope.** `pi_session_list()` uses the exact runtime CWD and
   active store. `cwd` selects another exact directory; `scope="global"` searches
   across projects. Both use Pi's default store, not other project settings/custom
   stores, and require appropriate authority. Global scope cannot combine with CWD.
   Matching is lexical, not recursive or symlink-expanded. Empty results prove no
   absence elsewhere. Prefer recorded full IDs; duplicate IDs are non-selectable,
   requiring narrower discovery rather than guessed identities.

2. **Respect pages and receipts.** Use `limit` 1–100; follow `nextCursor` with `cursor`
   alone. Snapshot omissions appear as `unavailableCount`; restart to see changes.
   Cursors expire or are superseded by discovery/CWD changes. Each page issues
   separate `copyReceipt` and trash `receipt` values; next pages supersede them.
   Re-list the page containing selected full IDs before acting, not reordered row
   numbers. Receipts bind selection, not permission. `directoryStatus` distinguishes
   `exists`, `missing` and `unknown`; missing may mean moved/offline, unknown may mean
   access errors. Neither these statuses nor age establishes inactivity or cleanup
   authority. Offer keep, copy or explicitly selected trash without assuming deletion.

3. **Inspect only authorized inactive sessions.** Metadata is not conversation context.
   Establish identity, store and inactivity from ownership/lifecycle evidence. An
   owned detached tmux probe may run `pi --session <full-id>` from matching CWD, with
   `--session-dir <store>` if needed; never guess using `--continue` or scan files.
   Supply no prompt, file input or submitted text. Review startup hooks first: resume
   can write state and cause effects. `--offline --no-extensions` limits networking
   and discovered extensions, but explicit `-e` still executes code and offline is
   not a model-call sandbox. Capture only needed visible status without changing
   user layout. Report resource differences; persisted/rounded footer usage is not
   fresh exact model context. Do not send prompts or compact for a better reading.
   Stop owned probes and verify closure; retain history unless trash is authorized.

4. **Copy selected history.** Call `pi_session_copy` with exact `sessionIds`, fresh
   `copyReceipt` and an existing authorized `targetCwd`. Confirm inactive sources
   and a destination suitable for private content; active-session rejection is not
   universal activity detection. Copies use new IDs and preserve provenance/history;
   originals remain unchanged and malformed history is rejected. Project files,
   external state and historical paths are not migrated. Destination storage is the
   default store, not custom project configuration. Verify copied IDs by discovery;
   copying does not authorize trashing originals or rebinding in place.

5. **Trash with scoped permission.** Call `pi_session_trash` with full `sessionIds`
   (or legacy `sessionId`) and fresh trash `receipt`; no extra CWD is needed.
   Establish authority and inactivity; reuse clear scoped removal permission or
   ask for candidate selection. Membership, completion and age prove neither.
   Keep uncertain sessions. Use recoverable OS trash only; failures never authorize
   raw file operations or permanent deletion. Copy/trash receipts are not interchangeable.

6. **Reconcile failures before retrying.** Mutations validate selections and recheck
   between operations. Claimed receipts are consumed even on partial failure.
   Preserve successes, failures and unattempted IDs; failed copies may leave a new
   destination file. Do not automatically retry or delete it. Reconcile with the
   user and re-list for authorized recovery. Expiration allows same-scope relisting,
   but identity or directory-status changes need reassessment. Unavailable tools
   require reporting/reload, not bypasses. No automatic retention cleanup, move,
   permanent-delete or custom-store discovery is provided.
