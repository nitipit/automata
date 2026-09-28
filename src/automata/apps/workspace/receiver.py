"""Private app-owned router receiver lifecycle; no agents or model turns launched."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from threading import RLock, Thread
from urllib.parse import urlparse

from .store import WorkspaceStore


class PostReceiver:
    def __init__(self, store: WorkspaceStore, endpoint: Path, *, client_module: Path | None = None):
        if not endpoint.is_absolute() or endpoint.stat().st_mode & 0o077:
            raise ValueError("App receiver endpoint must be an absolute private file")
        credential = json.loads(endpoint.read_text())
        url = urlparse(credential.get("wsUrl", ""))
        if (credential.get("kind") != "page" or credential.get("participant") != "workspace-app"
                or url.scheme != "ws" or url.hostname != "127.0.0.1" or not url.port
                or url.username or url.password or not isinstance(credential.get("token"), str)
                or len(credential["token"]) < 32):
            raise ValueError("Invalid private app receiver endpoint")
        browser_path = os.environ.get("WORKSPACE_PAGE_ENDPOINT")
        if browser_path:
            browser = json.loads(Path(browser_path).read_text())
            if (browser.get("participant") == credential["participant"]
                    or browser.get("token") == credential["token"]):
                raise ValueError("App receiver must not share a browser credential")
        self.store = store
        self.credentials = {key: credential[key] for key in ("wsUrl", "participant", "token")}
        self.client_module = client_module or (
            Path(__file__).resolve().parents[2] / "tools/message-router/browser/client.js")
        if not self.client_module.is_file():
            raise ValueError("Shipped router client is unavailable")
        self.process = None
        self.phase = "offline"
        self.mutex = RLock()
        self.reader = None

    def start(self):
        with self.mutex:
            node = shutil.which("node")
            if not node:
                raise ValueError("Node with native WebSocket is required")
            self.process = subprocess.Popen(
                [node, str(Path(__file__).with_suffix(".mjs"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1, env={"PATH": os.environ.get("PATH", "")},
            )
            self.phase = "connecting"
            self.reader = Thread(target=self._read, daemon=True)
            self.reader.start()
            self._write({"type": "start", "credentials": self.credentials,
                         "clientModule": str(self.client_module)})

    def _write(self, value):
        with self.mutex:
            if not self.process or self.process.poll() is not None:
                raise RuntimeError("App receiver disconnected")
            self.process.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
            self.process.stdin.flush()

    def _read(self):
        process = self.process
        try:
            for line in process.stdout:
                if len(line) > 128 * 1024:
                    raise ValueError("Oversized adapter frame")
                event = json.loads(line)
                if event.get("type") == "state":
                    self.phase = event["phase"] if event.get("phase") in {
                        "connected", "offline", "failed"} else "failed"
                elif event.get("type") == "post":
                    try:
                        receipt = self.store.post(event["payload"], provenance=event["provenance"])
                    except (ValueError, TypeError, KeyError):
                        receipt = {"status": "rejected", "detail": (
                            "Invalid author, destination or post; "
                            "conflicting operation IDs cannot be reused")}
                    except (OSError, RuntimeError):
                        receipt = {"status": "uncertain", "detail": (
                            "Save not confirmed; retry only the identical operation")}
                    self._write({"type": "receipt", "id": event["id"], "payload": receipt})
        except (OSError, ValueError, RuntimeError, TypeError):
            self.phase = "failed"
        finally:
            if self.phase != "failed":
                self.phase = "offline"

    def status(self):
        return {"configured": True, "participant": "workspace-app", "phase": self.phase}

    def shutdown(self):
        with self.mutex:
            process = self.process
            if not process:
                return
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=3)
        if self.reader:
            self.reader.join(timeout=2)
        self.phase = "offline"


def configured_receiver(store: WorkspaceStore) -> PostReceiver | None:
    path = os.environ.get("WORKSPACE_APP_ENDPOINT")
    return PostReceiver(store, Path(path)) if path else None
