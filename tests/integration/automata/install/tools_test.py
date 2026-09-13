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


def test_install_tools_copies_bundled_agent_browser_bridge(tmp_path: Path) -> None:
    target_root = tmp_path / ".agents" / "tools"

    results = install_tools(target_root=target_root, tool_names=["agent-browser-bridge"])

    assert [result.name for result in results] == ["agent-browser-bridge"]
    installed = target_root / "agent-browser-bridge"
    for path in ("agent_browser_bridge.py", "README.md", "browser/client.js", "browser/page.js"):
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
