---
name: automata-pi-imagegen
description: Use in Pi when generating a new raster image through the codex-bridge extension's codex_imagegen tool.
---

# Automata Pi Imagegen

Use Pi's `codex_imagegen` tool for project illustrations, photos, textures,
sprites, product visuals and UI mockups. This workflow requires the installed
and exposed `codex-bridge` extension; installing the skill or selecting a model
does not expose the tool. If it is unavailable, report the missing capability.

The bridge owns native image generation and copying its result into the workspace.
Do not launch a separate CLI process or build a generator/publisher as a substitute.
This is Pi bridge guidance, not a prerequisite for another runtime's native image
capability.

## First Move

Decide whether the requested result is a generated bitmap. Use the existing
project's SVG, HTML/CSS, canvas or code asset workflow instead when the user needs
deterministic vector or code-native output.

## Workflow

1. Clarify subject, intended use, composition, style, exact text and constraints
   when a missing detail would materially change the result.
2. Establish authorization for one image: a clear current-turn generation request
   suffices; ambiguous wording or an agent-inferred image requires confirmation.
   Honor the bridge's confirmation flow. Never invent authorization or reinterpret
   a declined confirmation.
3. Call `codex_imagegen` once with a complete prompt, exact text and important
   exclusions. Follow its schema, using a workspace-relative `output_path` when
   a particular destination is needed.
4. Use the tool's returned workspace path as the source of truth. Inspect or
   integrate the selected image within the authorized scope before reporting
   the work complete.
5. Report the actual saved path and any meaningful limitation or failure. Do not
   claim a workspace file exists when the bridge has not saved it successfully.

## Boundaries

- This integration supports new image generation, not local-file editing or
  replacement of deterministic vector/icon systems.
- Generation consumes external quota. Explicit intent authorizes one image;
  ambiguous or agent-inferred calls require tool confirmation.
- Do not fall back to an API-key script, ask for an API key, use browser automation
  or silently change provider/model when the bridge is unavailable or fails.
- Do not overwrite an existing image without explicit user authorization or bypass
  the bridge's destination safeguards.
- If generation or workspace copying fails, report the known outcome rather than
  automatically making another generation call. Retain any reported artifact;
  scope recovery separately from generating a replacement image.
