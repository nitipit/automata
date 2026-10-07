"""Install both assets, relocate the optional example, verify its actual browser bridge."""

import json
import os
import select
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from automata.install.skills import install_skills
from automata.install.tools import install_tools

ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def run(args, *, cwd=None, env=ENV, timeout=120):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, result.stderr + result.stdout
    return result


def wait_started(process):
    deadline = time.monotonic() + 30
    text = ""
    while time.monotonic() < deadline:
        assert select.select([process.stdout], [], [], deadline - time.monotonic())[0], text
        piece = os.read(process.stdout.fileno(), 65536).decode()
        assert piece, text
        text += piece
        if "Application startup complete" in text:
            return
    pytest.fail(text)


def test_installed_skill_example_relocates_without_repo_imports_and_real_browser(tmp_path):
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome or not shutil.which("deno"):
        pytest.skip("Real browser example check requires installed Chrome/Chromium and Deno")
    tools = tmp_path / "install/.agents/tools"
    skills = tmp_path / "install/.agents/skills"
    install_tools(target_root=tools, tool_names=["python-runtime"])
    install_skills(
        target_root=skills, skill_names=["automata-python-workspace", "automata-adaptive-ui"]
    )
    installed = skills / "automata-python-workspace"
    entry = tools / "python-runtime/python_runtime.py"
    baseline = {
        path.relative_to(tmp_path / "install"): path.read_bytes()
        for path in (tmp_path / "install").rglob("*")
        if path.is_file()
    }
    work = tmp_path / "relocated/browser-counter"
    shutil.copytree(installed / "examples/browser-counter", work)
    run(["uv", "sync", "--offline", "--locked"], cwd=work)
    run(
        [
            "python",
            str(skills / "automata-adaptive-ui/scripts/build.py"),
            "--runtime-root",
            str(work / "browser"),
        ]
    )
    run(["deno", "install", "--cached-only", "--allow-scripts=npm:esbuild"], cwd=work)
    run(["deno", "task", "build"], cwd=work)
    run(["deno", "task", "check"], cwd=work)
    assert (work / "browser/lib/adaptive-ui.js").is_file()
    assert "./lib/adaptive-ui.js" in (work / "browser/live-counter.js").read_text()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="py-browser-") as directory:
        workspace = Path(directory)
        env = {
            **ENV,
            "AUTOMATA_PYTHON_RUNTIME_TOOL": str(entry.parent),
            "WORKSPACE_RUN_DIR": str(workspace),
            "WORKSPACE_PORT": str(port),
        }
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "--offline",
                "--locked",
                "python",
                "-m",
                "uvicorn",
                "server:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=work,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        kernel_pids = []
        completed = False
        try:
            wait_started(process)
            # Assert the imported runtime location, not just similar behavior.
            location = run(
                [
                    "uv",
                    "run",
                    "--offline",
                    "--locked",
                    "python",
                    "-c",
                    "import runtime_import; import automata_python_runtime; "
                    "print(automata_python_runtime.__file__)",
                ],
                cwd=work,
                env=env,
            )
            assert str(entry.parent) in location.stdout
            harness = Path(__file__).with_name("python_workspace_browser_harness.py")
            result = run(
                [
                    "uv",
                    "run",
                    "--offline",
                    "--script",
                    str(harness),
                    str(entry),
                    str(workspace),
                    str(port),
                    chrome,
                    str(tmp_path / "browser-mobile.png"),
                ]
            )
            evidence = json.loads(result.stdout)
            assert evidence["browser_bridge"] == "passed"
            kernel_pids = evidence["kernel_pids"]
            completed = True
        finally:
            if not completed and process.poll() is None:
                process.terminate()  # Only this test's isolated owned server.
            process.communicate(timeout=15)
            # Uvicorn may preserve SIGTERM as its exit status after graceful close.
            assert process.returncode in (0, 128 + signal.SIGTERM, -signal.SIGTERM)
            assert not (workspace / "agent.sock").exists()
            assert not (workspace / "server.pid").exists()
            for pid in kernel_pids:
                with pytest.raises(ProcessLookupError):
                    os.kill(pid, 0)
    final = {
        path.relative_to(tmp_path / "install"): path.read_bytes()
        for path in (tmp_path / "install").rglob("*")
        if path.is_file()
    }
    assert final == baseline, "Installed assets must remain read-only"
    assert not (installed / "examples/browser-counter/.run").exists()
    assert not (installed / "examples/browser-counter/.venv").exists()
