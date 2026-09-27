# Tool Stack Defaults

Use these when selecting a tool's implementation stack and project conventions do
not already decide it. Keep dependencies local and proportionate. These defaults
do not authorize installation or downloads.

## Python

- Prefer `uv`, a project-local `.venv`, and `uv run ...`.
- For substantive agent-facing CLIs, use `cyclopts` and `dictify` together:
  Dictify models define validated inputs; Cyclopts binds commands and help.
  Verify field descriptions and cross-field errors through the real CLI.
- Use Dictify for structured results, configuration or persisted state when useful;
  do not force a model onto data that needs no validation.
- Keep tiny tools on the standard library when dependencies do not reduce complexity.

## JavaScript / TypeScript

- Prefer `pnpm` for packages and execution, with local dependencies and `pnpm exec`.
- Prefer `tsx` for no-build TypeScript execution.
- Use `node:util.parseArgs` for tiny scripts and `commander` for normal local CLIs.
- Use `zod` only when runtime validation materially improves safety.

## Deno

- Prefer single-file tools with explicit permissions when that is simpler.
- Use a pinned Cliffy release for durable, self-documenting CLIs; manual `Deno.args`
  parsing is for tiny dependency-free or bootstrap scripts.
- Keep dependency fetching explicit with `deno cache`, then run with
  `deno run --cached-only`.
- Document recovery when Deno or cached dependencies are missing. Never silently
  install Deno or fetch dependencies.
