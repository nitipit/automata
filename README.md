# Automata

Local-first capabilities for AI agents: character, skills, shell tools and runtime
integrations. The goal is useful task capacity across runtimes, not identical APIs.
This README is a quick orientation map; follow the relevant source for details.

## Source map

| Location | Owns |
| --- | --- |
| [`src/automata/character/`](src/automata/character/) | Identity, language and behavior components |
| [`src/automata/skills/`](src/automata/skills/) | Canonical skills, nested packages, discovery and export |
| [`src/automata/tools/`](src/automata/tools/) | Shell tools for Anatomy, timers and LINE |
| [`src/automata/runtimes/pi/extensions/`](src/automata/runtimes/pi/extensions/) | Pi-native tools and event integrations |
| [`src/automata/install/`](src/automata/install/) | Asset discovery and installation |
| [`src/automata/plugin/`](src/automata/plugin/) | Selected-asset plugin export |
| [`tests/`](tests/) | Software, packaging and integration checks |

## Boundaries worth remembering

- Portable skills stay agent-CLI-brand-neutral. Genuinely runtime-dependent skills
  name their runtime and required interface; do not duplicate skills for symmetry.
- Reuse native capabilities and existing shared tools before adding wrappers.
  A model/provider name does not identify the host runtime.
- Reuse tmux for cross-runtime collaboration; native collaboration is optional.
  Sending a message is not proof of handling or completed work.
- Installing assets does not activate hooks, grant trust, register shell tools as
  native functions or prove capability readiness. Confirm scope and effects first.
- Canonical source is separate from installed copies. Avoid duplicate skill
  exposure; installers do not automatically remove obsolete names or migrate data.
- Keep generated output, private state and task scratch outside maintained source.
  Follow the relevant owner’s storage convention; do not relocate data by habit.
- Mock fixtures establish the boundaries they exercise, not live model judgment.
  Keep verification claims and remaining limitations explicit.

## Find the relevant guidance

- [Skill design](src/automata/skills/automata-skill-design/SKILL.md): scope, activation and composition.
- [Pi extension development](src/automata/skills/automata-pi-extension-dev/SKILL.md): author extensions with compact READMEs, discoverable usage guidance and focused TSDoc.
- [Setup](src/automata/skills/automata-setup/SKILL.md): asset selection, install modes and readiness.
- [Delegation](src/automata/skills/automata-delegation/SKILL.md): work division, handoffs, coordination and acceptance, with conditional team-design and hierarchy references.
- [Manager](src/automata/skills/automata-manager/SKILL.md): an optional dedicated management role, not a requirement for ordinary delegation.
- [Communication](src/automata/skills/automata-communication/SKILL.md): receiver, channel and outcome judgment; transport is an external integration.
- [Pi agent workers](src/automata/skills/automata-pi-agent-team/SKILL.md): control native RPC subprocesses, retain live state in a task-owned kernel and return results by event.
- [Pi NodalWire](src/automata/skills/automata-pi-nodalwire/SKILL.md): find the installed peer-messaging extension's preparation and usage guide.
- [Storage](src/automata/skills/automata-storage/SKILL.md) and [task spaces](src/automata/skills/automata-task-space/SKILL.md): ownership, placement and cleanup.

## Automata Anatomy

[`automata-anatomy`](src/automata/tools/anatomy/README.md) serves one local monitor
and canonical skill catalog/source/reference viewer, with shared navigation,
appearance and live reload. Serving is foreground by default. Prepare the optional
`anatomy` extra and cached chart assets only with setup authority; core CLI does not
require web dependencies. Use `automata anatomy` or `automata-anatomy`.
There is no maintained `src/automata/apps/` category or separate skill-site server.

## Pi Fast mode

The separate [`fast-mode` extension](src/automata/runtimes/pi/extensions/fast-mode/README.md)
provides `/fast` toggling, `/fast on|off|status` and startup `--fast` request
policy, including eligible warming calls. It defaults off and follows session branch history;
response tiers are not tracked. Use official direct routes with no proxies or
model switches during dispatch: guards are best-effort, not physical-route
isolation. Disable competing `/fast`/`--fast` extensions under separate approval
before activation. Premium access and native costs are not billing evidence.

## Pi agent workers

Use [native Pi RPC guidance](src/automata/skills/automata-pi-agent-team/SKILL.md)
for approved worker subprocesses. A task-owned persistent Python kernel can retain
handles and results; an approved event bridge such as NodalWire returns completion
evidence to the interactive coordinator. Native RPC owns process/session control;
agent reasoning owns task policy and acceptance. No separate team controller is
bundled. Verify effective settings before dispatch and stop owned resources after
use. Installation, callbacks and live-model trials require their own authority.

The legacy `pi-agent-team` extension is retired. Its usage skill remains as the
kernel/native-RPC entry point; it no longer requires the extension's `agent_*`
tools. Installation does not remove old copies: retire any existing bundle only
with explicit authority, then use a supported reload or a fresh Pi process to
refresh the loaded tools.

## Pi NodalWire messaging

The opt-in [`nodalwire` extension](src/automata/runtimes/pi/extensions/nodalwire/README.md)
connects Pi to an existing trusted-local NodalWire relay. It receives custom
messages preserving native `pi.sendMessage()` delivery/wake-up options and provides
`nodalwire_connection` for client lifecycle control and `nodalwire_send` for
API-shaped named-peer messages. Prepare the pinned Edictor validator and published
`@devcapsule/nodalwire-client` dependencies as described in its README. There is no
automatic installation, relay startup, peer discovery or authentication. Live-model
trials require separate approval; automated checks do not prove live delivery.

## Entry points

Python project managed with `uv`; dependencies and CLI entry points are in
[`pyproject.toml`](pyproject.toml). Inspect command help before selecting effects:

```bash
uv run automata --help
uv run automata skills install --help
uv run automata tools install --help
uv run automata pi-extension install --help
uv run automata plugin export --help
```

Skill installation units are outer parents, not nested children. Installation
preserves source-relative layout; selecting a parent includes its nested skills
without extra exposures. Use `skills install --dry-run` to preview additions,
changes, unchanged packages and explicitly selected `--retire` names. Changed
packages need `--mode replace --backup-root <chosen-root>`; retirements also need
an explicit backup root. Unchanged packages are skipped. Missing catalog entries
never authorize deletion. See [Setup](src/automata/skills/automata-setup/SKILL.md)
for selection, backup recovery and retirement-only semantics.

Tool installation also supports `--dry-run`. Use `--mode replace --backup-root
<chosen-root>` for recoverable replacements, with backups outside selected packages.
Replacements are staged before the old tool moves; a reported publication failure
restores it when possible, otherwise the error identifies its preserved backup.
Earlier successful tools in a batch remain applied and are listed on failure.
Use exclusive destination write ownership: batches are not transactions, and abrupt
process termination can require manual recovery. Legacy replacement without
`--backup-root` retains its prior behavior; existing tools preview as changes.

For development, use `uv run pytest` for the selected checks and
`uv run ruff check .` for lint. Prepare dependencies only within approved scope;
use offline execution when relying on already cached dependencies.

License: [MIT](LICENSE).
