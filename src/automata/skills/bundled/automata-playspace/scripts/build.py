#!/usr/bin/env python3
"""Compile Playspace TS + one shared Adaptive UI bundle using copied, cached inputs."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Requires existing Python, Deno, Node >=20.19 and Adaptive UI's locked cached "
        "dependencies (including esbuild 0.25.11). No installs/downloads, server or "
        "browser launch. Maintained/installed source is read-only. Inputs/checks live "
        "in a private temporary workspace; only compiled JS and starter assets are "
        "copied to the approved public root after a successful build. Existing unrelated "
        "public files and v1 browser cache are never removed. --validate runs focused "
        "component/state/transport/cache checks, not browser acceptance."
    ))
    parser.add_argument(
        "--runtime-root", required=True, type=Path, help="Approved public-safe website root"
    )
    parser.add_argument(
        "--ui-source", type=Path, help="Adaptive UI skill directory; defaults to sibling"
    )
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    ui = (args.ui_source or source.parent / "automata-adaptive-ui").resolve()
    public = args.runtime_root.expanduser().resolve()
    if public.is_relative_to(source) or public.is_relative_to(ui):
        parser.error("public root must be outside maintained/installed source")
    if not shutil.which("deno") or not shutil.which("node"):
        parser.error("Existing cached Deno and Node required; obtain authority before installing")
    try:
        with tempfile.TemporaryDirectory(prefix="automata-playspace-") as temporary:
            workspace = Path(temporary)
            ui_copy = workspace / "automata-adaptive-ui" / "lib"
            ps_copy = workspace / "automata-playspace"
            shutil.copytree(
                ui / "lib", ui_copy,
                ignore=shutil.ignore_patterns("node_modules", "dist", "browser"),
            )
            shutil.copytree(source / "lib", ps_copy / "lib")
            shutil.copytree(source / "tests", ps_copy / "tests")
            # One existing cached toolchain. Deno's cached-only task never fetches.
            subprocess.run(["deno", "task", "build"], cwd=ui_copy, check=True)
            config = {
                "nodeModulesDir": "auto", "unstable": ["sloppy-imports"],
                "compilerOptions": {"strict": False, "noImplicitOverride": False,
                                    "lib": ["dom", "dom.iterable", "esnext"]},
                "imports": {"@arrow-js/core": "npm:@arrow-js/core@1.0.6",
                            "@devcapsule/adapter": "npm:@jsr/devcapsule__adapter@4.0.0",
                            "edictor": "npm:edictor@0.4.0"},
            }
            (workspace / "deno.json").write_text(json.dumps(config))
            shutil.copy2(ui_copy / "deno.lock", workspace / "deno.lock")
            shutil.copy2(ui_copy / "dist" / "adaptive-ui.js", ps_copy / "lib")
            if args.validate:
                subprocess.run(
                    ["deno", "test", "--cached-only", "--no-run", "--config",
                     str(workspace / "deno.json"), *map(str, (ps_copy / "lib").glob("*.ts"))],
                    cwd=workspace, check=True,
                )
            staged = workspace / "public"
            (staged / "lib").mkdir(parents=True)
            shutil.copy2(ui_copy / "dist" / "adaptive-ui.js", staged / "lib")
            inputs = [
                path for path in (ps_copy / "lib").glob("*.ts")
                if not path.name.endswith(".d.ts")
            ]
            subprocess.run(
                ["node", str(ui_copy / "node_modules/esbuild/bin/esbuild"), *map(str, inputs),
                 "--format=esm", "--target=es2022", f"--outdir={staged / 'lib'}"],
                cwd=workspace, check=True,
            )
            for name in ["index.html", "index.js", "sample.js", "style.css"]:
                shutil.copy2(source / "starter" / name, staged / name)
            if args.validate:
                environment = {**os.environ, "PLAYSPACE_LIB": str(staged / "lib")}
                subprocess.run(
                    ["node", "--test", *map(str, (ps_copy / "tests").glob("*.test.mjs"))],
                    env=environment, cwd=workspace, check=True,
                )
            public.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staged, public, dirs_exist_ok=True)
        print(f"Built Playspace TS/public modules and shared Adaptive UI: {public}")
        return 0
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Playspace build failed: {error}; inspect public assets if copying was interrupted")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
