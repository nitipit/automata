import fcntl
import json
import os
import pty
import select
import shutil
import stat
import struct
import subprocess
import sys
import termios
import time
import zipfile
from pathlib import Path


def test_offline_wheel_ships_team_and_optional_metadata(tmp_path):
    uv = shutil.which("uv")
    assert uv is not None, "Offline uv build is required for package verification"
    root = Path(__file__).resolve().parents[4]
    output = tmp_path / "dist"
    result = subprocess.run(
        [uv, "build", "--offline", "--wheel", "--out-dir", str(output), str(root)],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(next(output.glob("*.whl"))) as archive:
        names = set(archive.namelist())
        for module in (
            "__init__",
            "cli",
            "models",
            "store",
            "server",
            "hierarchy",
            "view",
            "panels",
            "app",
        ):
            assert f"automata/tools/team/{module}.py" in names
        assert "automata/tools/team/README.md" in names
        assert "automata/tools/team/team.py" in names
        assert "automata/skills/automata-team-use/SKILL.md" in names
        assert not any("__pycache__" in name or name.endswith("db.sock") for name in names)
        metadata = archive.read(
            next(name for name in names if name.endswith(".dist-info/METADATA"))
        )
        assert b"Provides-Extra: team" in metadata
        for dependency in (b"dictify", b"shelfdb", b"textual"):
            assert any(
                line.startswith(b"Requires-Dist: " + dependency) and b"extra ==" in line
                for line in metadata.splitlines()
            )


def test_duplicate_server_refused_and_graceful_restart_preserves_db(service):
    before = service.snapshot()
    socket = service.root / "db.sock"
    assert stat.S_IMODE(socket.stat().st_mode) & 0o077 == 0
    duplicate = service.call("serve", ok=False)
    assert "socket already exists" in duplicate.stderr
    assert service.snapshot() == before
    service.stop()
    assert service.process.returncode == 0
    assert not socket.exists()
    from tests.apps.team.conftest import Service

    restarted = Service(service.root)
    try:
        assert restarted.snapshot() == before
    finally:
        restarted.stop()
        restarted.log.close()
    assert not socket.exists()


def test_all_help_surfaces_and_file_input(service, tmp_path):
    for command in ("serve", "init", "board", "put", "update", "json"):
        result = service.call(command, "--help")
        assert "--state-root" in result.stdout
    document = tmp_path / "patch.json"
    document.write_text(json.dumps({"note": "File-based publication"}))
    service.call(
        "update",
        "--goal",
        "g",
        "--actor",
        "alice",
        "--kind",
        "task",
        "--id",
        "t",
        "--file",
        str(document),
    )
    assert service.snapshot()["tasks"]["t"]["note"] == "File-based publication"


def test_base_cli_and_team_help_do_not_import_optional_dependencies():
    script = """
import importlib.abc
import sys
class NoTeamDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.split('.')[0] in {'dictify', 'shelfdb', 'textual'}:
            raise AssertionError('eager dependency import: ' + fullname)
sys.meta_path.insert(0, NoTeamDependencies())
from automata.cli import app
try:
    app(['team', '--help'])
except SystemExit as error:
    assert error.code == 0
try:
    app(['character', 'list'])
except SystemExit as error:
    assert error.code == 0
assert not any(name.split('.')[0] in {'dictify', 'shelfdb', 'textual'} for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], env=os.environ, text=True, capture_output=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert "Automata Team" in result.stdout
    assert "Personalities:" in result.stdout


def test_public_board_in_real_83_column_pty_q_leaves_service_running(report_service, tmp_path):
    service = report_service
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 46, 83, 0, 0))
    output = bytearray()
    process = subprocess.Popen(
        service.argv("board", "--goal", "g"),
        env=service.env,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )
    os.close(slave)
    try:
        deadline = time.monotonic() + 8
        while b"Shared goal" not in output:
            assert process.poll() is None, output.decode(errors="replace")
            assert time.monotonic() < deadline, output.decode(errors="replace")
            if select.select([master], [], [], 0.1)[0]:
                output.extend(os.read(master, 65536))
        assert b"\x1b[?1049h" in output  # Actual alternate-screen terminal startup.
        rows, columns, _, _ = struct.unpack(
            "HHHH", fcntl.ioctl(master, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        )
        assert (columns, rows) == (83, 46)
        os.write(master, b"q")
        while process.poll() is None:
            assert time.monotonic() < deadline
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
        assert process.wait(timeout=3) == 0
        (tmp_path / "board-83.ansi").write_bytes(output)
        assert service.process.poll() is None
        assert service.snapshot()["goals"]["g"]["name"] == "Shared goal"
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        os.close(master)


def test_missing_goal_board_fails_before_tui(service):
    result = service.call("board", "--goal", "missing", ok=False)
    assert "unknown goal" in result.stderr
    assert service.process.poll() is None


def test_state_root_too_long_is_actionable_and_non_destructive(service, tmp_path):
    root = tmp_path / ("long" * 30)
    result = subprocess.run(
        [sys.executable, "-m", "automata.cli", "team", "serve", "--state-root", str(root)],
        env=service.env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "shorter --state-root" in result.stderr
    assert not root.exists()
