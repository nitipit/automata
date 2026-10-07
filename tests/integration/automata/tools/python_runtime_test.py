"""Real installed-tool checks. Private temporary workspaces never target user preview."""

import concurrent.futures
import json
import os
import select
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from automata.install.tools import install_tools

ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def cli(entry, command, workspace, code=None, timeout=10, check=True):
    args = [
        "uv",
        "run",
        "--offline",
        "--script",
        str(entry),
        command,
        "--workspace",
        str(workspace),
    ]
    if code is not None:
        args.extend([code, "--timeout", str(timeout)])
    completed = subprocess.run(args, capture_output=True, text=True, env=ENV, timeout=60)
    if check:
        assert completed.returncode == 0, completed.stderr + completed.stdout
    return completed, json.loads(completed.stdout)


def ready(process):
    deadline = time.monotonic() + 25
    lines = []
    while time.monotonic() < deadline:
        assert select.select([process.stdout], [], [], deadline - time.monotonic())[0], lines
        line = process.stdout.readline()
        lines.append(line)
        assert line, "".join(lines)
        if line.startswith('{"ok":'):
            response = json.loads(line)
            assert response["ok"], response
            return response["result"]
    pytest.fail("Serve did not become ready")


@pytest.fixture
def installed(tmp_path):
    target = tmp_path / ".agents/tools"
    install_tools(target_root=target, tool_names=["python-runtime"])
    entry = target / "python-runtime/python_runtime.py"
    assert entry.is_file()
    yield entry
    assert not list(entry.parent.rglob("__pycache__"))
    assert not (entry.parent / ".run").exists()
    assert not (entry.parent / ".venv").exists()


@pytest.fixture
def daemon(installed, tmp_path):
    with tempfile.TemporaryDirectory(prefix="py-runtime-") as directory:
        workspace = Path(directory)
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "--offline",
                "--script",
                str(installed),
                "serve",
                "--workspace",
                str(workspace),
                "--cwd",
                str(tmp_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=ENV,
        )
        info = None
        try:
            info = ready(process)
            assert info["publication"] is None and info["generation"] == 1
            assert workspace.stat().st_mode & 0o777 == 0o700
            assert (workspace / "agent.sock").stat().st_mode & 0o777 == 0o600
            yield installed, workspace, info
        finally:
            if process.poll() is None and (workspace / "agent.sock").exists():
                cli(installed, "stop", workspace, check=False)
            process.communicate(timeout=15)
            assert process.returncode == 0
            assert not (workspace / "agent.sock").exists()
            assert not (workspace / "server.pid").exists()
            if info:
                with pytest.raises(ProcessLookupError):
                    os.kill(info["kernel_pid"], 0)


def test_generic_blank_kernel_independent_objects_partial_errors_and_correlation(daemon):
    entry, workspace, info = daemon
    _, first = cli(
        entry,
        "execute",
        workspace,
        "assert 'counter' not in globals(); bag = []; saved = bag; print(id(bag))",
    )
    _, second = cli(
        entry, "execute", workspace, "assert saved is bag; bag.append(2); print(id(bag))"
    )
    a, b = first["result"], second["result"]
    assert a["output"].strip() == b["output"].strip()
    assert a["request_id"] != b["request_id"]
    assert a["reply_received"] and a["idle_received"]
    assert b["runtime_id"] == info["runtime_id"]
    failed, error = cli(
        entry,
        "execute",
        workspace,
        "bag.append(3); raise ValueError('after mutation')",
        check=False,
    )
    assert failed.returncode == 1 and error["result"]["status"] == "error"
    cli(entry, "execute", workspace, "assert bag == [2, 3]")
    _, status = cli(entry, "status", workspace)
    assert status["result"]["publication"] is None


