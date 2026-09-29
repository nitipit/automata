"""User-facing CLI boundaries without starting live previews."""

import shlex
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from automata.apps.skill_builder.content import SKILLS, body


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "automata.apps.skill_builder.cli", *map(str, args)],
        capture_output=True,
        text=True,
    )


def test_help():
    assert "export-agent" in cli("--help").stdout
    result = cli("serve", "--help")
    assert result.returncode == 0
    assert "--all" in result.stdout and "--port" in result.stdout
    assert "restart" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ("serve",),
        ("serve", "message-router", "--all"),
        ("serve", "../private"),
        ("serve", "missing"),
        ("serve", "message-router", "--port", "0"),
    ],
)
def test_errors_are_bounded(args):
    result = cli(*args)
    assert result.returncode != 0
    assert "Traceback" not in result.stdout + result.stderr


def test_export(tmp_path):
    result = cli("export-agent", "message-router", "--output", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.name for p in tmp_path.iterdir()} == {"SKILL.md", "references"}
    assert (tmp_path / "SKILL.md").read_bytes() == (SKILLS / "message-router/SKILL.md").read_bytes()
    assert all(p.suffix == ".md" for p in tmp_path.rglob("*") if p.is_file())


def test_native_cli_signal_stops_child_and_removes_output(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log_path = tmp_path / "preview.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "automata.apps.skill_builder.cli", "serve",
             "message-router", "--port", str(port)], stdout=log, stderr=log,
        )
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/message-router/", timeout=.5
                    ).close()
                    break
                except OSError:
                    assert process.poll() is None, log_path.read_text()
                    time.sleep(.1)
            else:
                pytest.fail("Native CLI did not become ready")
            command = shlex.split(log_path.read_text().splitlines()[0])
            assert command[1:4] == ["-m", "engrave.main", "server"]
            output = Path(command[5])
            assert (output / "skills/message-router/SKILL.md").is_file()
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                pytest.fail("CLI signal cleanup did not finish")
    assert process.returncode == 0
    assert not output.exists()
    with socket.socket() as sock:
        assert sock.connect_ex(("127.0.0.1", port)) != 0


def test_frontmatter_and_literal_code():
    code = "# Instructions\n\n```yaml\nname: literal\n---\n```\n"
    assert body("---\nname: example\n---\n" + code) == code
    with pytest.raises(ValueError):
        body("---\nname: unclosed")
