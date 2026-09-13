---
name: automata-cue
description: Use when asked to remember, retain, or carry decisions or conventions into future work; create, consult, update, or forget cues; or recover relevant context for orientation or handoff using durable anchors.
---

# Automata Cue

Make quick notes that help a future agent recall something useful. A cue is a
reminder, not complete memory, an authoritative instruction, or the source of truth.

## Keep the useful reminder

Capture reusable decisions, preferences, discoveries, and pointers. Prefer one idea
per Markdown bullet, usually 15–40 words excluding its timestamp and source pointer.
This is a soft target: recall matters more than word count. Keep enough meaning to
recognize the idea; link to details rather than compressing everything into the note.
Leave changing task status in its existing owner records.

Start each new or revised note with the actual save-time ISO 8601 timestamp and
UTC offset. Add a source pointer when needed to recover context; verify consequential
claims at their source before acting. Preserve the surrounding file's structure.

Useful:
```markdown
- 2026-09-13T09:44:00+07:00 — Be an engineering partner, not an echo. Choose teams
  for real benefit; revise recommendations for evidence, not merely agreement.
```

Too much: a transcript of every team proposal, objection, and tool call. Keep the
lesson, not the whole conversation. Example timestamps are illustrative, not facts
to copy into a new note.

## Recall and save

Read relevant cues when they help orientation. Before saving, check the intended
file and revise a matching note rather than duplicating it; unchanged notes need
no rewrite. Save on an explicit “remember this” request or approved automatic
capture—not merely because a review or task finished.

Follow an established destination or explicit data convention. Otherwise use:

- Global preferences: `~/.agents/var/skills/automata-cue/cues.md`.
- Project-specific knowledge: `.agents/var/skills/automata-cue/cues.md` under the
  project root.

A save request authorizes creating the missing default file and parent directories;
no separate file-creation approval is needed. Ask when intent, scope, conflicting
notes, or sensitive content needs clarification—not for routine storage mechanics.

## Boundaries

Do not store secrets or raw transcripts, duplicate task records, or edit instruction
files merely to remember a convention. Remove notes only with scoped authorization;
prefer recoverable removal and never delete their referenced sources. Removing a
cue does not erase conversation history. Delegated agents return cue candidates to
their owner rather than writing shared notes without authority.

Cue owns anchor selection, retrieval, and maintenance—not task tracking or a
separate memory system.
