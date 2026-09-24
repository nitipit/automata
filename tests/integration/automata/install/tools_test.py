from pathlib import Path

import pytest
import yaml

from automata.install.tools import ToolInstallError, install_tools

SKILLS_ROOT = Path(__file__).parents[4] / "src" / "automata" / "skills"


def test_install_tools_copies_bundled_timer_without_runtime_state(tmp_path: Path) -> None:
    target_root = tmp_path / ".agents" / "tools"

    results = install_tools(target_root=target_root, tool_names=["timer"])

    assert [result.name for result in results] == ["timer"]
    assert (target_root / "timer" / "timer.py").exists()
    assert not (target_root / "timer" / "README.md").exists()
    assert not (target_root / "timer" / "state").exists()


def test_adaptive_ui_is_not_a_separate_bundled_tool(tmp_path: Path) -> None:
    with pytest.raises(ToolInstallError, match="Source tool directory does not exist"):
        install_tools(target_root=tmp_path / "tools", tool_names=["adaptive-ui"])
    assert not (tmp_path / "tools").exists()


def test_legacy_tool_ignore_still_filters_copies_and_replacements(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    source = source_root / "adaptive-ui"
    (source / "browser").mkdir(parents=True)
    (source / "browser" / "adaptive-ui.js").write_text("export {};\n")
    (source / "dist").mkdir()
    (source / "dist" / "leaked.js").write_text("generated\n")
    (source / "node_modules").mkdir()
    (source / "node_modules" / "leaked.js").write_text("generated\n")
    (source / ".automataignore").write_text("dist\nnode_modules\n")

    target_root = tmp_path / "copies"
    install_tools(
        source_root=source_root,
        target_root=target_root,
        tool_names=["adaptive-ui"],
    )
    installed = target_root / "adaptive-ui"
    assert (installed / "browser" / "adaptive-ui.js").is_file()
    assert not (installed / "dist").exists()
    assert not (installed / "node_modules").exists()

    (installed / "stale.txt").write_text("stale\n")
    install_tools(
        source_root=source_root,
        target_root=target_root,
        tool_names=["adaptive-ui"],
        mode="replace",
    )
    assert not (installed / "stale.txt").exists()
    assert not (installed / "dist").exists()
    assert not (installed / "node_modules").exists()

    symlink_root = tmp_path / "symlinks"
    install_tools(
        source_root=source_root,
        target_root=symlink_root,
        tool_names=["adaptive-ui"],
        mode="symlink",
    )
    linked = symlink_root / "adaptive-ui"
    assert linked.is_symlink()
    assert (linked / "dist" / "leaked.js").is_file()
    assert (linked / "node_modules" / "leaked.js").is_file()


@pytest.mark.parametrize("declaration", ["none", "legacy", "deno"])
def test_tool_bytecode_exclusions_are_defaults(tmp_path: Path, declaration: str) -> None:
    source_root = tmp_path / "source"
    source = source_root / "example"
    (source / "nested").mkdir(parents=True)
    retained = ["main.ts", "nested/helper.py", "data.pyc.txt", "pyproject.toml"]
    excluded = [
        "__pycache__/main.cpython-312.pyc",
        "nested/__pycache__/helper.cpython-312.pyc",
        "main.pyc",
        "nested/helper.pyc",
        "main.pyo",
        "nested/helper.pyo",
    ]
    for name in retained + excluded:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    if declaration == "legacy":
        (source / ".automataignore").write_text("# No bytecode rules needed\nother-output\n")
        (source / "other-output").write_text("generated\n")
    elif declaration == "deno":
        (source / "deno.json").write_text('{"exports":"./main.ts","publish":{"include":["."]}}\n')
        # Deno selection still takes precedence over legacy ignore declarations.
        (source / ".automataignore").write_text("nested\n")

    target_root = tmp_path / "copies"
    installed = target_root / "example"
    for mode in ("copy", "replace"):
        if mode == "replace":
            (installed / "stale.pyc").write_text("stale\n")
        install_tools(
            source_root=source_root,
            target_root=target_root,
            tool_names=["example"],
            mode=mode,
        )
        for name in retained:
            assert (installed / name).is_file(), name
        for name in excluded + ["__pycache__", "nested/__pycache__", "stale.pyc"]:
            assert not (installed / name).exists(), name
        if declaration == "legacy":
            assert not (installed / "other-output").exists()

    install_tools(
        source_root=source_root,
        target_root=tmp_path / "links",
        tool_names=["example"],
        mode="symlink",
    )
    linked = tmp_path / "links/example"
    assert linked.is_symlink()
    for name in retained + excluded:
        assert (linked / name).is_file(), name
        assert (source / name).is_file(), name


def test_install_tools_copies_bundled_message_router(tmp_path: Path) -> None:
    target_root = tmp_path / ".agents" / "tools"

    results = install_tools(target_root=target_root, tool_names=["message-router"])

    assert [result.name for result in results] == ["message-router"]
    assert not (target_root / "agent-router").exists()
    installed = target_root / "message-router"
    for path in (
        "message_router.py",
        "agent_browser_bridge.py",
        "README.md",
        "browser/client.js",
        "browser/pi-client.js",
        "browser/page.js",
        "automata_router/router.py",
    ):
        assert (installed / path).is_file(), path
    assert not (installed / "__pycache__").exists()
    assert not (tmp_path / ".agents" / "var").exists()


def test_install_tools_copies_bundled_tmux_message(tmp_path: Path) -> None:
    target_root = tmp_path / ".agents" / "tools"

    results = install_tools(target_root=target_root, tool_names=["tmux-message"])

    assert [result.name for result in results] == ["tmux-message"]
    installed = target_root / "tmux-message"
    assert (installed / "tmux_message.py").exists()
    assert not (installed / "README.md").exists()
    assert not (installed / "state").exists()


def test_all_skill_mapped_tools_resolve_after_install(tmp_path: Path) -> None:
    target_root = tmp_path / ".agents" / "tools"
    install_tools(target_root=target_root)

    for skill_file in SKILLS_ROOT.rglob("SKILL.md"):
        _, frontmatter_text, _ = skill_file.read_text().split("---\n", 2)
        frontmatter = yaml.safe_load(frontmatter_text)
        metadata = frontmatter.get("metadata", {})
        mapped_paths = metadata.get("automata-tools")
        if not mapped_paths:
            continue

        for runtime_path in mapped_paths.split(","):
            relative_entry = Path(runtime_path.strip()).relative_to(".agents/tools")
            assert (target_root / relative_entry).is_file(), skill_file
