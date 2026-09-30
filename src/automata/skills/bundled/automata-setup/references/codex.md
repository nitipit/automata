# Native Codex CLI setup and support

Use ordinary Codex CLI with shared Automata guidance and shell tools. No Automata
wrapper, custom app-server host, Pi extension or separate Codex catalog is needed.
Identify the host, not the model name: Pi running a Codex model is still Pi.

These instructions describe the shared-support slice checked against Codex
**0.159.0**. Native discovery was verified offline; live agent behavior and native
image generation were not tested. Recheck version-dependent controls if your
installed Codex differs; do not silently transfer compatibility claims.

## Choose scope and exposure

Confirm selected assets, destinations and mode before installing. The commands
below are examples, not permission to run them. Run `uv run automata ...` from an
Automata checkout/environment; use an absolute target for a different project.
Use cached dependencies with `uv run --offline` when downloads are not authorized.

| Asset | Repository | Global |
| --- | --- | --- |
| Shared skills | `<project>/.agents/skills` | `~/.agents/skills` |
| Shared shell tools | `<project>/.agents/tools` | `~/.agents/tools` |
| Codex character instructions | `<project>/AGENTS.md` | `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`) |
| Pi character instructions | `<project>/AGENTS.md` | `~/.pi/agent/AGENTS.md` |

Prefer one exposure for each skill: **direct shared installation** is the simplest
choice for both runtimes; **plugin export** is an optional packaging alternative.
Inspect relevant selected destinations and existing plugin selections first.
Codex can discover same-name skills from both repository and global roots; it does
not promise nearest-wins precedence. Legacy Codex skill roots or plugin copies can
add another exposure. Do not duplicate an installed skill merely to enable Codex,
remove existing assets without permission, or assume an installer collision check
resolves runtime ambiguity. Pi-specific skills may remain in a shared installation;
`automata-pi-sessions` is explicitly for Pi, not Codex session management.

## Direct shared installation (recommended)

For a repository, choose a small initial set or the explicitly approved full
catalog. For example, from the Automata environment:

```bash
uv run automata skills install \
  --target-root /absolute/project/.agents/skills \
  --skill automata-plan,automata-software-development,automata-setup \
  --mode copy
```

For a global installation, use `--target-root ~/.agents/skills` instead. Omit
`--skill` only when all bundled skills are approved. There is no Codex-specific
installer switch. `copy` and `symlink` require absent selected destinations;
`replace` removes selected existing destinations before copying, not merging.
A symlink exposes source changes; it is not a runtime reload command.

Install companion shell tools only for selected capabilities, for example:

```bash
uv run automata tools install \
  --target-root /absolute/project/.agents/tools --tool timer --mode copy
uv run --offline --no-project --script \
  /absolute/project/.agents/tools/timer/timer.py --help
```

A skill's `.agents/tools/...` mapping points to a shell entry, not a registered
Codex function. Resolve it against the selected project or global install root,
not the skill directory. Dependencies, executable availability, sandbox file/socket
permissions and any browser/network access remain capability prerequisites.
Do not loosen sandbox/approval settings to make a tool appear ready. `--help` is
not a scheduler, browser, messaging or external-effects acceptance test.

## Character content, distinct instruction surfaces

Compose once for review using the chosen character components:

```bash
uv run automata character compose \
  --personality automata --language thai --behavior co-pilot
```

The command prints Markdown; it does not edit instructions. Only with separate
approval, place or merge reviewed content into the chosen `AGENTS.md` surface.
Do not overwrite an existing file by blindly redirecting stdout. Shared repository
content can serve both hosts, but neither reads the other's global file.

Codex's project chain is root-bounded; `AGENTS.override.md` takes precedence over
`AGENTS.md` in a directory. Trust and document-size limits affect loading. The
composed additional-instruction-directory guidance is an instruction to read
files, not a promise of automatic native Codex discovery. Verify the intended
surface rather than copying Pi's global path into Codex configuration.

## Optional plugin packaging

Export selected skills using the existing portable Agent Plugins format:

```bash
uv run automata plugin export \
  --name automata-selected --skill automata-plan \
  --output /absolute/output/automata-selected
```

This creates a package; it does **not** install or enable it in Codex. Registering
a marketplace or installing/enabling a plugin is a separate authorized native
Codex operation. Consult the installed version's plugin interface for that step;
this slice does not establish an interactive installation recipe. Prefer direct
installation above when a verified file-placement path is wanted.

The 0.159.0 native loader recognized the portable `plugin.json` and namespaced
skill from an isolated local marketplace fixture. The package was not enabled,
and no behavioral activation was proven. Exported `me.umlab.automata` tool metadata
is passive: shell files do not become MCP tools. No hooks or MCP adapters are
installed by this route. Avoid selecting the same skill through both mechanisms.

## Support boundaries

| Capability | Ordinary Codex CLI path | Pi remains unchanged |
| --- | --- | --- |
| Shared skills and character | Native discovery/instruction surfaces; agent judgment not certified | Existing discovery and surfaces |
| Shell tools / browser UI assets | Shared files, subject to dependencies and sandbox permissions | Existing CLI/assets |
| Image generation | Exposed native interface only; no API-key fallback | `codex_imagegen` bridge with confirmation and saved workspace path |
| Context status / effort / compact | Native human controls such as `/status`, `/model`, `/compact`; not Pi tool contracts | `context_status`, `thinking_control`, `context_compact` |
| Skill activity | Can query authorized existing Pi observations; no Codex recorder | Existing Pi observer/database |
| Router | Shared service and generic browser clients; no Codex agent adapter | `message_router`, Pi admission and pending context |
| Token landmarks / stable timestamps | No Automata equivalent installed | Pi branch accounting and request-local annotations |
| Session copy/trash | Native resume/fork are different; no Pi receipt/copy/trash parity | `pi_session_*` tools |

Do not call absent Pi tools, attach to an existing Codex daemon, inject history,
trust hooks, or build an adapter as an implicit fallback. Native controls do not
promise Pi summary-model selection, branch token semantics, message projection or
router wakeup/admission. Any future hook/MCP integration needs its own contract,
authorization and validation, not a broad parity claim.

## Verify at the appropriate boundary

After approved installation, check selected files and intended paths. Check native
skill discovery in a fresh authorized Codex session; starting or reloading a
session is separate from placing files. Report discovery independently from
behavioral usability. Do not send model requests merely to validate installation.
A live capability test needs its own allowed effects and prerequisites.

For maintainers, the repository's `docs/audits/codex-0.159.0/proofs.md` gives the
isolated no-network/no-credentials native discovery recipe and explicit limits.
The probe does not use user sessions or a shared daemon. Its source/API metadata
checks do not establish ordinary CLI model behavior, tool execution or readiness.
