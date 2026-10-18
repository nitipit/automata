import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from importlib.resources import files as resource_files
from pathlib import Path

import pytest

from automata import __version__

PI_RUNTIME = ("runtimes", "pi")
PI_SKILLS = ("skills",)
PI_EXTENSIONS = (*PI_RUNTIME, "extensions")


def files(package: str) -> Path:
    """These filesystem packaging tests intentionally require concrete paths."""
    return Path(str(resource_files(package)))


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_package_includes_self_documenting_python_tools() -> None:
    package_root = files("automata").joinpath("tools")
    scripts = (
        package_root.joinpath("timer", "timer.py"),
        package_root.joinpath("line", "line_cli.py"),
    )

    for script in scripts:
        assert script.is_file()
        assert "from cyclopts import" in script.read_text()
        assert not script.parent.joinpath("README.md").is_file()


def test_package_excludes_removed_jev_capability() -> None:
    package_root = files("automata")
    assert not package_root.joinpath("tools", "jev").exists()
    assert not package_root.joinpath("skills", "operations", "automata-jev").exists()


def test_package_excludes_retired_workspace_implementation() -> None:
    package_root = files("automata")
    assert not package_root.joinpath("apps", "workspace").exists()
    assert not package_root.joinpath("skills", "core", "automata-workspace-app").exists()


def test_package_excludes_native_codex_runtime() -> None:
    package_root = files("automata")
    assert not package_root.joinpath("runtimes", "codex").exists()
    assert not package_root.joinpath("install", "codex.py").exists()
    assert not package_root.joinpath("skills", "automata-codex-sessions").exists()


def adaptive_ui_source():
    return files("automata").joinpath(
        "skills", "automata-web-design", "skills", "automata-adaptive-ui", "lib"
    )


def test_adaptive_ui_skill_ships_source_without_generated_library() -> None:
    source = adaptive_ui_source()
    assert source.joinpath("build.ts").is_file()
    assert source.joinpath("src", "ui", "adaptive-ui.ts").is_file()
    assert source.joinpath("package.json").is_file()
    assert source.parent.joinpath("scripts", "build.py").is_file()
    assert not source.joinpath("example", "chat-with-agent.html").exists()
    assert not source.parent.joinpath("scripts", "library").exists()
    assert not source.joinpath("example", "chat.html").exists()
    assert not source.joinpath("browser").is_dir()
    assert not files("automata").joinpath("tools", "adaptive-ui").is_dir()


def test_package_excludes_adaptive_ui_generated_trees_from_sdists_and_wheels() -> None:
    project_root = Path(__file__).parents[3]
    config = tomllib.loads((project_root / "pyproject.toml").read_text())

    assert config["tool"]["uv"]["build-backend"]["source-exclude"] == [
        "src/automata/skills/automata-web-design/skills/automata-adaptive-ui/lib/dist",
        "src/automata/skills/automata-web-design/skills/automata-adaptive-ui/lib/dist/**",
        "src/automata/skills/automata-web-design/skills/automata-adaptive-ui/lib/node_modules",
        "src/automata/skills/automata-web-design/skills/automata-adaptive-ui/lib/node_modules/**",
        "src/automata/skills/**/__pycache__/**",
        "src/automata/tools/**/__pycache__/**",
    ]


