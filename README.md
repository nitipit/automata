# Automata

Local-first capabilities for AI agents: character, skills, shell tools and runtime
integrations. The goal is useful task capacity across runtimes, not identical APIs.
This README is a quick orientation map; follow the relevant source for details.

## Source map

| Location | Owns |
| --- | --- |
| [`src/automata/character/`](src/automata/character/) | Identity, language and behavior components |
| [`src/automata/skills/bundled/`](src/automata/skills/bundled/) | Canonical skills and their supporting assets |
| [`src/automata/tools/`](src/automata/tools/) | Shared shell-invoked tools |
| [`src/automata/runtimes/pi/extensions/`](src/automata/runtimes/pi/extensions/) | Pi-native tools and event integrations |
| [`src/automata/apps/`](src/automata/apps/) | Maintained applications |
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

- [Skill design](src/automata/skills/bundled/automata-skill-design/SKILL.md): scope, activation and composition.
- [Setup](src/automata/skills/bundled/automata-setup/SKILL.md): asset selection, install modes and readiness.
- [Communication](src/automata/skills/bundled/automata-communication/SKILL.md): receiver, channel and outcome judgment; transport is an external integration.
- [Storage](src/automata/skills/bundled/automata-storage/SKILL.md) and [task spaces](src/automata/skills/bundled/automata-task-space/SKILL.md): ownership, placement and cleanup.
- [Testing](tests/README.md): test layout and verification scope.

## Pi Fast mode

The separate [`fast-mode` extension](src/automata/runtimes/pi/extensions/fast-mode/README.md)
provides `/fast on|off|status` and startup `--fast` request policy, including
eligible warming calls. It defaults off and follows session branch history;
response tiers are not tracked. Use official direct routes with no proxies or
model switches during dispatch: guards are best-effort, not physical-route
isolation. Disable competing `/fast`/`--fast` extensions under separate approval
before activation. Premium access and native costs are not billing evidence.

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

For development, use `uv run pytest` for the selected checks and
`uv run ruff check .` for lint. Prepare dependencies only within approved scope;
use offline execution when relying on already cached dependencies.

License: [MIT](LICENSE).
