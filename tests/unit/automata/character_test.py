from pathlib import Path

import pytest

from automata.character import CharacterError, compose_character, list_character_components


def test_list_character_components_excludes_base_from_selectable_behaviors() -> None:
    components = list_character_components()

    assert "automata" in components.personalities
    assert "milin" not in components.personalities
    assert "base" not in components.languages
    assert "thai" in components.languages
    assert "base" not in components.behaviors
    assert "co-pilot" in components.behaviors
    assert components.implicit_languages == ("base",)
    assert components.implicit_behaviors == ("base",)


def test_compose_character_includes_selected_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "character"
    components = {
        "personality/automata.md": "Selected personality.\n",
        "language/base.md": "Shared language.\n",
        "language/thai.md": "ภาษาไทย\n",
        "behavior/base.md": "Shared behavior.\n",
        "behavior/co-pilot.md": "1. Selected behavior.\n2. Preserve formatting.\n",
        "behavior/autonomous.md": "Unselected behavior.\n",
    }
    for relative, content in components.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr("automata.character.character_root", lambda: root)

    output = compose_character(
        personality="automata",
        language="thai",
        behaviors=["co-pilot"],
    )

    assert output == (
        "# Personality: automata\n\nSelected personality.\n\n"
        "# Language: base\n\nShared language.\n\n"
        "# Language: thai\n\nภาษาไทย\n\n"
        "# Behavior: base\n\nShared behavior.\n\n"
        "# Behavior: co-pilot\n\n1. Selected behavior.\n2. Preserve formatting.\n"
    )


def test_resource_awareness_is_shared_across_working_styles() -> None:
    for behavior in ("co-pilot", "autonomous"):
        output = compose_character(behaviors=[behavior])
        assert output.count("# Base Behavior") == 1
        section = output.split("# Base Behavior\n", 1)[1].split("\n# Behavior:", 1)[0]
        normalized = " ".join(section.split())
        assert "Keep resource awareness proportionate" in normalized
        assert "Distinguish estimates from observations" in normalized
        assert "revise expectations with evidence" in normalized
        assert "Check time when a pause, deadline, or time-dependent claim" in normalized
        assert "automata-" not in section  # No fixed skill invocation chain in behavior.


def test_compose_character_requires_a_selection() -> None:
    with pytest.raises(CharacterError, match="Select at least one character component"):
        compose_character()


def test_compose_character_includes_only_selected_personality() -> None:
    output = compose_character(personality="automata")

    assert "# Personality: automata" in output
    assert "# Automata Personality" in output
    assert "# Language:" not in output
    assert "# Behavior:" not in output


def test_compose_character_includes_language_base_only_when_language_selected() -> None:
    output = compose_character(language="thai")

    assert "# Personality:" not in output
    assert "# Language: base" in output
    assert "# Language: thai" in output
    assert "เพศหญิงหรือ feminine" in output
    assert "เพศชายหรือ masculine" in output
    assert "หากไม่ได้กำหนด" in output
    assert "# Automata Personality" not in output
    assert "# Behavior:" not in output
    assert output.index("# Language: base") < output.index("# Language: thai")


def test_compose_character_includes_behavior_base_only_when_behavior_selected() -> None:
    output = compose_character(behaviors=["co-pilot"])

    assert "# Personality:" not in output
    assert "# Language:" not in output
    assert "# Behavior: base" in output
    assert "# Behavior: co-pilot" in output
    assert output.index("# Behavior: base") < output.index("# Behavior: co-pilot")


def test_compose_character_rejects_explicit_base_language() -> None:
    with pytest.raises(CharacterError, match="included automatically"):
        compose_character(language="base")


def test_compose_character_rejects_explicit_base_behavior() -> None:
    with pytest.raises(CharacterError, match="included automatically"):
        compose_character(behaviors=["base"])


def test_compose_character_rejects_unknown_language() -> None:
    with pytest.raises(CharacterError, match="Unknown character language"):
        compose_character(language="missing")


def test_compose_character_rejects_unknown_component() -> None:
    with pytest.raises(CharacterError, match="Unknown character behavior"):
        compose_character(behaviors=["missing"])
