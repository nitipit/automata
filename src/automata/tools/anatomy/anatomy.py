#!/usr/bin/env python3
"""Copied tool launcher; requires the installed Automata package with [anatomy].

Canonical skills are supplied by that package, never duplicated in the tool copy.
Run with the already-prepared Python environment; this launcher installs nothing.
"""

import sys
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType


def main():

    root = Path(__file__).resolve().parent
    sys.dont_write_bytecode = True
    package = ModuleType("automata.tools.anatomy")
    package.__path__ = [str(root)]
    package.__package__ = "automata.tools.anatomy"
    package.__spec__ = ModuleSpec(package.__package__, loader=None, is_package=True)
    package.__spec__.submodule_search_locations = package.__path__
    sys.modules[package.__package__] = package
    from automata.tools.anatomy.cli import app

    app()


if __name__ == "__main__":
    main()
