# Python workspace example moved

The browser-counter example now ships with the
[Python workspace skill](../../src/automata/skills/bundled/automata-python-workspace/SKILL.md).
Follow its [example README](../../src/automata/skills/bundled/automata-python-workspace/examples/browser-counter/README.md)
to install the shared tool and copy the example into a task-owned directory.

The reusable execution engine lives in
[`src/automata/tools/python-runtime/`](../../src/automata/tools/python-runtime/).
The original prototype implementation was retired after verifying the packaged
replacement. Existing ignored local environments and artifacts are not migrated
or deleted automatically.
