---
name: automata-codex-imagegen
description: Use when the agent needs a new raster image generated through Codex's native image-generation capability.
---

# Automata Codex Imagegen

Use native image generation for project illustrations, photos, textures, sprites,
product visuals and UI mockups, rather than an API-key script or browser automation.

## Runtime dispatch

Identify the host from its exposed interfaces, not the model/provider name.
In **Pi**, the `codex-bridge` extension exposes `codex_imagegen` and returns a saved
workspace path. In **native Codex CLI**, use its native image-generation interface
(such as `image_gen`) only when actually exposed, following that interface's schema
and output contract. Do not call the Pi tool name or launch another Codex process
as a substitute. Neither a Codex model name nor installed guidance proves imagegen
is available. If the required native interface is absent, report the blocker.

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
3. Call the available native interface with one complete image prompt. In Pi,
   this is `codex_imagegen`. Include exact text verbatim and important exclusions.
4. Inspect or integrate the selected image within the authorized scope. Verify its
   actual saved path before reporting a workspace file. In Pi, the returned
   workspace path is the source of truth.
5. Report the saved path and any meaningful limitation or failed iteration.

## Boundaries

- Use this skill for generation, not for extending an existing SVG/vector/icon
  system or replacing deterministic code-native visuals.
- This workflow covers new image generation only; Pi's bridge does not support
  local-file editing. Other native editing features have separate contracts.
- Do not fall back to the OpenAI API CLI, ask for an API key, or use browser
  automation when native Codex imagegen is unavailable. Report the blocker.
- Do not overwrite an existing image unless the user explicitly requests it.
- Treat generation as an external quota-consuming action. Explicit user intent
  authorizes only one image; ambiguous or agent-inferred calls require confirmation.
  Use Pi's bridge confirmation flow; in Codex, obtain consent before invoking native
  generation. Do not invent a workspace path when the result has not supplied or
  saved one.
