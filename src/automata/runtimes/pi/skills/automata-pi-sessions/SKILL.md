---
name: automata-pi-sessions
description: Use when discovering, copying or recoverably trashing Pi sessions for the current directory, another exact directory, or the default global store, including missing-directory review.
---

# Automata Pi Sessions

Use Pi's session tools, not raw session-store scans or manual file deletion.
This skill owns scope, selection, consent and recovery judgment; tools enforce
receipt binding and file-identity checks. Delegation records own worker assignment
and completion, not a session's name or age.

## Choose discovery scope

- `pi_session_list()` lists the exact runtime CWD using its active session store.
- `pi_session_list(cwd="/project")` lists another exact CWD, including a deleted
  directory, in Pi's default store. Relative paths resolve against the runtime CWD.
- `pi_session_list(scope="global")` searches across projects in the default global
  store. Ask for or reuse explicit global-discovery authority; do not broaden a
  project-scoped request merely for convenience.

Global scope cannot be combined with `cwd`. Exact matching is lexical, not recursive
or symlink-expanded; nested directories and worktrees may have separate identities.
Other-directory/global discovery does not load project settings or search custom
stores. Report this limitation; an empty listing is not proof that no history exists
elsewhere. The current-directory default continues to support its active custom store.

Results contain IDs, optional names, recorded CWD, timestamps, message counts and
current-session/directory status, not session-file paths or conversation contents.
Prefer recorded full session IDs over rediscovery by name. Duplicate IDs within
a search are non-selectable; narrow to an exact CWD and investigate ambiguity rather
than choosing an arbitrary file.

## Pages and missing-directory review

Use `limit` (1–100) for smaller pages. Follow `nextCursor` by supplying `cursor`
alone. Pages share a short-lived snapshot; changed or inaccessible session files are
omitted with `unavailableCount`. Restart discovery to see new/changed sessions.
A cursor expires, is superseded by new discovery, or becomes invalid if runtime CWD
changes. Do not present a page as the whole inventory when more remain.

Filter with `directoryStatus` when relevant:

- `exists`: the recorded path is currently a directory.
- `missing`: lookup reports no such path/directory.
- `unknown`: permission/access errors or a non-directory at that path.

A missing directory may have moved or be on an unmounted volume. Unknown does not
mean deleted. Neither condition, age, nor a successful copy authorizes cleanup.
Offer keeping history, copying to an existing destination, or explicitly selected
trash. Do not infer inactivity from unchanged timestamps or absent project files.

Each page issues separate `copyReceipt` and trash `receipt` values covering only
that page. The next page supersedes previous receipts. Review across pages if needed,
then re-list the page containing the confirmed full IDs before acting. Do not rely
on row numbers from a reordered listing. Receipts are evidence of selection, not
user permission.

## Copy selected sessions

Use `pi_session_copy` with exact `sessionIds`, a fresh `copyReceipt` and an existing
`targetCwd`. Establish authorization for the selected history and destination;
confirm sources are inactive. The current runtime session is rejected, but the tool
cannot detect all other Pi processes. Ensure the destination can receive the private
conversation content.

Copies use Pi's fork API on a private snapshot: new IDs, destination CWD, original
source provenance and preserved history. Originals remain untouched, even if the
SDK would repair a missing final newline. Malformed history is rejected, not silently
dropped. Project files, external assets, operational state and historical paths are
not migrated or rewritten.

Destination storage is Pi's default store, not target project custom configuration.
Report that limitation. Verify discovery of the copied IDs in the destination.
Copy does not authorize moving, rebinding in place or trashing the originals.

## Trash selected sessions

Use `pi_session_trash` with confirmed full `sessionIds` (or legacy `sessionId`) and
one fresh trash `receipt`. Source directories and file identities come from the
listing, including exact-directory/global listings; no separate trash `cwd` is needed.
This supports sessions from known deleted directories without changing runtime CWD.

Before calling, establish authorization and inactivity from context. A clear scoped
removal request needs no repeated permission; otherwise present candidates with
reasons and ask for explicit selection. Same-project membership, a completed task,
or old timestamps do not establish ownership or inactivity. Keep uncertain sessions.

The tool rejects the runtime's active session, rechecks every selected identity and
directory status, and uses recoverable OS trash only. If trash fails, report the
failure; never fall back to permanent deletion or raw file operations. A receipt for
one operation cannot authorize the other, and listing alone authorizes neither.

## Failure and recovery

Both mutations validate all selected identities before starting and recheck between
operations. After claiming a receipt, it is consumed even on partial failure. Results
identify successes, failures and unattempted IDs; preserve them before deciding next
steps. A failed copy may leave a destination file under its reported new ID. Do not
automatically retry or delete it. Reconcile the outcome with the user and re-list
before authorized recovery.

If a session or its directory status changes, reassess rather than refreshing blindly.
Expiration alone can be handled by re-listing the same approved scope without asking
again. No move, permanent-delete, automatic-retention cleanup or custom-store discovery
is provided. If required tools are unavailable, report the missing/reload-needed
extension instead of bypassing its safeguards.
