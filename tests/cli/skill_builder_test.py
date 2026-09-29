"""User-facing CLI boundaries without starting live previews."""

import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from automata.skills.content import SKILLS, body


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "automata.skills.cli", *map(str, args)],
        capture_output=True,
        text=True,
    )


def test_help():
    assert "export-agent" in cli("--help").stdout
    public = subprocess.run(
        [sys.executable, "-c", "from automata.cli import app; app()", "skill-builder", "--help"],
        capture_output=True, text=True,
    )
    assert public.returncode == 0, public.stdout + public.stderr
    assert "export-agent" in public.stdout and "serve" in public.stdout
    result = cli("serve", "--help")
    assert result.returncode == 0
    assert "--port" in result.stdout and "--all" not in result.stdout
    assert "FastAPI" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ("serve", "--all"),
        ("serve", "automata-message-router"),
        ("serve", "--port", "0"),
    ],
)
def test_errors_are_bounded(args):
    result = cli(*args)
    assert result.returncode != 0
    assert "Traceback" not in result.stdout + result.stderr


def test_serve_defaults(monkeypatch):
    from automata.skills import cli as commands
    from automata.skills import server

    calls = []
    monkeypatch.setattr(server, 'serve', lambda **kwargs: calls.append(kwargs))
    commands.serve()
    commands.serve(port=8799)
    assert calls == [{'port': 8788}, {'port': 8799}]


def test_export(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", "from automata.cli import app; app()", "skill-builder", "export-agent",
         "automata-message-router", "--output", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.name for p in tmp_path.iterdir()} == {"SKILL.md", "references"}
    assert (tmp_path / "SKILL.md").read_bytes() == (
        SKILLS / "automata-message-router/SKILL.md"
    ).read_bytes()
    assert all(p.suffix == ".md" for p in tmp_path.rglob("*") if p.is_file())


def test_cli_signal_stops_preview_without_build_output(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log_path = tmp_path / "preview.log"
    stream = None
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-c", "from automata.cli import app; app()", "skill-builder", "serve",
             "--port", str(port)], stdout=log, stderr=log,
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
                pytest.fail("FastAPI CLI did not become ready")
            assert "engrave.main" not in log_path.read_text()
            stream = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/__skill_builder/events", timeout=5
            )
            assert stream.readline().startswith(b": connected")
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                pytest.fail("CLI signal cleanup did not finish with an open SSE stream")
            finally:
                if stream is not None:
                    stream.close()
    assert process.returncode in (0, -15)
    with socket.socket() as sock:
        assert sock.connect_ex(("127.0.0.1", port)) != 0


def test_frontmatter_and_literal_code():
    code = "# Instructions\n\n```yaml\nname: literal\n---\n```\n"
    assert body("---\nname: example\n---\n" + code) == code
    with pytest.raises(ValueError):
        body("---\nname: unclosed")
