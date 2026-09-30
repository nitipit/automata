"""Owned synthetic stores: scope, receipts, effect closure and failure semantics."""

import copy
import importlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from automata.install.codex import install_codex

RUNTIME = Path(__file__).parents[4] / "src/automata/runtimes/codex"
ONE = "00000000-0000-4000-8000-000000000001"
TWO = "00000000-0000-4000-8000-000000000002"
THREE = "00000000-0000-4000-8000-000000000003"
CHILD = "00000000-0000-4000-8000-000000000004"
PRIVATE = "PRIVATE_MESSAGE_BODY_NEVER_IN_LIST_OR_RECEIPT"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.syspath_prepend(str(RUNTIME))
    return SimpleNamespace(
        **{
            name: importlib.import_module("session_" + module)
            for name, module in {
                "store": "store",
                "receipts": "receipts",
                "ops": "operations",
                "recovery": "recovery",
                "copy": "copy",
            }.items()
        }
    )


@pytest.fixture
def fixture(api, tmp_path):
    root, state, cwd = tmp_path / "store", tmp_path / "state", tmp_path / "project"
    root.mkdir()
    cwd.mkdir()
    with sqlite3.connect(root / "state_5.sqlite") as db:
        integers = {"created_at", "updated_at", "archived", "is_pinned"}
        db.execute(
            "CREATE TABLE threads ("
            + ",".join(
                name
                + (" INTEGER" if name in integers else " TEXT")
                + (" PRIMARY KEY" if name == "id" else "")
                for name in api.store.COLUMNS
            )
            + ")"
        )
        db.execute("CREATE TABLE thread_spawn_edges (parent_thread_id TEXT, child_thread_id TEXT)")
        db.execute("CREATE TABLE thread_dynamic_tools (thread_id TEXT)")
        db.execute("CREATE TABLE thread_attachments (thread_id TEXT)")

    def add(identity=ONE, project=cwd, parent=None, provenance=None, version="0.159.0"):
        path = root / "sessions/2026/09/30" / f"rollout-2026-09-30T00-00-00-{identity}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": identity,
            "session_id": identity,
            "cli_version": version,
            "cwd": str(project),
            "history_mode": "paginated",
            "base_instructions": {"text": PRIVATE},
        }
        if parent:
            payload["history_base"] = {"thread_id": parent}
        if provenance:
            payload["forked_from_id"] = provenance
        path.write_text(
            json.dumps({"type": "session_meta", "ordinal": 0, "payload": payload}) + "\n"
        )
        row = dict.fromkeys(api.store.COLUMNS)
        row.update(
            id=identity,
            rollout_path=str(path),
            cwd=str(project),
            created_at=10,
            updated_at=int(identity[-1]),
            archived=0,
            cli_version=version,
            source="cli",
            model_provider="fixture",
            model="gpt-5.1-codex",
            history_mode="paginated",
            name="fixture-name",
            is_pinned=0,
        )
        with sqlite3.connect(root / "state_5.sqlite") as db:
            db.execute(
                "INSERT INTO threads VALUES (" + ",".join("?" for _ in row) + ")",
                list(row.values()),
            )
        return api.store.identify(root, row) if version == "0.159.0" else row

    return SimpleNamespace(root=root, state=state, cwd=cwd, add=add)


def listing(api, fixture, **kwargs):
    return api.receipts.list_sessions(fixture.state, fixture.root, str(fixture.cwd), **kwargs)


