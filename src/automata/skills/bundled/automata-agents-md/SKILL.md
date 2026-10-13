---
name: automata-agents-md
description: Use for configuring or reviewing AGENTS.md, character components and durable agent instructions. Not for temporary task assignments or runtime settings.
---

# Automata AGENTS.md

Configure durable instructions in the right scope. This skill owns instruction
configuration, not installation or temporary delegation briefs.

1. **Choose the target.** Inspect the instruction hierarchy, runtime and owning
   inputs. Confirm global, repository or nested scope and the destination file;
   do not assume the nearest file is the owner. Resolve competing surfaces before
   editing; approval for one file does not cover others.

2. **Align behavior.** Discuss material choices before writing. For new setups,
   consider role, action versus discussion, and follow-up preferences. For targeted
   changes, resolve only affected choices. Drafts and partial agreement are not
   editing permission; apply explicit approval without asking again for the same
   scope. Translate preferences into plain instructions, not unexplained labels.

3. **Compose from components.** Reuse suitable character components and inspect
   their actual content. Ask only about unresolved choices. For generated files,
   update owning inputs so regeneration preserves the change. Preview with:

   ```bash
   automata character list
   automata character compose --personality <name> --behavior <name>
   ```

   Composition prints Markdown; write it only to the approved destination.
   `--agents-md <directory>` selects additional-instruction discovery, not the
   output file. Keep those instructions in their skill-owned agent-data location.

4. **Keep instructions focused.** Use broadly applicable principles; leave
   specialized methods with their owner and temporary goals, permissions and
   evidence in task assignments. Resolve conflicts instead of appending more rules.
   Signal when specialized guidance matters, not a mandatory reading chain. Avoid
   copying additional instructions into generated files or putting host-specific
   paths in portable guidance.

5. **Check and report.** Review the result against approved behavior and scope.
   When practical, check runtime discovery; a correct file is not proof that a
   session loaded it. Report changes, unverified visibility and reload requirements.
