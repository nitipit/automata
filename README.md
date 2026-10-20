# Automata

Local-first capabilities for AI agents: character, skills, shell tools and runtime
integrations. The goal is useful task capacity across runtimes, not identical APIs.
This README is a quick orientation map; follow the relevant source for details.

## Source map

| Location | Owns |
| --- | --- |
| [`src/automata/character/`](src/automata/character/) | Identity, language and behavior components |
| [`src/automata/skills/`](src/automata/skills/) | Canonical skills, nested packages, discovery and export |
| [`src/automata/tools/`](src/automata/tools/) | Shell tools, including Anatomy and separate Team |
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
- [Setup](src/automata/skills/automata-setup/SKILL.md): asset selection, install modes and readiness.
- [Communication](src/automata/skills/automata-communication/SKILL.md): receiver, channel and outcome judgment; transport is an external integration.
- [NodalWire](src/automata/skills/automata-nodalwire/SKILL.md): connect and use trusted-local messaging, with optional Pi integration guidance.
- [Pi workers](src/automata/skills/automata-pi-workers/SKILL.md): launch and operate separate Pi agents, with verified readiness and completion.
- [Storage](src/automata/skills/automata-storage/SKILL.md) and [task spaces](src/automata/skills/automata-task-space/SKILL.md): ownership, placement and cleanup.
- [Testing](tests/README.md): test layout and verification scope.

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

## Pi NodalWire messaging

The opt-in [`nodalwire` extension](src/automata/runtimes/pi/extensions/nodalwire/README.md)
connects Pi to an existing trusted-local NodalWire relay. It receives external
messages as custom follow-ups and provides `nodalwire_connection` for explicit
client lifecycle control and `nodalwire_send` for named-peer replies.
Install the published `@devcapsule/nodalwire-client` dependency; there is no
automatic installation, relay startup, peer discovery or authentication. See its
README for setup and the isolated Python → Pi → Python trial.

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
