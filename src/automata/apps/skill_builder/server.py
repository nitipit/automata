"""Launch the ordinary Engrave CLI with reviewed assets and owned output.

No renderer, HTTP proxy, factory patch or custom watcher lives here. The source
layout can also be served directly with the command printed by ``serve``.
"""

import hashlib
import re
import shlex
import signal
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

from .content import SOURCE, discover

BUNDLES = {
    "prism.js": "db64933eccbb6f8edb10f1d0e0a94c1d5d4889fbc1c3705096a17dad9ffef8a2",
    "adaptive-ui.js": "c6642917e2be4da690c8c565d91f12e065c6e10247414bae67f2ca914b3ccc9a",
    "mermaid.js": "d0830a6c05546e9edb8fe20a8f545f3e0dc7c4c3134d584bad9c13a99d7a71e0",
}


def native_command(action, output, selector=None, all_skills=False, port=8788, root=SOURCE):
    """Construct a native CLI invocation; excludes also govern native HTTP paths.

    References are watched but not copied; selected SKILL.md files are public raw
    source assets. Shared HTML templates are inherited, not public routes.
    This is not a substitute for native Host/Origin/error handling (see README).
    """
    if version("engrave") != "3.2.6":
        raise RuntimeError("Skill site requires reviewed Engrave 3.2.6")
    root = root.resolve()
    pages = discover(root / "skills", selector, all_skills)
    for name, digest in BUNDLES.items():
        if hashlib.sha256((root / "templates/lib" / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unreviewed local bundle: {name}")
    assets = [
        root / "templates/skill.css.js",
        root / "templates/catalog.css.js",
        *(root / "templates/lib" / name for name in BUNDLES),
        *(root / "templates/components").glob("*.js"),
        *(root / "templates/licenses").glob("*.txt"),
    ]
    if any(not path.resolve().is_relative_to(root / "templates") for path in assets):
        raise ValueError("Asset escapes shared template root")
    copied = {path.relative_to(root).as_posix() for path in assets}
    copied.update(
        page.source.relative_to(root).as_posix()
        for page in pages if page.source.name == "SKILL.md"
    )
    allowed = set(copied)
    for page in pages:
        entry = root / page.template_name
        if not entry.is_file():
            raise ValueError(f"Missing native entry template: {page.template_name}")
        if not entry.resolve().is_relative_to(root):
            raise ValueError("Entry template escapes app root")
        allowed.update((page.template_name, page.url.lstrip("/")))
        allowed.add(page.source.relative_to(root).as_posix())
    allowed.add("templates/index.html")
    allow_pattern = "(?:" + "|".join(re.escape(path) for path in sorted(allowed)) + ")"
    command = [
        sys.executable, "-m", "engrave.main", action, str(root), str(output),
        "--copy", "^(?:" + "|".join(re.escape(path) for path in sorted(copied)) + r")\Z",
        "--exclude", "^(?!" + allow_pattern + r"\Z)",
    ]
    if action == "server":
        command += ["--host", "127.0.0.1", "--port", str(port)]
    return command


@contextmanager
def preview(selector=None, all_skills=False, port=8788, root=SOURCE):
    """Own one native subprocess and temporary output, including interrupted waits."""
    with tempfile.TemporaryDirectory(prefix="automata-skill-site-") as temporary:
        output = Path(temporary)
        command = native_command("server", output, selector, all_skills, port, root)
        print(shlex.join(command), flush=True)
        process = subprocess.Popen(command)
        try:
            yield process, output
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def serve(selector=None, all_skills=False, port=8788, root=SOURCE):
    def stop(signum, frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        with preview(selector, all_skills, port, root) as (process, _):
            try:
                if process.wait():
                    raise RuntimeError("Native Engrave failed; inspect its CLI output")
            except KeyboardInterrupt:
                pass
    finally:
        signal.signal(signal.SIGTERM, previous)
