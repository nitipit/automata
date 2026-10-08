import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest

from automata import __version__

PI_RUNTIME = ("runtimes", "pi")
PI_SKILLS = ("skills", "bundled")
PI_EXTENSIONS = (*PI_RUNTIME, "extensions")


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_package_includes_self_documenting_python_tools() -> None:
    package_root = files("automata").joinpath("tools")
    scripts = (
        package_root.joinpath("timer", "timer.py"),
        package_root.joinpath("tmux-message", "tmux_message.py"),
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
    assert not package_root.joinpath("skills", "bundled", "automata-codex-sessions").exists()


def adaptive_ui_source():
    return files("automata").joinpath("skills", "bundled", "automata-adaptive-ui", "lib")


def test_adaptive_ui_skill_ships_source_without_generated_library() -> None:
    source = adaptive_ui_source()
    assert source.joinpath("build.ts").is_file()
    assert source.joinpath("example", "index.html").is_file()
    assert source.joinpath("example", "reactive-shadow.html").is_file()
    assert source.joinpath("src", "server.ts").is_file()
    assert source.joinpath("src", "ui", "adaptive-ui.ts").is_file()
    assert source.joinpath("package.json").is_file()
    assert source.parent.joinpath("scripts", "build.py").is_file()
    assert not source.joinpath("example", "chat-with-agent.html").exists()
    assert not source.parent.joinpath("scripts", "library").exists()
    assert not source.joinpath("example", "chat.html").exists()
    assert not source.joinpath("browser").is_dir()
    assert not files("automata").joinpath("tools", "adaptive-ui").is_dir()


def test_adaptive_ui_example_teaches_direct_web_component_composition() -> None:
    example = adaptive_ui_source().joinpath("example", "index.html")
    text = example.read_text()

    assert text.index('<script type="module" src="./index.js"></script>') < text.index("<body>")
    assert '<link rel="icon" href="./catalog.svg"' in text
    for term in ("<aui-card", "<aui-button", "<aui-chat", "<example-note>"):
        assert term in text
    script = adaptive_ui_source().joinpath("example", "index.js").read_text()
    for term in (
        'import { Button, Card, Chat } from "/lib/adaptive-ui.js";',
        'import { ExampleNote } from "./_components/example-note.js";',
        'import { pageStyles } from "./index.css.js";',
        'Card.define("aui-card");',
        'Button.define("aui-button");',
        'Chat.define("aui-chat");',
    ):
        assert term in script


def test_adaptive_ui_example_teaches_reactive_shadow_composition() -> None:
    example = adaptive_ui_source().joinpath("example", "reactive-shadow.html")
    text = example.read_text()

    assert text.index('<script type="module">') < text.index("<body>")
    for term in (
        'from "/lib/adaptive-ui.js";',
        "class ReactivePage extends Base",
        "const state = reactive({ count: 0 });",
        "const Counter = component(() =>",
        '@click="${() => state.count++}"',
        'this.attachShadow({ mode: "open" })',
        'Card.define("aui-card");',
        'Button.define("aui-button");',
        'ReactivePage.define("aui-reactive-page");',
        'ReactiveShell.define("aui-reactive-shell");',
        "<aui-reactive-shell>",
    ):
        assert term in text


def test_package_excludes_adaptive_ui_generated_trees_from_sdists_and_wheels() -> None:
    project_root = Path(__file__).parents[3]
    config = tomllib.loads((project_root / "pyproject.toml").read_text())

    assert config["tool"]["uv"]["build-backend"]["source-exclude"] == [
        "src/automata/skills/bundled/automata-adaptive-ui/lib/dist",
        "src/automata/skills/bundled/automata-adaptive-ui/lib/dist/**",
        "src/automata/skills/bundled/automata-adaptive-ui/lib/node_modules",
        "src/automata/skills/bundled/automata-adaptive-ui/lib/node_modules/**",
        "src/automata/skills/bundled/**/__pycache__/**",
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
        "skills/bundled/automata-pi-context-status/SKILL.md",
        "skills/bundled/automata-pi-context-compaction/SKILL.md",
        "skills/bundled/automata-pi-sessions/SKILL.md",
        "skills/bundled/automata-pi-imagegen/SKILL.md",
        "skills/bundled/automata-pi-skill-activity/SKILL.md",
        "runtimes/pi/extensions/codex-bridge.ts",
        "skills/bundled/automata-workplan/SKILL.md",
        "skills/bundled/automata-storage/SKILL.md",
        "skills/bundled/automata-adaptive-ui/scripts/build.py",
        "skills/bundled/automata-agent-evaluation/templates/evaluation-record.json",
    }
    with zipfile.ZipFile(wheel) as archive:
        wheel_paths = {
            name.removeprefix("automata/")
            for name in archive.namelist()
            if name.startswith("automata/") and not name.endswith('/')
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
        assert not any(path.startswith("skills/bundled/automata-codex-sessions/")
                       for path in paths)
        assert "skills/bundled/automata-time-awareness/SKILL.md" not in paths
        assert "skills/bundled/automata-timer/SKILL.md" in paths
    source_catalog = root / "src/automata/skills/bundled"
    catalog_files = {
        "skills/bundled/" + path.relative_to(source_catalog).as_posix()
        for path in source_catalog.rglob("*") if path.is_file() and "__pycache__" not in path.parts
    }
    for paths in (wheel_paths, sdist_paths):
        assert expected <= paths
        assert catalog_files <= paths
        assert {
            "skills/bundled/automata-adaptive-ui/lib/example/index.js",
            "skills/bundled/automata-adaptive-ui/lib/example/index.css.js",
            "skills/bundled/automata-adaptive-ui/lib/example/catalog.svg",
        } <= paths
        for retired in (
            'skills/bundled/automata-message-router/',
            'skills/bundled/automata-playspace/',
            'tools/message-router/', 'runtimes/pi/extensions/message-router/',
        ):
            assert not any(path.startswith(retired) for path in paths)
        assert 'skills/templates/lib/mermaid.js' in paths
        assert 'skills/templates/lib/prism.js' in paths
        assert 'skills/templates/catalog.html' in paths
        assert 'skills/templates/skill.html' in paths
        assert 'skills/templates/index.html' not in paths
        assert 'skills/core/automata-workplan/SKILL.md' not in paths
        assert not any(path.startswith('skills/bundled/automata-plan/') for path in paths)
        assert not any('/node_modules/' in path or '/lib/dist/' in path
                       or '/__pycache__/' in path for path in paths)
        assert not any(path.startswith('apps/skill_builder/') for path in paths)
        assert 'skills/templates/lib/highlight.js' not in paths
        assert 'skills/templates/licenses/prism-LICENSE.txt' in paths
        assert 'skills/templates/licenses/highlightjs-LICENSE.txt' not in paths
        assert 'skills/templates/licenses/PROVENANCE.txt' in paths
        assert not any(path.startswith("extensions/") for path in paths)
        pi_skill_names = (
            "automata-pi-context-status", "automata-pi-context-compaction",
            "automata-pi-sessions", "automata-pi-imagegen",
            "automata-pi-skill-activity",
        )
        assert not any(
            path.startswith("skills/core/") and path.endswith(f"{name}/SKILL.md")
            for path in paths
            for name in pi_skill_names
        )

    # Exercise installed package resources outside the checkout, not only ZIP names.
    site = tmp_path / "site"
    installed = subprocess.run(
        [uv, "pip", "install", "--offline", "--no-deps", "--target", str(site), str(wheel)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    smoke = subprocess.run(
        [sys.executable, "-I", "-c", """
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
assert 'automata-thinking-control' not in sources
assert 'automata-pi-sessions' in sources
assert 'automata-playspace' not in sources
assert 'automata-codex-sessions' not in sources
assert not (site / 'automata/runtimes/codex').exists()
assert not (site / 'automata/install/codex.py').exists()
assert 'automata-time-awareness' not in sources
assert 'automata-timer' in sources
assert all(path.name == name for name, path in sources.items())
assert 'automata-message-router' not in sources
assert sources['automata-workplan'] == site / 'automata/skills/bundled/automata-workplan'
assert 'automata-plan' not in sources
assert not any(name in sys.modules for name in ('engrave', 'mistune', 'playwright'))
results = install_skills(target_root=work / 'skills')
assert {result.name for result in results} == set(sources)
for name in ('automata-storage', 'automata-pi-context-status',
             'automata-workplan', 'automata-agent-design'):
    assert (work / 'skills' / name / 'SKILL.md').is_file()
install_skills(target_root=work / 'linked', skill_names=['automata-agent-design'], mode='symlink')
linked = work / 'linked/automata-agent-design'
assert linked.is_symlink() and linked.resolve() == sources['automata-agent-design']
assert (linked / 'SKILL.md').read_bytes() == (work / 'skills/automata-agent-design/SKILL.md').read_bytes()
installed = install_pi_extensions(target_root=work / 'extensions')
assert {item.name for item in installed} == {
    'codex-bridge', 'context-compaction', 'context-status', 'fast-mode',
    'message-timestamps', 'pi-sessions', 'skill-activity', 'token-awareness',
}
assert not (work / 'extensions/thinking-control').exists()
assert not (work / 'extensions/message-router').exists()
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
assert {item.name for item in shared} == {'line', 'python-runtime', 'timer', 'tmux-message'}
assert not (work / 'tools/message-router').exists()
assert (work / 'tools/python-runtime/python_runtime.py').is_file()
""", str(site), str(tmp_path / "installed")],
        cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr


def test_package_separates_pi_extensions_from_bundled_skills() -> None:
    package = files("automata")
    assert not package.joinpath("extensions").exists()
    pi = package.joinpath(*PI_RUNTIME)
    for name in (
        "automata-pi-context-compaction", "automata-pi-context-status", "automata-pi-sessions",
        "automata-pi-imagegen", "automata-pi-skill-activity",
    ):
        assert package.joinpath(*PI_SKILLS, name, "SKILL.md").is_file()
        assert not pi.joinpath("skills", name).exists()
        assert not package.joinpath("skills", "core", name).exists()
        assert not package.joinpath("skills", "operations", name).exists()
        assert not package.joinpath("skills", "skill-ops", name).exists()


def test_package_retires_router_and_playspace_but_keeps_chat() -> None:
    package_root = files("automata")
    assert not package_root.joinpath(*PI_EXTENSIONS, "message-router").exists()
    assert not package_root.joinpath(*PI_EXTENSIONS, "agent-router").exists()
    assert not package_root.joinpath("tools", "agent-router").exists()
    assert not package_root.joinpath(*PI_EXTENSIONS, "agent-browser-bridge.ts").exists()
    assert not package_root.joinpath("tools", "message-router").exists()
    for name in ('automata-message-router', 'automata-playspace'):
        assert not package_root.joinpath('skills', 'bundled', name).exists()
    components = adaptive_ui_source().joinpath("src", "ui", "_components")
    for path in ("chat.ts", "chat.schema.ts"):
        assert components.joinpath(path).is_file(), path


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
