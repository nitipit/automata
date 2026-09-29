---
name: automata-codex-imagegen
description: Use when the agent needs a new raster image generated through Codex's native image-generation capability.
---

# Automata Codex Imagegen

Use the `codex_imagegen` tool for project images such as illustrations, photos,
textures, sprites, product visuals, and UI mockups. Prefer native imagegen over
an API-key-based script or browser automation.

## First Move

Decide whether the requested result is a generated bitmap. Use the existing
project's native SVG, HTML/CSS, canvas, or code asset workflow instead when the
user needs deterministic vector or code-native output.

## Workflow

1. Clarify the subject, intended use, composition, style, exact text, and
   constraints when a missing detail would materially change the result.
2. Establish authorization for one image: a clear current-turn generation request
   suffices; ambiguous wording or an agent-inferred image requires confirmation.
   Never invent authorization or reinterpret a declined confirmation.
3. Call `codex_imagegen` with one complete image prompt. Include exact text
   verbatim and state important things to avoid.
4. Use the returned workspace path as the source of truth. Inspect or integrate
   the selected image before reporting the work complete.
5. Report the saved path and any meaningful limitation or failed iteration.

## Boundaries

- Use this skill for generation, not for extending an existing SVG/vector/icon
  system or replacing deterministic code-native visuals.
- This integration currently supports new image generation only; do not promise
  local-file editing through it.
- Do not fall back to the OpenAI API CLI, ask for an API key, or use browser
  automation when native Codex imagegen is unavailable. Report the blocker.
- Do not overwrite an existing image unless the user explicitly requests it.
- Treat generation as an external quota-consuming action. Explicit user intent
  authorizes only one image; ambiguous or agent-inferred calls require tool
  confirmation. The tool must return the final workspace path.
