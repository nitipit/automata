"""Compatibility CLI alias for the unified Automata Anatomy tool."""

from automata.tools.anatomy.cli import app as app
from automata.tools.anatomy.cli import export_agent as export_agent
from automata.tools.anatomy.cli import serve as serve

if __name__ == "__main__":
    app()
