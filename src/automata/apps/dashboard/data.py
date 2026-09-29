"""Read-only, project-scoped anatomy projection; never reads work or chat records."""

from datetime import UTC, datetime
from pathlib import Path

import yaml

from .activity import activity, make_window

ROOT = Path(__file__).resolve().parents[4]
HOME = Path.home()
SKILL_ROOTS = [
    ("bundled", ROOT / "src/automata/skills/bundled"),
    ("global", HOME / ".agents/skills"),
    ("project", ROOT / ".agents/skills"),
]
TOOL_ROOTS = {
    "bundled": ROOT / "src/automata/tools",
    "global": HOME / ".agents/tools",
    "project": ROOT / ".agents/tools",
}


def label(path):
    """Keep provenance useful without publishing unrelated absolute paths."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return "~/" + str(path.relative_to(HOME))


def timestamp(path):
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()


def identity():
    path = HOME / ".pi/agent/AGENTS.md"
    return dict(
        source=label(path),
        status="available" if path.is_file() else "missing",
        body=path.read_text() if path.is_file() else "Global AGENTS.md was not found.",
        modified=timestamp(path) if path.is_file() else None,
        note=(
            "Managed through Automata's tools. Ask Automata to change it. "
            "This view is read-only; an existing session may need a reload or "
            "a new session to pick up configuration changes."
        ),
    )


def skills():
    groups = {}
    warnings = []
    for scope, root in SKILL_ROOTS:
        paths = root.glob("**/SKILL.md") if scope == "bundled" else root.glob("*/SKILL.md")
        for path in sorted(paths):
            try:
                text = path.read_text()
                if not text.startswith("---\n"):
                    raise ValueError("No frontmatter")
                meta = yaml.safe_load(text.split("---", 2)[1])
                name = meta["name"]
                if not isinstance(name, str) or not isinstance(meta.get("description"), str):
                    raise ValueError("Invalid skill metadata")
                row = groups.setdefault(
                    name, dict(name=name, description="", copies=[], toolPaths=[])
                )
                row["copies"].append(
                    dict(scope=scope, source=label(path), modified=timestamp(path))
                )
                # Project description wins over global, then bundled.
                row["description"] = meta["description"]
                metadata = meta.get("metadata") or {}
                declaration = metadata.get("automata-tools", "")
                row["toolPaths"] = (
                    [part.strip() for part in declaration.split(",") if part.strip()]
                    if isinstance(declaration, str)
                    else ["Unrecognized tool declaration"]
                )
            except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
                warnings.append("Could not read skill metadata: " + label(path))
    return sorted(groups.values(), key=lambda row: row["name"]), warnings


def tools():
    groups = {}
    for scope, root in TOOL_ROOTS.items():
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if not path.is_dir() or path.name.startswith((".", "_")):
                continue
            row = groups.setdefault(
                ("package", path.name), dict(name=path.name, kind="Tool package", copies=[])
            )
            row["copies"].append(dict(scope=scope, source=label(path)))
    for scope, root in [
        ("global", HOME / ".pi/agent/extensions"),
        ("project", ROOT / ".pi/extensions"),
    ]:
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.name.startswith((".", "_")) or not (
                path.is_dir() or path.suffix in (".ts", ".js")
            ):
                continue
            name = path.name if path.is_dir() else path.stem
            row = groups.setdefault(
                ("extension", name), dict(name=name, kind="Pi extension", copies=[])
            )
            row["copies"].append(dict(scope=scope, source=label(path)))
    return sorted(groups.values(), key=lambda row: (row["kind"], row["name"]))


def capabilities(skill_rows, tool_rows):
    """Link only explicit entry-path declarations; installation is not readiness."""
    items, linked = [], set()
    for skill in skill_rows:
        installed = any(copy["scope"] != "bundled" for copy in skill["copies"])
        dependencies = []
        for declaration in skill["toolPaths"]:
            path = Path(declaration)
            parts = path.parts
            if (
                path.is_absolute()
                or ".." in parts
                or len(parts) < 4
                or parts[:2] != (".agents", "tools")
                or any(char in declaration for char in "*?[]{}")
            ):
                dependencies.append(dict(declaration=declaration, status="unknown", sources=[]))
                continue
            package = parts[2]
            linked.add(package)
            relative = Path(*parts[2:])
            sources = [
                dict(scope=scope, source=label(root / relative))
                for scope, root in TOOL_ROOTS.items()
                if scope != "bundled" and (root / relative).is_file()
            ]
            dependencies.append(
                dict(
                    declaration=declaration,
                    package=package,
                    status="installed" if sources else "missing",
                    sources=sources,
                )
            )
        if not installed:
            status = "available"
        elif any(tool["status"] == "unknown" for tool in dependencies):
            status = "unknown"
        elif any(tool["status"] == "missing" for tool in dependencies):
            status = "incomplete"
        else:
            status = "installed"
        items.append(
            dict(
                name=skill["name"],
                description=skill["description"],
                status=status,
                skillInstalled=installed,
                copies=skill["copies"],
                tools=dependencies,
                readiness="Not checked",
            )
        )
    other = [
        tool for tool in tool_rows if tool["kind"] != "Tool package" or tool["name"] not in linked
    ]
    return dict(
        items=items,
        otherTools=other,
        note=(
            "Installed means the skill and its explicitly declared tool entry files "
            "exist on disk. Runtime exposure, login and connections are not checked. "
            "Tools without a declared skill relationship are listed separately."
        ),
    )


def snapshot(window=None):
    skill_rows, warnings = skills()
    tool_rows = tools()
    return dict(
        project=ROOT.name,
        scope="This project + global installed configuration",
        generatedAt=datetime.now(UTC).isoformat(),
        refreshSeconds=5,
        identity=identity(),
        capabilities=capabilities(skill_rows, tool_rows),
        activity=activity(ROOT, window or make_window()),
        warnings=warnings,
        boundaries=[
            "No stored knowledge, work items, conversations or session histories.",
            "Installed files do not prove an active session has loaded them.",
            "Tool inventory covers packages and Pi extensions, "
            "not the live callable-function list.",
        ],
    )
