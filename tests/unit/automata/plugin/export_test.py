import json
from pathlib import Path

import pytest

from automata.plugin import PluginExportError, export_plugin

NAMESPACE = "me.umlab.automata"


def test_export_core_profile_creates_standard_skill_package(tmp_path: Path) -> None:
    output = tmp_path / "automata-core"

    result = export_plugin(name="automata-core", profile="core", output=output)

    manifest = json.loads((output / "plugin.json").read_text())
    assert result.skills == ("automata-plan",)
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "automata-core"
    assert manifest["description"]
    assert set(path.name for path in (output / "skills").iterdir()) == set(result.skills)
    assert not (output / "mcp.json").exists()
    assert "extensions" not in manifest


def test_export_merges_profile_and_explicit_selections(tmp_path: Path) -> None:
    output = tmp_path / "automata-expanded"

    result = export_plugin(
        name="automata-expanded",
        profile="core",
        skill_names=("automata-cue", "automata-plan"),
        output=output,
    )

    assert result.skills == ("automata-plan", "automata-cue")
    assert (output / "skills" / "automata-cue" / "SKILL.md").is_file()


def test_export_selects_shared_and_pi_skills(tmp_path: Path) -> None:
    output = tmp_path / "plugin"
    result = export_plugin(
        name="mixed-skills",
        skill_names=("automata-storage", "automata-context-status"),
        output=output,
    )
    assert result.skills == ("automata-storage", "automata-context-status")
    for name in result.skills:
        assert (output / "skills" / name / "SKILL.md").is_file()


def test_export_custom_skill_root_is_exclusive(tmp_path: Path) -> None:
    custom = tmp_path / "custom"
    skill = custom / "nested" / "automata-storage"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("custom source\n")
    output = tmp_path / "plugin"
    with pytest.raises(PluginExportError, match="automata-context-status"):
        export_plugin(
            name="mixed-skills",
            skill_source_root=custom,
            skill_names=("automata-storage", "automata-context-status"),
            output=output,
        )
    assert not output.exists()
    result = export_plugin(
        name="custom-only", skill_source_root=custom,
        skill_names=("automata-storage",), output=output,
    )
    assert result.skills == ("automata-storage",)
    assert (output / "skills" / "automata-storage" / "SKILL.md").read_text() == "custom source\n"


def test_export_missing_selection_does_not_create_output(tmp_path: Path) -> None:
    output = tmp_path / "plugin"
    with pytest.raises(PluginExportError, match="does-not-exist"):
        export_plugin(
            name="mixed-skills",
            skill_names=("automata-storage", "does-not-exist"),
            output=output,
        )
    assert not output.exists()


def test_export_packages_tools_under_automata_extension(tmp_path: Path) -> None:
    output = tmp_path / "automata-runtime"

    result = export_plugin(
        name="automata-runtime",
        skill_names=("automata-plan",),
        tool_names=("tmux-message",),
        output=output,
    )

    manifest = json.loads((output / "plugin.json").read_text())
    extension = manifest["extensions"][NAMESPACE]
    assert result.tools == ("tmux-message",)
    assert extension == {
        "tools": ["tmux-message"],
        "toolRoot": "me.umlab.automata/tools",
    }
    assert (output / NAMESPACE / "tools" / "tmux-message" / "tmux_message.py").is_file()
    assert not list((output / NAMESPACE).rglob("__pycache__"))
    assert not list((output / NAMESPACE).rglob("*.pyc"))


def test_export_filters_tool_declared_generated_trees(tmp_path: Path) -> None:
    source_root = tmp_path / "tools"
    source = source_root / "adaptive-ui"
    (source / "browser").mkdir(parents=True)
    (source / "browser" / "adaptive-ui.js").write_text("export {};\n")
    (source / "dist").mkdir()
    (source / "dist" / "leaked.js").write_text("generated\n")
    (source / "node_modules").mkdir()
    (source / "node_modules" / "leaked.js").write_text("generated\n")
    (source / ".automataignore").write_text("dist\nnode_modules\n")
    output = tmp_path / "plugin"

    export_plugin(
        name="adaptive-ui-test",
        tool_names=("adaptive-ui",),
        tool_source_root=source_root,
        output=output,
    )

    exported = output / NAMESPACE / "tools" / "adaptive-ui"
    assert (exported / "browser" / "adaptive-ui.js").is_file()
    assert not (exported / "dist").exists()
    assert not (exported / "node_modules").exists()


def test_export_rejects_existing_output_without_replace(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(PluginExportError, match="already exists"):
        export_plugin(name="automata-core", profile="core", output=output)


def test_export_rejects_asset_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(PluginExportError, match="Invalid skill name"):
        export_plugin(
            name="automata-core",
            skill_names=("../outside",),
            output=tmp_path / "automata-core",
        )
