---
name: automata-cue
description: Use for remembering lasting decisions or preferences, recalling context through durable reminders, and updating or forgetting cues. Not for task tracking or full conversation archives.
---

# Automata Cue

Save short reminders that help future agents recover useful context. A cue is not
an authoritative instruction, complete memory or source of truth.

1. **Keep useful reminders.** Capture reusable decisions, preferences, discoveries
   and pointers. Keep one understandable idea per Markdown bullet; link to existing
   details instead of duplicating them. A cue does not require a fuller record.
   Leave changing task status with its existing owner.

2. **Recall and verify.** Read relevant cues when they help orientation or handoff.
   Follow pointers and verify consequential claims at their source before acting;
   a saved reminder is not current evidence or permission.

3. **Save with clear intent.** Save when asked to remember, given a clearly lasting
   instruction, or covered by approved automatic capture. Future intent matters,
   not specific words such as "always." Incidental remarks, one-off directions and
   task completion do not authorize saving. Resolve unclear intent, scope,
   conflicting notes or sensitive content; do not ask again about approved mechanics.
   Check the target file and update a matching note; leave unchanged notes alone.

4. **Use the right location.** Prefer established destinations for the confirmed
   scope. Use project scope for project conventions; global scope needs clear
   cross-project intent. Otherwise, use these defaults:
   - Project: `.agents/var/skills/automata-cue/cues.md` under the project root.
   - Global: `~/.agents/var/skills/automata-cue/cues.md`.
   A save request covers creating the default file and missing parent directories.
   Start new or revised notes with the actual save-time ISO 8601 timestamp and UTC
   offset; include source pointers where needed and preserve surrounding structure.

5. **Maintain safely.** Do not save secrets, raw transcripts or duplicate task
   records. Do not edit instruction files merely to remember a convention.
   Remove notes only with scoped permission; prefer recoverable removal and never
   delete referenced sources. Forgetting a cue does not erase conversation history.
   Delegated agents return cue candidates to their owner unless authorized to write
   shared notes.
