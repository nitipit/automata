---
name: automata-storage
description: Use for choosing ownership, location and retention of agent-generated data or helpers, or reviewing and cleaning that storage. Not for arbitrary user-file management.
---

# Automata Storage

Choose storage by owner, lifetime and sensitivity, not file extension. Location
advice grants no creation, promotion, installation or migration authority.

1. **Use the owner's location.** Follow explicit conventions first. Repository defaults:
   - One-off helpers/intermediates: approved task area; `/tmp` only if restart loss is acceptable.
   - Skill helpers/preferences/setup: `.agents/var/skills/<skill-name>/`.
   - Tool data: `.agents/var/tools/<tool-name>/`.
   - App data: `.agents/var/apps/<app-name>/`.
   - User outputs: agreed destination, not a producer's cache.
   Use `~/.agents/var/` equivalents only for explicitly global capabilities; clarify
   unclear scope. The actual owner—not the creator—defines layout. Avoid duplicate
   shared state, unused directories and a central storage-skill directory. Task and
   source layouts remain with their owners; keep established paths unless migration
   is authorized. Packaged/installed helpers need promotion and deployment authority.

2. **Separate lifetimes.** Distinguish reusable knowledge, live handles, caches and
   evidence; separate files are optional. Keep useful verified knowledge, not secrets
   or copies of authoritative configuration. Owners define validity and recovery;
   recheck affected prerequisites and live identity before reuse.

3. **Review without automatic deletion.** Review accumulation at useful boundaries,
   not every write. Follow agreed retention policies; thresholds prompt review.
   Separate disposable caches from unique evidence, outputs and user material.
   Age or task status proves neither inactivity nor deletion permission.

4. **Clean within authority.** Identify exact owned candidates, dependencies and effects.
   Reuse clear scoped permission or ask. Prefer recoverable removal; permanent or
   automatic deletion needs explicit authority. Never delete active resources,
   follow links into another owner's data or discard referenced evidence by proximity.
   Ask before out-of-scope relocation/consolidation. Stopping activity and deleting
   records are separate actions.
