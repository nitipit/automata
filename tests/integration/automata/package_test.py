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
PI_SKILLS = (*PI_RUNTIME, "skills")
PI_EXTENSIONS = (*PI_RUNTIME, "extensions")


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_package_includes_self_documenting_python_tools() -> None:
    package_root = files("automata").joinpath("tools")
    scripts = (
        package_root.joinpath("timer", "timer.py"),
        package_root.joinpath("tmux-message", "tmux_message.py"),
        package_root.joinpath("line", "line.py"),
    )

    for script in scripts:
        assert script.is_file()
        assert "from cyclopts import" in script.read_text()
        assert not script.parent.joinpath("README.md").is_file()


def test_package_excludes_removed_jev_capability() -> None:
    package_root = files("automata")
    assert not package_root.joinpath("tools", "jev").exists()
    assert not package_root.joinpath("skills", "operations", "automata-jev").exists()


def adaptive_ui_source():
    return files("automata").joinpath("skills", "operations", "automata-adaptive-ui", "lib")


def test_adaptive_ui_skill_ships_source_without_generated_library() -> None:
    source = adaptive_ui_source()
    assert source.joinpath("build.ts").is_file()
    assert source.joinpath("example", "index.html").is_file()
    assert source.joinpath("example", "reactive-shadow.html").is_file()
    assert source.joinpath("src", "server.ts").is_file()
    assert source.joinpath("src", "ui", "adaptive-ui.ts").is_file()
    assert source.joinpath("package.json").is_file()
    assert source.parent.joinpath("scripts", "build.py").is_file()
    assert source.joinpath("example", "chat-with-agent.html").is_file()
    assert not source.parent.joinpath("scripts", "library").exists()
    assert not source.joinpath("example", "chat.html").exists()
    assert not source.joinpath("browser").is_dir()
    assert not files("automata").joinpath("tools", "adaptive-ui").is_dir()


def test_adaptive_ui_example_teaches_direct_web_component_composition() -> None:
    example = adaptive_ui_source().joinpath("example", "index.html")
    text = example.read_text()

    assert text.index('<script type="module">') < text.index("<body>")
    for term in (
        'import { Base, Button, Card, Chat } from "/lib/adaptive-ui.js";',
        "class CatalogPage extends Base",
        "this.css = `",
        'CatalogPage.define("aui-catalog-page");',
        'Card.define("aui-card");',
        'Button.define("aui-button");',
        "<aui-catalog-page>",
        "<aui-card",
        "<aui-button",
    ):
        assert term in text


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
        "src/automata/skills/operations/automata-adaptive-ui/lib/dist",
        "src/automata/skills/operations/automata-adaptive-ui/lib/dist/**",
        "src/automata/skills/operations/automata-adaptive-ui/lib/node_modules",
        "src/automata/skills/operations/automata-adaptive-ui/lib/node_modules/**",
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
        "runtimes/pi/extensions/message-router/index.ts",
        "runtimes/pi/skills/automata-context-status/SKILL.md",
        "runtimes/pi/skills/automata-context-compaction/SKILL.md",
        "runtimes/pi/skills/automata-pi-sessions/SKILL.md",
        "runtimes/pi/skills/automata-codex-imagegen/SKILL.md",
        "runtimes/pi/skills/automata-skill-activity/SKILL.md",
        "runtimes/pi/skills/automata-message-router/SKILL.md",
        "skills/core/automata-storage/SKILL.md",
    }
    with zipfile.ZipFile(wheel) as archive:
        wheel_paths = {
            name.removeprefix("automata/")
            for name in archive.namelist()
            if name.startswith("automata/")
        }
    with tarfile.open(sdist) as archive:
        sdist_paths = {
            name.split("/src/automata/", 1)[1]
            for name in archive.getnames()
            if "/src/automata/" in name
        }
    for paths in (wheel_paths, sdist_paths):
        assert expected <= paths
        assert not any(path.startswith("extensions/") for path in paths)
        pi_skill_names = (
            "automata-context-status", "automata-context-compaction",
            "automata-pi-sessions", "automata-codex-imagegen",
            "automata-skill-activity", "automata-message-router",
        )
        assert not any(
            path.startswith("skills/") and path.endswith(f"{name}/SKILL.md")
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
results = install_skills(target_root=work / 'skills')
assert {result.name for result in results} == set(sources)
for name in ('automata-storage', 'automata-context-status', 'automata-message-router'):
    assert (work / 'skills' / name / 'SKILL.md').is_file()
installed = install_pi_extensions(target_root=work / 'extensions')
assert 'message-router' in {item.name for item in installed}
assert (work / 'extensions/message-router/index.ts').is_file()
assert (work / 'extensions/skill-activity/store.py').is_file()
export_plugin(name='wheel-smoke', output=work / 'plugin',
              skill_names=['automata-storage', 'automata-context-status'])
assert (work / 'plugin/skills/automata-context-status/SKILL.md').is_file()
""", str(site), str(tmp_path / "installed")],
        cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False,
    )
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr


def test_package_uses_only_pi_runtime_roots_for_pi_resources() -> None:
    package = files("automata")
    assert not package.joinpath("extensions").exists()
    pi = package.joinpath(*PI_RUNTIME)
    for name in (
        "automata-context-compaction", "automata-context-status", "automata-pi-sessions",
        "automata-codex-imagegen", "automata-skill-activity", "automata-message-router",
    ):
        assert pi.joinpath("skills", name, "SKILL.md").is_file()
        assert not package.joinpath("skills", "core", name).exists()
        assert not package.joinpath("skills", "operations", name).exists()
        assert not package.joinpath("skills", "skill-ops", name).exists()


def test_package_includes_message_router_and_chat() -> None:
    package_root = files("automata")
    for name in ("index.ts", "transport.ts", "protocol.ts"):
        assert package_root.joinpath(*PI_EXTENSIONS, "message-router", name).is_file()
    assert not package_root.joinpath(*PI_EXTENSIONS, "agent-router").exists()
    assert not package_root.joinpath("tools", "agent-router").exists()
    assert not package_root.joinpath(*PI_EXTENSIONS, "agent-browser-bridge.ts").exists()
    tool = package_root.joinpath("tools", "message-router")
    for path in (
        "message_router.py",
        "agent_browser_bridge.py",
        "README.md",
        "LEGACY.md",
        "browser/client.js",
        "browser/pi-client.js",
        "browser/page.js",
        "automata_router/router.py",
        "automata_router/server.py",
    ):
        assert tool.joinpath(path).is_file(), path
    skill = package_root.joinpath(*PI_SKILLS, "automata-message-router", "SKILL.md")
    assert skill.is_file()
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
    skill = package_root.joinpath(*PI_SKILLS, "automata-context-compaction", "SKILL.md")

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
