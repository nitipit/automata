"""Render canonical skill Markdown for people, or export Markdown for agents."""

from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

app = App(name="skill-builder", help=__doc__)


@app.command
def serve(
    skill: Annotated[str | None, Parameter(help="Skill directory name in this app.")] = None,
    *,
    all_: Annotated[bool, Parameter(name="--all", help="Serve the app skill catalog.")] = False,
    port: Annotated[int, Parameter(help="Loopback HTTP port.")] = 8788,
) -> None:
    """Launch native Engrave CLI watching/SSE; never export or sync.

    Exactly one skill or --all is required. SKILL.md is shown as exact source;
    references use native trusted Markdown/Jinja rendering. Canonical edits refresh
    live; changing selection, links or shared templates needs restart.
    Requires cached Engrave 3.2.6. Binds only http://127.0.0.1:PORT.
    """
    try:
        if not 1 <= port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        from .server import serve as run

        run(skill, all_, port)
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        app.console.print(f"Serve failed: {error}", markup=False)
        raise SystemExit(1) from error


@app.command(name="export-agent")
def export_agent(
    skill: str,
    *,
    output: Annotated[Path, Parameter(help="Agent skill directory; receives Markdown only.")],
) -> None:
    """Copy SKILL.md and linked references; no HTML, libraries, install or sync."""
    try:
        from .content import export_agent as export

        export(skill, output)
    except (ImportError, OSError, ValueError) as error:
        app.console.print(f"Export failed: {error}", markup=False)
        raise SystemExit(1) from error
    print(f"Exported agent Markdown: {output}")


if __name__ == "__main__":
    app()
