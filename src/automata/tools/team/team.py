#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.15"
# dependencies = [
#   "cyclopts>=4.11.1", "dictify>=5.0.2,<6",
#   "shelfdb>=3.0.2,<4", "textual>=8.2.7,<9",
# ]
# ///
"""Standalone installed entry, preserving canonical ShelfDB callable namespaces."""

import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType


def main():
    root = Path(__file__).resolve().parent
    sys.dont_write_bytecode = True
    # Bootstrap only this copied tool, never an ambient Automata installation.
    for name, directory in (("automata", root.parent.parent), ("automata.tools", root.parent)):
        package = ModuleType(name)
        package.__path__ = [str(directory)]
        package.__package__ = name
        package.__spec__ = ModuleSpec(name, loader=None, is_package=True)
        package.__spec__.submodule_search_locations = package.__path__
        sys.modules[name] = package
    from automata.tools.team.cli import app

    app()


if __name__ == "__main__":
    main()
