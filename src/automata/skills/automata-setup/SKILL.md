---
name: automata-setup
description: Use for installing or updating Automata skills, tools and runtime integrations, or preparing approved global/repository capabilities. Not for skill authoring or character composition.
---

# Automata Setup

Use the `automata` CLI, not manual copies or a new installer wrapper. Installation,
exposure and verified readiness are different outcomes.

1. **Confirm the scope.** Resolve source (bundled by default), global/repository roots,
   resource types, selected names or explicitly all assets, and install mode. Reuse
   existing approval; ask only about missing choices. Default roots are global
   `~/.agents/skills`, `~/.agents/tools` or repository `.agents/skills`, `.agents/tools`.
   Identify runtime from intent/evidence, not model name; read its documented help
   and supported discovery paths. Respect narrower requests. Observers need explicit
   transcript/state-root consent. Character composition requires separate configuration.

2. **Preview and install.** Inspect selected destinations, then choose:
   - `copy`: create; changed existing skill destinations are refused.
   - `replace`: replace then copy, never merge.
   - `symlink`: expose source; conflicting existing destinations are refused.
   Skills skip identical copies/links in every mode. Other installers retain their
   own mode behavior. Skills require `--dry-run`; changed replacements need `replace`
   and an explicit `--backup-root`. Preview never creates targets or backups.
   ```bash
   uv run automata skills install --target-root <skills-root> \
     --skill <name-a>,<name-b> --mode replace --dry-run
   uv run automata skills install --target-root <skills-root> \
     --skill <name-a>,<name-b> --mode replace --backup-root <backup-root>
   ```
   Omit `--skill` only for all outer parents, except retirement-only requests.
   Custom `--source-root <local-path-or-file-url>` is exclusive, not bundled fallback;
   remote sources must first become confirmed local sources. Recursive discovery
   preserves source-relative layout and rejects duplicate names. Only outer parents
   install/export; nested children come with the parent, not flat extra exposures.
   Inspect relevant exposures; neither parent selection nor installation proves
   runtime precedence or nearest-wins behavior. Avoid duplicate exposures.

3. **Retire only selected names.** `--retire <name>` is explicit and requires backups.
   With no `--skill`, it means retirement-only, not install-all. Absent retired names
   are unchanged. A legacy flat nested-child name may be retired without touching
   its embedded parent copy; selecting that child for installation still rejects.
   Never infer retirement from catalog absence; preserve custom skills and data.
   ```bash
   uv run automata skills install --target-root <skills-root> \
     --retire <old-name> --dry-run
   uv run automata skills install --target-root <skills-root> \
     --retire <old-name> --backup-root <backup-root>
   ```
   Each changing run creates a unique `skills-*` backup directory outside packages.
   Links back up as links. Recovery restores the reported backup after safely setting
   aside replacements. Inspect partial failures before retrying.

4. **Verify the requested result.** Check installed files and report roots, modes,
   replacements and backups. Use fresh sessions/supported reload for runtime discovery;
   placement alone activates no hooks, trust or native tools. For tools use
   `uv run automata tools install --target-root <tools-root> --mode <mode>`; for runtime
   integrations use their documented installer and approved asset/state roots.
   Do not replace working symlinks just to refresh source changes.

5. **Establish readiness only when requested.** Follow the capability owner's smallest
   useful checks and recovery guidance. Installation alone permits no external tests,
   messages, dependency changes, services or agents. Reuse covered permissions; report
   missing prerequisites and untested limits. For communication, sending is not
   receiver handling or a working return path. Retain useful setup knowledge only
   within approved owner storage; do not create mandatory readiness registries or
   live-handle records. Recheck affected facts, not every installed capability.

Do not edit installed asset contents or `AGENTS.md` as setup, expand resource scope,
or infer global placement from convenience. Skill design and capability owners
retain their own responsibilities.
