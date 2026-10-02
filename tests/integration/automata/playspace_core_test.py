"""Focused offline build and Playspace-core ownership boundary checks."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILLS = Path(__file__).parents[3] / "src/automata/skills/bundled"
PLAYSPACE = SKILLS / "automata-playspace"


@pytest.mark.skipif(
    shutil.which("deno") is None or shutil.which("node") is None,
    reason="existing cached Deno and Node required",
)
def test_playspace_core_cached_build_and_contracts(tmp_path: Path) -> None:
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
    assert (public / "lib/adaptive-ui.js").is_file()
    assert (public / "router/client.js").is_file()
    assert (public / "router/session.js").is_file()
    assert (public / "component.js").is_file()
    assert (public / "page.js").is_file()
    assert not (public / "catalog.json").exists()
    assert not (public / "lib/chat.js").exists()
    assert not (public / "sample.js").exists()
    assert "<ps-chat" not in (public / "index.html").read_text()


def test_core_and_starter_do_not_depend_on_chat_or_duplicate_router() -> None:
    # Independent Adaptive UI may still export its own Chat; that API is outside
    # this package's scope. Assert actual consumers, not foundation-bundle absence.
    sources = [*PLAYSPACE.glob("lib/*.ts"), *PLAYSPACE.glob("starter/*.js")]
    for path in sources:
        text = path.read_text()
        assert "ps-chat" not in text, path
        assert "bindChatTransport" not in text, path
        assert "createMessageRouterChatClient" not in text, path
        assert 'from "./chat.js"' not in text, path
        assert "new WebSocket" not in text, path
    assert not (PLAYSPACE / "lib/form-history.ts").exists()
    assert not (PLAYSPACE / "lib/chat.ts").exists()
    entry = (PLAYSPACE / "starter/index.js").read_text()
    assert 'from "./router/client.js"' in entry
    assert 'from "./router/session.js"' in entry
    assert "__playspace_core_snapshot_v1__" in entry
    page = (PLAYSPACE / "starter/page.js").read_text()
    assert "record.source !== starterDefinition.source" in page
    assert "record.css !== starterDefinition.css" in page
