"""Offline interfaces only; actual Podman proof is in sandbox_podman_test.py."""

import json
import queue
import subprocess
import time
import types
from pathlib import Path

import pytest

HELPER = Path(__file__).parents[3] / "exams/automata-harness/sandbox/candidate.py"


@pytest.fixture
def sandbox():
    module = types.ModuleType("exam_sandbox_test")
    module.__file__ = str(HELPER)
    exec(compile(HELPER.read_text(), str(HELPER), "exec"), module.__dict__)
    return module


@pytest.mark.parametrize("code, expected", [(0, True), (1, False), (125, None)])
def test_exists_distinguishes_absence_from_errors(sandbox, monkeypatch, code, expected):
    monkeypatch.setattr(sandbox, "command", lambda args: subprocess.CompletedProcess(args, code))
    if expected is None:
        with pytest.raises(RuntimeError):
            sandbox.exists("a" * 64)
    else:
        assert sandbox.exists("a" * 64) is expected


def test_cid_is_write_once(sandbox, tmp_path):
    sandbox.publish_cid(tmp_path, "a" * 64)
    sandbox.publish_cid(tmp_path, "a" * 64)
    with pytest.raises(RuntimeError):
        sandbox.publish_cid(tmp_path, "b" * 64)
    assert json.loads((tmp_path / "cid.json").read_text())["cid"] == "a" * 64


def test_oauth_projection_and_expiry_fail_closed(sandbox, tmp_path):
    path = tmp_path / "auth.json"
    data = {
        "openai": {
            "type": "oauth",
            "access": "fixture-access-secret",
            "refresh": "fixture-refresh-secret",
            "expires": (time.time() + 2000) * 1000,
        },
        "other": {"key": "unrelated-secret"},
    }
    path.write_text(json.dumps(data))
    projected, secrets = sandbox.project_auth(path, 900)
    assert set(projected) == {"openai"}
    assert projected["openai"]["refresh"] == ""
    assert "fixture-refresh-secret" not in json.dumps(projected)
    assert "unrelated-secret" not in json.dumps(projected)
    assert secrets == ["fixture-access-secret"]
    data["openai"]["expires"] = 0
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        sandbox.project_auth(path, 900)


def test_model_projection_rejects_route_or_id_changes(sandbox, tmp_path):
    path = tmp_path / "models.json"
    data = {
        "providers": {
            "openai": {
                "models": [
                    {"id": sandbox.MODEL, "api": "openai-responses", "reasoning": True},
                    {"id": "unselected"},
                ]
            }
        }
    }
    path.write_text(json.dumps(data))
    assert len(sandbox.project_model(path)["providers"]["openai"]["models"]) == 1
    data["providers"]["openai"]["baseUrl"] = "https://fixture.invalid"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        sandbox.project_model(path)


@pytest.mark.parametrize("excluded", [".git", "examiner", "tests"])
def test_materials_exclude_private_trees(sandbox, tmp_path, excluded):
    source = tmp_path / "input"
    source.mkdir()
    (source / "paper.md").write_text("selected fixture paper")
    (source / excluded).mkdir()
    with pytest.raises(ValueError):
        sandbox.copy_materials(source, tmp_path / "output")


def test_material_copy_rejects_symlinks_and_preserves_allowed_data(sandbox, tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "paper.md").write_text("selected fixture paper")
    sandbox.copy_materials(source, tmp_path / "good")
    assert (tmp_path / "good/paper.md").read_bytes() == (source / "paper.md").read_bytes()
    (source / "link").symlink_to(tmp_path / "good/paper.md")
    with pytest.raises(ValueError):
        sandbox.copy_materials(source, tmp_path / "bad")