def test_listing_explicit_scope_pages_receipts_and_no_bodies(api, fixture):
    fixture.add()
    fixture.add(TWO)
    first = listing(api, fixture, limit=1)
    assert len(first["sessions"]) == 1 and first["nextCursor"]
    assert {"copyReceipt", "forkReceipt", "trashReceipt"} <= first.keys()
    assert first["totalCount"] == 2 and first["sessions"][0]["id"] == TWO
    assert all(
        key not in first["sessions"][0] for key in ("path", "preview", "turns", "rollout_path")
    )
    assert PRIVATE not in json.dumps(first)
    assert all(PRIVATE not in path.read_text() for path in fixture.state.glob("*.json"))
    second = api.receipts.list_sessions(fixture.state, fixture.root, cursor=first["nextCursor"])
    assert second["sessions"][0]["id"] == ONE and second["nextCursor"] is None
    assert second["copyReceipt"] != first["copyReceipt"]
    with api.receipts.locked(fixture.state, fixture.root) as (root, path):
        with pytest.raises(api.store.CoverageError):
            api.receipts.claim(path, root, "copy", first["copyReceipt"], [TWO], None)


@pytest.mark.parametrize("case", ["no-scope", "two-scopes", "relative-cwd", "limit"])
def test_discovery_scope_is_not_implicit(api, fixture, case):
    kwargs = {
        "no-scope": {},
        "two-scopes": {"cwd": str(fixture.cwd), "all_projects": True},
        "relative-cwd": {"cwd": "relative"},
        "limit": {"cwd": str(fixture.cwd), "limit": 101},
    }[case]
    with pytest.raises(api.store.CoverageError):
        api.receipts.list_sessions(fixture.state, fixture.root, **kwargs)


def test_missing_root_and_missing_cwd_are_not_deletion_authority(api, fixture, tmp_path):
    missing = api.receipts.list_sessions(
        fixture.state, tmp_path / "missing-store", cwd=str(fixture.cwd)
    )
    assert missing["sessions"] == [] and missing["coverage"] == "missing-root"
    assert not (tmp_path / "missing-store").exists()
    fixture.add(project=tmp_path / "gone-project")
    found = api.receipts.list_sessions(
        fixture.state, fixture.root, cwd=str(tmp_path / "gone-project")
    )
    assert found["sessions"][0]["directoryStatus"] == "missing"
    assert "not inactivity or permission" in found["warning"]


@pytest.mark.parametrize(
    "case", ["stale", "wrong-id", "wrong-operation", "expired", "root", "current"]
)
def test_receipt_binding_fails_before_mutation(api, fixture, monkeypatch, case):
    candidate = fixture.add()
    current = ONE if case == "current" else None
    result = listing(api, fixture, current=current)
    identity, token = ONE, result["copyReceipt"]
    if case == "stale":
        with Path(candidate["path"]).open("a") as stream:
            stream.write("{}\n")
    elif case == "wrong-id":
        identity = TWO
    elif case == "wrong-operation":
        token = result["trashReceipt"]
    elif case == "expired":
        monkeypatch.setattr(api.receipts.time, "time", lambda: result["expiresAt"] + 1)
    elif case == "root":
        fixture.root.rename(fixture.root.with_name("old-store"))
        fixture.root.mkdir()
    with api.receipts.locked(fixture.state, fixture.root) as (root, path):
        with pytest.raises(api.store.CoverageError):
            api.receipts.claim(path, root, "copy", token, [identity], current)


def test_receipt_consumed_and_duplicate_selection_rejected(api, fixture):
    fixture.add()
    result = listing(api, fixture)
    with api.receipts.locked(fixture.state, fixture.root) as (root, path):
        with pytest.raises(api.store.CoverageError):
            api.receipts.claim(path, root, "copy", result["copyReceipt"], [ONE, ONE], None)
        assert (
            api.receipts.claim(path, root, "copy", result["copyReceipt"], [ONE], None)[0]["id"]
            == ONE
        )
        with pytest.raises(api.store.CoverageError):
            api.receipts.claim(path, root, "copy", result["copyReceipt"], [ONE], None)