def test_bounded_output_stdin_timeout_interrupt_and_explicit_publication(daemon):
    entry, workspace, _ = daemon
    _, output = cli(entry, "execute", workspace, "print('x' * 20000)")
    assert len(output["result"]["output"]) == 8192 and output["result"]["truncated"]
    failed, stdin = cli(entry, "execute", workspace, "input('no')", check=False)
    assert failed.returncode == 1 and "StdinNotImplementedError" in stdin["result"]["error"]
    failed, timed = cli(
        entry, "execute", workspace, "value = 7\nwhile True: pass", timeout=0.3, check=False
    )
    assert failed.returncode == 1 and timed["result"]["status"] == "timeout"
    assert timed["result"]["reply_received"] and timed["result"]["idle_received"]
    cli(entry, "execute", workspace, "assert value == 7")
    with concurrent.futures.ThreadPoolExecutor() as pool:
        busy = pool.submit(
            cli, entry, "execute", workspace, "value = 8\nwhile True: pass", 20, False
        )
        # Status is out-of-band. Bounded checks establish actual submitted busy work.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            _, state = cli(entry, "status", workspace)
            if state["result"]["busy"]:
                break
        else:
            pytest.fail("Python never became busy")
        time.sleep(0.3)
        cli(entry, "interrupt", workspace)
        _, interrupted = busy.result(timeout=10)
        assert "KeyboardInterrupt" in interrupted["result"]["error"]
    cli(entry, "execute", workspace, "assert value == 8")
    code = (
        "from IPython.display import display; "
        "display({'application/vnd.automata.workspace+json': {'rows': [1, 2]}}, raw=True)"
    )
    _, published = cli(entry, "execute", workspace, code)
    assert published["result"]["publication"] == {"rows": [1, 2]}
    _, rejected = cli(
        entry, "execute", workspace, code.replace("{'rows': [1, 2]}", "{'text': 'x' * 20000}")
    )
    assert rejected["result"]["publication"] is None


def test_restart_new_generation_no_replay_external_effect_survives(daemon):
    entry, workspace, initial = daemon
    marker = workspace / "side-effect"
    cli(
        entry, "execute", workspace, f"remembered = 123; open({str(marker)!r}, 'w').write('effect')"
    )
    _, reset = cli(entry, "restart", workspace)
    state = reset["result"]
    assert state["runtime_id"] == initial["runtime_id"]
    assert state["generation"] == initial["generation"] + 1
    assert state["kernel_pid"] != initial["kernel_pid"]
    assert marker.read_text() == "effect"
    assert any(e["kind"] == "state_lost" for e in state["events"])
    cli(
        entry,
        "execute",
        workspace,
        "assert 'remembered' not in globals(); assert 'counter' not in globals()",
    )
    # The daemon fixture verifies original PID; also verify the replacement is owned/closed.
    replacement_pid = state["kernel_pid"]
    cli(entry, "stop", workspace)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(replacement_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("Replacement kernel did not shut down")


def test_queue_wait_rejection_does_not_submit_and_duplicate_owner_preserves_workspace(daemon):
    entry, workspace, info = daemon
    duplicate = subprocess.run(
        ["uv", "run", "--offline", "--script", str(entry), "serve", "--workspace", str(workspace)],
        capture_output=True,
        text=True,
        env=ENV,
        timeout=20,
    )
    assert duplicate.returncode == 2 and "already owned" in duplicate.stdout
    _, state = cli(entry, "status", workspace)
    assert state["result"]["runtime_id"] == info["runtime_id"]
    with concurrent.futures.ThreadPoolExecutor() as pool:
        busy = pool.submit(cli, entry, "execute", workspace, "import time; time.sleep(7)", 15)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            _, state = cli(entry, "status", workspace)
            if state["result"]["busy"]:
                break
        failed, rejection = cli(entry, "execute", workspace, "should_not_exist = True", check=False)
        assert failed.returncode == 1 and "code not submitted" in rejection["error"]
        busy.result(timeout=15)
    cli(entry, "execute", workspace, "assert 'should_not_exist' not in globals()")


def test_cli_help_validation_and_missing_owner(installed, tmp_path):
    for command in ([], ["serve"], ["execute"], ["status"], ["stop"]):
        result = subprocess.run(
            ["uv", "run", "--offline", "--script", str(installed), *command, "--help"],
            capture_output=True,
            text=True,
            env=ENV,
            timeout=20,
        )
        assert result.returncode == 0 and "workspace" in result.stdout
    failed, invalid = cli(installed, "execute", tmp_path, "1", timeout=31, check=False)
    assert failed.returncode == 2 and not invalid["ok"]
    failed, absent = cli(installed, "status", tmp_path, check=False)
    assert failed.returncode == 2 and "FileNotFoundError" in absent["error"]


@pytest.mark.parametrize("stage", ["kernel_ready", "socket_bind", "pid_write", "bootstrap"])
def test_real_kernel_cleanup_after_startup_failure(installed, stage):
    harness = Path(__file__).with_name("python_runtime_startup_harness.py")
    completed = subprocess.run(
        ["uv", "run", "--offline", "--script", str(harness), str(installed.parent), stage],
        capture_output=True,
        text=True,
        env=ENV,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["cleaned"]
