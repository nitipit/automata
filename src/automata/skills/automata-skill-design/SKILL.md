---
name: automata-skill-design
description: "Use for designing, reviewing or editing skills: purpose, activation, instructions, assets and boundaries."
---

# Automata Skill Design

Write compact, actionable skills. This skill owns design and revision, not installation.

1. **Define the purpose.** State the outcome and when to use the skill, including
   nearby non-matches. Split only distinct capabilities. Keep name/description
   frontmatter minimal; use a unique lowercase, hyphen-separated name matching
   the installed directory.

2. **Teach the missing part.** Add knowledge, decisions and constraints the agent
   would otherwise miss. Use familiar words, action verbs and clear headings;
   keywords for known concepts, short rules for decisions and permission. Preserve
   essential defaults, exceptions and stopping rules. Skip familiar explanations
   and repetition; prescribe steps only when order matters for correctness or safety.

3. **Improve the right owner.** Read the whole skill; distinguish weak guidance
   from discovery, loading or instruction conflicts. Avoid overlapping skills and
   rules. Keep style with character and runtime details with their owner. Refer to
   existing conventions without duplicating host-specific values or prescribing
   skill-loading chains. Preserve interface contracts. Discussion is not editing
   permission; ask before expanding approved scope.

4. **Keep the core small.** Keep essential rules in `SKILL.md`; load optional detail
   only when needed. Add assets only for a useful purpose; relocating always-read
   prose saves no context. Map tools through `metadata.automata-tools` to installed
   `.agents/tools/...` paths, not source paths. Installation does not prove readiness.

5. **Keep state separate.** Store mutable data outside the package with its owner;
   separate reusable knowledge from temporary state. Recheck outdated assumptions;
   never store secrets. Saved knowledge grants no permission, and completion grants
   no cleanup authority. Define retention; enforce concurrency and destructive-action
   safeguards in tools, not just prose.

6. **Check and report.** Preserve meaning, not just brevity. When evaluation is
   warranted, check selection and useful results separately using realistic tasks
   and nearby non-matches; loading or matching words alone proves neither. Keep
   checks proportionate. Report changed paths, changes, checks and limits. Compare
   bytes, lines and added/deleted lines with the pre-edit baseline unless another
   format is requested; disclose missing baselines and exclude unrelated changes.
   Counts are not quality scores or exact token measures.
