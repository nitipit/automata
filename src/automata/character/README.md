# Character

Reusable character components for composing agent behavior.

Character files are packaged plain Markdown instructions that can be rendered
for agents, AGENTS.md files, prompts, or global agent configuration. They are
meant to be mixed and matched rather than copied into one large instruction
file.

## Layout

- `personality/`: character, relationship, and voice.
- `language/base.md`: shared language-selection defaults.
- `language/`: optional language-specific style and usage.
- `behavior/base.md`: shared response shape, uncertainty, and tool-awareness defaults.
- `behavior/`: agency level, request handling, follow-up, and when to act or ask.

## CLI

Compose character instructions for another agent to read:

```bash
automata character compose \
  --personality automata \
  --language thai \
  --behavior co-pilot
```

Personality, language, and behavior groups are opt-in. A selected personality
includes only its file. When `--language` is selected, `language/base.md` is
included before the selected language. When one or more `--behavior` options are
selected, `behavior/base.md` is included before the selected behaviors. With no
component selections, composition fails with a `CharacterError`.

Successful composition includes discovery guidance for the default repository-local
additional-instruction directory. Use `--agents-md <path>` to override that directory.

## Examples

- `personality/automata.md` + `language/thai.md` + `behavior/co-pilot.md`:
  warm Thai-speaking thinking partner who discusses ambiguous work before
  acting.
- `personality/automata.md` + `behavior/autonomous.md`: warm implementation
  partner who acts independently when the goal is clear.
