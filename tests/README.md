# Tests

Use the prepared Python development environment and `python -m pytest` for the
repository-wide entry point. TypeScript assertions use Node's built-in
`node:test`; thin pytest bridges prepare isolated copies and report Node failures.

## Pi agent-team and NodalWire

```sh
python -m pytest tests/unit/automata/extensions
python -m pytest tests/integration/automata/extensions/extension_test.py
# Select one extension across both levels:
python -m pytest tests/unit/automata/extensions tests/integration/automata/extensions/extension_test.py -k pi-agent-team
```

Add `-s` to see Node's individual TAP cases on success; failures always include
Node output. A passing pytest case represents a Node suite, not one assertion.

- `tests/unit/automata/extensions/<extension>/*.test.ts`: isolated logic and
  registration/messaging with doubles. Requires Node **24+** and the real library
  dependencies used by that suite, not an installed Pi runtime, relay or model.
- `tests/integration/automata/extensions/<extension>/*.test.ts`: real OS subprocess
  RPC, installed Pi loader or installed API compatibility. The fake-worker fixture
  is local to the worker integration directory; it never calls a provider.
- The bridges at each level use shared preparation in `tests/conftest.py`.
  Each suite checks its own prerequisites; missing Pi or a library does not skip
  unrelated cases. Node transforms TypeScript for execution; this is not `tsc`
  static type checking. No additional TypeScript test framework is used.

Set `PI_EXTENSION_TEST_NODE_MODULES` to a prepared `node_modules` containing
`typebox` and `edictor` **0.4.0**. This root is authoritative: missing libraries
skip only affected suites, without falling back to a host. Capture needs neither.
For existing setups, `NODALWIRE_TEST_NODE_MODULES` can supply Edictor separately;
source-local libraries and an installed Pi's TypeBox are optional conveniences.
No libraries are installed automatically. Native Pi cases discover `pi` on PATH
or use `PI_TEST_PACKAGE_ROOT` pointing to its package root.

The selected suites use no relay or real model and need no credentials. The
separate `tests/integration/automata/extensions/nodalwire_live_trial.py` utility
uses real processes/network/model quota and is **not** a routine test; execution
requires separate authorization.

Other extension suites retain their existing layout for now. Do not infer unit
or integration level solely from their current directory; this migration covers
only `pi-agent-team` and NodalWire.
