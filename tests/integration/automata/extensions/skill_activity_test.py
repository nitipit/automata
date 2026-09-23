"""Installed bundle/CLI boundaries, with opt-in native Pi execution and no live model."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from automata.install.pi_extensions import install_pi_extensions


@pytest.fixture
def installed(tmp_path: Path) -> Path:
    install_pi_extensions(
        target_root=tmp_path / ".pi/extensions", extension_names=["skill-activity"]
    )
    return tmp_path / ".pi/extensions/skill-activity"


def test_skill_activity_cli_round_trip(installed: Path, tmp_path: Path) -> None:
    pytest.importorskip("shelfdb", reason="Run with the optional ShelfDB dependency")
    pytest.importorskip("dictify")
    db = tmp_path / "db"
    event = {
        "timestamp": "2026-09-23T18:00:00Z",
        "sessionId": "fixture-session",
        "toolCallId": "read-one",
        "project": str(tmp_path),
        "skill": "fixture-skill",
        "path": str(tmp_path / "SKILL.md"),
    }

    def cli(action, *args):
        return subprocess.run(
            [sys.executable, str(installed / "store.py"), action, "--db", str(db), *args],
            capture_output=True, text=True, timeout=10,
        )

    empty = cli("list")
    assert empty.returncode == 0, empty.stderr
    assert json.loads(empty.stdout) == []
    assert not db.exists()
    first = cli("record", "--event", json.dumps(event))
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout) == {"inserted": True}
    replay = cli("record", "--event", json.dumps(event))
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == {"inserted": False}
    for invalid in ({**event, "body": "DO NOT STORE"}, {**event, "skill": ""}, []):
        rejected = cli("record", "--event", json.dumps(invalid))
        assert rejected.returncode == 2
        assert "DO NOT STORE" not in rejected.stderr
    listed = cli("list")
    assert listed.returncode == 0, listed.stderr
    assert json.loads(listed.stdout) == [{**event, "source": "read", "status": "loaded"}]
    assert cli("list", "--limit", "101").returncode == 2


def test_skill_activity_native_pi(installed: Path, tmp_path: Path) -> None:
    sdk = os.environ.get("PI_SKILL_ACTIVITY_SDK")
    node = shutil.which("node")
    if not sdk or not node or not shutil.which("uv"):
        pytest.skip("Set PI_SKILL_ACTIVITY_SDK to an installed Pi dist/index.js; Node/uv required")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("skill_activity_native_test.mjs"))],
        env={
            **os.environ,
            "PI_OFFLINE": "1",
            "PI_CODING_AGENT_DIR": str(tmp_path / "agent"),
            "SKILL_ACTIVITY_TEST_ROOT": str(tmp_path),
            "SKILL_ACTIVITY_EXTENSION": str(installed),
        },
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads((tmp_path / "result.json").read_text())
    assert len(receipt["records"]) == 2
    assert receipt["externalModelCalls"] == 0
