"""Opt-in native Codex protocol probe; no model turns or user runtime access.

Run with --binary PATH (the installed native executable, not its Node shim) and
--state-root PATH (a new, task-owned directory). Requires Linux bubblewrap.
This is an audit proof, not an Automata adapter or Codex launcher for real work.
"""
from __future__ import annotations

import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path


class Probe:
    def __init__(self, binary: Path, root: Path):
        self.root = root
        self.records = []
        self.sequence = 0
        self.buffer = b""
        self.stderr = (root / "stderr.log").open("wb")
        # No host home, /etc, sockets, credentials, or project ancestors are mounted.
        # No daemon transport; the only endpoint is this owned child's stdio.
        command = [
            "bwrap", "--die-with-parent", "--new-session", "--unshare-all",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
            "--tmpfs", "/tmp", "--dir", "/etc", "--dir", "/home",
            "--bind", str(root), "/probe", "--ro-bind", str(binary), "/codex",
            "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "HOME", "/probe/home", "--setenv", "CODEX_HOME", "/probe/codex",
            "--setenv", "XDG_CONFIG_HOME", "/probe/home/.config",
            "--chdir", "/probe/project", "/codex", "app-server", "--stdio",
        ]
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.stderr, start_new_session=True,
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)

    def send(self, value):
        self.process.stdin.write(json.dumps(value).encode() + b"\n")
        self.process.stdin.flush()

    def request(self, method, params):
        # Hard allowlist: adding turn/start, compact, queue/start or shell operations
        # requires a different, separately authorized proof.
        allowed = {
            "initialize", "skills/list", "thread/start", "thread/inject_items",
            "thread/read", "thread/settings/update", "thread/fork", "thread/resume",
            "thread/unsubscribe", "hooks/list", "plugin/read", "plugin/list",
        }
        if method not in allowed:
            raise ValueError(f"Not an offline proof method: {method}")
        self.sequence += 1
        identifier = self.sequence
        self.send({"id": identifier, "method": method, "params": params})
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if b"\n" not in self.buffer:
                if not self.selector.select(max(0, deadline - time.monotonic())):
                    break
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError("Native app-server exited; inspect stderr.log")
                self.buffer += chunk
                continue
            line, self.buffer = self.buffer.split(b"\n", 1)
            event = json.loads(line)
            self.records.append(event)
            if event.get("id") == identifier:
                return event
        raise TimeoutError(method)

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=3)
        self.selector.close()
        self.stderr.close()
        (self.root / "protocol.json").write_text(json.dumps(self.records, indent=2) + "\n")


def skill(root, name, description):
    target = root / name / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n# Fixture\n")


def run(binary: Path, root: Path):
    root.mkdir(parents=True, exist_ok=False)
    for name in ["home", "codex", "project/.git", "project/nested"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "codex/config.toml").write_text(
        'model = "gpt-5.1-codex"\napproval_policy = "on-request"\n'
        'sandbox_mode = "read-only"\n[analytics]\nenabled = false\n'
        '[feedback]\nenabled = false\n[features]\n'
        'memories = false\nweb_search = false\n'
    )
    skill(root / "home/.agents/skills", "audit-duplicate", "global fixture")
    skill(root / "project/.agents/skills", "audit-duplicate", "repo fixture")
    skill(root / "project/nested/.agents/skills", "audit-nested", "nested fixture")
    skill(root / "project/.agents/skills", "audit-repo", "unique repo fixture")
    (root / "project/.agents/skills/audit-linked").symlink_to("audit-repo")
    # A harmless command proves hook trust remains enforced (must NOT execute).
    (root / "codex/hooks.json").write_text(json.dumps({"hooks": {"SessionStart": [{
        "hooks": [{"type": "command", "command": "touch /probe/UNTRUSTED_HOOK_RAN"}]
    }]}}))
    # Exercise the candidate installer/exporter, not global installed copies.
    source = Path(__file__).resolve().parents[4] / "src"
    sys.path.insert(0, str(source))
    from automata.install.skills import install_skills
    from automata.plugin.export import export_plugin

    installed = install_skills(target_root=root / "project/.agents/skills")
    export_plugin(name="automata-audit", output=root / "project/plugins/automata-audit",
                  skill_names=["automata-plan"], tool_names=["timer"])
    marketplace = root / "project/.agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True)
    marketplace.write_text(json.dumps({"name": "audit-local", "plugins": [{
        "name": "automata-audit", "source": {"source": "local", "path": "./plugins/automata-audit"}
    }]}))
    results = {"candidate_installed_skills": [item.name for item in installed]}
    probe = Probe(binary, root)
    try:
        results["initialize"] = probe.request("initialize", {
            "clientInfo": {"name": "automata_offline_audit", "version": "1"},
            "capabilities": {"experimentalApi": True},
        })
        probe.send({"method": "initialized"})
        results["skills"] = probe.request("skills/list", {
            "cwds": ["/probe/project/nested"], "forceReload": True,
        })
        results["plugin"] = probe.request("plugin/read", {
            "pluginName": "automata-audit",
            "marketplacePath": "/probe/project/.agents/plugins/marketplace.json",
        })
        params = {
            "cwd": "/probe/project/nested", "model": "gpt-5.1-codex",
            "approvalPolicy": "on-request", "sandbox": "read-only",
            "dynamicTools": [{"type": "function", "name": "audit_echo",
                              "description": "Offline registration fixture only",
                              "inputSchema": {"type": "object", "properties": {}}}],
        }
        results["start"] = probe.request("thread/start", params)
        if "error" in results["start"]:
            return results
        tid = results["start"]["result"]["thread"]["id"]
        results["hooks"] = probe.request("hooks/list", {"cwds": ["/probe/project/nested"]})
        results["inject"] = probe.request("thread/inject_items", {
            "threadId": tid,
            "items": [{"type": "message", "role": "developer",
                       "content": [{"type": "input_text",
                                    "text": "AUDIT_MODEL_CONTEXT_SENTINEL"}]}],
        })
        results["read"] = probe.request("thread/read", {"threadId": tid, "includeTurns": True})
        results["inject_fixture_conversation"] = probe.request("thread/inject_items", {
            "threadId": tid, "items": [
                {"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": "Synthetic fixture, not a model turn"}]},
                {"type": "message", "role": "assistant", "content": [
                    {"type": "output_text", "text": "Synthetic reply, no usage telemetry"}]},
            ],
        })
        results["settings"] = probe.request("thread/settings/update", {
            "threadId": tid, "effort": "low",
        })
        results["invalid_effort"] = probe.request("thread/settings/update", {
            "threadId": tid, "effort": "not-a-supported-effort",
        })
        results["fork"] = probe.request("thread/fork", {
            "threadId": tid, "deferGoalContinuation": True,
        })
        results["unsubscribe"] = probe.request("thread/unsubscribe", {"threadId": tid})
        results["resume"] = probe.request("thread/resume", {"threadId": tid})
        results["untrusted_hook_executed"] = (root / "UNTRUSTED_HOOK_RAN").exists()
    finally:
        probe.close()
        results["process_exit_code"] = probe.process.returncode
        (root / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.binary.resolve(strict=True), args.state_root.resolve())
    print(json.dumps({key: ("error" if isinstance(value, dict) and "error" in value else "observed")
                      for key, value in result.items()}, indent=2))
