"""Verify generated, owned sequence_probe artifacts; print only bounded evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PREFIX = "[Codex token checkpoint; replay of latest snapshot, not current usage]\n"


def packets(request):
    found = []
    for item in request.get("input", []):
        if item.get("role") != "developer":
            continue
        for content in item.get("content", []):
            text = content.get("text", "")
            if PREFIX in text:
                packet, _ = json.JSONDecoder().raw_decode(text.split(PREFIX, 1)[1])
                found.append(packet)
    return found


def verify(root: Path) -> dict:
    requests = json.loads((root / "requests.json").read_text())
    controls = json.loads((root / "controls.json").read_text())
    assert len(requests) == 6  # five normal turns and one explicit compaction
    assert not packets(requests[0])
    second = packets(requests[1])
    assert any(p["counted"] == 110025 and p["throughResponse"] == "resp_1" for p in second)
    after_compact = packets(requests[3])
    assert any(
        p["counted"] == 220050
        and p["throughResponse"] == "resp_2"
        and p["excludedCompactionRecords"] == 1
        for p in after_compact
    )
    assert controls["inspect"]["counted"] == 330075
    assert controls["inspect"]["measuredResponses"] == 3
    assert controls["inspect"]["throughResponse"] == "resp_4"
    assert controls["set"]["threshold"] == 1000000
    assert controls["set"]["counted"] == controls["inspect"]["counted"]
    resumed = controls["resume"]
    assert resumed["counted"] == 440100
    assert resumed["measuredResponses"] == 4
    assert resumed["excludedCompactionRecords"] == 1
    checkpoint = controls["inspect"]["latestCheckpoint"]
    assert resumed["latestCheckpoint"] == checkpoint
    assert any(p["checkpointId"] == checkpoint["checkpointId"] for p in packets(requests[4]))
    fork = controls["fork"]
    assert fork["thread"] != resumed["thread"]
    assert fork["counted"] == 110025 and fork["measuredResponses"] == 1
    assert "inherited completeness unknown" in fork["baseline"]
    assert not fork["latestCheckpoint"]  # no invented inherited checkpoint
    for packet in second + after_compact:
        assert packet["cumulative"]["input"] == 108000 * packet["measuredResponses"]
        assert packet["cumulative"]["cacheRead"] == 10000 * packet["measuredResponses"]
        assert packet["cumulative"]["cacheWrite"] == 2000 * packet["measuredResponses"]
        assert "NOT active-branch" in packet["scope"]
        assert packet["throughRecordOrdinal"] != packet["throughResponse"]
    return {
        "nativeVersion": "0.159.0",
        "mockProviderRequests": 6,
        "nextPromptPacketDelivered": True,
        "compactionUsageExcluded": True,
        "installedInspectSet": True,
        "restartDedupAndCheckpointReplay": True,
        "forkLocalUsageWithUnknownInheritedBaseline": True,
        "noExtraModelTurnForCheckpoint": True,
        "limits": "Controlled offline responses, not live reporting or model judgment",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.state_root), indent=2))
