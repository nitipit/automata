---
name: automata-skill-activity
description: Use when querying or analyzing recorded skill activations, locating their schema and storage, or explaining recording coverage. Not for creating skills or deciding which skill to load.
---

# Automata Skill Activity

Inspect observed skill loads using the runtime's skill-activity contract.
Recording requires its installed observer, not activation of this skill. A record
proves an observed load/insertion, not that the agent followed the instructions.

## Runtime dispatch

Identify the host, not the model. Pi uses its extension and ShelfDB contract
below. Native Codex uses the separately installed, explicitly activated 0.159.0
hook/helper described here; installing this skill alone installs no observer.
Never mix their counts or infer activation from discovery, shell intent or empty
storage. Either host may query the other runtime's records only within authorized
scope, with the relevant helper/dependencies and an explicit runtime label.

## Native Codex: query and coverage

Use the exact `skill_activity.py list` command supplied by the current session's
Automata hook. It includes the installed helper, chosen `--state-root`, explicit
`--transcript` and `--session`. Do not guess paths or discover neighboring sessions.
Use `--skill NAME` to filter before `--limit 1..100` (default 20); results are
newest native ordinal first. `matchedCount` counts retained insertion events,
not distinct skills or sessions. `inspect` returns the same observation contract.
Both commands read the authorized transcript and update recording through that
observation; they are not read-only database queries.

For historical queries, use the hook-supplied `skill_activity.py saved` command,
with only the authorized `--state-root` and durable `--thread UUID`. It needs no
transcript and performs no enrollment, backfill, lock-file creation or state write.
The same skill/limit filters apply. `saved-observations-only` and
`currentCoverage: unknown; transcript not consulted` distinguish saved evidence
from live coverage. It remains usable when the transcript is missing, rewound or
oversized. Absent state reports unknown enrollment/history without creating it;
never discover other threads or present an absent file as proof of no skill use.

Codex state is separate: `<state-root>/skill-activity/<thread-uuid>.json`, schema
version 1 in the installed `skill_activity.py` and `skill_records.py`. No Pi DB
migration or shared-schema reinterpretation occurs. Records include runtime,
skill name/path, native timestamp, observation time, session/thread/project,
message/turn IDs and `evidenceKind: native_instruction_insertion`. The observer
reads no skill file for identity and saves no instruction or conversation bodies.

Only successful native local-file instruction insertions carrying
`skills.selected_skill_instructions` metadata count. A user message shaped like
`<skill>`, available-skill list, failed/missing selection, shell read/script or
explicit cooperative report is not counted. Insertion may itself be natively
truncated; this is not Pi's complete-file-read meaning. Native metadata establishes
insertion, not necessarily every invocation, compliance or current context presence.

Enrollment starts at the first successful hook/control observation; prior history
is excluded, including inherited fork history. Later hooks/controls observe new
records, deduplicated by native message ID and content-part index. Resume/retries
retain identities. Delivery is delayed to a supported hook, not guaranteed at
turn end; query can bring it current. Results are lifetime observations, not
active-branch totals. Rewound/malformed/unavailable transcripts report unknown
coverage without deleting prior state. An empty result never proves no skill use.

With authorization to change recording, replace `list` with `disable` or `enable`.
The control first observes through the current boundary under the previous setting,
then changes it; enabling excludes events while disabled, with no backfill.
`disabledSkipped`, `capacitySkipped` and `partialTailDeferred` describe known gaps.
At 10,000 retained events per thread, recording stops adding events and reports
capacity skips, without eviction. There is no export/import/reset/delete action.
Review retention with the owner; do not remove active state or fabricate events.
If hooks/helper are absent, report uninstalled/unknown coverage rather than reading
history or installing an adapter implicitly.

## Pi: locate the contract

The recorder uses one global database across projects. Scope queries to the
requested project by its `project` field; use the current working directory when
no broader scope is requested. Shared storage does not authorize cross-project
analysis or scanning Pi session histories to fill gaps.

- **Database:** `~/.agents/var/tools/skill-activity/db`.
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
Installation and reload are separate from querying existing records. Older
versions recorded under `<session working directory>/.agents/var/tools/skill-activity/db`.
Those records remain there; the new default does not migrate or merge them. Inspect
an old project database only within the requested scope; moving records needs
separate authorization.

## Query

The narrow CLI provides a quick bounded view for the current project:

```bash
uv run --no-project --offline --script ~/.pi/agent/extensions/skill-activity/store.py \
  list --db ~/.agents/var/tools/skill-activity/db --project "$PWD" --limit 20
```

Use the actual installed helper path and exact absolute project path recorded in
`project`. The project filter applies before the limit. Omit `--project` only for
an authorized cross-project view. `list` returns at most 100 records in key order,
not latest-first; do not present that sample as the full history. `record`
is for the observer and validates metadata before writing; do not fabricate events
or manually log this skill's activation.

For flexible queries, use ShelfDB directly with the same contract. The helper's
script metadata pins ShelfDB and Dictify versions; use an isolated environment
with those dependencies, rather than changing a project's environment. Existing
cached dependencies can be used offline. Query only trusted local databases.

```python
from pathlib import Path
from shelfdb.shelf import DB

path = Path.home() / ".agents/var/tools/skill-activity/db"
project = str(Path.cwd())
if (path / "data.mdb").exists():
    with DB(str(path)) as db, db.transaction(write=False) as tx:
        records = [
            item.value for item in tx.shelf("skill_activations").items()
            if item.value["project"] == project
            and item.value["skill"] == "automata-teamwork-design"
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
backfill, or broader cross-project analysis. When accumulated data needs retention
review, propose scoped cleanup rather than automatically deleting old records.
The initial contract has no migration/versioning interface; do not silently
reinterpret invalid records. See the actual schema and the
[Dictify documentation](https://keenlycode.github.io/dictify/latest/).
