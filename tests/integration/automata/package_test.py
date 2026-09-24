import tomllib
from importlib.resources import files
from pathlib import Path

from automata import __version__


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


def test_package_includes_message_router_and_chat() -> None:
    package_root = files("automata")
    for name in ("index.ts", "transport.ts", "protocol.ts"):
        assert package_root.joinpath("extensions", "message-router", name).is_file()
    assert not package_root.joinpath("extensions", "agent-router").exists()
    assert not package_root.joinpath("tools", "agent-router").exists()
    assert not package_root.joinpath("extensions", "agent-browser-bridge.ts").exists()
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
    skill = package_root.joinpath("skills", "operations", "automata-message-router", "SKILL.md")
    assert skill.is_file()
    components = adaptive_ui_source().joinpath("src", "ui", "_components")
    for path in ("chat.ts", "chat.schema.ts"):
        assert components.joinpath(path).is_file(), path


def test_package_includes_bundled_codex_bridge_pi_extension() -> None:
    extension = files("automata").joinpath("extensions", "codex-bridge.ts")

    assert extension.is_file()


def test_package_includes_bundled_context_status_pi_extension() -> None:
    extensions = files("automata").joinpath("extensions")
    extension = extensions.joinpath("context-status.ts")

    assert extension.is_file()
    assert not extensions.joinpath("context-awareness.ts").is_file()
    assert 'CONTEXT_SIGNAL_TYPE = "automata-context-awareness"' in extension.read_text()


def test_package_includes_context_compaction_extension_and_skill() -> None:
    package_root = files("automata")
    extension = package_root.joinpath("extensions", "context-compaction.ts")
    skill = package_root.joinpath("skills", "core", "automata-context-compaction", "SKILL.md")

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
    extension = package_root.joinpath("extensions", "pi-sessions.ts")
    skill = package_root.joinpath("skills", "operations", "automata-pi-sessions", "SKILL.md")

    assert extension.is_file()
    assert skill.is_file()


def test_pi_sessions_extension_keeps_destructive_boundaries() -> None:
    extension = files("automata").joinpath("extensions", "pi-sessions.ts").read_text()

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
