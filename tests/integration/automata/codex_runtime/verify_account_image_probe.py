"""Read-only validation of an explicitly selected CX009 synthetic fixture.

Does not invoke Codex, generate an image, inspect auth.json, or query an account.
A passing image check is not completion of the account-status half.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path


def verify(root: Path) -> dict:
    evidence = json.loads((root / "account-image-evidence.json").read_text())
    calls = evidence["httpCalls"]
    image_calls = [call for call in calls if call["path"].endswith("/images/generations")]
    assert len(image_calls) == 1
    assert image_calls[0]["body"]["model"] == "gpt-image-2"
    assert not any(call["path"].endswith("/images/edits") for call in calls)
    assert evidence["command"][:3] == ["/codex", "exec", "--json"]
    assert evidence["returncode"] == 0
    assert len(evidence["nativeArtifacts"]) == 1
    native = Path(evidence["nativeArtifacts"][0])
    relative = native.relative_to("/probe/codex/generated_images")
    assert len(relative.parts) == 2 and ".." not in relative.parts
    source = root / "codex/generated_images" / relative
    assert source.resolve().is_relative_to((root / "codex/generated_images").resolve())
    output = root / "project/output/imagegen/synthetic.png"
    assert output.resolve().is_relative_to((root / "project").resolve())
    data = source.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data == output.read_bytes()
    assert hashlib.sha256(data).hexdigest() == evidence["fixtureSha256"]
    # Native must have decoded and returned image content, not merely saved bad bytes.
    returned_images = [
        part
        for request in evidence["requests"]
        for item in request.get("input", [])
        if item.get("type") == "function_call_output"
        and item.get("call_id") == "cx009_fixture_image"
        for part in item["output"]
        if isinstance(part, dict) and part.get("type") == "input_image"
    ]
    assert returned_images
    assert base64.b64decode(returned_images[0]["image_url"].split(",", 1)[1]) == data
    text = json.dumps(evidence)
    assert "synthetic-access-sentinel" not in text
    assert "synthetic-refresh-sentinel" not in text
    controller = json.loads(evidence["controllerAccount"]["stdout"])
    assert controller["rateLimits"]["primary"]["usedPercent"] == 25
    assert controller["rateLimits"]["secondary"]["usedPercent"] == 60
    assert controller["rateLimits"]["primary"]["resetsAt"] == 1900000000
    assert "native-process-exited" in evidence["stdout"]  # Own-shell account gap, not success.
    assert "Read-only file system" in evidence["agentAccountDiagnostic"]
    return {
        "image": "ordinary native CLI invocation, decoded PNG and workspace copy verified",
        "account": "controller quota only; own-shell account RPC unavailable",
        "consent": "not a native one-per-turn authorization gate",
        "realProviderOrEntitlementTested": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    print(json.dumps(verify(parser.parse_args().state_root), indent=2))
