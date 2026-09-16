"""Static PC-control contract checks; live behavior needs separate evidence."""

from importlib.resources import files

import yaml

ROOT = files("automata").joinpath("skills", "operations", "automata-pc-ui-control")
SKILL = ROOT.joinpath("SKILL.md")
REFERENCE = ROOT.joinpath("references", "linux-and-browser-control.md")


def normalized(resource=SKILL) -> str:
    return " ".join(resource.read_text().casefold().split())


def test_pc_ui_skill_has_portable_setup_activation_and_compact_metadata() -> None:
    text = SKILL.read_text()
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == "automata-pc-ui-control"
    for trigger in ("desktop", "setting up", "focusing", "recovering"):
        assert trigger in metadata["description"]
    assert len(text) < 5_000
    assert "references/linux-and-browser-control.md" in text
    assert len(REFERENCE.read_text()) < 8_000


def test_pc_ui_requires_end_to_end_setup_and_honest_readiness_claims() -> None:
    text = normalized()
    for term in (
        "detected executable is a candidate",
        "actual client endpoint",
        "inactive or missing named service does not prove",
        "missing default socket does not exclude",
        "preserve these distinctions in the answer",
        "target selection, input, and observed feedback work together",
        "report what remains unverified",
        "next-step proposal should say how the intended ui result will be checked",
        "changed hypothesis",
    ):
        assert term in text, term


def test_pc_ui_distinguishes_native_focus_from_transport_success() -> None:
    text = normalized()
    for term in (
        "verify the exact target and current focus",
        "native window activation, browser content focus, and the intended widget",
        "disable emulation where supported and seek native evidence",
        "refocus the owned target yourself",
        "do not send global input",
        "observe the actual target ui result",
        "exit zero, accepted transport, or injected key events alone are not success",
        "stop on wrong-target or missing feedback",
    ):
        assert term in text, term


def test_pc_ui_bounds_helpers_without_redundant_permission_requests() -> None:
    text = normalized()
    for term in (
        "temporary user-owned helper can be normal execution",
        "do not ask again merely because it is called a daemon",
        "honor any explicit restriction",
        "persistent service registration",
        "permission changes",
        "never stop another owner's helper",
        "exact action and target are already authorized",
    ):
        assert term in text, term


def test_pc_ui_separates_durable_setup_from_volatile_runtime() -> None:
    text = normalized()
    for term in (
        "when reuse helps, retain verified setup knowledge",
        "proof and limitations",
        "invalidation conditions",
        "when continuity or recovery needs a live record, track runtime state separately",
        "never persist focus, pane, window, process, or session identities as durable truth",
        "temporary handles, subject to revalidation",
        "without rediscovering the whole setup",
        "recover only the affected setup",
        "follow-up use is intended and authorized",
        "do not delete durable knowledge or unrelated data",
    ):
        assert term in text, term


def test_pc_ui_reference_preserves_mechanism_limits_and_cleanup() -> None:
    text = normalized(REFERENCE)
    for term in (
        "empty-text invocation",
        "ydotool_socket",
        "finally",
        "emulation.setfocusemulationenabled",
        "not a native activation guarantee",
        "do not use an arbitrary old enter event",
        "discard raw logs",
        "transient capabilities",
        "not that the token alone caused success",
        "older retained instance",
    ):
        assert term in text, term