def test_receipt_whitelist_and_redaction_before_truncation(sandbox):
    event = {
        "type": "tool_execution_end",
        "toolName": "read",
        "toolCallId": "fixture",
        "result": {
            "content": [
                {"type": "text", "text": "fixture-access-secret"},
                {"type": "thinking", "thinking": "private-reasoning"},
            ],
            "nestedCalls": {"messages": ["private-transcript"]},
        },
        "unneeded": "private-state",
    }
    retained = sandbox.bounded(sandbox.tool_receipt(event), ["fixture-access-secret"])
    text = json.dumps(retained)
    assert all(
        s not in text
        for s in [
            "fixture-access-secret",
            "private-reasoning",
            "private-transcript",
            "private-state",
        ]
    )
    assert sandbox.bounded(
        {"text": "fixture-access-secret" * 100}, ["fixture-access-secret"], limit=40
    )["truncated"]


def test_rpc_drops_thinking_and_keeps_final_text(sandbox, tmp_path):
    rpc = sandbox.Rpc.__new__(sandbox.Rpc)
    rpc.root, rpc.secrets, rpc.deadline = tmp_path, [], time.monotonic() + 2
    rpc.events = queue.Queue()
    rpc.trace_bytes, rpc.gaps, rpc.assistants, rpc.provider_error = 0, False, 0, False
    rpc.events.put(
        (
            "stdout",
            json.dumps(
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "stopReason": "stop",
                        "content": [
                            {"type": "thinking", "thinking": "private-reasoning"},
                            {
                                "type": "text",
                                "text": "final answer",
                                "textSignature": "private-signature",
                            },
                        ],
                    },
                }
            ).encode(),
        )
    )
    rpc.next()
    assert rpc.final == "final answer"
    assert "private-" not in (tmp_path / "receipts.jsonl").read_text()


def test_cleanup_refuses_mismatched_ownership(sandbox, tmp_path, monkeypatch):
    plan = {"run_id": "fixture", "owner": "nonce", "name": "owned-name"}
    sandbox.save(tmp_path / "owner.json", plan)
    sandbox.publish_cid(tmp_path, "a" * 64)
    calls = []

    def command(args):
        calls.append(args)
        if args[1] == "container":
            return subprocess.CompletedProcess(args, 0)
        data = [{"Id": "a" * 64, "Name": "owned-name", "Config": {"Labels": {}}, "Pod": ""}]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(data).encode())

    monkeypatch.setattr(sandbox, "command", command)
    assert sandbox.cleanup(tmp_path)["status"] == "unconfirmed"
    assert not any(args[1] in {"stop", "rm"} for args in calls)


def test_guard_exits_after_confirmed_cleanup(sandbox, tmp_path):
    sandbox.save(tmp_path / "owner.json", {"deadline": time.monotonic() + 5})
    sandbox.save(tmp_path / "cleanup.json", {"status": "confirmed-absent"})
    assert sandbox.guard(tmp_path) == 0
    assert (tmp_path / "guard-done.json").is_file()


def test_create_contract_has_only_readonly_material_bind(sandbox, tmp_path):
    plan = {"name": "fixture", "owner": "nonce", "run_id": "fixture", "seconds": 900}
    args = sandbox.create_args(plan, tmp_path, "a" * 64, "pasta")
    assert "--network=" + sandbox.PROVIDER_NETWORK in args
    assert "--cap-drop=ALL" in args and "--read-only" in args
    mounts = [args[i + 1] for i, value in enumerate(args) if value == "--volume"]
    assert mounts == [str(tmp_path / "materials") + ":/materials:ro,Z"]
    assert "--pod" not in args and "--privileged" not in args


def test_capture_redacts_before_retention_and_records_missing(sandbox, tmp_path, monkeypatch):
    data = {"files": {"out/answers.md": "fixture-access-secret"}, "skipped": [], "missing": []}
    monkeypatch.setattr(
        sandbox,
        "command",
        lambda args: subprocess.CompletedProcess(args, 0, stdout=json.dumps(data).encode()),
    )
    sandbox.capture_workspace("a" * 64, tmp_path, ["fixture-access-secret"], "knowledge")
    assert (tmp_path / "artifacts/out/answers.md").read_text() == "[REDACTED]"
    assert json.loads((tmp_path / "artifact-capture.json").read_text())["missing"] == []
