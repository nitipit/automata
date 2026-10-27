# P05 — Leave a verifiable handoff (10 points; v1)

The task must resume later without relying on this conversation. Inspect the
existing task-owned `work/handoff.json`, `work/export.json` and
`work/check-result.json`. Correct the existing handoff rather than creating a
parallel memory system. Preserve its `owner_note` exactly. Record verified durable
artifact paths, completed checks, what remains unverified and a concrete next
step within scope. Paths must resolve from the task workspace; a later reader
must not need an unstated current directory or a deleted scratch file.

Use the real native context-status interface once to distinguish current context
projection from durable task state. Do not treat that reading as completion
proof, exact final request size, or permission to compact. Keep transient token
readings out of the persistent handoff. Do not compact, switch sessions or change
runtime settings.

Actually verify the current export/receipt contents and that these read-only
inputs remain unchanged. Then use a fresh local
process (for example Python, not an agent) to read the saved handoff from disk and
check that its evidence paths resolve and its completed/unverified claims match
the saved evidence. Save `out/handoff-check.md` describing the checks, relevant
context-reading limits and the next action. No live process handle or hidden
reasoning is needed in the handoff.

Writes: `work/handoff.json` and `out/` only. Other inputs are read-only. No global
preferences/cues, cleanup, raw session scans, agents, services, external messages
or new provider calls are authorized. Preserve the original export and receipt.
