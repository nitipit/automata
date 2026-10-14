# Development tool readiness

Use this reference when a task needs tool selection, environment preparation or
setup recovery. It is language-independent guidance, not a required audit or a
reason to install every tool mentioned here.

## Discover only what matters

Start with project instructions, manifests, lockfiles, existing scripts and CI
commands. Identify the languages, runtimes and dependency environments actually
involved in the change. Reuse the project's conventions before suggesting a stack.
Check relevant areas, not every row on every task:

| Area | Useful evidence |
| --- | --- |
| Environment | Compatible runtime/compiler, package manager, dependencies and lockfile |
| Code intelligence | Available navigation, diagnostics, language server or type checker |
| Code quality | Existing formatter/linter, configuration and invocation scope |
| Testing | Runner, fixtures, focused commands, test dependencies and required services |
| Test quality | A concrete gap that coverage, property-based or mutation testing could address |
| Build/integration | Build/package commands, generated assets and external prerequisites |
| Debugging | Suitable logs, debugger or profiler when investigation needs them |

**Installed** means the executable or library exists. **Configured** means it
uses the intended project settings and environment. **Usable** means a small
representative operation succeeds for this task. Neither a version string nor
an empty diagnostics cache establishes readiness. Avoid sensitive output and
unrelated process or environment inspection.

## Resolve a consequential gap

Distinguish a missing tool from a wrong interpreter, discovery/configuration
problem, unavailable dependency, or broken invocation. Reuse verified setup and
inspect the failure before retrying; do not replace a working toolchain merely
because another tool is familiar.

Recommend the smallest remedy and its effects. A project development dependency,
a temporary isolated invocation, a globally managed standalone CLI, or no new
tool can each be appropriate. Libraries and plugins must be available to the
runtime executing the project; a separate global environment does not supply
imports or plugins to every project automatically.

Existing approval may cover routine operations, but downloads, dependency or
lockfile changes, installations and configuration changes need the relevant
permission. Tool execution can implicitly sync/download dependencies: inspect
that behavior and use offline/no-download controls when scope requires them.
Do not add wrappers, global configuration or agent integrations just to make a
familiar command available. Installing/exposing reusable Automata assets is a
separate setup operation, not implied by permission to prepare project tooling.

After an approved remedy, verify a relevant operation in the intended environment.
Report what is usable, what remains missing, and any platform/version limits.

## Choose verification by risk

Use changed behavior, callers/imports, existing tests and integration boundaries
to choose focused checks. Dependency analysis and previous execution coverage are
additional evidence, not proof that every affected test has been selected.
Shared fixtures, collection/configuration, dependency, packaging, lifecycle or
resource changes can require broader verification within the approved scope.

- **Coverage:** locate meaningful unexercised branches and failure paths. Evaluate
  assertions and behavior, not just percentages. Child processes and other
  runtimes may need explicit instrumentation; assets/services are not made safe
  by Python or other language coverage alone.
- **Property-based testing:** specify real contracts such as round-trip behavior,
  valid ordering, idempotence or rejected operations preserving state. Generate
  constrained useful inputs, keep examples independent and retain a minimized
  failing example as a regression. Existing example/integration tests remain.
- **Mutation testing:** assess whether tests detect altered behavior when test
  strength is uncertain. It is costly and intentionally modifies execution/code;
  agree on its scope, use an isolated checkout and preserve ordinary test results.
- **Parallel execution or environment matrices:** use when runtime cost or
  compatibility matters. Isolate ports, services, mutable state and dependency
  environments before assuming concurrency is safe.

Run at meaningful logical checkpoints, not automatically after each edit. Bound
expensive or generated-input runs, distinguish selection from execution, and
report skipped coverage honestly. A zero-test selection is not a correctness
result. Broader checks and release/CI verification retain their own authority.

## Ecosystem examples, not defaults

Select equivalents that fit the existing project; do not install these on sight:

- Python: pytest with pytest-cov for coverage; Hypothesis for generated properties.
  A project dependency or authorized `uv run --with` invocation can provide them.
- JavaScript/TypeScript: the existing runner's coverage support; fast-check for
  properties when it fits the runner and project.
- Rust: cargo test; cargo-llvm-cov for coverage; proptest for properties.
- Go: go test with coverage; built-in fuzz tests for input exploration.

Keep mutable reports, databases and generated examples outside installed skill
packages and maintained source, following the project's storage/ignore conventions.
Do not commit caches, share mutable test state between independent worktrees, or
remove recovery evidence without authority. Guidance and installation alone do
not prove an agent uses these tools appropriately; evaluate that separately when
needed and approved.
