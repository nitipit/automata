"""Resolve the separately installed tool explicitly; no repository-relative fallback."""

import os
import sys
from pathlib import Path

value = os.environ.get("AUTOMATA_PYTHON_RUNTIME_TOOL")
if not value:
    raise RuntimeError("Set AUTOMATA_PYTHON_RUNTIME_TOOL to the installed python-runtime directory")
TOOL = Path(value).expanduser().resolve()
if not (TOOL / "automata_python_runtime" / "__init__.py").is_file():
    raise RuntimeError(
        f"Python runtime tool is missing at {TOOL}; install selected python-runtime tool"
    )
sys.dont_write_bytecode = True
sys.path.insert(0, str(TOOL))
from automata_python_runtime import (  # noqa: E402
    PUBLICATION_MIME,
    KernelRuntime,
    WorkspaceServer,
    request,
)

__all__ = ["PUBLICATION_MIME", "KernelRuntime", "WorkspaceServer", "request", "TOOL"]
