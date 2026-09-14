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


def test_compose_character_includes_selected_components() -> None:
    output = compose_character(
        personality="automata",
        language="thai",
        behaviors=["co-pilot"],
    )

    normalized = " ".join(output.split())

    assert "# Personality: automata" in output
    assert "# Automata Personality" in output
    assert "Your name is Automata." in output
    assert "Your speaking identity is feminine." in normalized
    assert "Use feminine forms consistently" in normalized
    assert "Call yourself" not in output
    assert "Call the user" not in output
    assert "Um" not in output
    assert "# Language: base" in output
    assert "# Base Language" in output
    assert "# Language: thai" in output
    assert "# Thai Language" in output
    assert "ไม่เลียนแบบคำลงท้ายของผู้ใช้" in output
    assert "ใช้ `ค่ะ`/`คะ` ไม่ใช้ `ครับ`" in output
    assert "ใช้ `ครับ` ไม่ใช้ `ค่ะ`/`คะ`" in output
    assert "ก่อนส่ง ตรวจคำลงท้ายให้สอดคล้องกัน" in output
    assert "ไม่ต้องเติมทุกประโยค" in output
    assert "ยกเว้นเมื่อยกคำพูดหรือกล่าวถึงภาษาของผู้อื่น" in output
    assert "Explain procedures only when useful to the user" in normalized
    assert "Respect requested formats" in normalized
    assert output.index("# Personality: automata") < output.index("# Language: base")
    assert output.index("# Language: base") < output.index("# Language: thai")
    assert output.index("# Language: thai") < output.index("# Behavior: base")
    assert "# Behavior: base" in output
    assert "# Base Behavior" in output
    assert "# Behavior: co-pilot" in output
    assert "# Co-Pilot Behavior" in output
    for principle in (
        "engineering partner, not an echo",
        "Change recommendations with evidence or goals, not merely to agree",
        "Choose solo work or coordination by expected benefit",
        "Establish authority before delegating",
        "Ask clear questions only when uncertainty affects the answer or action",
        "use numbered choices when helpful",
        "Discuss unresolved choices that materially affect scope, behavior, risk, "
        "or user priorities",
        "Discussion alone is not authorization",
        "make ordinary engineering decisions and verify the result without repeated approval",
        "ask before unapproved destructive, consequential, or independently scoped actions",
        "Usefulness alone does not authorize action",
    ):
        assert principle in normalized
    assert "Load applicable skills" not in output
    assert "Check available skill descriptions" not in output
    assert len(output) < 3_000  # Bounds generated text, not a token estimate.


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
