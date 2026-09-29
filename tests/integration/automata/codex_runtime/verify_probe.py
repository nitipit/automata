"""Validate and summarize only task-owned output of offline_probe.py.

Usage: python verify_probe.py STATE_ROOT
No access to the user's Codex state; no Codex process is launched here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def verify(root: Path) -> dict:
    data = json.loads((root / "results.json").read_text())
    for key, value in data.items():
        if isinstance(value, dict):
            assert "error" not in value, (key, value)
    skills = data["skills"]["result"]["data"][0]
    assert skills["errors"] == []
    candidates = data["candidate_installed_skills"]
    actual = [s["name"] for s in skills["skills"] if s["name"].startswith("automata-")]
    assert sorted(actual) == sorted(candidates)
    duplicates = [s for s in skills["skills"] if s["name"] == "audit-duplicate"]
    assert {s["scope"] for s in duplicates} == {"repo", "user"}
    assert len([s for s in skills["skills"] if s["name"] == "audit-repo"]) == 1
    plugin = data["plugin"]["result"]["plugin"]
    assert plugin["skills"][0]["name"] == "automata-audit:automata-plan"
    assert plugin["mcpServers"] == []
    assert plugin["summary"]["installed"] is False
    assert data["untrusted_hook_executed"] is False
    hooks = data["hooks"]["result"]["data"][0]["hooks"]
    assert hooks[0]["trustStatus"] == "untrusted"
    assert data["read"]["result"]["thread"]["turns"] == []
    assert data["resume"]["result"]["reasoningEffort"] == "not-a-supported-effort"
    parent = data["start"]["result"]["thread"]["id"]
    child = data["fork"]["result"]["thread"]["id"]
    assert parent != child
    assert data["fork"]["result"]["thread"]["forkedFromId"] == parent
    assert data["resume"]["result"]["thread"]["id"] == parent
    histories = {}
    for path in (root / "codex/sessions").rglob("*.jsonl"):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        metadata = next(row["payload"] for row in rows if row["type"] == "session_meta")
        assert metadata["dynamic_tools"][0]["name"] == "audit_echo"
        histories[metadata["id"]] = {
            "sentinel_count": sum(
                "AUDIT_MODEL_CONTEXT_SENTINEL" in json.dumps(row) for row in rows
            ),
            "token_usage_records": sum(row["type"] == "token_usage_record" for row in rows),
        }
    assert histories[parent]["sentinel_count"] == 1
    # History-only injection is NOT equivalent to an admitted/completed user turn.
    # Preserve this negative finding instead of claiming general fork continuity.
    assert histories[child]["sentinel_count"] == 0
    assert all(h["token_usage_records"] == 0 for h in histories.values())
    assert data["process_exit_code"] == 0
    assert not (root / "stderr.log").read_text()
    summary = {
        "runtime": data["initialize"]["result"]["userAgent"],
        "proof_kind": "installed native executable; isolated stdio; no model requests",
        "candidate_skills_discovered": len(actual),
        "duplicate_name_scopes": sorted(s["scope"] for s in duplicates),
        "symlink_alias_deduplicated": True,
        "portable_plugin_recognized": True,
        "plugin_skill_name": plugin["skills"][0]["name"],
        "packaged_shell_tool_registered_as_mcp": False,
        "dynamic_tool_metadata_persisted": True,
        "untrusted_hook_executed": False,
        "developer_injection_persisted": True,
        "developer_injection_visible_turns": 0,
        "history_only_fork_inherited_developer_sentinel": False,
        "invalid_effort_accepted_and_returned_on_resume": True,
        "effective_model_execution": "not tested",
        "compaction": "not invoked; model operation",
        "process_exit_code": 0,
    }
    (root / "verified-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1]).resolve(strict=True)), indent=2))
