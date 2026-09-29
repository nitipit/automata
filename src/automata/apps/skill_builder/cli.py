"""Build ready-to-install skill assets without installing or launching them."""
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

app = App(name="skill-builder", help=__doc__)


@app.command(name="message-router")
def message_router(
    *,
    output: Annotated[
        Path | None, Parameter(help="Complete skill directory, not webref alone.")
    ] = None,
    library_root: Annotated[
        Path | None, Parameter(help="Directory containing the reviewed cached JavaScript bundles.")
    ] = None,
) -> None:
    """Build SKILL.md + self-contained webref; no downloads, installs, or live router.

    Defaults to the canonical Pi skill output and existing dashboard library cache.
    Run from a source checkout with Engrave 3.2.6 available through uv's shared cache.
    """
    try:
        from .message_router.build import LIBRARY, SKILL, build

        destination = output if output is not None else SKILL
        build(destination, library_root if library_root is not None else LIBRARY)
    except (ImportError, OSError, ValueError) as error:
        app.console.print(f"Build failed: {error}", markup=False)
        raise SystemExit(1) from error
    print(f"Built complete Message Router skill: {destination}")


if __name__ == "__main__":
    app()
