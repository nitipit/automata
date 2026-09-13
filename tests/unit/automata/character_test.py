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
    assert "ไม่ใช่คำลงท้ายที่ผู้ใช้เลือกใช้" in output
    assert "ไม่ใช้ `ครับ` ในเสียงของตัวเอง" in output
    assert "ไม่ใช้ `ค่ะ` หรือ `คะ` ในเสียงของตัวเอง" in output
    assert "อย่าเลียนแบบหรือสลับไปใช้คำลงท้ายที่บ่งเพศของผู้ใช้" in output
    assert "ห้ามผสมรูปภาษาของเพศหญิงและเพศชาย" in output
    assert "ก่อนส่งคำตอบภาษาไทย" in output
    assert "ไม่จำเป็นต้องเติมคำลงท้ายทุกประโยค" in output
    assert "## Communication" in output
    assert "Keep internal procedures and skill mechanics out of the response" in normalized
    assert "Respect required output formats" in normalized
    assert output.index("# Personality: automata") < output.index("# Language: base")
    assert output.index("# Language: base") < output.index("# Language: thai")
    assert output.index("# Language: thai") < output.index("# Behavior: base")
    assert "# Behavior: base" in output
    assert "# Base Behavior" in output
    assert "# Behavior: co-pilot" in output
    assert "# Co-Pilot Behavior" in output
    assert "## Independent Judgment" in output
    assert "engineering partner who helps the user think and implement—not an echo" in normalized
    assert "Change recommendations when evidence or goals change" in normalized
    assert "Choose solo work or coordination for its expected benefit" in normalized
    assert "establish its authority before delegating" in normalized
    assert "Make requests for input explicit and easy to answer" in normalized
    assert "Use numbered choices when they help, not as a mandatory format" in normalized
    assert "## Discussion and Execution" in output
    assert "Do not treat casual observations or discussion as authorization to act" in normalized
    assert "within that scope without repeatedly asking permission" in normalized
    assert "Ask before destructive, consequential, or independently scoped actions" in normalized
    assert "An action being useful does not itself authorize it" in normalized


def test_resource_awareness_is_shared_across_working_styles() -> None:
    for behavior in ("co-pilot", "autonomous"):
        output = compose_character(behaviors=[behavior])
        assert output.count("## Skills and Judgment") == 1
        assert output.index("## Skills and Judgment") < output.index(f"# Behavior: {behavior}")
        section = output.split("## Skills and Judgment\n", 1)[1].split("\n## ", 1)[0]
        normalized = " ".join(section.split())
        assert "Keep resource awareness proportionate to the work" in normalized
        assert "Distinguish estimates from observations" in normalized
        assert "revise expectations when evidence changes" in normalized
        assert "Refresh time context" in normalized
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
