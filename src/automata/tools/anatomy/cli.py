"""Automata Anatomy: local monitoring and canonical skill reading."""

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

app = App(name="automata-anatomy", help=__doc__)


@app.command
@app.default
def serve(
    *,
    port: Annotated[int, Parameter(help="Loopback HTTP port.")] = 8766,
    asset_root: Annotated[
        Path | None, Parameter(help="Prepared chart assets directory (contains lib/echarts.js).")
    ] = None,
) -> None:
    """Serve FastAPI/Jinja monitor and skill catalog in the foreground on 127.0.0.1."""
    try:
        if not 1 <= port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        from .server import serve as run

        if asset_root is None:
            run(port=port)
        else:
            run(port=port, asset_root=asset_root)
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        app.console.print(f"Serve failed: {error}", markup=False)
        raise SystemExit(1) from error


@app.command(name="export-agent")
def export_agent(
    skill: str,
    *,
    output: Annotated[Path, Parameter(help="Agent directory; receives all canonical skill files.")],
) -> None:
    """Copy a complete canonical skill; no viewer HTML, install or sync."""
    try:
        from .content import export_agent as export

        export(skill, output)
    except (ImportError, OSError, ValueError) as error:
        app.console.print(f"Export failed: {error}", markup=False)
        raise SystemExit(1) from error
    print(f"Exported agent skill: {output}")


if __name__ == "__main__":
    app()
