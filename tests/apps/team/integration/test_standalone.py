"""Installed outside-repo entry and both directions of ShelfDB interoperability."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from automata.install.tools import install_tools
from tests.apps.team.conftest import report_documents


@pytest.fixture
def installed_tool(tmp_path):
    target = tmp_path / "installed/tools"
    install_tools(target_root=target, tool_names=["team"])
    outside = tmp_path / "outside"
    outside.mkdir()
    entry = target / "team/team.py"
    env = dict(os.environ, UV_OFFLINE="true", UV_PYTHON_DOWNLOADS="never")
    for name in ("UV_PYTHON", "PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(name, None)
    return entry, outside, env


@pytest.fixture
def standalone_state_root(tmp_path):
    root = tmp_path / "state"
    # Match existing Team fixtures without weakening the Unix socket limit.
    short_parent = os.environ.get("AUTOMATA_TEAM_TEST_STATE_ROOT")
    if short_parent and len(os.fsencode(root.resolve() / "db.sock")) > 103:
        with tempfile.TemporaryDirectory(prefix="", dir=short_parent) as directory:
            yield Path(directory)
    else:
        yield root


@pytest.mark.parametrize("standalone_server", [False, True])
@pytest.mark.parametrize("callable_transport", [False, True], ids=["records", "callables"])
def test_installed_and_cli_interoperate_both_directions(
    installed_tool, tmp_path, standalone_state_root, standalone_server, callable_transport
):
    entry, outside, env = installed_tool
    # Serialized Python code is not cross-version portable. Keep the callable
    # namespace test on one interpreter; records still exercise uv's default.
    if callable_transport:
        env = env | {"UV_PYTHON": sys.executable}
    root = standalone_state_root
    cli_env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[4] / "src"))
    cli = [str(Path(sys.executable).with_name("automata")), "team"]
    tool = ["uv", "run", str(entry)]
    server_command = tool if standalone_server else cli
    client_command = cli if standalone_server else tool
    server_env = env if standalone_server else cli_env
    client_env = cli_env if standalone_server else env
    log = (tmp_path / "interop-server.log").open("w+")
    process = subprocess.Popen(
        server_command + ["serve", "--state-root", str(root)],
        cwd=outside,
        env=server_env,
        stdout=log,
        stderr=log,
    )
    try:
        import time

        deadline = time.monotonic() + 15
        while not (root / "db.sock").exists():
            if process.poll() is not None or time.monotonic() >= deadline:
                log.seek(0)
                pytest.fail(log.read())
            time.sleep(0.02)

        def call(command, *args, document=None, environment=client_env):
            if document is not None:
                args += ("--file", "-")
            result = subprocess.run(
                command + list(args) + ["--state-root", str(root)],
                input=json.dumps(document) if document else None,
                cwd=outside,
                env=environment,
                text=True,
                capture_output=True,
                timeout=15,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            return result

        call(
            client_command, "init", "--goal", "g", "--actor", "manager", document=report_documents()
        )
        call(
            client_command,
            "update",
            "--goal",
            "g",
            "--actor",
            "bob",
            "--kind",
            "agent",
            "--id",
            "bob",
            document={"report": {"summary": "Cross-entry publication"}},
        )
        # Also use the server's entry as client against the same database.
        data = json.loads(
            call(server_command, "json", "--goal", "g", environment=server_env).stdout
        )
        assert data["agents"]["bob"]["report"]["summary"] == "Cross-entry publication"
        assert data["tasks"] == {}
        # Exercise actual callable transport, not only JSON records. Dill must
        # resolve a canonical Team function on the other entry's server.
        script = """
import asyncio, runpy, sys
if sys.argv[1] != "cli":
    entry = sys.argv[1]
    saved = sys.argv[:]
    sys.argv = [entry, "--help"]
    try:
        runpy.run_path(entry, run_name="__main__")
    except SystemExit as error:
        assert error.code == 0
    sys.argv = saved
from automata.tools.team.view import context_cell
from shelfdb.client import Client
async def check():
    client = await Client.connect(sys.argv[2])
    try:
        async with client.transaction() as tx:
            rows = await tx.shelf("agents").items().sort(
                key=lambda item, project=context_cell: project(item.value)
            ).query()
            assert len(rows) == 3
    finally:
        await client.close()
asyncio.run(check())
"""
        if callable_transport:
            callable_result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    script,
                    "cli" if standalone_server else str(entry),
                    "unix://" + str(root / "db.sock"),
                ],
                cwd=outside,
                env=client_env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert callable_result.returncode == 0, callable_result.stderr
        assert not (entry.parent / "__pycache__").exists()
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        log.close()
    assert process.returncode == 0
    assert not (root / "db.sock").exists()


def test_installed_help_ignores_ambient_automata(installed_tool):
    entry, outside, env = installed_tool
    (outside / "automata.py").write_text("raise RuntimeError('ambient Automata imported')\n")
    result = subprocess.run(
        ["uv", "run", str(entry), "--help"],
        cwd=outside,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "Automata Team" in result.stdout


def test_installed_board_in_real_terminal(installed_tool, report_service, tmp_path):
    from tests.apps.team.integration.test_lifecycle import (
        test_public_board_in_real_83_column_pty_q_leaves_service_running as check_board,
    )

    entry, outside, env = installed_tool
    service = report_service
    service.env = env
    service.argv = lambda *args: ["uv", "run", str(entry), *args, "--state-root", str(service.root)]
    check_board(service, outside)
