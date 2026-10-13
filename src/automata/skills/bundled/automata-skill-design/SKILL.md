---
name: automata-skill-design
description: Use when designing, reviewing, or modifying skills—their scope, activation, instructions, supporting assets, or boundaries.
---

# Automata Skill Design

Write a short, concept-first contract: what the capability enables, when it
applies, and the principles that guide good decisions. Add detail only when it
changes behavior, resolves ambiguity or preserves a necessary contract.

1. **Define the capability.** Identify its useful outcome, scope and recognizable
   activation. A skill can supply judgment without an app or runtime. Keep a
   separate skill only for a distinct capability or decision; different labels
   or subtopics alone do not justify splitting. Check overlap and non-activation.
   Use minimal name/description frontmatter and a lowercase, hyphen-separated
   runtime name matching the installed directory; check name collisions.

2. **Summarize the judgment.** Prefer a few clear principles over long paragraphs,
   exhaustive checklists and prescribed workflows. Keep necessary defaults,
   conditions, exceptions, authority, success criteria and stopping boundaries.
   Require fixed steps only for mechanical, interoperability or safety needs.
   Clarity beats word-count reduction; do not force every skill into one template.
   Ordinary response style belongs to character guidance.

3. **Keep ownership clear.** Each skill stands independently and composes through
   context, with clear responsibilities, inputs, outputs and handoffs. Describe
   needed capabilities rather than requiring named skill-invocation chains.
   Keep portable contracts agent-CLI-brand-neutral; put runtime-dependent
   interfaces and prerequisites with their runtime owner. Installation does not
   prove that tools or extensions are exposed. Leave team topology and timing
   flexible unless the contract requires them.

4. **Keep the core small.** Keep essential obligations and defaults in `SKILL.md`,
   not optional reading. Use references for genuinely on-demand detail, examples
   for general behavior, templates for formats and tools for repeated mechanics.
   Moving always-read prose does not save context. Add assets only for a useful
   purpose, not to make the skill look substantial. Map tools via installed
   `.agents/tools/...` entries in `metadata.automata-tools`, not source paths.

5. **Separate instructions from state.** Keep mutable data outside the package
   under its owner's convention. Separate reusable setup knowledge, temporary
   handles, generated outputs and user inputs according to their lifetimes.
   Consult verified recipes and recheck invalidated assumptions, not everything.
   Retain useful commands, prerequisites, recovery and invalidation knowledge;
   never secrets. Saved knowledge grants no authority. Define resource lifecycle,
   retention and cleanup permission; completion does not authorize deletion.
   Enforce concurrency and destructive-operation safeguards in tools, not prose.

6. **Improve the right owner.** Read the whole skill before editing. Diagnose
   missing guidance versus failed discovery, loading, understanding or conflicting
   instructions. Fix a weak obligation before adding another skill; remove overlap
   rather than continually append rules. Do not universalize one incident.
   Complete approved changes, but ask before expanding scope, storage or runtime
   integrations. Discussion alone is not authorization.

7. **Verify meaning and behavior.** Preserve decisions and exceptions, not just
   shorter wording. Use proportionate behavior or interface checks; textual
   assertions do not prove agent behavior. Above 8,000 characters, review
   repetition and separable detail—not an automatic split or size target.

8. **Report the change.** Capture pre-edit baselines. Report edited paths, bytes
   and physical lines before → after, and added/deleted lines against that
   baseline. Exclude unrelated changes; disclose missing baselines. Summarize
   meaningful changes, verification and limits. Counts are not quality or exact
   token measures; honor a requested alternative report format.

This skill owns design and revision, not installation or runtime exposure.
