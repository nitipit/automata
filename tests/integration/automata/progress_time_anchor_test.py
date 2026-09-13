"""Check timestamp-anchor ownership for persistent progress guidance."""

from pathlib import Path

ROOT = Path(__file__).parents[3] / "src" / "automata" / "skills" / "core"
TEAM_MANAGEMENT = ROOT / "automata-team-management" / "SKILL.md"


def normalized(path: Path) -> str:
    return " ".join(path.read_text().casefold().split())


def test_team_management_anchors_aggregate_freshness() -> None:
    text = normalized(TEAM_MANAGEMENT)

    for boundary in (
        "aggregate checkpoint",
        "child evidence as-of",
        "newly assembled report",
        "stale child evidence",
        "missing coverage and unknowns",
        "source, window, as-of time, and coverage",
    ):
        assert boundary in text

    # Presentation is contextual; freshness remains part of the reporting contract.
    assert "use the recipient's required format" in text
    assert "supporting evidence, material risks, and the next useful move" in text
    assert "exactly one work line" not in text


def test_aggregate_skill_does_not_add_estimation_procedure() -> None:
    team = normalized(TEAM_MANAGEMENT)

    assert "time-estimation semantics" not in team
    assert "first establish what must be finished" not in team
    assert "lightweight calibration records" not in team
