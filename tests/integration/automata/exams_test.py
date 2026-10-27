"""Mechanical exam/fixture contracts, not agent performance or prose quality."""

import csv
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from automata.install.skills import install_skills

EXAM_ROOT = Path(__file__).parents[3] / "exams" / "automata-harness"


def test_exam_manifest_paths_ids_and_point_totals() -> None:
    data = json.loads((EXAM_ROOT / "exam.json").read_text())
    assert data["schema_version"] == 1
    for field in ("blueprint", "setup_guide", "knowledge_paper", "knowledge_key"):
        assert (EXAM_ROOT / data[field]).is_file()
    questions = data["questions"]
    by_id = {question["id"]: question for question in questions}
    assert len(by_id) == len(questions)
    for question in questions:
        assert question["points"] > 0
        assert question["version"] > 0 and question["key_version"] > 0
        assert question["status"] == "authored"
        for field in ("prompt", "key", "fixtures"):
            if field not in question:
                continue
            path = (EXAM_ROOT / question[field]).resolve()
            assert path.is_relative_to(EXAM_ROOT.resolve())
            assert path.exists()
        assert question["prompt"].startswith("candidate/")
        assert question["key"].startswith("examiner/")
        if "required_profile" in question:
            profile = data["candidate_profiles"][question["required_profile"]]
            assert question["id"] in profile["supported_practical_ids"]
    domains = {question["domain"] for question in questions}
    assert len(domains) == 6
    for domain in domains:
        grouped = [question for question in questions if question["domain"] == domain]
        assert sorted(q["points"] for q in grouped if q["type"] == "knowledge") == [2, 3]
        assert [q["points"] for q in grouped if q["type"] == "practical"] == [10]
    for kind, paper in data["papers"].items():
        selected = [by_id[key] for key in paper["question_ids"]]
        assert len(selected) == len({question["id"] for question in selected})
        assert all(question["type"] == kind for question in selected)
        assert sum(question["points"] for question in selected) == paper["possible"]
    assert Counter(question["type"] for question in questions) == {
        "knowledge": 12, "practical": 6,
    }
    for profile in data["candidate_profiles"].values():
        ids = profile["supported_practical_ids"]
        assert len(ids) == len(set(ids))
        assert all(by_id[key]["type"] == "practical" for key in ids)
    for sitting in data["pilot"]["sittings"]:
        selected = [by_id[key] for key in sitting["question_ids"]]
        assert all(question["status"] == "authored" for question in selected)
        assert all(question["type"] == sitting["type"] for question in selected)
        assert sum(question["points"] for question in selected) == sitting["possible"]
        assert sitting["maximum_minutes"] <= 15
        if sitting["type"] == "practical":
            profile = data["candidate_profiles"][data["pilot"]["profile"]]
            assert set(sitting["question_ids"]) <= set(profile["supported_practical_ids"])


def files_under(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


def test_p01_fixture_with_real_installer_preserves_preview_and_backup(tmp_path: Path) -> None:
    source = EXAM_ROOT / "candidate/practical/01-project-assets/fixtures"
    root = tmp_path / "task"
    shutil.copytree(source, root)
    installed = root / "work/installed"
    old = files_under(installed / "automata-exam-report")
    custom = files_under(installed / "local-custom")
    before = files_under(root)
    kwargs = {
        "source_root": root / "work/source",
        "target_root": installed,
        "skill_names": ["automata-exam-report"],
        "mode": "replace",
        "backup_root": root / "work/backups",
    }
    install_skills(**kwargs, dry_run=True)
    assert files_under(root) == before
    assert not (root / "work/backups").exists()
    (result,) = install_skills(**kwargs)
    assert result.backup is not None
    assert files_under(Path(result.backup)) == old
    assert files_under(installed / "automata-exam-report") == files_under(
        root / "work/source/automata-exam-report"
    )
    assert files_under(installed / "local-custom") == custom


def test_state_and_coordination_fixture_data_contracts() -> None:
    state = EXAM_ROOT / "candidate/practical/05-context-and-state/fixtures/work"
    rows = json.loads((state / "export.json").read_text())
    receipt = json.loads((state / "check-result.json").read_text())
    assert len(rows) == receipt["local_validation"]["record_count"]
    assert len({row["id"] for row in rows}) == len(rows)
    handoff = json.loads((state / "handoff.json").read_text())
    assert handoff["owner_note"]
    for path in handoff["artifacts"]:
        assert not (state.parent / path).exists()
    request = EXAM_ROOT / "candidate/practical/04-coordination/fixtures/work/request.json"
    records = json.loads(request.read_text())["records"]
    assert records and len({row["id"] for row in records}) == len(records)
    assert all(isinstance(row["value"], int) for row in records)


@pytest.mark.parametrize("repaired", [False, True])
def test_p06_exporter_fixture_contract(tmp_path: Path, repaired: bool) -> None:
    """Exercise the helper with controlled inputs, never a live candidate session."""
    source = EXAM_ROOT / "candidate/practical/06-boundaries-and-recovery/fixtures"
    root = tmp_path / "task"
    shutil.copytree(source, root)
    preserved = ["export_report.py", "work/rows.json", "protected/operator-notes.txt"]
    original = {name: (root / name).read_bytes() for name in preserved}
    if repaired:
        config_path = root / "work/config.json"
        config = json.loads(config_path.read_text())
        config["delimiter"] = "\t"
        config_path.write_text(json.dumps(config))
    output = root / "out/report.tsv"
    result = subprocess.run(
        [sys.executable, str(root / "export_report.py"),
         "--config", str(root / "work/config.json"),
         "--rows", str(root / "work/rows.json"), "--output", str(output)],
        capture_output=True, text=True, check=False,
    )
    if repaired:
        assert result.returncode == 0, result.stderr
        with output.open(newline="") as stream:
            report = list(csv.reader(stream, delimiter="\t"))
        rows = json.loads((root / "work/rows.json").read_text())
        assert report == [["id", "status"]] + [[row["id"], row["status"]] for row in rows]
    else:
        assert result.returncode != 0
        assert not output.exists()
    assert original == {name: (root / name).read_bytes() for name in preserved}
