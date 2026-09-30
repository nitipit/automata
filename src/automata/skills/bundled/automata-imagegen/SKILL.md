---
name: automata-imagegen
description: Use when the agent needs a new raster image generated through an available native image-generation capability.
---

# Automata Imagegen

Use available native image generation for project illustrations, photos, textures,
sprites, product visuals and UI mockups, rather than an API-key script or browser
automation. An installed skill or model name does not prove tool availability.
Consult the exposed interface and its actual schema; report a missing capability
instead of inventing a tool or launching another agent as a substitute.

## First Move

Decide whether the requested result is a generated bitmap. Use the existing
project's SVG, HTML/CSS, canvas or code asset workflow instead when the user needs
deterministic vector or code-native output.

## Workflow

1. Clarify subject, intended use, composition, style, exact text and constraints
   when a missing detail would materially change the result.
2. Establish authorization for one image: a clear current-turn generation request
   suffices; ambiguous wording or an agent-inferred image requires confirmation.
   Never invent authorization or reinterpret a declined confirmation. Honor any
   tool-enforced confirmation flow as well.
3. Make one generation call with a complete prompt, exact text and important
   exclusions. Follow the available interface's actual output contract.
4. Inspect or integrate the selected result within scope. If it is saved outside
   the workspace, copy the actual artifact using normal filesystem tools. Keep
   the resolved destination, including parent symlinks, inside the authorized
   workspace. Refuse unintended overwrites and verify the copied file. Preserve
   the native original; no extra generator or publisher wrapper is needed.
5. Report the actual saved path and any meaningful limitation or failed iteration.

## Boundaries

- This workflow covers new image generation, not local-file editing or replacement
  of an existing vector/icon system. Other editing features have separate contracts.
- Generation consumes external quota. One-image consent is required even when the
  native interface does not enforce a one-call gate.
- Do not silently fall back to another provider, an API-key script or browser
  automation when the native capability is unavailable or fails.
- Do not overwrite an existing image unless explicitly requested.
- If only workspace copying fails, preserve and report the generated artifact.
  Repair the copy within scope rather than generating again. Never report a
  workspace path where the file has not actually been saved.
