"""Static pause guidance and packaging checks, not runtime behavior evaluation."""

from pathlib import Path

import yaml

from automata.install.skills import bundled_skill_root, find_skill_dir, install_skills

SKILL_NAME = "automata-work-pause"


def skill_text() -> str:
    return (find_skill_dir(bundled_skill_root(), SKILL_NAME) / "SKILL.md").read_text()


def test_work_pause_is_a_core_guidance_skill() -> None:
    root = find_skill_dir(bundled_skill_root(), SKILL_NAME)
    _, frontmatter, _ = skill_text().split("---\n", 2)
    metadata = yaml.safe_load(frontmatter)

    assert root.parent.name == "core"
    assert metadata["name"] == SKILL_NAME
    assert set(metadata) == {"name", "description"}
    assert "pause for later continuation" in metadata["description"]
    assert "computer shutdown" in metadata["description"]


def test_pause_uses_existing_sessions_without_default_checkpoint_documents() -> None:
    normalized = " ".join(skill_text().casefold().split())
    for term in (
        "leave pi open but idle by default",
        "retain its saved session",
        "no checkpoint-document updates by default",
        "only when essential information would otherwise be lost",
        "not already recoverable from retained sessions or artifacts",
        "a small operational-state update",
    ):
        assert term in normalized, term


def test_pause_stops_activity_without_becoming_handoff_or_cleanup() -> None:
    normalized = " ".join(skill_text().casefold().split())
    for term in (
        "an already idle worker needs no new assignment",
        "suspend task-owned triggers",
        "leave unrelated services and reminders alone",
        "do not rediscover the environment or audit the task",
        "report the remaining activity or uncertain outcome",
        "do not run tests, review results, accept work, commit, back up, or delete",
        "a late callback or old deadline does not authorize resuming",
        "explicit resume instruction from the user or authorized task owner",
        "confirm the pause briefly",
    ):
        assert term in normalized, term


def test_work_pause_installs_only_its_guidance_into_a_fixture(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    results = install_skills(target_root=target, skill_names=[SKILL_NAME])

    assert [result.name for result in results] == [SKILL_NAME]
    installed = target / SKILL_NAME
    assert (installed / "SKILL.md").read_text() == skill_text()
    assert list(tmp_path.iterdir()) == [target]
    assert list(target.iterdir()) == [installed]
    assert list(installed.iterdir()) == [installed / "SKILL.md"]
