"""Mechanical skill-package contracts, not evidence of agent judgment or skill quality."""

import json
import re
from pathlib import Path, PurePosixPath

import pytest
import yaml

from automata.install.skills import install_skills

PACKAGE_ROOT = Path(__file__).parents[3] / "src" / "automata"
SKILLS_ROOT = PACKAGE_ROOT / "skills"
TOOLS_ROOT = PACKAGE_ROOT / "tools"
SKILL_FILES = sorted(SKILLS_ROOT.rglob("SKILL.md"))
REQUIRED_SKILLS = {
    "automata-agents-md",
    "automata-agent-design",
    "automata-capability-research",
    "automata-work-design",
    "automata-adaptive-ui",
    "automata-browser-use",
    "automata-line-use",
    "automata-agent-router",
    "automata-codex-imagegen",
    "automata-question",
    "automata-context-status",
    "automata-context-compaction",
    "automata-pi-sessions",
    "automata-delegation",
    "automata-cue",
    "automata-time-awareness",
    "automata-team-management",
    "automata-plan",
    "automata-skill-design",
    "automata-setup",
    "automata-timer",
    "automata-storage",
    "automata-agent-evaluation",
    "automata-communication",
    "automata-goal",
    "automata-pc-ui-control",
    "automata-plain-text-writing",
    "automata-runtime-status",
    "automata-software-development",
    "automata-stateful-workflow",
    "automata-tmux-background",
    "automata-tmux-communication",
    "automata-tmux-observation",
    "automata-toolsmith",
    "automata-work-pause",
}
RETIRED_SKILLS = {
    "automata-jev",
    "automata-agent-data",
    "automata-javascript",
    "automata-python",
    "automata-worklog",
    "automata-roles",
    "automata-next-improvement",
    "automata-time-estimation",
    "automata-token-estimation",
    "automata-skill-install",
    "automata-action-routing",
    "automata-align",
    "automata-task-design",
    "automata-contract-diffusion",
    "automata-agent-browser-bridge",
    "automata-ui-channel-setup",
    "automata-web-browser-control",
}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), path
    parts = text.split("---\n", 2)
    assert len(parts) == 3 and parts[2].strip(), path
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), path
    return data


def test_skill_catalog_has_valid_unique_runtime_names() -> None:
    names = set()
    assert SKILL_FILES
    for path in SKILL_FILES:
        data = parse_frontmatter(path)
        name = data.get("name")
        assert isinstance(name, str) and re.fullmatch(r"automata-[a-z0-9]+(?:-[a-z0-9]+)*", name)
        assert name == path.parent.name, path
        assert name not in names, name
        names.add(name)
        assert isinstance(data.get("description"), str) and data["description"].strip(), path
    assert REQUIRED_SKILLS <= names
    assert not RETIRED_SKILLS & names
    for name in RETIRED_SKILLS:
        assert not list(SKILLS_ROOT.rglob(name)), name


def test_skill_tool_mappings_resolve_to_bundled_entries() -> None:
    expected = {
        "automata-agent-router": ".agents/tools/agent-router/agent_router.py",
        "automata-timer": ".agents/tools/timer/timer.py",
        "automata-line-use": ".agents/tools/line/line.py",
        "automata-tmux-communication": ".agents/tools/tmux-message/tmux_message.py",
    }
    for path in SKILL_FILES:
        metadata = parse_frontmatter(path).get("metadata", {})
        assert isinstance(metadata, dict), path
        mapping = metadata.get("automata-tools")
        if path.parent.name in expected:
            assert mapping == expected[path.parent.name], path
        if mapping is None:
            continue
        assert isinstance(mapping, str), path
        entries = [entry.strip() for entry in mapping.split(",")]
        assert all(entries) and len(entries) == len(set(entries)), path
        for entry in entries:
            relative = PurePosixPath(entry)
            assert relative.parts[:2] == (".agents", "tools"), (path, entry)
            assert len(relative.parts) >= 4 and ".." not in relative.parts, (path, entry)
            assert TOOLS_ROOT.joinpath(*relative.parts[2:]).is_file(), (path, entry)


def test_declared_skill_asset_references_exist() -> None:
    for asset in (
        "operations/automata-pc-ui-control/references/linux-and-browser-control.md",
        "skill-ops/automata-agent-evaluation/references/scoring.md",
    ):
        assert (SKILLS_ROOT / asset).is_file(), asset
    # Check actual package paths, not prose, example commands, or runtime destinations.
    for skill in SKILL_FILES:
        for document in skill.parent.rglob("*.md"):
            text = document.read_text()
            paths = re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", text)
            paths += re.findall(r"`((?:references|templates|scripts|lib)/[^`\s]+\.[a-z]+)`", text)
            for target in paths:
                if ":" in target or target.startswith(("#", "/", "~")):
                    continue
                target = target.split("#", 1)[0]
                if not target or any(marker in target for marker in ("<", ">", "*", "...")):
                    continue
                assert (document.parent / target).exists(), (document, target)


def test_bundled_skills_exclude_runtime_and_provider_state() -> None:
    for name in ("config", "generated", "openai.yaml", "calibration-records.md"):
        assert not list(SKILLS_ROOT.rglob(name)), name
    assert not (TOOLS_ROOT / "ui-channel").exists()
    assert not (PACKAGE_ROOT / "extensions/ui-channel.ts").exists()
    assert not (
        SKILLS_ROOT / "operations/automata-adaptive-ui/references/build-and-preview.md"
    ).exists()


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=lambda p: p.parent.name)
def test_selected_skill_installs_only_its_packaged_files(tmp_path: Path, skill_file: Path) -> None:
    name = skill_file.parent.name
    target = tmp_path / "skills"
    results = install_skills(target_root=target, skill_names=[name])
    assert [result.name for result in results] == [name]
    assert list(tmp_path.iterdir()) == [target]
    installed = target / name
    assert list(target.iterdir()) == [installed]
    assert not installed.is_symlink()

    def contents(directory: Path) -> dict[str, bytes]:
        return {
            str(p.relative_to(directory)): p.read_bytes()
            for p in directory.rglob("*")
            if p.is_file()
        }

    assert contents(installed) == contents(skill_file.parent)


def test_evaluation_record_example_is_internally_consistent() -> None:
    path = SKILLS_ROOT / "skill-ops/automata-agent-evaluation/templates/evaluation-record.json"
    data = json.loads(path.read_text())
    assert data["schema_version"] == 1
    for field in ("run_id", "subject", "runtime", "evaluator", "rubric", "scenario"):
        assert data[field], field
    criteria = [c for c in data["criteria"] if c["status"] == "scored"]
    assert criteria
    for criterion in criteria:
        assert 0 <= criterion["score"] <= criterion["maximum"]
        assert criterion["evidence"]
    earned = sum(c["score"] for c in criteria)
    maximum = sum(c["maximum"] for c in criteria)
    assert maximum > 0
    assert data["score"] == {
        "earned": earned,
        "maximum": maximum,
        "percent": earned / maximum * 100,
    }
    # An example record must not contradict its own score and gates. This does not
    # grade real evidence or endorse a universal numerical threshold for agent quality.
    if data["verdict"] == "PASS":
        assert all(gate["status"] == "PASS" and gate["evidence"] for gate in data["critical_gates"])
        assert data["score"]["percent"] >= data["rubric"]["threshold_percent"]
        assert all(c["minimum"] is None or c["score"] >= c["minimum"] for c in criteria)
