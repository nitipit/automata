---
name: automata-runtime-status
description: Use when checking which provider, model, or thinking level the current agent is running, including verification for team design or delegation.
---

# Automata Runtime Status

Verify the current agent's provider, model, and thinking level from runtime
information rather than recalling earlier settings or guessing variable names.

## Check current settings

In Pi, first run this through the current session's shell tool:

```bash
printenv PI_PROVIDER PI_MODEL PI_REASONING_LEVEL
```

Output follows that order. Pi injects these settings when the shell tool runs;
`PI_REASONING_LEVEL` is the thinking level, not `PI_THINKING_LEVEL` or
`PI_THINKING`. Missing variables can produce a nonzero exit code and fewer
lines. If output is incomplete, inspect each named variable separately so values
are not assigned to the wrong field. Report missing fields as unknown.

When operating inside a Pi extension, `ctx.model.provider`, `ctx.model.id`, and
`ctx.thinkingLevel` expose current settings; handle an absent model explicitly.
If the supported interface is unavailable, consult the installed runtime docs
before choosing another read-only source. Other harnesses may expose different
interfaces; do not assume Pi variables exist there.

Report the evidence source and distinguish current runtime settings from
historical session records. A snapshot describes settings at the time checked,
not a guarantee about provider-side execution or future requests. Do not scan
conversation histories as a routine fallback. Recheck after a relevant setting
change when the next decision depends on it.

## Boundaries

Read-only verification does not authorize changing settings, launching agents,
reading credentials, or creating logs or background processes. Inspect only the
named metadata, not the entire environment. Current-session evidence does not
verify a delegated worker; obtain that worker's own runtime evidence.

Model selection and team authority remain with their existing owners. Context
pressure and token usage remain with context-status; this skill only verifies
provider, model, and thinking settings.
