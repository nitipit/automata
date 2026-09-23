---
name: automata-skill-activity
description: Use when querying or analyzing recorded skill activations, locating their schema and storage, or explaining recording coverage. Not for creating skills or deciding which skill to load.
---

# Automata Skill Activity

Inspect observed skill loads using the skill-activity data contract. Recording is
performed by the Pi extension, not by activating this skill. A record proves an
observed load, not that the agent followed the instructions.

## Locate the contract

Use the requested project's working directory; do not scan other projects or Pi
session histories to fill gaps.

- **Database:** `<session working directory>/.agents/var/tools/skill-activity/db`.
- **Shelf:** `skill_activations`.
- **Schema:** `SkillRead` and `SkillActivation` in the installed extension's
  `store.py`, at `~/.pi/agent/extensions/skill-activity/store.py` for the global
  extension. Read its Dictify definitions before building a consumer; do not
  maintain a second schema. The skill itself can be installed repo-locally or
  globally without changing the database location.
- **Key:** Python `json.dumps([sessionId, toolCallId])`, with default JSON spacing.
  This identifies a tool call, not a skill or a chronological position.
- **Value:** a mapping conforming to `SkillActivation`. It includes the skill name,
  path, timestamp, session and project, with `source: read` and `status: loaded`.
  No prompts or instruction bodies are stored.

If the extension or database is absent, report that recording may not be installed,
loaded, or used yet. An empty result does not establish that no skills were used.
Installation and reload are separate from querying existing records.

## Query

The narrow CLI provides a quick bounded view:

```bash
uv run --no-project --offline --script ~/.pi/agent/extensions/skill-activity/store.py \
  list --db .agents/var/tools/skill-activity/db --limit 20
```

Use the actual installed helper path. `list` returns at most 100 records in key
order, not latest-first; do not present that sample as the full history. `record`
is for the observer and validates metadata before writing; do not fabricate events
or manually log this skill's activation.

For flexible queries, use ShelfDB directly with the same contract. The helper's
script metadata pins ShelfDB and Dictify versions; use an isolated environment
with those dependencies, rather than changing a project's environment. Existing
cached dependencies can be used offline. Query only trusted local databases.

```python
from pathlib import Path
from shelfdb.shelf import DB

path = Path(".agents/var/tools/skill-activity/db")
if (path / "data.mdb").exists():
    with DB(str(path)) as db, db.transaction(write=False) as tx:
        records = [
            item.value for item in tx.shelf("skill_activations").items()
            if item.value["skill"] == "automata-work-design"
        ]
    # Analyze the selected records after closing the read transaction.
    print(records)
```

Keep transactions short and bound collection to the requested analysis. Report
whether counts mean load events or distinct sessions. Replayed session/tool-call
IDs are deduplicated; genuine rereads with different call IDs remain separate.
Sort parsed timestamps explicitly when chronology matters.

## Interpret coverage and preserve records

Only successful, complete, unpaginated `read` calls for `SKILL.md` with a simple
valid name are observed. Explicit limits, partial/truncated reads, failed reads,
`/skill:name`, shell reads and standalone Markdown skills are not recorded.
Reading a skill for review is indistinguishable from reading it for use. Records
do not indicate whether instructions remain in context after compaction.

Logging is best effort; failure warns without changing the read result. Crashes or
interrupted writes can leave gaps. This is usage evidence, not a security audit
trail or an evaluation of skill quality.

Keep records private. Querying does not authorize export, modification, deletion,
backfill, or cross-project collection. When accumulated data needs retention
review, propose scoped cleanup rather than automatically deleting old records.
The initial contract has no migration/versioning interface; do not silently
reinterpret invalid records. See the actual schema and the
[Dictify documentation](https://keenlycode.github.io/dictify/latest/).
