"""LMDB transaction retry behavior across isolated OS processes, not only threads."""
import json
import os
import subprocess
import sys
from pathlib import Path

from automata.apps.workspace.store import WorkspaceStore


def test_concurrent_processes_preserve_one_receipt(tmp_path):
    source = Path(__file__).resolve().parents[3] / "src"
    program = """
import json, sys
from pathlib import Path
from automata.apps.workspace.store import WorkspaceStore
value = {"operationId": "concurrent-process-operation",
         "context": {"projectId": "project-northstar", "conversationId": "conversation-aster"},
         "content": [{"id": "text", "type": "text", "version": 1, "data": {"text": "Synthetic"}}]}
print(json.dumps(WorkspaceStore(Path(sys.argv[1])).post(value, provenance={
    "kind": "agent", "id": "workspace-agent", "sessionId": "synthetic-process"})))
"""
    processes = []
    try:
        for _ in range(6):
            processes.append(subprocess.Popen(
                [sys.executable, "-c", program, str(tmp_path / "data")],
                env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(source)},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        receipts = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, stderr
            receipts.append(json.loads(stdout))
        assert all(receipt == receipts[0] for receipt in receipts)
        state = WorkspaceStore(tmp_path / "data").load()
        assert state["revision"] == 1 and len(state["postOperations"]) == 1
        assert len(state["conversations"]["conversation-aster"]["messages"]) == 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