def test_built_archives_ship_pi_resources_only_at_new_paths(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for offline package build")
    root = Path(__file__).parents[3]
    output = tmp_path / "dist"
    build = subprocess.run(
        [uv, "build", "--offline", "--out-dir", str(output), str(root)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheel = next(output.glob("*.whl"))
    sdist = next(output.glob("*.tar.gz"))
    expected = {
        "runtimes/pi/extensions/context-status.ts",
        "runtimes/pi/extensions/fast-mode/index.ts",
        "runtimes/pi/extensions/fast-mode/README.md",
        "runtimes/pi/extensions/message-timestamps.ts",
        "runtimes/pi/extensions/token-awareness.ts",
        "skills/automata-pi-context-status/SKILL.md",
        "skills/automata-pi-context-compaction/SKILL.md",
        "skills/automata-pi-sessions/SKILL.md",
        "skills/automata-pi-imagegen/SKILL.md",
        "skills/automata-pi-skill-activity/SKILL.md",
        "runtimes/pi/extensions/codex-bridge.ts",
        "skills/automata-workplan/SKILL.md",
        "skills/automata-storage/SKILL.md",
        "skills/automata-web-design/skills/automata-adaptive-ui/scripts/build.py",
        "skills/automata-agent-evaluation/templates/evaluation-record.json",
        "tools/anatomy/server.py",
        "tools/anatomy/cli.py",
    }
    with zipfile.ZipFile(wheel) as archive:
        wheel_paths = {
            name.removeprefix("automata/")
            for name in archive.namelist()
            if name.startswith("automata/") and not name.endswith("/")
        }
    with tarfile.open(sdist) as archive:
        sdist_paths = {
            member.name.split("/src/automata/", 1)[1]
            for member in archive.getmembers()
            if member.isfile() and "/src/automata/" in member.name
        }
    for paths in (wheel_paths, sdist_paths):
        assert not any(path.startswith("runtimes/codex/") for path in paths)
        assert "install/codex.py" not in paths
        assert not any(path.startswith("skills/automata-codex-sessions/") for path in paths)
        assert "skills/automata-time-awareness/SKILL.md" not in paths
        assert "skills/automata-timer/SKILL.md" in paths
    source_catalog = root / "src/automata/skills"
    catalog_files = {
        "skills/" + path.relative_to(source_catalog).as_posix()
        for path in source_catalog.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    for paths in (wheel_paths, sdist_paths):
        assert expected <= paths
        assert catalog_files <= paths
        assert not any(path.startswith("skills/automata-playspace/") for path in paths)
        assert "tools/anatomy/templates/skills/lib/mermaid.js" in paths
        assert "tools/anatomy/templates/skills/lib/prism.js" in paths
        assert "tools/anatomy/templates/skills/catalog.html" in paths
        assert "tools/anatomy/templates/skills/skill.html" in paths
        assert "tools/anatomy/templates/skills/index.html" not in paths
        assert "skills/core/automata-workplan/SKILL.md" not in paths
        assert not any(path.startswith("skills/automata-plan/") for path in paths)
        assert not any(
            path.startswith(("apps/", "skills/bundled/", "skills/templates/")) for path in paths
        )
        assert not any(
            "/node_modules/" in path or "/lib/dist/" in path or "/__pycache__/" in path
            for path in paths
        )
        assert "tools/anatomy/templates/skills/lib/highlight.js" not in paths
        assert "tools/anatomy/templates/skills/licenses/prism-LICENSE.txt" in paths
        assert "tools/anatomy/templates/skills/licenses/highlightjs-LICENSE.txt" not in paths
        assert "tools/anatomy/templates/skills/licenses/PROVENANCE.txt" in paths
        assert not any(path.startswith("extensions/") for path in paths)
        pi_skill_names = (
            "automata-pi-context-status",
            "automata-pi-context-compaction",
            "automata-pi-sessions",
            "automata-pi-imagegen",
            "automata-pi-skill-activity",
        )
        assert not any(
            path.startswith("skills/core/") and path.endswith(f"{name}/SKILL.md")
            for path in paths
            for name in pi_skill_names
        )

    # Exercise extracted wheel resources outside the checkout without installing.
    site = tmp_path / "site"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(site)
    smoke = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            """
import sys
from pathlib import Path
site, work = map(Path, sys.argv[1:])
sys.path.insert(0, str(site))
import automata
from automata.install.skills import install_skills, skill_sources
from automata.install.pi_extensions import install_pi_extensions
from automata.plugin import export_plugin
assert Path(automata.__file__).is_relative_to(site)
sources = skill_sources()
assert all(path.is_relative_to(site) for path in sources.values())
assert len(sources) == 38
assert 'automata-team-use' not in sources
assert (sources['automata-background-process'] / 'SKILL.md').is_file()
assert 'automata-thinking-control' not in sources
assert 'automata-pi-sessions' in sources
assert 'automata-web-design' in sources
assert 'automata-web-app' in sources
assert 'automata-web-dev' not in sources
assert 'automata-playspace' not in sources
assert 'automata-codex-sessions' not in sources
assert not (site / 'automata/runtimes/codex').exists()
assert not (site / 'automata/install/codex.py').exists()
assert 'automata-time-awareness' not in sources
assert 'automata-timer' in sources
assert all(path.name == name for name, path in sources.items())
assert sources['automata-workplan'] == site / 'automata/skills/automata-workplan'
assert 'automata-plan' not in sources
assert not any(name in sys.modules for name in ('engrave', 'mistune', 'playwright'))
results = install_skills(target_root=work / 'skills')
assert set(skill_sources(work / 'skills')) == set(sources)
for name in ('automata-storage', 'automata-pi-context-status',
             'automata-workplan', 'automata-agent-design'):
    assert (work / 'skills' / name / 'SKILL.md').is_file()
install_skills(target_root=work / 'linked', skill_names=['automata-agent-design'], mode='symlink')
linked = work / 'linked/automata-agent-design'
assert linked.is_symlink() and linked.resolve() == sources['automata-agent-design']
assert (linked / 'SKILL.md').read_bytes() == (
    work / 'skills/automata-agent-design/SKILL.md'
).read_bytes()
# Copy the webapp from installed skills, resolving its installed sibling dependency.
import subprocess, json
web_skill = work / 'skills/automata-web-design/skills/automata-web-app'
project = work / 'webapp'
created = subprocess.run([sys.executable, str(web_skill / 'scripts/create.py'),
                          '--output', str(project)], capture_output=True, text=True)
assert created.returncode == 0, created.stdout + created.stderr
config = json.loads((project / 'deno.json').read_text())
from urllib.parse import urlparse, unquote
for key, value in config['imports'].items():
    if key.startswith('@adaptive/'):
        dependency = Path(unquote(urlparse(value).path))
        assert dependency.is_file() and dependency.is_relative_to(work / 'skills')
assert (project / 'app/main.py').is_file()
assert not (project / 'node_modules').exists()
installed = install_pi_extensions(target_root=work / 'extensions')
assert {item.name for item in installed} == {
    'codex-bridge', 'context-compaction', 'context-status', 'fast-mode',
    'message-timestamps', 'pi-sessions', 'skill-activity', 'token-awareness',
}
assert not (work / 'extensions/thinking-control').exists()
assert (work / 'extensions/skill-activity/store.py').is_file()
assert (work / 'extensions/token-awareness.ts').is_file()
assert (work / 'extensions/fast-mode/index.ts').is_file()
assert (work / 'extensions/fast-mode/README.md').is_file()
export_plugin(name='wheel-smoke', output=work / 'plugin',
              skill_names=['automata-storage', 'automata-pi-context-status'])
assert (work / 'plugin/skills/automata-pi-context-status/SKILL.md').is_file()
# Pi runtime assets and the existing shared tools survive wheel installation.
assert (work / 'extensions/codex-bridge.ts').is_file()
from automata.install.tools import install_tools
shared = install_tools(target_root=work / 'tools')
assert {item.name for item in shared} == {
    'line', 'timer', 'anatomy'
}
assert not (work / 'tools/team').exists()
assert not (work / 'tools/tmux-message').exists()
assert (work / 'tools/anatomy/anatomy.py').is_file()
assert not (work / 'tools/python-runtime').exists()
""",
            str(site),
            str(tmp_path / "installed"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr


def test_package_separates_pi_extensions_from_bundled_skills() -> None:
    package = files("automata")
    assert not package.joinpath("extensions").exists()
    pi = package.joinpath(*PI_RUNTIME)
    for name in (
        "automata-pi-context-compaction",
        "automata-pi-context-status",
        "automata-pi-sessions",
        "automata-pi-imagegen",
        "automata-pi-skill-activity",
    ):
        assert package.joinpath(*PI_SKILLS, name, "SKILL.md").is_file()
        assert not pi.joinpath("skills", name).exists()
        assert not package.joinpath("skills", "core", name).exists()
        assert not package.joinpath("skills", "operations", name).exists()
        assert not package.joinpath("skills", "skill-ops", name).exists()


def test_package_retires_playspace() -> None:
    package_root = files("automata")
    assert not package_root.joinpath("skills", "automata-playspace").exists()


def test_package_includes_bundled_codex_bridge_pi_extension() -> None:
    extension = files("automata").joinpath(*PI_EXTENSIONS, "codex-bridge.ts")

    assert extension.is_file()


def test_package_includes_bundled_context_status_pi_extension() -> None:
    extensions = files("automata").joinpath(*PI_EXTENSIONS)
    extension = extensions.joinpath("context-status.ts")

    assert extension.is_file()
    assert not extensions.joinpath("context-awareness.ts").is_file()
    assert 'CONTEXT_SIGNAL_TYPE = "automata-context-awareness"' in extension.read_text()


def test_package_includes_context_compaction_extension_and_skill() -> None:
    package_root = files("automata")
    extension = package_root.joinpath(*PI_EXTENSIONS, "context-compaction.ts")
    skill = package_root.joinpath(*PI_SKILLS, "automata-pi-context-compaction", "SKILL.md")

    assert extension.is_file()
    assert skill.is_file()

    source = extension.read_text()
    for term in (
        'name: "context_compact"',
        'pi.on("agent_settled"',
        'pi.on("session_compact"',
        "ctx.compact({",
        "terminate: true",
        '{ deliverAs: "nextTurn" }',
    ):
        assert term in source

    assert "registerCommand" not in source
    assert "sendUserMessage" not in source
    assert "tmux" not in source.casefold()


def test_package_includes_pi_sessions_extension_and_skill() -> None:
    package_root = files("automata")
    extension = package_root.joinpath(*PI_EXTENSIONS, "pi-sessions.ts")
    skill = package_root.joinpath(*PI_SKILLS, "automata-pi-sessions", "SKILL.md")

    assert extension.is_file()
    assert skill.is_file()


def test_pi_sessions_extension_keeps_destructive_boundaries() -> None:
    extension = files("automata").joinpath(*PI_EXTENSIONS, "pi-sessions.ts").read_text()

    for term in (
        'name: "pi_session_list"',
        'name: "pi_session_trash"',
        'name: "pi_session_copy"',
        "SessionManager.list(",
        "cwd === normalizePath(ctx.cwd) ? ctx.sessionManager.getSessionDir() : undefined",
        'session.cwd !== ""',
        "latestReceipt",
        "sameIdentity",
        "ctx.sessionManager.getSessionId()",
        'pi.exec("trash", [path]',
        'pi.exec("gio", ["trash", path]',
    ):
        assert term in extension

    assert "unlink(" not in extension
    assert "ctx.ui.confirm" not in extension
    assert "ctx.hasUI" not in extension
    assert "prior scoped authorization needs no repeated confirmation" in extension
    assert "ownership and inactivity are sufficiently established" in extension
