"""User-facing CLI boundaries without starting live previews."""

import socket
import subprocess
import sys
import time
import urllib.request

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
    assert "FastAPI" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
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


@pytest.mark.parametrize(
    ('skill', 'all_', 'expected'),
    [(None, False, (None, True, 8788)),
     ('plan', False, ('plan', False, 8788)),
     (None, True, (None, True, 8788))],
)
def test_serve_selection_defaults(monkeypatch, skill, all_, expected):
    from automata.apps.skill_builder import cli as commands
    from automata.apps.skill_builder import server

    calls = []
    monkeypatch.setattr(server, 'serve', lambda *args: calls.append(args))
    commands.serve(skill, all_=all_)
    assert calls == [expected]


def test_export(tmp_path):
    result = cli("export-agent", "message-router", "--output", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.name for p in tmp_path.iterdir()} == {"SKILL.md", "references"}
    assert (tmp_path / "SKILL.md").read_bytes() == (SKILLS / "message-router/SKILL.md").read_bytes()
    assert all(p.suffix == ".md" for p in tmp_path.rglob("*") if p.is_file())


def test_cli_signal_stops_preview_without_build_output(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log_path = tmp_path / "preview.log"
    stream = None
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
