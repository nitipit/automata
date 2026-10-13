---
name: automata-documentation
description: Use when writing or restructuring related documentation for discoverability, clear information ownership, navigation and source traceability. Not ordinary text formatting or configuration editing.
---

# Automata Documentation

Make related documents easy for humans and agents to find, understand and maintain.
A reader should locate the relevant answer, inspect little unrelated content and
trace a maintained claim to its authoritative owner.

## Write for retrieval

Use descriptive filenames, explicit headings and consistent domain terminology.
Put important search terms in visible prose, not only metadata. Lead a section
with its answer or governing idea, then necessary conditions, exceptions and
examples. Keep search excerpts understandable without unexplained references to
"this" or "the above". Do not stuff keywords or repeat paragraphs for search.

Give each section a clear purpose. Prefer useful headings before splitting files;
split when a topic has an independently useful responsibility, not to meet an
arbitrary length. Keep related material together and provide navigation when the
structure would otherwise be difficult to discover.

## Define shared information once

Within a documentation tree, give shared facts, definitions, rules and procedures
one authoritative page or section. Reference that owner using relative links
instead of maintaining duplicate definitions. Do not repeat concrete paths or
values already defined by another owner.

Keep enough local orientation to explain why a reference matters; a brief summary
may help, but must not become a competing contract. If definitions conflict,
identify the intended owner and verify the claim rather than silently choosing the
newest wording. Single ownership does not guarantee freshness.

## Make references useful

Use descriptive link text and link to the relevant heading when it helps. Preserve
stable destinations where practical. When moving, renaming or restructuring pages,
update affected incoming links and navigation within scope; ask before changes
outside it. A link is useful only if the intended reader can access its target.

For derived documentation, identify the authoritative source and keep the derived
representation distinct. Link engineering claims to relevant code, tests, issues
or decisions where useful. Distinguish observed behavior, interpretation, proposals
and verified outcomes; do not present a proposal as current behavior.

## Verify and stop

Check affected links, headings and navigation, using existing renderers or link
checks when available. Verify changed claims against their owners and review that
conditions and exceptions survived restructuring. Report skipped or inaccessible
checks. Stop when the approved documentation outcome is clear and navigable; do
not expand into a repository-wide rewrite.

This guidance owns documentation structure and information relationships, not
configuration schemas, skill interfaces or storage policy. Do not impose universal
frontmatter, directory layouts or templates. Standalone prompts and configuration
files may need self-contained values; links cannot replace their required content.
