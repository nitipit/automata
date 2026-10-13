---
name: automata-pi-imagegen
description: Use in Pi for generating a new raster image with codex-bridge's codex_imagegen tool. Not for editing images or deterministic vector/code assets.
---

# Automata Pi Imagegen

Use the exposed `codex_imagegen` tool. Skill installation or model selection does
not expose it; report an unavailable bridge rather than substituting a CLI, API-key
script, browser workflow or different provider/model. Other runtimes need not use
this Pi bridge.

1. **Choose the asset type.** Generate bitmaps such as photos, textures or mockups.
   Use the project's SVG, HTML/CSS, canvas or code workflow for deterministic output.
   This tool creates new images; it does not edit local files.

2. **Confirm intent and brief.** A clear current-turn generation request authorizes
   one image and its external quota use. Ambiguous or agent-inferred images need
   confirmation; respect declined confirmations. Clarify only missing details that
   materially affect the result, then specify subject, use, composition, style,
   exact text, constraints and exclusions in the prompt.

3. **Generate and verify.** Call once using the tool schema and a workspace-relative
   `output_path` when needed. Use the returned workspace path as source of truth;
   inspect or integrate within scope and report the actual path and limits. Never
   claim a file exists without successful copying or overwrite an existing image
   without explicit authority; honor destination safeguards.

4. **Recover without duplicating generation.** Report known generation/copy outcomes
   and preserve reported artifacts. Failure does not authorize another generation,
   alternate provider or safeguard bypass. Scope recovery separately from a new image.
