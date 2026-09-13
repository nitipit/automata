---
name: automata-pi-sessions
description: Use when discovering or removing Pi sessions where exact current-working-directory attribution and safe cleanup matter.
---

# Automata Pi Sessions

Use Pi's session tools instead of scanning, parsing, or deleting files under the
session store. Treat the exact Pi runtime current working directory (CWD) as the
session boundary.

## Session Identity

A recorded session ID is the primary identity for a delegated or otherwise owned
agent session. Record it when the session is created. Use `pi_session_list` for
discovery or recovery when that identity is missing or needs verification.

The same repository, a nested directory, another worktree, and a symlinked path
may have different CWD identities. Do not broaden exact-CWD results to a Git
repository or inferred path relationship.

A same-CWD listing does not prove that a session is owned, finished, or closed in
another Pi process. Establish those facts from the applicable delegation record,
return path, or user confirmation before cleanup.

## Discovery

Call `pi_session_list` without supplying a path. It obtains the CWD and session
storage location from trusted runtime context, omits unattributable sessions,
and returns full session IDs plus a short-lived listing receipt. It does not
return session paths or conversation content.

Do not substitute `SessionManager.listAll()`, filesystem searches, encoded
session-directory names, session names, or partial IDs for current-CWD identity.

## Intent and Permission

The agent establishes user intent and permission from context; the tool does not
show a confirmation dialog. A clear removal request or prior scoped authorization
is sufficient without asking again. A request to list or inspect sessions, or
agreement about the cleanup design, does not itself authorize removal.

When targets or scope are unclear, present relevant candidates with enough
metadata to distinguish them and ask what to move to recoverable trash. Stable
numbered choices can reduce effort: bind each number to an exact full session ID
from the displayed list, and keep that mapping during follow-up. A selection
authorizes removal only when the question clearly named that action.

Stay within the authorized scope. Establish ownership and inactivity from
applicable records or user clarification; names, age, and an unchanged file do
not prove a session is closed. The tool does not detect sessions open in another
Pi process. If uncertainty matters, clarify or leave the session untouched.

## Safe Cleanup

1. Obtain a fresh `pi_session_list` result.
2. Resolve the authorized target to its exact full session ID in that result.
3. Pass that ID and the matching receipt to `pi_session_trash`.

For several authorized targets, trash one at a time and list again after each
success because the receipt is invalidated. Preserve the user's selected IDs,
not positions in a refreshed list. Listing returns at most 100 sessions; disclose
omitted results rather than presenting it as a complete list.

If a receipt expires, refresh it without repeating permission for the same
unchanged targets and scope. If a session changes, disappears, or cannot be
identified unambiguously, reassess before proceeding; a new receipt alone does
not resolve uncertainty about intent or inactivity.

The trash tool rechecks the trusted CWD, receipt, session ID, file identity,
modification time, and current-session protection. It moves the session only to
recoverable operating-system trash and does not fall back to permanent deletion.

## Boundaries

- Do not use raw paths, `rm`, `unlink`, shell globs, or direct JSONL deletion for
  Pi session cleanup.
- Do not remove by session name, partial ID, guessed ownership, or repository
  membership.
- Do not remove the active session, sessions from another CWD, multiple sessions
  in one tool call, or a session that may still be open elsewhere.
- This skill owns exact-CWD discovery and safe trash decisions. Delegation and
  team-management guidance own session assignment, ownership, and completion.
- If `pi_session_list` or `pi_session_trash` is unavailable, report the missing
  Pi extension instead of bypassing its safety checks.
