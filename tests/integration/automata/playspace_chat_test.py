"""Focused offline build/contract check for Playspace-owned reusable components."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILLS = Path(__file__).parents[3] / "src/automata/skills/bundled"
PLAYSPACE = SKILLS / "automata-playspace"
UI = SKILLS / "automata-adaptive-ui"


@pytest.mark.skipif(
    shutil.which("deno") is None or shutil.which("node") is None,
    reason="existing cached Deno and Node required",
)
def test_playspace_ts_build_and_component_contracts(tmp_path: Path) -> None:
    public = tmp_path / "public"
    result = subprocess.run(
        [sys.executable, str(PLAYSPACE / "scripts/build.py"),
         "--runtime-root", str(public), "--validate"],
        capture_output=True, text=True, timeout=90, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(public.rglob("*.ts"))
    assert not list(public.rglob("node_modules"))
    assert (public / "lib/playspace.js").is_file()
    assert (public / "lib/form.schema.js").is_file()
    shared = (public / "lib/adaptive-ui.js").read_text()
    assert "var Chat = class" not in shared
    assert "agent-message" not in shared
    chat = (public / "lib/chat.js").read_text()
    assert 'from "./adaptive-ui.js"' in chat
    assert "WebSocket" not in chat
    assert "class Chat extends Base" in chat
    assert "agent-message" in chat
    assert "<ps-chat" in (public / "index.html").read_text()


def test_chat_ownership_and_thin_public_page() -> None:
    components = UI / "lib/src/ui/_components"
    assert not list(components.glob("chat*.ts"))
    assert not (UI / "lib/example/chat-with-agent.html").exists()
    assert not (UI / "lib/chat.md").exists()
    public_entry = (UI / "lib/src/ui/adaptive-ui.ts").read_text()
    assert "Chat" not in public_entry
    shared_viewer = SKILLS.parent / "templates/lib/adaptive-ui.js"
    assert "var Chat = class" not in shared_viewer.read_text()
    assert "Model" in public_entry and "defineField" in public_entry
    for name in ("chat.ts", "content.ts", "form.ts", "form.schema.ts", "contracts.ts", "types.ts"):
        assert (PLAYSPACE / "lib" / name).is_file()
    page = (PLAYSPACE / "starter/index.js").read_text()
    assert 'from "./lib/playspace.js"' in page
    assert "registerPlayspace()" in page
    assert "defineField" not in page
    assert "createFormRegistry" not in page
    assert "__playspace_chat_snapshot_v2__" in page
    assert "__playspace_chat_snapshot_v1__" not in page
