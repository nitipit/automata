"""Shared headerless label/value grids; canonical facts stay in storage."""

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .view import summary_fields


def label_value_grid(fields, width):
    """Rich lays out cells; wrapped continuations stay under the value column."""
    width = max(16, width)
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(width=7, no_wrap=True, style="#8495a8")
    grid.add_column(ratio=1, overflow="fold", style="#dbe4ee")
    for label, value in fields:
        grid.add_row(Text(label), Text(value))
    # Keep styled text as the existing widget interface. Resize rebuilds the grid.
    result = Text()
    for segment in Console(width=width).render(grid):
        if not segment.control:
            result.append(segment.text, style=segment.style)
    return result[:-1] if result.plain.endswith("\n") else result


def agent_panel(state, aid, width):
    path, fields = summary_fields(state, aid)
    return path, label_value_grid(fields, width)
