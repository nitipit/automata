"""Verify CX-005 packets in the existing isolated native six-request fixture."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from verify_sequence_probe import verify as verify_tokens

PREFIX = "[Codex context/timestamp snapshot; sequence-linked, may be replayed]\n"


def packets(request):
    result = []
    for item in request.get("input", []):
        if item.get("role") != "developer":
            continue
        for content in item.get("content", []):
            text = content.get("text", "")
            if PREFIX in text:
                packet, _ = json.JSONDecoder().raw_decode(text.split(PREFIX, 1)[1])
                result.append(packet)
    return result


def verify(root):
    summary = verify_tokens(root)
    requests = json.loads((root / "requests.json").read_text())
    controls = json.loads((root / "controls.json").read_text())
    protocol = json.loads((root / "protocol.json").read_text())
    first, second, _, compacted, resumed, forked = [packets(request)[-1] for request in requests]
    assert first["context"] is None and first["pressureBand"] == "unknown"
    assert first["nativeTask"]["modelWindow"] == 258400
    assert first["inputAnchor"]["kind"] == "first-hook-observation-of-turn-input"
    assert second["context"]["tokens"] == 120025
    assert second["context"]["window"] == 258400
    assert second["context"]["percent"] == round(120025 * 100 / 258400, 3)
    assert len(second["recentMessages"]) == 2
    assert compacted["context"]["source"] == "recomputed-context-estimate"
    assert 0 < compacted["context"]["tokens"] < 120025
    assert len(resumed["recentMessages"]) == 6
    assert forked["context"] is None and forked["contextAvailability"] == "unknown"
    assert forked["recentMessages"] == []
    completed = {}
    for event in protocol:
        if event.get("method") == "item/completed":
            value = event["params"]
            completed[(value["turnId"], value["item"]["id"])] = value.get("completedAtMs")
    seen = {}
    for request in requests:
        for packet in packets(request):
            assert len(packet["recentMessages"]) <= 6
            assert datetime.fromisoformat(packet["observedAt"]).utcoffset() is not None
            assert "not active work" in packet["coverage"]
            assert "not live request size" in packet["coverage"]
            for message in packet["recentMessages"]:
                key = (message["turn"], message["item"])
                native_time = datetime.fromtimestamp(completed[key] / 1000, UTC).isoformat()
                assert message["completedAt"] == native_time
                assert datetime.fromisoformat(message["recordedAt"]).utcoffset() is not None
                if key in seen:
                    assert seen[key] == message
                seen[key] = message
    status = controls["contextBeforeRestart"]
    assert status["context"]["tokens"] == 120025  # not normalized counted110025
    assert status["anchorUsage"]["counted"] == 110025
    assert status["anchorUsage"]["measuredResponses"] == 1
    assert status["elapsedWallSecondsAtInspect"] >= 0
    assert controls["contextResume"]["context"]["tokens"] == 120025
    assert controls["contextFork"]["context"]["tokens"] == 120025
    return {
        **summary,
        "nativeContextPacket": True,
        "recomputedContextAfterCompaction": True,
        "stableNativeMessageTimestamps": True,
        "boundedRecentTimestampReplay": True,
        "installedContextInspect": True,
        "wallClockNotActiveWork": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.state_root), indent=2))
