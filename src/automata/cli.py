"""Command line interface for Automata assets."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from automata.character import CharacterError, compose_character, list_character_components
from automata.install.directory import InstallMode
from automata.install.pi_extensions import (
    PiExtensionInstallError,
    install_pi_extensions,
    normalize_pi_extension_names,
)
from automata.install.skills import (
    SkillInstallError,
    install_skills,
    normalize_skill_names,
)
from automata.install.tools import ToolInstallError, install_tools, normalize_tool_names
from automata.plugin import PluginExportError, export_plugin

app = App(help="Automata reusable agent guidance tools.")
character_app = App(
    help=(
        "Render packaged character components as Markdown for an AI agent to read. "
        "The receiving agent decides how to reference, copy, adapt, or merge the text "
        "into its own AGENTS.md."
    )
)
app.command(character_app, name="character")
skills_app = App(help="Install or expose skill directories into an agent skill root.")
app.command(skills_app, name="skills")
tools_app = App(help="Install bundled or local tools into an agent tool root.")
app.command(tools_app, name="tools")
plugin_app = App(help="Build Agent Plugin packages from Automata assets.")
app.command(plugin_app, name="plugin")
pi_extension_app = App(help="Install bundled or local Pi extension files.")
app.command(pi_extension_app, name="pi-extension")

DEFAULT_AGENT_INSTRUCTIONS_PATH = Path(".agents/var/skills/automata-agents-md")


@character_app.command(name="list")
def list_() -> None:
    """List available character components."""

    components = list_character_components()
    print("Personalities:")
    print_names(components.personalities)
    print("\nLanguages:")
    print_names(components.languages)
    print("\nBehaviors:")
    print_names(components.behaviors)
    print("\nImplicit languages:")
    print_names(components.implicit_languages)
    print("\nImplicit behaviors:")
    print_names(components.implicit_behaviors)


@character_app.command
def compose(
    *,
    personality: Annotated[
        str | None,
        Parameter(help="Personality component name from character/personality/."),
    ] = None,
    language: Annotated[
        str | None,
        Parameter(help="Language component name from character/language/."),
    ] = None,
    behavior: Annotated[
        list[str] | None,
        Parameter(
            name="--behavior",
            help="Behavior component name. Repeat for multiple behaviors.",
        ),
    ] = None,
    agents_md: Annotated[
        Path | None,
        Parameter(
            name="--agents-md",
            help="Override the default directory for additional agent instructions.",
        ),
    ] = None,
) -> None:
    """Compose character Markdown with additional-instruction discovery."""

    try:
        output = compose_character(
            personality=personality,
            language=language,
            behaviors=behavior or (),
        )
    except CharacterError as exc:
        raise SystemExit(str(exc)) from exc

    instructions_path = agents_md if agents_md is not None else DEFAULT_AGENT_INSTRUCTIONS_PATH
    print(output + format_agent_instructions_notice(instructions_path), end="")


def format_agent_instructions_notice(path: Path) -> str:
    display_path = path.as_posix()
    if not display_path.endswith("/"):
        display_path += "/"
    return (
        "\n# Additional Instructions\n\n"
        f"Additional instruction directory: `{display_path}`.\n"
        "When this directory exists, discover and read its existing `.md` files.\n"
        "If it is absent or contains no Markdown files, continue without them.\n"
        "This is instruction data, not a skill package; do not assume a `SKILL.md` exists.\n"
    )


@skills_app.command
def install(
    *,
    source_root: Annotated[
        str | None,
        Parameter(help="Exclusive skill source; defaults to bundled shared and Pi skills."),
    ] = None,
    target_root: Annotated[
        Path,
        Parameter(help="Directory to install skills under."),
    ],
    skill_names: Annotated[
        list[str] | None,
        Parameter(
            name="--skill",
            help="Skill name to install. Repeat or use comma-separated names.",
        ),
    ] = None,
    mode: Annotated[
        InstallMode,
        Parameter(help="Install mode: copy, replace, or symlink."),
    ] = "copy",
    json_output: Annotated[
        bool,
        Parameter(name="--json", help="Print machine-readable JSON output."),
    ] = False,
) -> None:
    """Install all or selected skill directories."""

    try:
        results = install_skills(
            source_root=source_root,
            target_root=target_root,
            skill_names=normalize_skill_names(skill_names),
            mode=mode,
        )
    except SkillInstallError as exc:
        raise SystemExit(str(exc)) from exc

    print_install_results(results, json_output=json_output)


@pi_extension_app.command(name="install")
def install_pi_extensions_command(
    *,
    target_root: Annotated[
        Path,
        Parameter(help="Directory to install Pi extension files under."),
    ],
    source_root: Annotated[
        str | None,
        Parameter(help="Optional directory containing extensions; defaults to bundled extensions."),
    ] = None,
    extension_names: Annotated[
        list[str] | None,
        Parameter(
            name="--extension",
            help="Extension name to install. Repeat or use comma-separated names.",
        ),
    ] = None,
    mode: Annotated[
        InstallMode,
        Parameter(help="Install mode: copy, replace, or symlink."),
    ] = "copy",
    json_output: Annotated[
        bool,
        Parameter(name="--json", help="Print machine-readable JSON output."),
    ] = False,
) -> None:
    """Install all or selected Pi extension files."""

    try:
        results = install_pi_extensions(
            source_root=source_root,
            target_root=target_root,
            extension_names=normalize_pi_extension_names(extension_names),
            mode=mode,
        )
    except PiExtensionInstallError as exc:
        raise SystemExit(str(exc)) from exc

    print_install_results(results, json_output=json_output)


@tools_app.command(name="install")
def install_tools_command(
    *,
    target_root: Annotated[
        Path,
        Parameter(help="Directory to install tools under."),
    ],
    source_root: Annotated[
        str | None,
        Parameter(help="Optional directory containing tools; defaults to bundled tools."),
    ] = None,
    tool_names: Annotated[
        list[str] | None,
        Parameter(
            name="--tool",
            help="Tool name to install. Repeat or use comma-separated names.",
        ),
    ] = None,
    mode: Annotated[
        InstallMode,
        Parameter(help="Install mode: copy, replace, or symlink."),
    ] = "copy",
    json_output: Annotated[
        bool,
        Parameter(name="--json", help="Print machine-readable JSON output."),
    ] = False,
) -> None:
    """Install all or selected bundled or local tool directories."""

    try:
        results = install_tools(
            source_root=source_root,
            target_root=target_root,
            tool_names=normalize_tool_names(tool_names),
            mode=mode,
        )
    except ToolInstallError as exc:
        raise SystemExit(str(exc)) from exc

    print_install_results(results, json_output=json_output)


@plugin_app.command(name="export")
def export_plugin_command(
    *,
    name: Annotated[str, Parameter(help="Plugin name, for example automata-core.")],
    output: Annotated[Path, Parameter(help="Output directory for the plugin package.")],
    profile: Annotated[
        str | None,
        Parameter(help="Optional profile to use as the starting selection."),
    ] = None,
    skill_names: Annotated[
        list[str] | None,
        Parameter(name="--skill", help="Skill name to include; repeat or comma-separate."),
    ] = None,
    tool_names: Annotated[
        list[str] | None,
        Parameter(name="--tool", help="Tool name to include; repeat or comma-separate."),
    ] = None,
    version: Annotated[str, Parameter(help="Plugin package version.")] = "0.1.0",
    description: Annotated[
        str | None,
        Parameter(help="Optional plugin description."),
    ] = None,
    replace: Annotated[
        bool,
        Parameter(help="Replace an existing output directory."),
    ] = False,
    json_output: Annotated[
        bool,
        Parameter(name="--json", help="Print machine-readable JSON output."),
    ] = False,
) -> None:
    """Export selected Automata skills and tools as an Agent Plugin package."""

    try:
        result = export_plugin(
            name=name,
            output=output,
            profile=profile,
            skill_names=normalize_skill_names(skill_names),
            tool_names=normalize_tool_names(tool_names),
            version=version,
            description=description,
            replace=replace,
        )
    except PluginExportError as exc:
        raise SystemExit(str(exc)) from exc

    if json_output:
        print(json.dumps(asdict(result), sort_keys=True))
        return

    print(f"Exported {result.name} to {result.output}")
    print(f"Skills: {', '.join(result.skills) or '(none)'}")
    print(f"Tools: {', '.join(result.tools) or '(none)'}")


def print_install_results(results, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps([asdict(result) for result in results], sort_keys=True))
        return

    for result in results:
        print(f"Installed {result.name}: {result.source} -> {result.target} ({result.mode})")


def print_names(names: tuple[str, ...]) -> None:
    if not names:
        print("  (none)")
        return
    for name in names:
        print(f"- {name}")


if __name__ == "__main__":
    app()
