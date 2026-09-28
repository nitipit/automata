"""Copy the maintained webboard example to an explicit new public directory."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

EXAMPLE = Path(__file__).parent / "examples" / "webboard"
ASSETS = ("index.html", "board.css", "board.js")


def provision(target: Path) -> None:
    """Operator-only setup; never overwrite content or follow symlink ancestors.

    The destination's parent directories must be trusted, not concurrently changed
    by another writer. This is not a sandboxed filesystem API for board scripts.
    """
    if not target.is_absolute() or ".." in target.parts:
        raise ValueError("Choose an absolute destination without '..'")
    for path in (target, *target.parents):
        if path.is_symlink():
            raise ValueError("Refusing a symlink destination or ancestor")
    if target.exists():
        raise ValueError("Refusing to overwrite an existing destination")
    for name in ASSETS:
        source = EXAMPLE / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("Example asset missing or not a regular source file")
    target.mkdir(parents=True, exist_ok=False)
    # Copy only browser assets, not the README or future private/example metadata.
    # A failed copy deliberately remains visible for operator review, not auto-delete.
    for name in ASSETS:
        with (EXAMPLE / name).open("rb") as source, (target / name).open("xb") as destination:
            shutil.copyfileobj(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("web_dir", type=Path, help="Absolute NEW public web directory")
    args = parser.parse_args()
    try:
        provision(args.web_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Provisioning stopped: {error}\n")
    print(f"Provisioned webboard assets at {args.web_dir}")


if __name__ == "__main__":
    main()
