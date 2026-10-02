"""Canonical link graph and export boundaries, independent of native rendering."""

import pytest

from automata.skills.content import discover


def test_discovery_rejects_escape_and_missing_references(tmp_path):
    skills = tmp_path / "skills"
    root = skills / "demo"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("# Demo\n\n[Private](../../private.md)\n")
    with pytest.raises(ValueError, match="escapes"):
        discover(skills, "demo", False)
    (root / "SKILL.md").write_text("# Demo\n\n[Missing](references/missing.md)\n")
    with pytest.raises(FileNotFoundError):
        discover(skills, "demo", False)


def test_title_ignores_code_fences_and_frontmatter(tmp_path):
    root = tmp_path / "demo"
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\nname: hidden\n---\n```sh\n# Not a title\n```\n\n# Real title\n"
    )
    assert discover(tmp_path, "demo", False)[0].title == "Real title"


def test_symlink_skill_cannot_read_outside_app(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    outside = tmp_path / "private"
    outside.mkdir()
    (outside / "SKILL.md").write_text("# Must not read\n")
    (skills / "demo").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        discover(skills, "demo", False)
