"""Curated skill and tool selections for plugin exports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginProfile:
    """A named starting point for composing a plugin package."""

    description: str
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()


PROFILES = {
    "core": PluginProfile(
        description="Contextual execution planning for Automata agents.",
        skills=("automata-plan",),
    ),
}


def get_profile(name: str) -> PluginProfile:
    """Return a named profile or raise a useful export error."""

    try:
        return PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(PROFILES)) or "none"
        raise ValueError(
            f"Unknown plugin profile {name!r}; available profiles: {available}"
        ) from exc
