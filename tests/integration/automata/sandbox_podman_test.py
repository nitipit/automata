"""Opt-in actual rootless Podman checks. No models, credentials or provider requests."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

HELPER = Path(__file__).parents[3] / "exams/automata-harness/sandbox/candidate.py"
pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOMATA_EXAM_LIVE_PODMAN") != "1",
    reason="explicit scoped Podman smoke authorization required",
)


def wait_file(path, process=None, seconds=15):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if path.exists():
            return json.loads(path.read_text())
        if process and process.poll() is not None:
            raise AssertionError(f"launcher exited early: {process.returncode}")
        time.sleep(0.05)
    raise AssertionError(f"owned receipt did not arrive: {path}")


@pytest.fixture
def launch(tmp_path):
    image = os.environ["AUTOMATA_EXAM_TEST_IMAGE"]
    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "paper.md").write_text("No-model lifecycle fixture. Do not call a provider.\n")
    canary = tmp_path / "outside-only.txt"
    canary.write_text("benign outside-only fixture")
    root = tmp_path / "owned-run"
    args = [
        sys.executable,
        str(HELPER),
        "--materials",
        str(materials),
        "--output",
        str(root),
        "--image",
        image,
        "--seconds",
        "12",
        "--outside-canary",
        str(canary),
        "--exam-fingerprint",
        "0" * 64,
    ]
    return root, args


def assert_absent_and_guard_exited(root):
    cid = json.loads((root / "cid.json").read_text())["cid"]
    result = subprocess.run(["podman", "container", "exists", cid], capture_output=True)
    assert result.returncode == 1, (cid, result.returncode)
    assert json.loads((root / "cleanup.json").read_text())["status"] == "confirmed-absent"
    done = wait_file(root / "guard-done.json")
    process = Path(f"/proc/{done['pid']}")
    until = time.monotonic() + 3
    while process.exists() and time.monotonic() < until:
        try:
            if process.joinpath("stat").read_bytes().split(b") ", 1)[1].startswith(b"Z"):
                return
            if str(root).encode() not in process.joinpath("cmdline").read_bytes():
                return  # Original guard exited; do not act on a reused PID.
        except FileNotFoundError:
            return
        time.sleep(0.05)
    assert not process.exists(), "owned guard is still running"


@pytest.mark.parametrize(
    "mode, code, status",
    [
        ("normal", 0, "dummy-complete"),
        ("failure", 7, "dummy-command-failed"),
        ("timeout", 124, "dummy-native-timeout"),
    ],
)
def test_actual_completion_failure_and_native_timeout(launch, mode, code, status):
    root, args = launch
    result = subprocess.run([*args, "--dummy", mode], capture_output=True, timeout=25)
    assert result.returncode == code, result.stdout.decode()
    assert json.loads((root / "result.json").read_text())["status"] == status
    assert_absent_and_guard_exited(root)


def test_actual_signal_cancellation(launch):
    root, args = launch
    process = subprocess.Popen(
        [*args, "--dummy", "timeout"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    wait_file(root / "client.json", process)
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=10) == 130
    assert json.loads((root / "result.json").read_text())["status"] == "cancelled"
    assert_absent_and_guard_exited(root)


@pytest.mark.parametrize("stage", ["running", "before-start", "before-publish"])
def test_actual_forced_loss_and_created_window(launch, stage):
    root, args = launch
    if stage != "running":
        wrapper = """
import os,signal,sys,types
m=types.ModuleType('owned_fault_fixture'); m.__file__=sys.argv[1]
exec(compile(open(sys.argv[1]).read(),sys.argv[1],'exec'),m.__dict__)
old=m.command
def command(a,**k):
    if a[:2]==['podman','start']: os.kill(os.getpid(),signal.SIGKILL)
    return old(a,**k)
m.command=command; sys.argv=sys.argv[1:]; m.main()
"""
        if stage == "before-publish":
            wrapper = wrapper.replace(
                "m.command=command;",
                "m.publish_cid=lambda *a: os.kill(os.getpid(),signal.SIGKILL);",
            )
        invocation = [sys.executable, "-c", wrapper, *args[1:], "--dummy", "timeout"]
    else:
        invocation = [*args, "--dummy", "timeout"]
    process = subprocess.Popen(
        invocation, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
    )
    wait_file(root / "cid.json", seconds=16)
    if stage == "running":
        client = wait_file(root / "client.json", process)
        cid = json.loads((root / "cid.json").read_text())["cid"]
        argv = Path(f"/proc/{client['pid']}/cmdline").read_bytes().split(b"\0")
        assert Path(os.fsdecode(argv[0])).name == "podman"
        assert argv[1:3] == [b"exec", cid.encode()]
        os.kill(client["pid"], signal.SIGKILL)
        process.kill()
    assert process.wait(timeout=10) == -signal.SIGKILL
    assert wait_file(root / "backstop.json", seconds=20)["status"] == "confirmed-absent"
    assert_absent_and_guard_exited(root)


def test_actual_provider_network_has_no_host_loopback_mapping(launch):
    root, args = launch
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
        process = subprocess.Popen(
            [*args, "--network", "pasta", "--dummy", "timeout"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            wait_file(root / "client.json", process)
            cid = json.loads((root / "cid.json").read_text())["cid"]
            code = """
import json,pathlib,socket,sys
result={}
for host in ['127.0.0.1','169.254.1.2']:
    with socket.socket() as s:
        s.settimeout(1); result[host]=s.connect_ex((host,int(sys.argv[1])))!=0
hosts=pathlib.Path('/etc/hosts')
result['no_host_alias']=not hosts.exists() or 'host.containers.internal' not in hosts.read_text()
print(json.dumps(result))
"""
            probe = subprocess.run(
                ["podman", "exec", cid, "python3", "-c", code, str(port)],
                capture_output=True,
                timeout=5,
            )
            assert probe.returncode == 0
            evidence = json.loads(probe.stdout)
            assert all(evidence.values()), evidence
            (root / "network-probe.json").write_text(json.dumps(evidence, indent=2) + "\n")
            write = "from pathlib import Path; p=Path('/workspace/out'); p.mkdir(); "
            write += "(p/'answers.md').write_text('synthetic-secret'); "
            write += "(p/'unselected.txt').write_text('must not be retained')"
            subprocess.run(["podman", "exec", cid, "python3", "-c", write], check=True)
            module = types.ModuleType("live_capture_fixture")
            exec(compile(HELPER.read_text(), str(HELPER), "exec"), module.__dict__)
            module.capture_workspace(cid, root, ["synthetic-secret"], "knowledge")
            assert (root / "artifacts/out/answers.md").read_text() == "[REDACTED]"
            assert not (root / "artifacts/out/unselected.txt").exists()
        finally:
            process.wait(timeout=20)
    assert_absent_and_guard_exited(root)