@pytest.mark.parametrize("case", ["escape", "symlink", "version", "identity"])
def test_unselectable_native_files_not_exposed(api, fixture, tmp_path, case):
    candidate = fixture.add(version="0.160.0" if case == "version" else "0.159.0")
    path = Path(candidate.get("path", candidate.get("rollout_path")))
    if case == "escape":
        outside = tmp_path / path.name
        shutil.copyfile(path, outside)
        with sqlite3.connect(fixture.root / "state_5.sqlite") as db:
            db.execute("UPDATE threads SET rollout_path=?", [str(outside)])
    elif case == "symlink":
        saved = path.with_suffix(".saved")
        path.rename(saved)
        path.symlink_to(saved)
    elif case == "identity":
        value = json.loads(path.read_text())
        value["payload"]["id"] = TWO
        path.write_text(json.dumps(value) + "\n")
    result = listing(api, fixture)
    assert result["sessions"] == [] and result["unavailableCount"] == 1


@pytest.mark.parametrize("kind", ["spawn", "history"])
def test_dependency_closure_rejects_unselected_and_unsupported_selected_groups(api, fixture, kind):
    fixture.add()
    fixture.add(
        TWO,
        project=fixture.cwd.parent / "another-project",
        parent=ONE if kind == "history" else None,
    )
    if kind == "spawn":
        with sqlite3.connect(fixture.root / "state_5.sqlite") as db:
            db.execute("INSERT INTO thread_spawn_edges VALUES (?,?)", [ONE, TWO])
    with pytest.raises(api.store.CoverageError, match="unselected"):
        api.store.effect_closure(fixture.root, [ONE])
    with pytest.raises(api.store.CoverageError, match="groups unsupported"):
        api.store.effect_closure(fixture.root, [ONE, TWO])


@pytest.mark.parametrize("base", [[], {}, "unknown-schema"])
def test_unknown_history_dependency_metadata_blocks_removal(api, fixture, base):
    fixture.add()
    child = fixture.add(TWO)
    path = Path(child["path"])
    metadata = json.loads(path.read_text())
    metadata["payload"]["history_base"] = base
    path.write_text(json.dumps(metadata) + "\n")
    with pytest.raises(api.store.CoverageError, match="dependency metadata"):
        api.store.effect_closure(fixture.root, [ONE])


def test_independent_copy_provenance_is_not_history_dependency(api, fixture):
    fixture.add()
    fixture.add(TWO, provenance=ONE)
    assert api.store.effect_closure(fixture.root, [ONE]) == [ONE]
    assert api.store.effect_closure(fixture.root, [TWO]) == [TWO]


def test_ancillary_state_is_not_silently_discarded(api, fixture):
    candidate = fixture.add()
    with sqlite3.connect(fixture.root / "state_5.sqlite") as db:
        db.execute("INSERT INTO thread_attachments VALUES (?)", [ONE])
    with pytest.raises(api.store.CoverageError, match="ancillary"):
        api.store.ensure_recoverable_subset(fixture.root, candidate)


