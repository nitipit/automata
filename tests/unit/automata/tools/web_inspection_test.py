import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from automata.tools.web.cli import status
from automata.tools.web.status import engine_status


def test_absent_does_not_create_namespace(monkeypatch, capsys):
    # sockaddr_un has a 107-byte path limit; keep the test runtime root short.
    with TemporaryDirectory(dir="/tmp") as root:
        monkeypatch.setenv("XDG_RUNTIME_DIR", root)
        status(cwd=Path.cwd(), as_json=True)
        assert not list(Path(root).iterdir())
    result = json.loads(capsys.readouterr().out)
    assert result["managed_host"] == {"state": "not_running"}
    assert result["engine"] == {"state": "not_checked"}
    assert result["browser_control"] == "not_checked"


def test_refuses_public_or_missing_credentials(tmp_path):
    p = tmp_path / "kernel.json"
    for exists in (False, True):
        if exists:
            p.write_text("{}")
            p.chmod(0o644)
        assert asyncio.run(engine_status(p, tmp_path)) == {
            "state": "unknown",
            "reason": "invalid_connection_file",
        }


def test_timeout_disconnects_client(tmp_path, monkeypatch):
    p = tmp_path / "kernel.json"
    info = {
        f"{channel}_port": i
        for i, channel in enumerate(("shell", "control", "iopub", "stdin", "hb"), 10000)
    }
    p.write_text(
        json.dumps(
            dict(
                info, transport="tcp", ip="127.0.0.1", key="fixture", signature_scheme="hmac-sha256"
            )
        )
    )
    p.chmod(0o600)
    stopped = []

    class Client:
        def load_connection_info(self, info):
            pass

        def start_channels(self, **kwargs):
            pass

        async def execute(self, *args, **kwargs):
            await asyncio.sleep(30)

        def stop_channels(self):
            stopped.append(True)

    monkeypatch.setitem(sys.modules, "jupyter_client", SimpleNamespace(AsyncKernelClient=Client))
    assert asyncio.run(engine_status(p, tmp_path, timeout=0.01)) == {
        "state": "unknown",
        "reason": "timeout",
    }
    assert stopped == [True]
