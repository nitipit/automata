"""Read and compose packaged Automata character components."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal

ComponentKind = Literal["personality", "language", "behavior"]


class CharacterError(RuntimeError):
    """Raised when character components cannot be read or composed."""


@dataclass(frozen=True)
class CharacterComponents:
    personalities: tuple[str, ...]
    languages: tuple[str, ...]
    behaviors: tuple[str, ...]
    # Base components are implicit when their component group is selected.
    implicit_languages: tuple[str, ...] = ("base",)
    implicit_behaviors: tuple[str, ...] = ("base",)


def character_root():
    return files("automata").joinpath("character")


def list_character_components() -> CharacterComponents:
    return CharacterComponents(
        personalities=list_component_names("personality"),
        languages=tuple(name for name in list_component_names("language") if name != "base"),
        behaviors=tuple(name for name in list_component_names("behavior") if name != "base"),
    )


def compose_character(
    *,
    personality: str | None = None,
    language: str | None = None,
    behaviors: list[str] | tuple[str, ...] = (),
) -> str:
    if not personality and not language and not behaviors:
        raise CharacterError("Select at least one character component")

    sections: list[tuple[str, str]] = []

    if personality:
        sections.append((f"Personality: {personality}", read_component("personality", personality)))

    if language:
        if language == "base":
            raise CharacterError("language/base is included automatically; do not select it")
        sections.append(("Language: base", read_component("language", "base")))
        sections.append((f"Language: {language}", read_component("language", language)))

    if behaviors:
        sections.append(("Behavior: base", read_component("behavior", "base")))
        for behavior in behaviors:
            if behavior == "base":
                raise CharacterError("behavior/base is included automatically; do not select it")
            sections.append((f"Behavior: {behavior}", read_component("behavior", behavior)))

    return "\n\n".join(format_section(title, body) for title, body in sections) + "\n"


def list_component_names(kind: ComponentKind) -> tuple[str, ...]:
    directory = character_root().joinpath(kind)
    if not directory.is_dir():
        raise CharacterError(f"Missing character component directory: {directory}")

    names = (
        path.name.removesuffix(".md")
        for path in directory.iterdir()
        if path.name.endswith(".md")
    )
    return tuple(sorted(names))


def read_component(kind: ComponentKind, name: str) -> str:
    validate_component_name(name)
    path = character_root().joinpath(kind, f"{name}.md")
    if not path.is_file():
        raise CharacterError(f"Unknown character {kind}: {name}")
    return path.read_text(encoding="utf-8").strip()


def validate_component_name(name: str) -> None:
    path = Path(name)
    if path.name != name or name in {"", ".", ".."} or path.suffix:
        raise CharacterError(f"Invalid character component name: {name}")


def format_section(title: str, body: str) -> str:
    return f"# {title}\n\n{body}"
