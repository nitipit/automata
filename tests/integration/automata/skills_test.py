"""Mechanical skill-package contracts, not evidence of agent judgment or skill quality."""

import json
import re
from pathlib import Path, PurePosixPath

import pytest
import yaml

from automata.install.pi_extensions import install_pi_extensions
from automata.install.skills import SkillInstallError, install_skills, skill_sources

PACKAGE_ROOT = Path(__file__).parents[3] / "src" / "automata"
SKILLS_ROOT = PACKAGE_ROOT / "skills"
SKILL_ROOTS = (SKILLS_ROOT,)
PI_SKILL_NAMES = {
    "automata-pi-extension-dev",
    "automata-pi-agent-team",
    "automata-pi-nodalwire",
    "automata-pi-imagegen",
    "automata-pi-context-compaction",
    "automata-pi-context-status",
    "automata-pi-sessions",
    "automata-pi-skill-activity",
}
TOOLS_ROOT = PACKAGE_ROOT / "tools"
SOURCES = skill_sources()
SKILL_FILES = sorted(path / "SKILL.md" for path in SOURCES.values())
REQUIRED_SKILLS = {
    "automata-adaptive-ui",
    "automata-agents-md",
    "automata-agent-design",
    "automata-model-selection",
    "automata-browser-use",
    "automata-line-use",
    "automata-pi-imagegen",
    "automata-question",
    "automata-pi-context-status",
    "automata-pi-context-compaction",
    "automata-pi-sessions",
    "automata-pi-skill-activity",
    "automata-delegation",
    "automata-cue",
    "automata-manager",
    "automata-workplan",
    "automata-skill-design",
    "automata-setup",
    "automata-timer",
    "automata-storage",
    "automata-task-space",
    "automata-agent-evaluation",
    "automata-communication",
    "automata-goal",
    "automata-git-worktree",
    "automata-gnome-desktop-control",
    "automata-text-writing",
    "automata-documentation",
    "automata-runtime-environment",
    "automata-python-kernel",
    "automata-background-process",
    "automata-pi-extension-dev",
    "automata-pi-agent-team",
    "automata-pi-nodalwire",
    "automata-software-dev",
    "automata-toolsmith",
    "automata-work-pause",
}
RETIRED_SKILLS = {
    "automata-pi-delegation",
    "automata-nodalwire",
    "automata-pi-team",
    "automata-pi-workers",
    "automata-teamwork-design",
    "automata-team-management",
    "automata-web-design",
    "automata-web-app",
    "automata-tmux-background",
    "automata-tmux-communication",
    "automata-tmux-observation",
    "automata-zellij-background",
    "automata-zellij-communication",
    "automata-zellij-observation",
    "automata-team-use",
    "automata-python-workspace",
    "automata-plain-text-writing",
    "automata-journal",
    "automata-playspace",
    "automata-capability-research",
    "automata-stateful-workflow",
    "automata-plan",
    "automata-imagegen",
    "automata-context-compaction",
    "automata-context-status",
    "automata-skill-activity",
    "automata-codex-imagegen",
    "automata-codex-sessions",
    "automata-thinking-control",
    "automata-time-awareness",
    "automata-workspace",
    "automata-workspace-app",
    "automata-pc-ui-control",
    "automata-runtime-status",
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
    "automata-ui-channel-setup",
    "automata-web-browser-control",
    "automata-web-dev",
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
        assert SOURCES[name] == path.parent, path
        assert name not in names, name
        names.add(name)
        assert isinstance(data.get("description"), str) and data["description"].strip(), path
    assert REQUIRED_SKILLS <= names
    assert not RETIRED_SKILLS & names
    for name in RETIRED_SKILLS:
        assert not [path for root in SKILL_ROOTS for path in root.rglob(name)], name


def test_pi_skills_share_one_catalog_with_all_skills() -> None:
    assert len(list(SKILLS_ROOT.rglob("SKILL.md"))) == len(REQUIRED_SKILLS)
    for name in PI_SKILL_NAMES:
        assert (SKILLS_ROOT / name / "SKILL.md").is_file()
        assert not (SKILLS_ROOT / name).is_symlink()


@pytest.mark.parametrize(
    "layout", [".pi/extensions", "custom-agent/extensions", "chosen/extensions"]
)
def test_nodalwire_bundle_documentation_links_survive_install(
    tmp_path: Path, layout: str
) -> None:
    """Packaged local links resolve outside the checkout, not a prose-quality check."""
    extension = "nodalwire"
    skill_name = "automata-pi-nodalwire"
    skill_root = tmp_path / "skills"
    extension_root = tmp_path / layout
    install_skills(target_root=skill_root, skill_names=[skill_name])
    install_pi_extensions(target_root=extension_root, extension_names=[extension])

    bundle = extension_root / extension
    installed_skill = skill_root / skill_name
    for owner, document in [
        (bundle, bundle / "README.md"),
        (installed_skill, installed_skill / "SKILL.md"),
    ]:
        assert document.is_file()
        links = re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", document.read_text())
        local_links = [
            link for link in links
            if not re.match(r"^[a-z][a-z0-9+.-]*:", link, re.IGNORECASE)
            and not link.startswith(("#", "//"))
        ]
        assert local_links  # References survive copying outside the checkout.
        for link in local_links:
            target = (document.parent / link.split("#", 1)[0]).resolve()
            assert target.is_relative_to(owner.resolve()), (document, link)
            assert target.is_file(), (document, link)


def test_changed_portable_guidance_keeps_runtime_details_external() -> None:
    for name in ("automata-setup", "automata-skill-design"):
        for path in SOURCES[name].rglob("*.md"):
            assert not re.search(r"\b(?:Pi|Codex)\b", path.read_text()), path
    assert not (SOURCES["automata-setup"] / "references/codex.md").exists()


def test_renamed_pi_compaction_preserves_preference_paths() -> None:
    text = (SOURCES["automata-pi-context-compaction"] / "SKILL.md").read_text()
    assert "`.agents/var/skills/automata-context-compaction/preferences.md`" in text
    assert "`~/.agents/var/skills/automata-context-compaction/preferences.md`" in text
    assert "var/skills/automata-pi-context-compaction" not in text


def test_skill_tool_mappings_resolve_to_bundled_entries() -> None:
    expected = {
        "automata-timer": ".agents/tools/timer/timer.py",
        "automata-line-use": ".agents/tools/line/line_cli.py",
    }
    for path in SKILL_FILES:
        metadata = parse_frontmatter(path).get("metadata", {})
        assert isinstance(metadata, dict), path
        mapping = metadata.get("automata-tools")
        name = parse_frontmatter(path)["name"]
        if name in expected:
            assert mapping == expected[name], path
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
    for asset in ("automata-agent-evaluation/references/scoring.md",):
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
        assert not [path for root in SKILL_ROOTS for path in root.rglob(name)], name
    assert not (TOOLS_ROOT / "ui-channel").exists()
    assert not (PACKAGE_ROOT / "runtimes/pi/extensions/ui-channel.ts").exists()
    assert not (SKILLS_ROOT / "automata-adaptive-ui/references/build-and-preview.md").exists()


def test_default_install_includes_every_shared_and_pi_skill(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    results = install_skills(target_root=target)
    expected = set(SOURCES)
    assert len(expected) == len(REQUIRED_SKILLS)
    assert "automata-pi-sessions" in expected
    assert "automata-codex-sessions" not in expected
    roots = expected - {"automata-documentation"}
    assert {result.name for result in results} == roots
    assert {path.name for path in target.iterdir()} == roots
    assert set(skill_sources(target)) == expected


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=lambda p: p.parent.name)
def test_selected_skill_installs_only_its_packaged_files(tmp_path: Path, skill_file: Path) -> None:
    name = parse_frontmatter(skill_file)["name"]
    target = tmp_path / "skills"
    nested_parents = {
        "automata-documentation": "automata-text-writing",
    }
    if name in nested_parents:
        with pytest.raises(SkillInstallError, match=f"select outer parent {nested_parents[name]}"):
            install_skills(target_root=target, skill_names=[name])
        assert not target.exists()
        return
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


def test_delegation_installs_conditional_team_references(tmp_path: Path) -> None:
    target = tmp_path / "skills"
    install_skills(target_root=target, skill_names=["automata-delegation"])
    installed = target / "automata-delegation"
    assert {path.name for path in installed.joinpath("references").glob("*.md")} == {
        "team-design.md",
        "hierarchical-teams.md",
        "manager-recovery.md",
        "missing-evidence.md",
    }
    assert {path.name for path in target.iterdir()} == {"automata-delegation"}


def test_cue_does_not_name_other_skills() -> None:
    for name in ("automata-cue",):
        root = SKILLS_ROOT / name
        for path in root.rglob("*.md"):
            names = set(re.findall(r"automata-[a-z0-9]+(?:-[a-z0-9]+)*", path.read_text()))
            assert names <= {name}, (path, names)


def test_evaluation_record_example_is_internally_consistent() -> None:
    path = SKILLS_ROOT / "automata-agent-evaluation/templates/evaluation-record.json"
    data = json.loads(path.read_text())
    assert data["schema_version"] == 2
    for field in ("run_id", "exam", "candidate", "runtime", "conditions", "examiner"):
        assert data[field], field
    exam = data["exam"]
    assert exam["type"] in {"knowledge", "practical"}
    assert exam["version"] > 0 and exam["answer_key_version"] > 0
    pass_mark = exam["pass_mark_percent"]
    assert pass_mark is None or 0 <= pass_mark <= 100
    assert exam["package_fingerprint"]
    assert exam["git_identity"]["commit"]
    assert data["runtime"]["candidate_profile"]
    for asset in data["runtime"]["assets"]:
        assert asset["kind"] and asset["root"] and asset["revision"]
        assert asset["source"] in {"source", "installed"}
    assert "dirty_tree_identity" in exam["git_identity"]
    selection = exam["selection"]
    assert selection["kind"] in {"full", "subset"}
    selected_ids = selection["question_ids"]
    paper_ids = selection["paper_question_ids"]
    assert len(selected_ids) == len(set(selected_ids))
    assert len(paper_ids) == len(set(paper_ids))
    assert set(selected_ids) <= set(paper_ids)
    if selection["kind"] == "full":
        assert set(selected_ids) == set(paper_ids)
        assert selection["selected_possible"] == selection["paper_possible"]
    else:
        assert set(selected_ids) < set(paper_ids)
        assert selection["selected_possible"] < selection["paper_possible"]
    questions = data["question_results"]
    assert questions
    assert {question["id"] for question in questions} == set(selected_ids)
    assert sum(question["possible"] for question in questions) == selection["selected_possible"]
    assert len({question["id"] for question in questions}) == len(questions)
    graded = [question for question in questions if question["status"] == "graded"]
    for question in questions:
        assert question["status"] in {"graded", "invalid", "not_run"}
        assert question["possible"] > 0
        if question["status"] == "graded":
            assert 0 <= question["earned"] <= question["possible"]
            assert question["evidence"]
        else:
            assert question["earned"] is None
            assert question["comment"]
    earned = sum(question["earned"] for question in graded)
    possible = sum(question["possible"] for question in graded)
    percent = earned / possible * 100 if possible else None
    assert data["score"] == {
        "earned": earned,
        "possible": possible,
        "percent": percent,
        "questions_graded": len(graded),
        "questions_total": len(questions),
    }
    for failure in data["critical_failures"]:
        assert failure["id"] in exam["critical_rules"]
        assert failure["evidence"]
    # Template consistency only: this does not grade real evidence or prove ability.
    if data["critical_failures"]:
        expected = "FAIL"
    elif len(graded) != len(questions) or percent is None:
        expected = "INCONCLUSIVE"
    elif pass_mark is None:
        expected = "SCORED"
    else:
        expected = "PASS" if percent >= pass_mark else "FAIL"
    assert data["result"] == expected
