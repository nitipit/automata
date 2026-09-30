"""Short-lived native management RPC, isolated from user startup and networks.

Linux bubblewrap is required, never bypassed. Normal Codex interaction is unchanged.
The logical CODEX_HOME retains its path, but sees synthesized config and only the
bound rollout/lock directories. SQLite uses the explicitly selected backing store.
"""

from __future__ import annotations

import json
import os
import selectors
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from token_records import CoverageError

METHODS = {
    "thread/fork",
    "thread/read",
    "thread/resume",
    "thread/delete",
    "thread/name/set",
    "thread/turns/list",
    "thread/loaded/list",
}
MAX_RESPONSE = 16 * 1024 * 1024


class NativeClient:
    def __init__(self, binary, store, scratch_root, cwds, provider="openai", model="gpt-5.1-codex"):
        self.binary, self.store = Path(binary), Path(store)
        self.scratch_root, self.cwds = Path(scratch_root), cwds
        self.provider, self.model = provider, model
        self.sequence, self.buffer = 0, b""
        self.process = None
        self.temporary = None
        self.selector = self.stderr = None

    def __enter__(self):
        if not shutil.which("bwrap"):
            raise CoverageError("bubblewrap required; no unsandboxed fallback")
        for cwd in self.cwds:
            path = Path(cwd)
            if not path.is_absolute() or path == Path("/") or path.is_relative_to(self.store):
                raise CoverageError("unsupported native working directory")
        for name in ("sessions", "archived_sessions", "thread-writer-locks"):
            if (self.store / name).is_symlink():
                raise CoverageError("symlinked native storage unsupported")
        self.scratch_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.temporary = tempfile.TemporaryDirectory(prefix="native-", dir=self.scratch_root)
        temporary = Path(self.temporary.name)
        config = temporary / "config.toml"
        config.write_text(
            f'sqlite_home="/automata-store"\nmodel={json.dumps(self.model)}\n'
            f"model_provider={json.dumps(self.provider)}\n"
            'approval_policy="never"\nsandbox_mode="read-only"\n'
            f'[model_providers.{json.dumps(self.provider)}]\nname="Offline management"\n'
            'base_url="http://127.0.0.1:9/v1"\nwire_api="responses"\n'
            "requires_openai_auth=false\n"
            "[analytics]\nenabled=false\n[feedback]\nenabled=false\n"
            "[features]\nhooks=false\ngoals=false\nmemories=false\nplugins=false\n"
            "shell_snapshot=false\nshell_snapshot_v2=false\n"
            "background_paginated_rollout_migration=false\nweb_search=false\n"
        )
        empty = temporary / "empty"
        empty.write_text("")
        command = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all"]
        for system in ("/usr", "/lib", "/lib64"):
            if Path(system).exists():
                command += ["--ro-bind", system, system]
        command += [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/etc",
            "--dir",
            "/home/management",
            "--bind",
            str(self.store),
            "/automata-store",
        ]
        # No credential/config contents are read. Existing surfaces in the backing
        # mount are hidden as well as absent from the synthesized CODEX_HOME.
        for name in ("auth.json", ".credentials.json", "config.toml", "hooks.json", "AGENTS.md"):
            if (self.store / name).exists():
                command += ["--ro-bind", str(empty), "/automata-store/" + name]
        command += ["--tmpfs", str(self.store)]
        for name in ("sessions", "archived_sessions", "thread-writer-locks"):
            directory = self.store / name
            if directory.is_symlink():
                raise CoverageError("symlinked native storage unsupported")
            directory.mkdir(exist_ok=True, mode=0o700)
            command += ["--bind", str(directory), str(directory)]
        command += ["--ro-bind", str(config), str(self.store / "config.toml")]
        for cwd in set(self.cwds):
            path = Path(cwd)
            if not path.is_absolute() or path == Path("/") or path.is_relative_to(self.store):
                raise CoverageError("unsupported native working directory")
            command += ["--dir", str(path)]
        command += [
            "--ro-bind",
            str(self.binary),
            "/codex",
            "--clearenv",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--setenv",
            "HOME",
            "/home/management",
            "--setenv",
            "CODEX_HOME",
            str(self.store),
            "--chdir",
            "/home/management",
        ]
        try:
            version = subprocess.check_output(command + ["/codex", "--version"], timeout=10)
            if version.strip() != b"codex-cli 0.159.0":
                raise CoverageError("unsupported native Codex version")
            self.stderr = (temporary / "stderr").open("wb")
            self.process = subprocess.Popen(
                command + ["/codex", "app-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.stderr,
            )
            self.selector = selectors.DefaultSelector()
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            self._request(
                "initialize",
                {
                    "clientInfo": {"name": "automata_session_management", "version": "1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self._send({"method": "initialized"})
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def _send(self, value):
        self.process.stdin.write(json.dumps(value).encode() + b"\n")
        self.process.stdin.flush()

    def _receive(self, deadline):
        while True:
            if time.monotonic() >= deadline:
                raise CoverageError("native management timed out; outcome may be partial")
            if b"\n" in self.buffer:
                break
            if len(self.buffer) > MAX_RESPONSE:
                raise CoverageError("native response too large")
            if not self.selector.select(max(0, deadline - time.monotonic())):
                raise CoverageError("native management timed out; outcome may be partial")
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise CoverageError("native management exited; outcome may be partial")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        if len(line) > MAX_RESPONSE:
            raise CoverageError("native response too large")
        value = json.loads(line)
        if "id" in value and "method" in value:
            raise CoverageError("unexpected native approval/request; not answered")
        return value

    def _request(self, method, params):
        self.sequence += 1
        current = self.sequence
        self._send({"id": current, "method": method, "params": params})
        deadline = time.monotonic() + 30
        while True:
            if time.monotonic() >= deadline:
                raise CoverageError("native management timed out; outcome may be partial")
            value = self._receive(deadline)
            if value.get("id") == current:
                if "error" in value:
                    raise CoverageError("native operation rejected; no automatic retry")
                return value["result"]

    def request(self, method, params):
        if method not in METHODS:
            raise CoverageError("not an authorized management RPC")
        return self._request(method, params)

    def __exit__(self, *_args):
        if self.process:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        if self.selector:
            self.selector.close()
            self.selector = None
        if self.stderr:
            self.stderr.close()
            self.stderr = None
        if self.temporary:
            self.temporary.cleanup()
            self.temporary = None
