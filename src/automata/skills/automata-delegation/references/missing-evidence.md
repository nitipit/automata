# Missing delegation evidence

Use on an overdue-evidence notice or a concrete delivery failure. A worker's
missing callback is not manager loss; preserve the existing ownership contract.

1. Check once whether the expected callback or result already arrived, including
   queued messages and task correlation. If present, assess it instead of sending
   another status request.
2. If useful, send one bounded status request through the agreed safe return-capable
   transport. Use the communication owner's delivery checks; do not blindly retry
   a message that may already have been delivered.
3. Diagnose only the explicitly owned worker. Prefer its relevant message/artifact,
   then process/pane metadata; capture diagnostic output once if needed. Activity
   is not completion, acceptance or proof of callback delivery. Do not busy-poll.
4. Choose recovery, escalation, cancellation or stopping within the current contract.
   Preserve partial work and report the actual blocker. Replacing a worker requires
   an authorized ownership transfer, not just launching another process.

After assessment, cancel or re-arm the watchdog for the next meaningful evidence.
Its notice must wake the coordinator, identify the expected evidence and preserve
correlation. If the existing path becomes unsafe or unavailable, establish an agreed
replacement before removing still-needed coverage. Do not silently leave work
unwatched or turn recurring status requests into a substitute for callbacks.
