"""Render canonical skill Markdown for people, or export full skills for agents."""

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

app = App(name="skill-builder", help=__doc__)


@app.command
def serve(
    skill: Annotated[str | None, Parameter(help="Skill directory name in this app.")] = None,
    *,
    all_: Annotated[bool, Parameter(name="--all", help="Serve all skills (also the default without a skill name).")] = False,
    port: Annotated[int, Parameter(help="Loopback HTTP port.")] = 8788,
) -> None:
    """Serve shared FastAPI/Jinja views with one watcher and SSE reload.

    Without a skill name, serve all skills. SKILL.md is exact literal source;
    references are Markdown, never Jinja templates. Canonical content and shared
    template edits refresh live. Binds only http://127.0.0.1:PORT; no install/sync.
    """
    try:
        if not 1 <= port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        from .server import serve as run

        run(skill, all_ or skill is None, port)
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        app.console.print(f"Serve failed: {error}", markup=False)
        raise SystemExit(1) from error


@app.command(name="export-agent")
def export_agent(
    skill: str,
    *,
    output: Annotated[Path, Parameter(help="Agent skill directory; receives all canonical files.")],
) -> None:
    """Copy the complete canonical skill; no viewer HTML, install or sync."""
    try:
        from .content import export_agent as export

        export(skill, output)
    except (ImportError, OSError, ValueError) as error:
        app.console.print(f"Export failed: {error}", markup=False)
        raise SystemExit(1) from error
    print(f"Exported agent skill: {output}")


if __name__ == "__main__":
    app()
