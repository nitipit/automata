---
name: automata-pi-skill-activity
description: Use for querying Pi skill-activity records, their schema/storage or recording coverage. Not for creating skills or choosing which skill to load.
---

# Automata Pi Skill Activity

Inspect observed skill loads, not instruction adherence. The extension records
activity; activating this skill does not create records.

1. **Locate the contract.** The global database is
   `~/.agents/var/tools/skill-activity/db`, shelf `skill_activations`. Read `SkillRead`
   and `SkillActivation` in the installed extension's `store.py` before building
   consumers; do not duplicate the schema. The global helper is
   `~/.pi/agent/extensions/skill-activity/store.py`. Keys are default-spacing Python
   `json.dumps([sessionId, toolCallId])`, not chronological positions. Values include
   skill/path/time/session/project and `source: read`, `status: loaded`, not prompts
   or instruction bodies. Missing/empty data does not prove no skill use. Legacy
   project-local databases remain unmigrated; inspect only within authorized scope.

2. **Query narrowly.** Default to the current project using exact recorded absolute
   `project` paths; shared storage grants no cross-project or session-history access.
   A bounded installed-helper query is:
   ```bash
   uv run --no-project --offline --script ~/.pi/agent/extensions/skill-activity/store.py \
     list --db ~/.agents/var/tools/skill-activity/db --project "$PWD" --limit 20
   ```
   The project filter precedes the limit; omit it only with broader authority.
   `list` returns at most 100 records in key order, not latest-first or full history.
   `record` belongs to the observer; never fabricate load events. Flexible consumers
   may use ShelfDB with the same schema and helper-pinned dependencies in an isolated
   environment. Query trusted local data with short read-only transactions and
   bounded collection; analyze after closing transactions.

3. **Interpret coverage.** Only successful complete, unpaginated `read` calls of
   `SKILL.md` with valid simple names are observed. Partial/limited/truncated/failed
   reads, shell reads, `/skill:name` and standalone Markdown skills are excluded.
   Review loads are indistinguishable from usage; records do not prove continued
   context after compaction. Replayed session/tool-call IDs deduplicate; new rereads
   remain events. Label event versus distinct-session counts and sort parsed times
   explicitly for chronology. Logging is best effort, not an audit or quality score.

4. **Preserve privacy and records.** Querying grants no export, modification, deletion,
   backfill or migration authority. Propose scoped retention cleanup rather than
   deleting old data automatically. There is no initial migration/versioning interface;
   report invalid records instead of reinterpreting them. Refer to the actual schema
   and [Dictify documentation](https://keenlycode.github.io/dictify/latest/).
