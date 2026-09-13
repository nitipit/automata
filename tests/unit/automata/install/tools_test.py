import json
from pathlib import Path

import pytest

from automata.install.directory import InstallMode
from automata.install.tools import ToolInstallError, install_tools


def test_install_tools_supports_custom_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_tool(source_root / "demo")

    install_tools(
        source_root=source_root,
        target_root=tmp_path / "target",
        tool_names=["demo"],
    )

    assert (tmp_path / "target" / "demo" / "tool.py").exists()


def test_replacing_tool_does_not_remove_external_runtime_state(tmp_path: Path) -> None:
    agents_root = tmp_path / ".agents"
    target_root = agents_root / "tools"
    source_root = make_tool_source(tmp_path)
    install_tools(target_root=target_root, source_root=source_root)
    state_file = agents_root / "tool-state" / "timer" / "jobs" / "job.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{}\n")

    install_tools(
        target_root=target_root,
        source_root=source_root,
        tool_names=["timer"],
        mode="replace",
    )

    assert state_file.exists()
    assert (target_root / "timer" / "tool.py").exists()


def test_install_tools_rejects_path_like_tool_name(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_tool(source_root / "demo")

    with pytest.raises(ToolInstallError, match="Invalid tool name"):
        install_tools(
            source_root=source_root,
            target_root=tmp_path / "target",
            tool_names=["../demo"],
        )


@pytest.mark.parametrize("mode", ["copy", "replace", "symlink"])
def test_missing_required_artifact_is_rejected_before_any_install(
    tmp_path: Path, mode: InstallMode
) -> None:
    source = tmp_path / "source"
    make_tool(source / "alpha")
    tool = make_tool(source / "demo")
    (tool / "deno.json").write_text(json.dumps({"exports": "./browser/demo.js"}))
    target = tmp_path / "target"
    if mode == "replace":
        existing = make_tool(target / "demo")
        (existing / "keep.txt").write_text("working installation\n")

    with pytest.raises(ToolInstallError, match="Build the source tool"):
        install_tools(source_root=source, target_root=target, mode=mode)

    assert not (target / "alpha").exists()
    if mode == "replace":
        assert (target / "demo" / "keep.txt").read_text() == "working installation\n"
    else:
        assert not target.exists()


@pytest.mark.parametrize("mode", ["copy", "replace", "symlink"])
def test_required_artifact_allows_install_when_present(tmp_path: Path, mode: InstallMode) -> None:
    source = tmp_path / "source"
    tool = make_tool(source / "demo")
    (tool / "deno.json").write_text(
        json.dumps({"exports": "./tool.py", "publish": {"include": ["tool.py"]}})
    )

    install_tools(source_root=source, target_root=tmp_path / "target", mode=mode)

    assert (tmp_path / "target" / "demo" / "tool.py").is_file()


@pytest.mark.parametrize("entry", ["/tmp/outside", "../outside", "assets/../../outside"])
def test_required_artifact_paths_must_stay_inside_tool(tmp_path: Path, entry: str) -> None:
    source = tmp_path / "source"
    tool = make_tool(source / "demo")
    (tool / "deno.json").write_text(json.dumps({"exports": entry}))

    with pytest.raises(ToolInstallError, match="Invalid package path"):
        install_tools(source_root=source, target_root=tmp_path / "target")

    assert not (tmp_path / "target").exists()


def test_required_artifact_cannot_be_an_external_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    tool = make_tool(source / "demo")
    outside = tmp_path / "outside.js"
    outside.write_text("export {};\n")
    (tool / "artifact.js").symlink_to(outside)
    (tool / "deno.json").write_text(json.dumps({"exports": "./artifact.js"}))

    with pytest.raises(ToolInstallError, match="Invalid package path"):
        install_tools(source_root=source, target_root=tmp_path / "target")


def test_deno_include_selects_nested_paths_and_keeps_config(tmp_path: Path) -> None:
    source = tmp_path / "source"
    tool = make_tool(source / "demo")
    (tool / "browser").mkdir()
    (tool / "browser" / "entry.js").write_text("export {};\n")
    (tool / "browser" / "entry.js.tmp").write_text("partial build\n")
    (tool / "src").mkdir()
    (tool / "src" / "component.ts").write_text("export {};\n")
    (tool / "deno.json").write_text(
        json.dumps(
            {"exports": "./browser/entry.js", "publish": {"include": ["browser/entry.js", "src/"]}}
        )
    )

    install_tools(source_root=source, target_root=tmp_path / "target")

    installed = tmp_path / "target" / "demo"
    assert (installed / "deno.json").is_file()
    assert (installed / "browser" / "entry.js").is_file()
    assert (installed / "src" / "component.ts").is_file()
    assert not (installed / "browser" / "entry.js.tmp").exists()
    assert not (installed / "tool.py").exists()


@pytest.mark.parametrize(
    "config",
    [
        {"exports": {".": "./tool.py"}},
        {"publish": {"include": "tool.py"}},
        {"publish": {"include": ["**/*.py"]}},
        {"publish": {"include": ["../outside"]}},
        {"publish": {"include": [42]}},
        {"exports": "./tool.py", "publish": {"include": []}},
        {"publish": {"include": ["."], "exclude": ["private/"]}},
        {"publish": []},
    ],
)
def test_unsupported_or_inconsistent_deno_fields_fail_before_replace(
    tmp_path: Path, config: dict
) -> None:
    source = tmp_path / "source"
    tool = make_tool(source / "demo")
    (tool / "deno.json").write_text(json.dumps(config))
    existing = make_tool(tmp_path / "target" / "demo")
    (existing / "keep.txt").write_text("working copy\n")

    with pytest.raises(ToolInstallError):
        install_tools(source_root=source, target_root=tmp_path / "target", mode="replace")

    assert (existing / "keep.txt").read_text() == "working copy\n"


def test_invalid_deno_json_gives_install_error(tmp_path: Path) -> None:
    tool = make_tool(tmp_path / "source" / "demo")
    (tool / "deno.json").write_text("{broken json")

    with pytest.raises(ToolInstallError, match="Invalid strict-JSON deno.json"):
        install_tools(source_root=tmp_path / "source", target_root=tmp_path / "target")


def test_jsonc_config_is_not_silently_ignored(tmp_path: Path) -> None:
    tool = make_tool(tmp_path / "source" / "demo")
    (tool / "deno.jsonc").write_text('{"publish": {"include": ["tool.py"]}}')

    with pytest.raises(ToolInstallError, match="requires strict-JSON deno.json"):
        install_tools(source_root=tmp_path / "source", target_root=tmp_path / "target")


def test_package_json_does_not_control_copy_selection(tmp_path: Path) -> None:
    tool = make_tool(tmp_path / "source" / "demo")
    (tool / "package.json").write_text(json.dumps({"exports": "./not-built.js", "files": []}))

    install_tools(source_root=tmp_path / "source", target_root=tmp_path / "target")

    assert (tmp_path / "target" / "demo" / "tool.py").is_file()


def make_tool(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "tool.py").write_text("print('ok')\n")
    return path


def make_tool_source(tmp_path: Path) -> Path:
    source_root = tmp_path / "source"
    make_tool(source_root / "timer")
    return source_root
