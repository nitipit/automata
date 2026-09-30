"""Verify installed native management and content-complete recoverability evidence."""

import configparser
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote


def history_digest(turns):
    return hashlib.sha256(
        json.dumps(turns, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def verify(root):
    evidence = json.loads((root / "management-evidence.json").read_text())
    before = evidence["before"][1]
    expected = history_digest(before["turns"])
    items = before["turns"][0]["items"]
    assert [item["type"] for item in items] == ["userMessage", "commandExecution", "agentMessage"]
    assert items[1]["exitCode"] == 0 and items[1]["aggregatedOutput"] == "owned tool payload\n"
    assert items[0]["content"] and items[2]["text"]
    assert evidence["initialRequests"] == evidence["finalRequests"] == 4
    assert len(evidence["unselectedBefore"]) == 2
    assert evidence["unselectedBefore"] == evidence["unselectedAfter"]
    assert evidence["fork"]["status"] == "forked"
    assert evidence["fork"]["results"][0]["independentCopy"] is False
    assert "unselected spawned/history dependents" in evidence["dependencyReject"]["error"]
    assert evidence["trash"]["status"] == "trashed"
    assert before["id"] not in [item["id"] for item in evidence["afterTrash"]["sessions"]]
    assert evidence["restore"]["status"] == "restored"
    restored = evidence["restored"]
    assert restored["id"] == before["id"] and restored["name"] == before["name"]
    assert restored["turns"] == before["turns"]  # complete payload equality, not ID-only
    assert evidence["copy"]["status"] == "copied"
    assert evidence["copy"]["results"][0]["independentCopy"]
    copied = evidence["copied"]
    assert copied["id"] != before["id"] and copied["forkedFromId"] == before["id"]
    assert copied["cwd"] == "/probe/destination" and copied["name"] == before["name"]
    assert copied["turns"] == before["turns"]
    assert evidence["independentResume"]["id"] == copied["id"]
    assert evidence["independentDigest"]["sha256"] == expected
    assert "history_base" not in evidence["materializedMeta"]
    only_child = list((root / "copy-validation/sessions").glob("**/*.jsonl"))
    assert len(only_child) == 1 and copied["id"] in only_child[0].name
    with sqlite3.connect(root / "copy-validation/state_5.sqlite") as db:
        assert db.execute("SELECT id FROM threads").fetchall() == [(copied["id"],)]
    recovery = evidence["trash"]["recoveryId"]
    journal = json.loads((root / f"management/recoveries/{recovery}.json").read_text())
    assert journal["entries"][0]["signature"]["sha256"] == expected
    package = root / Path(journal["packagePath"]).relative_to("/probe")
    info_path = root / Path(journal["trashInfoPath"]).relative_to("/probe")
    config = configparser.ConfigParser(interpolation=None)
    config.read(info_path)
    assert unquote(config["Trash Info"]["Path"]) == journal["stagingPath"]
    assert config["Trash Info"]["DeletionDate"]
    manifest = json.loads((package / "manifest.json").read_text())
    entry = manifest["entries"][0]
    assert entry["candidate"]["id"] == before["id"] and len(manifest["entries"]) == 1
    assert hashlib.sha256((package / entry["filename"]).read_bytes()).hexdigest() == entry["sha256"]
    with sqlite3.connect(root / "codex/state_5.sqlite") as db:
        rows = db.execute("SELECT id,rollout_path FROM threads").fetchall()
        assert len(rows) == 4
        for identity, path in rows:
            assert identity in Path(path).name
            assert (root / Path(path).relative_to("/probe")).is_file()
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    for row in evidence["listing"]["sessions"]:
        assert "path" not in row and "preview" not in row and "turns" not in row
    print(
        "native management verified: metadata receipts, linked fork, "
        "independent content-complete copy, "
        "selected recoverable trash/restore, dependency rejection; 4 creation-only mock requests"
    )


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
