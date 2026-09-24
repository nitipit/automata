# Skill activity extension

A Pi read-event observer with a bundled ShelfDB/Dictify CLI. Agent-facing data
access and interpretation guidance lives in the discoverable
`automata-skill-activity` skill (installed separately), not this developer README. The authoritative schemas remain in `store.py`.

## Storage

New records go to `~/.agents/var/tools/skill-activity/db`, regardless of the session
working directory or where the extension is installed. Each record retains its
`project` path. `list --project /absolute/project/path` filters before applying the
limit; omitting the filter lists across projects. The helper's explicit `--db`
argument remains available for scoped historical queries and isolated tests.
Existing project-local databases are not migrated, merged or deleted.

## Development

The extension runs the helper offline with a five-second timeout. Prepare its
pinned dependencies explicitly before use; installation itself does not fetch
Python packages or create a database. The helper exposes only `record` and `list`.

Set `PI_SKILL_ACTIVITY_SDK` to an installed Pi `dist/index.js` to enable the native
integration test, then run from the Automata checkout:

```bash
uv run --offline --with shelfdb==3.0.2 pytest -q \
  tests/integration/automata/extensions/skill_activity_test.py
```

The test uses an installed bundle, real Pi read/event handling and real ShelfDB,
with an offline model stub and a temporary home directory for global storage. Without the explicit SDK path,
the native test skips. No real model provider is called.
