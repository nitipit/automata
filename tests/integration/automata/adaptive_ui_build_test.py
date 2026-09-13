"""Build a skill-owned shared website library without touching installed source."""

import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from automata.install.skills import install_skills

SKILL = (
    Path(__file__).parents[3]
    / "src"
    / "automata"
    / "skills"
    / "operations"
    / "automata-adaptive-ui"
)
SOURCE = SKILL / "scripts" / "library"
HAS_BUILD_RUNTIME = shutil.which("deno") and shutil.which("node")
requires_build = pytest.mark.skipif(
    not HAS_BUILD_RUNTIME, reason="Runtime library build requires cached Deno and Node"
)


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def build(skill: Path, cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(skill / "scripts" / "build.py"), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=90,
    )


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Source-only skill installation does not require a frontend runtime.
    with monkeypatch.context() as environment:
        environment.setenv("PATH", "")
        install_skills(
            target_root=tmp_path / "installed skills", skill_names=["automata-adaptive-ui"]
        )
    skill = tmp_path / "installed skills" / "automata-adaptive-ui"
    assert not (skill / "scripts" / "library" / "browser").exists()
    assert not (skill / "scripts" / "library" / "node_modules").exists()
    assert not (skill / "scripts" / "library" / "dist").exists()
    return skill


def test_build_help_owns_operation_without_frontend_runtime(
    installed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = snapshot(tmp_path)
    monkeypatch.setenv("PATH", "")
    result = build(installed, tmp_path, "--help")
    assert result.returncode == 0, result.stderr
    assert snapshot(tmp_path) == before
    text = " ".join(result.stdout.casefold().split())
    for term in (
        "python >=3.12, deno, node >=20.19, and cached locked dependencies",
        "no dependency fetching is implicit",
        "obtain approval before installing runtimes",
        "display needs no build runtime",
        "private temporary workspace outside source and the website tree",
        "cached-only deno tasks",
        "success atomically replaces the bundle",
        "a failed build preserves the previous bundle",
        "after interruption, inspect ownership before cleanup",
        "relative roots resolve against the invocation cwd",
        "--check compares freshness without replacement",
        "--validate also runs type checks, tests, and lint",
        "--source-root and a separate --runtime-root",
        "no mandatory public/ folder or per-session server",
        "import /lib/adaptive-ui.js",
        "do not copy the bundle into individual sessions",
        "next reload",
        "everything under the served root must be public-safe",
        '--allow-net=127.0.0.1 --allow-read="$runtime_root"',
        '--root="$runtime_root" --port=<port>',
        "http://127.0.0.1:<port>/sessions/<name>/",
        "this builder does not start a server or browser",
    ):
        assert term in text, term


def test_skill_installs_cleanly_and_rejects_build_output_in_source(
    installed: Path, tmp_path: Path
) -> None:
    before = snapshot(installed)
    result = build(installed, tmp_path, "--runtime-root", str(installed / "generated"))
    assert result.returncode != 0
    assert "outside maintained and installed skill source" in result.stderr
    assert snapshot(installed) == before


@requires_build
def test_default_runtime_is_cwd_based_and_build_preserves_source(
    installed: Path, tmp_path: Path
) -> None:
    project = tmp_path / "project with spaces"
    project.mkdir()
    before = snapshot(installed)
    source_before = snapshot(SKILL)
    result = build(installed, project, "--validate")
    assert result.returncode == 0, result.stdout + result.stderr
    runtime = project / ".agents" / "var" / "skills" / "automata-adaptive-ui"
    asset = runtime / "lib" / "adaptive-ui.js"
    assert len(asset.read_bytes()) > 10_000
    assert set(snapshot(runtime)) == {"lib/adaptive-ui.js"}
    assert snapshot(installed) == before
    assert snapshot(SKILL) == source_before
    assert not (project / ".agents" / "tools").exists()
    checked = build(installed, project, "--check")
    assert checked.returncode == 0, checked.stderr
    assert "Fresh:" in checked.stdout
    asset.write_text("// stale shared asset\n")
    stale = build(installed, project, "--check")
    assert stale.returncode != 0
    assert "stale" in stale.stderr
    assert asset.read_text() == "// stale shared asset\n"
    assert snapshot(installed) == before


@requires_build
def test_explicit_root_build_failure_preserves_library_and_sessions(
    installed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "website"
    private = tmp_path / "private builds"
    private.mkdir()
    monkeypatch.setenv("TMPDIR", str(private))
    monkeypatch.setenv("TEMP", str(private))
    monkeypatch.setenv("TMP", str(private))
    args = ["--runtime-root", str(runtime)]
    missing = build(installed, tmp_path, *args, "--check")
    assert missing.returncode != 0
    assert "shared library is missing" in missing.stderr
    result = build(installed, tmp_path, *args)
    assert result.returncode == 0, result.stderr
    asset = runtime / "lib" / "adaptive-ui.js"
    previous = asset.read_bytes()
    page = runtime / "sessions" / "dashboard" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text('<script type="module">import "/lib/adaptive-ui.js";</script>')
    broken = tmp_path / "experimental source"
    shutil.copytree(SOURCE, broken)
    (broken / "build.ts").write_text('throw new Error("intentional build failure");\n')
    failed = build(installed, tmp_path, *args, "--source-root", str(broken))
    assert failed.returncode != 0
    assert "existing library preserved" in failed.stderr
    assert asset.read_bytes() == previous
    assert "import" in page.read_text()
    assert not list(private.iterdir())
    assert set(snapshot(runtime)) == {"lib/adaptive-ui.js", "sessions/dashboard/index.html"}
    assert not (tmp_path / ".agents").exists()


def test_adaptive_ui_internal_tasks_are_cached_and_permissioned() -> None:
    config = json.loads((SOURCE / "deno.json").read_text())
    tasks = config["tasks"]
    assert "exports" not in config and "publish" not in config
    assert config["nodeModulesDir"] == "manual"
    assert "serve" not in tasks  # Serving requires an explicitly selected website root.
    for name in ("build", "check", "test"):
        assert "--cached-only" in tasks[name]
    assert "--no-run" in tasks["check"]
    permissions = {
        value
        for value in shlex.split(tasks["build"])
        if value == "-A" or value.startswith("--allow-")
    }
    assert permissions == {"--allow-read=.", "--allow-write=dist", "--allow-run=node"}
    source = (SOURCE / "build.ts").read_text()
    assert "Node >=20.19" in source
    assert "clearEnv: true" in source


def test_adaptive_ui_keeps_arrow_and_reactive_component_contracts() -> None:
    package = json.loads((SOURCE / "package.json").read_text())
    ui = (SOURCE / "src" / "ui" / "adaptive-ui.ts").read_text()
    button = (SOURCE / "src" / "ui" / "_components" / "button.ts").read_text()
    assert package["dependencies"]["@arrow-js/core"] == "1.0.6"
    for export in ("component", "html", "nextTick", "onCleanup", "reactive"):
        assert export in ui
    assert 'from "@arrow-js/core"' in ui
    assert "attributeChangedCallback(" in button
    assert 'return ["label", "tone", "type"]' in button
