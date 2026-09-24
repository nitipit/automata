"""Model research delivery boundaries, not tests of agent judgment or model quality."""

from importlib.resources import files
from pathlib import Path

from automata.install.skills import install_skills
from automata.plugin.export import export_plugin

NAME = "automata-model-research"


def source_bytes() -> bytes:
    return files("automata").joinpath("skills", "core", NAME, "SKILL.md").read_bytes()


def test_selected_install_and_update_preserve_notes_and_other_skills(tmp_path: Path) -> None:
    target = tmp_path / ".agents/skills"
    data = tmp_path / ".agents/var/skills" / NAME
    data.mkdir(parents=True)
    notes = {
        "selection-guide.md": "Existing research evidence",
        "preferences.md": "Existing user-approved preferences",
    }
    for name, text in notes.items():
        (data / name).write_text(text)
    other = target / "unrelated-skill/SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("Preserve this installed skill")

    for mode in ("copy", "replace"):
        results = install_skills(target_root=target, skill_names=[NAME], mode=mode)
        assert [result.name for result in results] == [NAME]
        installed = target / NAME
        assert sorted(p.name for p in installed.iterdir()) == ["SKILL.md"]
        assert (installed / "SKILL.md").read_bytes() == source_bytes()
        assert {p.name: p.read_text() for p in data.iterdir()} == notes
        assert other.read_text() == "Preserve this installed skill"
        assert sorted(p.name for p in target.iterdir()) == [NAME, "unrelated-skill"]
        if mode == "copy":
            (installed / "SKILL.md").write_text("Old installed instructions")


def test_selected_plugin_export_contains_only_skill_instructions(tmp_path: Path) -> None:
    output = tmp_path / "plugin"
    export_plugin(name="model-research-check", output=output, skill_names=[NAME])
    skill = output / "skills" / NAME
    assert sorted(p.name for p in skill.iterdir()) == ["SKILL.md"]
    assert (skill / "SKILL.md").read_bytes() == source_bytes()
    assert not (tmp_path / ".agents").exists()
