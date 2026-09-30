"""Verify real installed hook output, native skill metadata, and isolated controls."""

import json
import sys
from pathlib import Path


def verify(root):
    checks = json.loads((root / "activity-controls.json").read_text())
    assert checks["discovery"]["retainedCount"] == 0
    inserted = checks["inserted"]["records"]
    assert len(inserted) == 1
    for key in ("repeatInspect", "resumed", "missing"):
        assert checks[key]["records"] == inserted, key
    assert checks["secondInsertion"]["retainedCount"] == 2
    assert not checks["disabled"]["enabled"]
    assert checks["enabled"]["enabled"]
    assert checks["enabled"]["disabledSkipped"] == 1
    assert checks["final"]["records"] == checks["secondInsertion"]["records"]
    assert checks["final"]["retainedCount"] == 2
    assert checks["final"]["capacitySkipped"] == 0
    assert checks["saved"]["records"] == checks["final"]["records"]
    assert checks["saved"]["readOnly"] and checks["saved"]["available"]
    assert checks["saved"]["currentCoverage"] == "unknown; transcript not consulted"
    assert all(r["runtime"] == "codex" for r in checks["final"]["records"])
    assert all(r["evidenceKind"] == "native_instruction_insertion" for r in inserted)
    assert inserted[0]["ordinal"] > checks["inserted"]["enrollmentOrdinal"]
    thread = json.loads((root / "thread.json").read_text())
    transcript = root / Path(thread["path"]).relative_to("/probe")
    rows = [json.loads(line) for line in transcript.read_text().splitlines()]
    native = [
        r
        for r in rows
        if "skills.selected_skill_instructions"
        in (r["payload"].get("internal_chat_message_metadata_passthrough") or {}).get(
            "content_item_kinds", []
        )
    ]
    assert len(native) == 3  # two recorded, one while explicitly disabled
    for record in checks["final"]["records"]:
        item = next(r for r in native if r["payload"]["id"] == record["message"])
        assert item["timestamp"] == record["timestamp"]
        assert item["ordinal"] == record["ordinal"]
        assert (
            item["payload"]["internal_chat_message_metadata_passthrough"]["turn_id"]
            == record["turn"]
        )
    requests = json.loads((root / "requests.json").read_text())
    assert len(requests) == 7  # no request solely for recording/delivery
    texts = [json.dumps(r) for r in requests]
    assert "Retained native insertion observations: 0" in texts[0]
    assert "Retained native insertion observations: 1" in texts[2]
    assert "skill_activity.py" in texts[0]
    assert "saved --state-root" in texts[0] and "--thread" in texts[0]
    assert "native_instruction_insertion" not in texts[0]  # body-free bounded hook summary
    states = list((root / "token-state/skill-activity").glob("*.json"))
    assert len(states) == 1
    state = json.loads(states[0].read_text())
    assert len(state["records"]) == 2
    assert "Fixture instructions." not in states[0].read_text()
    assert not (root / "home/.agents/var/tools/skill-activity").exists()
    print(
        "native activity proof: 7 mock requests; insertion, missing selection, "
        "resume, dedup, controls verified"
    )


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
