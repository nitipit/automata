#!/usr/bin/env python3
"""Build the skill-owned UI library without modifying maintained or installed source."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""Requirements and execution:
  Building requires Python >=3.12, Deno, Node >=20.19, and cached locked
  dependencies. No dependency fetching is implicit; obtain approval before
  installing runtimes or deliberately prefetching missing dependencies.
  Installation needs no frontend runtime; display needs no build runtime once
  lib/adaptive-ui.js exists.

  Build inputs are copied to a private temporary workspace outside source and
  the website tree. Cached-only Deno tasks run there, never in maintained or
  installed source. Success atomically replaces the bundle; a failed build
  preserves the previous bundle. Temporary workspaces are removed on normal
  success or failure. After interruption, inspect ownership before cleanup.

Paths and updates:
  Relative roots resolve against the invocation CWD, not the skill directory.
  Resolve the approved website root absolutely before launching subprocesses.
  --check compares freshness without replacement; exit 0 means fresh, nonzero
  means missing, stale, or a build error (see stderr). Rebuild without --check
  when needed. --validate also runs type checks, tests, and lint.
  For experimental inputs, copy the shipped library outside installed source
  and the served tree, then use --source-root and a separate --runtime-root.

Website and preview:
  One website root shares lib/adaptive-ui.js across sessions/<name>/ pages.
  Adapt a shipped example into sessions/<name>/index.html; session assets may
  use relative URLs. There is no mandatory public/ folder or per-session server.
  Import /lib/adaptive-ui.js; do not copy the bundle into individual sessions.
  A shared rebuild affects all pages on their next reload. Automatic and
  agent-triggered reloads are full reloads, not transient-state preservation.
  Everything under the served root must be public-safe; keep credentials,
  browser profiles, build inputs, and operational records outside it.
  Any suitable loopback static server can serve an already built website.
  The bundled server below requires Deno but no external dependencies.

Examples (replace <skill-directory>, <name>, and <port>):
  RUNTIME_ROOT="$PWD/.agents/var/skills/automata-adaptive-ui"
  python <skill-directory>/scripts/build.py --runtime-root "$RUNTIME_ROOT"
  python <skill-directory>/scripts/build.py --runtime-root "$RUNTIME_ROOT" --check --validate
  deno run --no-config --no-lock --allow-net=127.0.0.1 --allow-read="$RUNTIME_ROOT" \
    <skill-directory>/scripts/library/src/server.ts --root="$RUNTIME_ROOT" --port=<port>
  Visit http://127.0.0.1:<port>/sessions/<name>/.

  This builder does not start a server or browser. Establish process ownership
  and cleanup before leaving either running; validate actual rendering and
  interactions, not just startup. Report the root, page URL, reload behavior,
  and observed result.
""",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=Path(".agents/var/skills/automata-adaptive-ui"),
        help="Website root (default: .agents/var/skills/automata-adaptive-ui "
        "under invocation CWD). Writes lib/adaptive-ui.js, never sessions/.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(__file__).resolve().parent / "library",
        help="Frontend source directory; defaults to the library shipped with this skill.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare a fresh build with the existing library without replacing it.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Also run cached Deno type checks, tests and lint in the temporary workspace.",
    )
    args = parser.parse_args()
    source = args.source_root.expanduser().resolve()
    runtime = args.runtime_root.expanduser().resolve()
    library = (runtime / "lib").resolve()
    skill = Path(__file__).resolve().parents[1]
    if library.is_relative_to(source) or library.is_relative_to(skill):
        parser.error("runtime library must be outside maintained and installed skill source")
    if not (source / "deno.json").is_file() or not (source / "build.ts").is_file():
        parser.error("source root must contain deno.json and build.ts")
    asset = library / "adaptive-ui.js"
    if args.check and not asset.is_file():
        parser.error("shared library is missing; build without --check first")
    deno = shutil.which("deno")
    if deno is None:
        parser.error("Deno is required to build; obtain permission before installing it")

    try:
        library.mkdir(parents=True, exist_ok=True)
        # Dependencies and build inputs must stay outside source AND the served tree.
        with tempfile.TemporaryDirectory(prefix="automata-adaptive-ui-") as temporary:
            workspace = Path(temporary) / "source"
            shutil.copytree(
                source,
                workspace,
                ignore=shutil.ignore_patterns("node_modules", "dist", "browser", "__pycache__"),
            )
            tasks = ["check", "test", "lint", "build"] if args.validate else ["build"]
            for task in tasks:
                subprocess.run([deno, "task", task], cwd=workspace, check=True)
            bundle = workspace / "dist" / "adaptive-ui.js"
            if args.check:
                if bundle.read_bytes() != asset.read_bytes():
                    print("Shared library is stale; rebuild without --check", file=sys.stderr)
                    return 1
                print(f"Fresh: {asset}")
            else:
                # Stage only the public bundle beside the destination for atomic replacement.
                descriptor, staged = tempfile.mkstemp(
                    prefix=".adaptive-ui-", suffix=".tmp", dir=library
                )
                try:
                    with os.fdopen(descriptor, "wb") as output, bundle.open("rb") as input_file:
                        shutil.copyfileobj(input_file, output)
                    os.replace(staged, asset)
                finally:
                    Path(staged).unlink(missing_ok=True)
                print(f"Built: {asset}")
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Build failed; existing library preserved: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