def test_known_current_and_inactivity_attestation(api, monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", ONE)
    assert api.ops.caller(None, False, True) == ONE
    for current, outside, inactive in [(TWO, False, True), (None, True, True), (ONE, False, False)]:
        with pytest.raises(api.store.CoverageError):
            api.ops.caller(current, outside, inactive)
    monkeypatch.delenv("CODEX_THREAD_ID")
    with pytest.raises(api.store.CoverageError):
        api.ops.caller(None, False, True)
    assert api.ops.caller(None, True, True) is None


def test_content_digest_detects_payload_change_with_identical_ids(api):
    turns = [
        {
            "id": "turn-1",
            "status": "completed",
            "items": [
                {"id": "user-1", "type": "userMessage", "content": [{"text": "original user"}]},
                {
                    "id": "cmd-1",
                    "type": "commandExecution",
                    "command": "printf x",
                    "aggregatedOutput": "x",
                },
                {"id": "agent-1", "type": "agentMessage", "text": "original answer"},
            ],
        }
    ]

    class Client:
        def request(self, *_args):
            return {"thread": {"id": ONE, "turns": turns}}

    original = api.recovery.signature(Client(), ONE)
    for index, field in [(0, "content"), (1, "aggregatedOutput"), (2, "text")]:
        saved = copy.deepcopy(turns[0]["items"][index][field])
        turns[0]["items"][index][field] = "altered payload"
        assert api.recovery.signature(Client(), ONE) != original
        turns[0]["items"][index][field] = saved
    assert PRIVATE not in json.dumps(original) and set(original) == {
        "sha256",
        "turnCount",
        "itemCount",
    }


def test_real_os_trash_package_and_collision_restore(api, fixture, tmp_path):
    if not shutil.which("gio"):
        pytest.skip("gio required for actual fixture-owned freedesktop trash")
    candidate = fixture.add()
    fixture.state.mkdir()
    path, receipt = api.recovery.stage(
        fixture.state,
        fixture.root,
        [candidate],
        {ONE: {"sha256": "fixture", "turnCount": 0, "itemCount": 0}},
        tmp_path / "xdg",
    )
    assert Path(receipt["trashInfoPath"]).is_file()
    assert Path(receipt["packagePath"]).is_dir() and not Path(receipt["stagingPath"]).exists()
    _, loaded, package = api.recovery.load_recovery(
        fixture.state, fixture.root, receipt["recoveryId"]
    )
    assert loaded["entries"][0]["candidate"]["id"] == ONE
    assert (package / (ONE + ".jsonl")).read_bytes() == Path(candidate["path"]).read_bytes()
    with pytest.raises(api.store.CoverageError, match="collision"):
        api.ops.restore(
            fixture.state, fixture.root, Path("/never-called"), receipt["recoveryId"], [ONE], None
        )
    (package / (ONE + ".jsonl")).write_text("tampered")
    with pytest.raises(api.store.CoverageError, match="changed"):
        api.recovery.load_recovery(fixture.state, fixture.root, receipt["recoveryId"])
    assert path.exists() and Path(candidate["path"]).exists()


def test_dependency_rejection_precedes_native_or_trash_side_effects(api, fixture, monkeypatch):
    fixture.add()
    fixture.add(TWO, parent=ONE)
    result = listing(api, fixture)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("must reject dependencies before native or package side effects")

    monkeypatch.setattr(api.ops, "native", forbidden)
    monkeypatch.setattr(api.ops, "stage", forbidden)
    with pytest.raises(api.store.CoverageError):
        api.ops.trash(
            fixture.state,
            fixture.root,
            Path("/unused"),
            result["trashReceipt"],
            [ONE],
            fixture.state / "xdg",
            None,
        )


def test_trash_partial_failure_retains_package_and_reports_unattempted(api, fixture, monkeypatch):
    selected = [fixture.add(identity) for identity in (ONE, TWO, THREE)]
    result = listing(api, fixture)
    calls = []

    class Client:
        def __init__(self, identity):
            self.identity = identity

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def request(self, method, _params):
            if method == "thread/read":
                return {"thread": {"id": self.identity, "turns": []}}
            calls.append(self.identity)
            if self.identity == TWO:
                raise api.store.CoverageError("injected native failure")
            candidate = next(c for c in selected if c["id"] == self.identity)
            Path(candidate["path"]).unlink()
            with sqlite3.connect(fixture.root / "state_5.sqlite") as db:
                db.execute("DELETE FROM threads WHERE id=?", [self.identity])
            return {}

    def staged(*_args):
        journal = {"entries": [{"status": "prepared"} for _ in selected]}
        path = fixture.state / "retained-recovery.json"
        path.write_text(json.dumps(journal))
        return path, journal

    monkeypatch.setattr(api.ops, "native", lambda _b, _r, _s, c: Client(c["id"]))
    monkeypatch.setattr(api.ops, "stage", staged)
    output = api.ops.trash(
        fixture.state,
        fixture.root,
        Path("/unused"),
        result["trashReceipt"],
        [ONE, TWO, THREE],
        fixture.state / "xdg",
        None,
    )
    assert output["status"] == "incomplete"
    assert [r["status"] for r in output["results"]] == ["trashed", "failed", "not_attempted"]
    assert calls == [ONE, TWO] and (fixture.state / "retained-recovery.json").exists()
    assert Path(selected[1]["path"]).exists() and Path(selected[2]["path"]).exists()
    with api.receipts.locked(fixture.state, fixture.root) as (root, path):
        with pytest.raises(api.store.CoverageError):
            api.receipts.claim(path, root, "trash", result["trashReceipt"], [TWO], None)


def test_installed_list_entrypoint_does_not_start_native(api, fixture, tmp_path):
    fixture.add()
    install_codex(target_root=tmp_path / "assets", state_root=tmp_path / "hook-state")
    helper = tmp_path / "assets/session_management.py"
    output = subprocess.check_output(
        [
            sys.executable,
            str(helper),
            "list",
            "--store-root",
            str(fixture.root),
            "--state-root",
            str(fixture.state),
            "--cwd",
            str(fixture.cwd),
        ],
        text=True,
    )
    assert json.loads(output)["sessions"][0]["id"] == ONE
    assert PRIVATE not in output


@pytest.mark.parametrize("failure", ["validation", "published"])
def test_failed_copy_does_not_delete_published_destination_or_retry(
    api, fixture, monkeypatch, failure
):
    source = fixture.add()
    fixture.add(TWO)
    original = Path(source["path"]).read_bytes()
    target = fixture.cwd.with_name("destination")
    target.mkdir()
    receipt = listing(api, fixture)

    class Client:
        def __init__(self, _binary, root, *_args, **_kwargs):
            self.root = Path(root)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def request(self, method, params):
            if method == "thread/fork":
                path = self.root / "sessions" / ("rollout-" + CHILD + ".jsonl")
                path.parent.mkdir(exist_ok=True)
                header = {
                    "ordinal": 0,
                    "type": "session_meta",
                    "payload": {
                        "id": CHILD,
                        "cwd": str(target),
                        "history_mode": "paginated",
                        "forked_from_id": ONE,
                        "history_base": {"thread_id": ONE},
                    },
                }
                path.write_text(json.dumps(header) + "\n")
                return {"thread": {"id": CHILD, "forkedFromId": ONE, "path": str(path)}}
            return {"thread": {"id": params["threadId"], "cwd": str(target)}}

    def signature(client, identity):
        if identity == CHILD and (
            failure == "validation"
            and client.root.name == "validation"
            or failure == "published"
            and client.root == fixture.root
        ):
            raise api.store.CoverageError("injected history verification failure")
        return {"sha256": "fixture-history", "turnCount": 0, "itemCount": 0}

    monkeypatch.setattr(api.copy, "NativeClient", Client)
    monkeypatch.setattr(api.copy, "native", lambda binary, root, *args: Client(binary, root))
    monkeypatch.setattr(api.copy, "signature", signature)
    monkeypatch.setattr(api.copy, "scan", lambda *_args: None)
    result = api.copy.copy_sessions(
        fixture.state,
        fixture.root,
        Path("/unused"),
        receipt["copyReceipt"],
        [ONE, TWO],
        target,
        None,
    )
    assert result["status"] == "incomplete"
    assert [row["status"] for row in result["results"]] == ["failed", "not_attempted"]
    assert result["results"][0]["automaticRetrySafe"] is False
    published = failure == "published"
    assert result["results"][0]["destinationMayContainCopy"] is published
    destination = fixture.root / "sessions" / ("rollout-" + CHILD + ".jsonl")
    assert destination.exists() is published
    if published:
        assert destination.stat().st_mode & 0o777 == 0o600
    assert Path(source["path"]).read_bytes() == original
    with api.receipts.locked(fixture.state, fixture.root) as (root, path):
        with pytest.raises(api.store.CoverageError):
            api.receipts.claim(path, root, "copy", receipt["copyReceipt"], [ONE], None)
