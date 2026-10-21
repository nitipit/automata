"""Package inventory and invocation-scoped runtime locations (no web imports)."""

from pathlib import Path

from automata.install.skills import bundled_skill_root

# A copied tool still reads canonical inventory from the installed package.
SKILLS = bundled_skill_root()
PACKAGE = SKILLS.parent
ROOT = Path.cwd().resolve()
HOME = Path.home()
TEMPLATES = Path(__file__).resolve().parent / "templates"
SITE = ROOT / ".agents/var/tools/automata-anatomy/public"
SKILL_ROOTS = [
    ("bundled", SKILLS),
    ("global", HOME / ".agents/skills"),
    ("project", ROOT / ".agents/skills"),
]
TOOL_ROOTS = {
    "bundled": PACKAGE / "tools",
    "global": HOME / ".agents/tools",
    "project": ROOT / ".agents/tools",
}
