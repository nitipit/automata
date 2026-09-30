# Codex quickstart

For the person or agent installing Automata into ordinary Codex CLI.
The optional helpers target **Codex 0.159.0, Linux/POSIX, Python 3.12+**.
See [README.md](README.md) for behavior, prerequisites and verification limits.

## Install approved assets

Run from an Automata environment, after confirming roots and mode:

```bash
uv run --offline automata codex install \
  --target-root ~/.agents/codex \
  --state-root ~/.agents/var/tools/codex-token-awareness \
  --mode copy
```

Helpers, this guide, README and generated `hooks.json` go **directly into the
chosen target root**. State stays outside it and is not created by installation.
`copy`/`symlink` require absent managed files; `replace` updates only managed
filenames, preserving other contents. Symlink mode links scripts/docs to source.
Legacy `token-awareness/` installations are not moved or deleted automatically:
verify the new files first, then remove only approved old files. Never remove an
old directory containing unrelated files or state.

Shared skills and tools use `automata skills install` and `automata tools install`;
inspect `--help` and select approved assets. Reuse existing skill exposure instead
of duplicating it. Runtime-specific skills require their named runtime.
Character composition and plugin export are separate operations, not activation.

## Activation is separate

Installation does **not** edit Codex config, `AGENTS.md`, hooks or trust, start a
session, or reload anything. With separate approval, review and merge the generated
hook groups into the intended native hooks file, preserving existing entries, and
review those exact commands with native `/hooks`. Changed paths need renewed review.
Activation authorizes current-session transcript observation and metadata storage;
explicit session-management commands require their own store/selection authority.

Check installed files and generated paths without model calls. Hook delivery and
live capability use need separately authorized checks; file placement is not proof
of activation or live model behavior.
