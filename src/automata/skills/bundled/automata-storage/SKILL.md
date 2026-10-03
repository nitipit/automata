---
name: automata-storage
description: Use when choosing ownership, locations, or retention for agent-generated helpers, temporary work, preferences, or operational data; also when reviewing or cleaning up that storage.
---

# Automata Storage

Choose storage by owner, lifecycle, and sensitivity, not file extension or every
read/write. Executable operational helpers are not automatically maintained source.
This skill chooses storage and retention; it does not approve tool creation,
promotion, installation, or arbitrary management of user files.

## Ownership and location

Follow explicit conventions first. Otherwise, in a repository use:

- One-off helpers/intermediates: the task's approved temporary area. Use `/tmp`
  only when loss across restart is acceptable; temporary is a lifecycle, not an owner.
- Reusable skill-owned helpers, preferences, and setup knowledge:
  `.agents/var/skills/<skill-name>/`.
- Existing tools' operational data: `.agents/var/tools/<tool-name>/`.
- Apps' operational data: `.agents/var/apps/<app-name>/`.
- User-requested outputs: the task's agreed destination, not a skill cache merely
  because a skill produced them.

Choose the actual owner, not whoever generated the file. Let that owner define the
internal layout; shared assets need one owner, not duplicate copies or a central
storage-skill directory. Do not create unused directories. Task-workspace and
maintained-source layout remain with their existing owners.

Use equivalent `~/.agents/var/` paths only for an explicitly global capability;
ask before choosing durable global storage when scope is unclear. Defaults do not
authorize new effects, migration, or installation. Keep existing locations unless
an authorized migration is needed. Putting a helper in packaged source or an
installed tools directory requires explicit creation/promotion and deployment
authority, not merely a convenient path.

## Reuse and lifetime

Separate preferences/setup knowledge, live handles, caches, and evidence when their
lifetimes differ; separate files are optional. Retain only useful verified knowledge
within storage authority, not secrets or copies of authoritative configuration.
Owners define validity and recovery. Recheck changed prerequisites and live identity
before reuse; a saved handle is not a permanent source of truth.

## Retention and cleanup

Review accumulation at meaningful boundaries using lightweight evidence, not scans
on every write. Apply the owner's agreed policy; thresholds prompt review, not
automatic deletion. Distinguish disposable caches from unique evidence, outputs,
and user-authored material. Age or terminal status does not establish inactivity.

Identify exact owned candidates, dependencies, and effects before moving or deleting.
Clear scoped cleanup approval needs no repeated confirmation; otherwise ask.
Prefer recoverable removal; permanent or automatic deletion needs explicit authority.
Never delete active resources, follow links into another owner's data, or discard
referenced evidence merely because it is nearby. Ask before relocating/consolidating
outside approved storage. Stopping activity and deleting its records are separate.
