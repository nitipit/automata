"""Check observation ownership and packaged guidance, not live tmux readiness."""

from importlib.resources import files
from pathlib import Path

from automata.install.skills import install_skills


def observation() -> str:
    return " ".join(
        files("automata")
        .joinpath("skills", "communication", "automata-tmux-observation", "SKILL.md")
        .read_text()
        .split()
    )


def test_observation_limits_target_scope_and_cli_output() -> None:
    text = observation()
    for term in (
        "explicitly owned or assigned tmux pane",
        "intended server, exact `session:window.pane` target",
        "does not prove current identity or ownership",
        "Start with pane/process metadata",
        "Capture output only when it is needed",
        'tmux display-message -p -t "$TARGET"',
        'tmux capture-pane -p -t "$TARGET" -S 0 -E 39',
        "Report lookup and capture failures",
        "Do not persist captures by default",
    ):
        assert term in text, term


def test_observation_leaves_interpretation_and_actions_to_caller() -> None:
    text = observation()
    for term in (
        "The caller chooses the question and interprets the evidence",
        "not proof of readiness, message receipt, or work completion",
        "not delivery of that reply to its intended recipient",
        "do not send keys, dismiss prompts, attach, switch clients",
        "Do not turn an observation into an automatic polling loop",
        "repeated observation needs a new reason within the caller's scope",
        "without a mandatory invocation chain",
    ):
        assert term in text, term


def test_observation_is_installable_as_an_independent_skill(tmp_path: Path) -> None:
    results = install_skills(
        target_root=tmp_path,
        skill_names=["automata-tmux-observation"],
    )
    assert [result.name for result in results] == ["automata-tmux-observation"]
    installed = tmp_path / "automata-tmux-observation" / "SKILL.md"
    assert " ".join(installed.read_text().split()) == observation()
    assert not (tmp_path / "automata-tmux-communication").exists()
